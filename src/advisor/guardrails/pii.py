r"""PII detection and redaction for Indian e-commerce context.

Patterns (§5.8):
  - Indian mobile numbers: 10-digit starting with 6-9, optionally prefixed by +91 / 0
  - International phone: +<country-code> <digits>
  - Email addresses
  - Aadhaar: 12-digit number (+ Verhoeff check when CHECK_AADHAAR=True)
  - PAN: [A-Z]{5}\d{4}[A-Z]
  - Card-like: 16-digit groups (Luhn-checked)

All redaction happens at ingest — only redacted text is stored in the DB.
WHY: §5.1 cleaning table — "Redact phone/email/Aadhaar/PAN/etc. at ingest;
     store only redacted text in the DB used by the app."

The sentinels are predictable strings so tests can assert on them:
  [REDACTED_PHONE]  [REDACTED_PHONE_INTL]  [REDACTED_EMAIL]
  [REDACTED_AADHAAR]  [REDACTED_PAN]  [REDACTED_CARD]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Verhoeff check-digit table (for Aadhaar 12-digit validation)
# WHY: Raw 12-digit pattern matches too many false positives (order IDs,
#      product codes). Verhoeff narrows it to structurally valid Aadhaar numbers.
# ---------------------------------------------------------------------------
_V_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_V_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_V_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_validate(number: str) -> bool:
    """Return True if the number passes Verhoeff check digit validation."""
    c = 0
    for i, ch in enumerate(reversed(number)):
        if not ch.isdigit():
            return False
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


# ---------------------------------------------------------------------------
# Luhn check (for card-like 16-digit numbers)
# ---------------------------------------------------------------------------

def _luhn_validate(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) != 16:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Indian mobile: 10 digits, first digit 6-9; optionally prefixed by +91 / 0 / 91
_RE_PHONE_IN = re.compile(
    r"(?<!\d)"
    r"(?:\+91[\s\-]?|91[\s\-]?|0)?"
    r"([6-9]\d{9})"
    r"(?!\d)"
)

# International phone: +<1-3 digit country code> <6-14 digits>
_RE_PHONE_INTL = re.compile(
    r"(?<!\d)\+(\d{1,3})[\s\-](\d{6,14})(?!\d)"
)

# Email
_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Aadhaar: 12 consecutive digits (we Verhoeff-check before redacting)
_RE_AADHAAR_CANDIDATE = re.compile(
    r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)"
)

# PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
_RE_PAN = re.compile(
    r"(?<!\w)[A-Z]{5}\d{4}[A-Z](?!\w)"
)

# Card-like: four groups of 4 digits separated by space or hyphen
_RE_CARD_CANDIDATE = re.compile(
    r"(?<!\d)\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}(?!\d)"
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class PIIResult:
    """Returned by scan(); caller uses hit_counts to log aggregates."""
    redacted_text: str
    hit_counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_pii(self) -> bool:
        return any(v > 0 for v in self.hit_counts.values())


def redact(text: str, *, check_aadhaar: bool = True, check_luhn: bool = True) -> PIIResult:
    """Redact all PII from text and return the sanitised string + hit counts.

    Args:
        text: raw text (product description, review body, etc.)
        check_aadhaar: if True, apply Verhoeff validation before redacting.
                       Set False only in tests that need to bypass the check.
        check_luhn:    if True, apply Luhn validation before redacting cards.

    Returns:
        PIIResult with redacted_text and per-type hit counts.
    """
    if not isinstance(text, str) or not text:
        return PIIResult(redacted_text=text or "", hit_counts={})

    counts: dict[str, int] = {}

    # 1. Indian mobile — apply first so +91-prefixed numbers aren't also caught
    #    by PHONE_INTL pattern.
    def _replace_phone_in(m: re.Match) -> str:
        counts["phone_in"] = counts.get("phone_in", 0) + 1
        return "[REDACTED_PHONE]"

    text = _RE_PHONE_IN.sub(_replace_phone_in, text)

    # 2. International phone
    def _replace_phone_intl(m: re.Match) -> str:
        counts["phone_intl"] = counts.get("phone_intl", 0) + 1
        return "[REDACTED_PHONE_INTL]"

    text = _RE_PHONE_INTL.sub(_replace_phone_intl, text)

    # 3. Email
    def _replace_email(m: re.Match) -> str:
        counts["email"] = counts.get("email", 0) + 1
        return "[REDACTED_EMAIL]"

    text = _RE_EMAIL.sub(_replace_email, text)

    # 4. Aadhaar (with optional Verhoeff)
    def _replace_aadhaar(m: re.Match) -> str:
        digits_only = re.sub(r"[\s\-]", "", m.group())
        if check_aadhaar and not _verhoeff_validate(digits_only):
            return m.group()  # not a valid Aadhaar — leave untouched
        counts["aadhaar"] = counts.get("aadhaar", 0) + 1
        return "[REDACTED_AADHAAR]"

    text = _RE_AADHAAR_CANDIDATE.sub(_replace_aadhaar, text)

    # 5. PAN
    def _replace_pan(m: re.Match) -> str:
        counts["pan"] = counts.get("pan", 0) + 1
        return "[REDACTED_PAN]"

    text = _RE_PAN.sub(_replace_pan, text)

    # 6. Card-like (with optional Luhn)
    def _replace_card(m: re.Match) -> str:
        digits_only = re.sub(r"[\s\-]", "", m.group())
        if check_luhn and not _luhn_validate(digits_only):
            return m.group()
        counts["card"] = counts.get("card", 0) + 1
        return "[REDACTED_CARD]"

    text = _RE_CARD_CANDIDATE.sub(_replace_card, text)

    return PIIResult(redacted_text=text, hit_counts=counts)


def scan(text: str) -> dict[str, int]:
    """Return hit counts without modifying text.

    WHY: Used by profile.py to count PII in the raw data before any redaction,
    so the profile report can quantify the PII exposure.
    """
    return redact(text).hit_counts
