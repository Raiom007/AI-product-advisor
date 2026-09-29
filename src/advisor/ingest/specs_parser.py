"""Spec text parser — free text → structured {key: value} dict.

Driven by domain/electronics/spec_keys.yaml and domain/electronics/unit_norms.yaml.
Adding a new key or unit requires only editing those YAML files (§4.1 data-not-code).

Output contract:
  {
    "ram_gb":     {"value": 16.0, "unit": "GB", "spec_id": "spec:P001:1"},
    "weight_kg":  {"value": 1.8,  "unit": "kg", "spec_id": "spec:P001:3"},
    "raw:Type":   {"value": "TWS", "unit": "",   "spec_id": "spec:P001:5"},
  }

Keys prefixed "raw:" are unknown keys kept verbatim — never dropped (§5.1 "Missing
fields: store NULL, treat as unverified").

Stable spec_id is passed in from clean_products.py (format: spec:{pid}:{n}).
The parser is idempotent: same input → same output (no randomness, no timestamps).

WHY: Deterministic parsing is required for constraint checking (§5.6 gate) and
for grounding (§5.7 evidence IDs). The LLM never checks constraints directly.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Vocabulary loading
# ---------------------------------------------------------------------------

# specs_parser.py is at:  src/advisor/ingest/specs_parser.py
# parents[0] = src/advisor/ingest/
# parents[1] = src/advisor/
# parents[2] = src/
# parents[3] = project_root/
_DOMAIN_DIR = Path(__file__).resolve().parents[3] / "domain" / "electronics"



@lru_cache(maxsize=1)
def _load_spec_keys() -> list[dict]:
    path = _DOMAIN_DIR / "spec_keys.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["spec_keys"]


@lru_cache(maxsize=1)
def _load_unit_norms() -> dict[str, tuple[str, float]]:
    """Return {raw_unit_lower: (canonical_unit, multiplier)}."""
    path = _DOMAIN_DIR / "unit_norms.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)["unit_norms"]
    return {row["raw_unit"].lower(): (row["canonical"], float(row["multiplier"])) for row in data}


@lru_cache(maxsize=1)
def _build_alias_map() -> dict[str, dict]:
    """Return {lower_alias: spec_key_entry} for O(1) lookup."""
    alias_map: dict[str, dict] = {}
    for entry in _load_spec_keys():
        for alias in entry["aliases"]:
            alias_map[alias.lower().strip()] = entry
    return alias_map


# ---------------------------------------------------------------------------
# Line parsing helpers
# ---------------------------------------------------------------------------

def _split_lines(spec_text: str) -> list[str]:
    """Split spec text on common separators."""
    if not spec_text:
        return []
    for sep in ("\n", " | ", "; "):
        if sep in spec_text:
            return [line_.strip() for line_ in spec_text.split(sep) if line_.strip()]
    return [spec_text.strip()]


def _parse_kv(line: str) -> tuple[str | None, str | None]:
    """Extract (raw_key, raw_value) from a spec line.

    Supports: "Key: Value", "Key - Value", "Key:Value", "Value Key" (e.g. "16GB RAM").
    Returns (None, None) if no split can be found.
    """
    for sep in (":", " - "):
        if sep in line:
            parts = line.split(sep, 1)
            k, v = parts[0].strip(), parts[1].strip()
            if k and v:
                return k, v
    return None, line.strip()   # no separator → whole line is the value


def _normalise_numeric(
    raw_value: str,
    unit_target: str,
    extract_pattern: str,
    value_type: str,
) -> tuple[float | None, str | None]:
    """Extract and normalise a numeric value from raw_value string.

    Returns (canonical_float, canonical_unit) or (None, None).
    """
    if value_type not in ("numeric", "count"):
        return None, None

    unit_norms = _load_unit_norms()
    text = raw_value.lower().strip()

    # Try the spec-key-specific regex first
    if extract_pattern:
        m = re.search(extract_pattern, text, re.IGNORECASE)
        if m:
            try:
                num = float(m.group(1))
            except (ValueError, IndexError):
                return None, None
            # Try to detect unit in rest of match or nearby text.
            # WHY: sorted by descending key length so "kg" is tried before "g"
            # (substring match would otherwise make "1.8 kg" → 0.0018 kg).
            rest = text[m.start():]
            for raw_u in sorted(unit_norms, key=len, reverse=True):
                canon_u, mult = unit_norms[raw_u]
                if canon_u != unit_target:
                    continue
                # Word-boundary match: unit must not be part of a longer word
                if re.search(r'(?<![a-z])' + re.escape(raw_u) + r'(?![a-z])', rest):
                    return round(num * mult, 4), canon_u
            # Unit not found in text — assume unit_target (common for storage/RAM)
            if unit_target:
                return num, unit_target
            return num, None

    # Fallback: generic "number [unit]" pattern
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z\"']+)?", text)
    if not m:
        return None, None
    try:
        num = float(m.group(1))
    except ValueError:
        return None, None
    raw_unit = (m.group(2) or "").lower().strip()
    # WHY: sorted by length so longer units (e.g. "kg") are checked before shorter ("g")
    for raw_u in sorted(unit_norms, key=len, reverse=True):
        if raw_unit == raw_u:
            canon_u, mult = unit_norms[raw_u]
            return round(num * mult, 4), canon_u
    if unit_target:
        return num, unit_target
    return num, raw_unit or None


def _is_boolean_true(raw_value: str) -> bool | None:
    """Return True/False/None for boolean spec values."""
    v = raw_value.lower().strip()
    if v in ("yes", "true", "1", "active noise cancellation", "anc", "✓", "✔"):
        return True
    if v in ("no", "false", "0", "none", "not available", "n/a"):
        return False
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

ParsedSpecs = dict[str, dict[str, Any]]


def parse_specs(
    spec_text: str,
    product_id: str,
    spec_rows: list[dict[str, Any]] | None = None,
) -> ParsedSpecs:
    """Parse free-text spec field into structured dict.

    Args:
        spec_text:   raw spec field value from the CSV
        product_id:  for constructing stable spec_ids if spec_rows not given
        spec_rows:   pre-parsed spec rows from clean_products._parse_specs()
                     (each has spec_id, seq, original_line). If None,
                     the parser splits the text itself.

    Returns:
        ParsedSpecs: {canonical_key: {value, unit, spec_id, raw_value}}
        Unknown keys → "raw:{original_key}": {...}
    """
    alias_map = _build_alias_map()
    result: ParsedSpecs = {}

    if spec_rows:
        lines_with_ids = [(row["original_line"], row["spec_id"]) for row in spec_rows]
    else:
        lines = _split_lines(spec_text)
        lines_with_ids = [(line, f"spec:{product_id}:{i+1}") for i, line in enumerate(lines)]

    for line, spec_id in lines_with_ids:
        raw_key, raw_value = _parse_kv(line)
        if not raw_value:
            continue

        # Look up canonical key via alias map
        lookup_key = (raw_key or raw_value).lower().strip()
        entry = alias_map.get(lookup_key)

        # Try partial match if exact fails (handles "RAM: 16GB" where key is "RAM")
        if entry is None and raw_key:
            for alias, e in alias_map.items():
                if alias in lookup_key:
                    entry = e
                    break

        if entry is None:
            # Unknown key → raw bucket
            canonical_key = f"raw:{raw_key or 'unknown'}"
            result[canonical_key] = {
                "value": raw_value,
                "unit": "",
                "spec_id": spec_id,
                "raw_value": raw_value,
            }
            continue

        canonical_key = entry["canonical"]
        value_type = entry.get("value_type", "text")
        unit_target = entry.get("unit_target", "")
        extract = entry.get("extract", "")

        if value_type in ("numeric", "count"):
            num, unit = _normalise_numeric(raw_value, unit_target, extract, value_type)
            if num is not None:
                result[canonical_key] = {
                    "value": num,
                    "unit": unit or unit_target,
                    "spec_id": spec_id,
                    "raw_value": raw_value,
                }
            else:
                # Could not parse numeric — store as raw with canonical key
                result[canonical_key] = {
                    "value": None,
                    "unit": unit_target,
                    "spec_id": spec_id,
                    "raw_value": raw_value,
                }

        elif value_type == "boolean":
            bool_val = _is_boolean_true(raw_value)
            result[canonical_key] = {
                "value": bool_val,
                "unit": "",
                "spec_id": spec_id,
                "raw_value": raw_value,
            }

        else:  # text
            result[canonical_key] = {
                "value": raw_value.strip(),
                "unit": unit_target,
                "spec_id": spec_id,
                "raw_value": raw_value,
            }

    return result


# ---------------------------------------------------------------------------
# Parse-coverage report (aggregate only — no raw values printed)
# ---------------------------------------------------------------------------

def coverage_report(parsed_list: list[ParsedSpecs]) -> dict[str, dict]:
    """Return per-key parse coverage stats over a list of parsed specs.

    WHY: The prompt asks to "report parse coverage per key (% of products
    with a value)". This drives which constraints are actually checkable.
    Returns aggregate stats only — no raw row values.
    """
    n = len(parsed_list)
    if n == 0:
        return {}
    key_counts: dict[str, int] = {}
    key_parsed: dict[str, int] = {}

    for parsed in parsed_list:
        for k, v in parsed.items():
            key_counts[k] = key_counts.get(k, 0) + 1
            if v.get("value") is not None:
                key_parsed[k] = key_parsed.get(k, 0) + 1

    report: dict[str, dict] = {}
    for k in sorted(key_counts):
        present = key_counts[k]
        with_value = key_parsed.get(k, 0)
        report[k] = {
            "products_with_key": present,
            "pct_with_key": round(present / n * 100, 1),
            "products_with_parsed_value": with_value,
            "parse_rate": round(with_value / present * 100, 1) if present else 0,
        }
    return report
