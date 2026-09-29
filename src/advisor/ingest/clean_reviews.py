"""Review cleaning pipeline.

Cleaning decisions (per owner review 2026-09-29):
  1. Column rename: review_text → text, review_title → title
  2. Orphan reviews (product_id not in catalogue) → quarantine table, log count
  3. Alias re-pointing: if review.product_id is an alias, set canonical id,
     store original in original_product_id column
  4. Exact duplicates: identical (reviewer_id, product_id, text) triple.
     COUNT before dropping. Keep first occurrence. is_duplicate=1 on dropped rows.
     NOTE: cross-product near-duplicate text (e.g. template reviews) is NOT
     deduplicated here — that's the fake-review detector signal (P11).
  5. PII redaction: title and text fields
  6. Injection flagging: text and title; flag=True, never delete
  7. Empty text: drop rows where text is None/empty after stripping

WHY: §5.1 cleaning table — "orphan reviews → quarantine table";
     "exact-dup drop (but keep count for fake signal)";
     "PII redacted at ingest".
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from advisor.guardrails.injection import is_injection
from advisor.guardrails.pii import redact

# Column names confirmed from dev-fixture profile (configs/data.yaml)
COL = {
    "id": "review_id",
    "product_id": "product_id",
    "rating": "rating",
    "title": "review_title",
    "text": "review_text",
    "date": "review_date",
    "reviewer": "reviewer_id",
    "helpful": "helpful_votes",
}


def clean_review_row(
    raw: dict[str, Any],
    canonical_ids: set[str],
    alias_map: dict[str, str],
) -> tuple[str, dict[str, Any] | None]:
    """Clean one raw review row.

    Args:
        raw:           raw CSV row dict
        canonical_ids: set of canonical product_ids (for orphan check)
        alias_map:     {alias_id: canonical_id} from dedup_products()

    Returns:
        (disposition, row_dict | None)
        disposition: "ok" | "orphan" | "empty_text"
        row_dict: cleaned dict ready for insert, or None if orphan/empty.
    """
    now = datetime.now(tz=UTC).isoformat()
    rid = str(raw.get(COL["id"], "")).strip()
    pid_raw = str(raw.get(COL["product_id"], "")).strip()
    title_raw = str(raw.get(COL["title"], "") or "").strip() or None
    text_raw = str(raw.get(COL["text"], "") or "").strip()

    # Drop empty text
    if not text_raw:
        return "empty_text", None

    # Alias re-pointing
    original_pid: str | None = None
    pid = pid_raw
    if pid_raw in alias_map:
        original_pid = pid_raw
        pid = alias_map[pid_raw]

    # Orphan check
    if pid not in canonical_ids and (not alias_map or pid_raw not in alias_map):
        return "orphan", None

    # Re-check canonical after re-pointing
    if pid not in canonical_ids:
        return "orphan", None

    # PII redaction
    pii_hits = 0
    if title_raw:
        r = redact(title_raw)
        title_raw = r.redacted_text
        pii_hits += sum(r.hit_counts.values())
    r = redact(text_raw)
    text_redacted = r.redacted_text
    pii_hits += sum(r.hit_counts.values())

    # Injection flagging
    inj = is_injection(text_redacted) or is_injection(title_raw or "")

    # Cast numerics
    try:
        rating = int(float(str(raw.get(COL["rating"], 0) or 0)))
    except (ValueError, TypeError):
        rating = None
    try:
        helpful = int(float(str(raw.get(COL["helpful"], 0) or 0)))
    except (ValueError, TypeError):
        helpful = 0

    row = {
        "review_id": rid,
        "product_id": pid,
        "original_product_id": original_pid,
        "rating": rating,
        "title": title_raw,
        "text": text_redacted,
        "review_date": str(raw.get(COL["date"], "") or "").strip() or None,
        "reviewer_id": str(raw.get(COL["reviewer"], "") or "").strip() or None,
        "helpful_votes": helpful,
        "injection_flag": int(inj),
        "is_duplicate": 0,
        "ingested_at": now,
        "_pii_hits": pii_hits,   # internal; stripped before insert
        "_dedup_key": (str(raw.get(COL["reviewer"], "")), pid, text_redacted),
    }
    return "ok", row


def dedup_reviews(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Mark exact duplicates (reviewer_id, product_id, text).

    WHY: Only byte-for-byte identical triples are duplicates. Cross-product
    near-duplicate text (template reviews) must survive — they are fake-review
    signals, not data errors.

    Returns:
        (rows_with_dup_flag, exact_dup_count_before_drop)
    """
    seen: set[tuple] = set()
    result: list[dict[str, Any]] = []
    dup_count = 0

    for row in rows:
        key = row.pop("_dedup_key")
        if key in seen:
            dup_count += 1
            # Still write the row as is_duplicate=1 for audit; the fake
            # detector can count it. But mark it so the retrieval layer can
            # exclude it.
            dup_row = dict(row)
            dup_row["is_duplicate"] = 1
            result.append(dup_row)
        else:
            seen.add(key)
            result.append(row)

    return result, dup_count


def build_quarantine_row(
    raw: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "review_id": str(raw.get(COL["id"], "")).strip(),
        "missing_product_id": str(raw.get(COL["product_id"], "")).strip(),
        "reason": reason,
        "review_date": str(raw.get(COL["date"], "") or "").strip() or None,
        "ingested_at": now,
    }
