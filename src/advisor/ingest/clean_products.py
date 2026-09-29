"""Product cleaning pipeline.

Cleaning decisions (per owner review of profile.md, 2026-09-29):
  1. Column rename: product_name → name, specification_text → spec_text (internal)
  2. Price logic:
       effective = discounted if present AND discounted <= retail
       else retail if present
       else NULL + price_unknown=True
       if discounted > retail: price_anomaly=True, use retail as effective, log
  3. Category: split on " >> " (always 3 levels), produce cat_l1/l2/l3
  4. Dedup: normalise(name, brand, category_tree) → keep first-seen as canonical
     Re-point reviews on alias ids to canonical (done in clean_reviews.py)
  5. Image URLs: split on "|"; flag broken heuristically (bad scheme OR contains
     "broken-cdn.invalid"); keep URL in record either way
  6. Missing brand/description/spec → NULL, never imputed, product kept
  7. PII-redact description and specification_text at ingest
  8. Injection-flag description and specification_text

WHY: §5.1 table, §5.8, §0 A4.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from advisor.guardrails.injection import is_injection
from advisor.guardrails.pii import redact

# ---------------------------------------------------------------------------
# Column names sourced from configs/data.yaml (values confirmed 2026-09-29)
# WHY: hard-coded here rather than loaded from YAML so the cleaning pipeline
# can be unit-tested without touching the config system.
# Update this dict when real CSVs arrive with different column names.
# ---------------------------------------------------------------------------
COL = {
    "id": "product_id",
    "name": "product_name",
    "brand": "brand",
    "cat": "category_tree",
    "price_retail": "retail_price_inr",
    "price_disc": "discounted_price_inr",
    "specs": "specification_text",
    "desc": "description",
    "images": "image_urls",
}

_CAT_SEP = " >> "
_IMG_SEP = "|"
_URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]{2,}")


def _normalise_key(name: str, brand: str, cat: str) -> str:
    """Deduplicate key: lowercased+stripped (name, brand, category_tree)."""
    def _n(s: str) -> str:
        s = unicodedata.normalize("NFKC", str(s or "")).lower().strip()
        return re.sub(r"\s+", " ", s)
    return f"{_n(name)}|{_n(brand)}|{_n(cat)}"


def _parse_price(raw: Any) -> float | None:
    """Strip ₹ / commas / whitespace and cast to float; return None on failure."""
    if raw is None or str(raw).strip() in ("", "nan"):
        return None
    cleaned = re.sub(r"[₹,\s]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_category(cat_str: str) -> tuple[str | None, str | None, str | None]:
    """Split 'Electronics >> Laptops >> Gaming Laptop' → (l1, l2, l3)."""
    if not cat_str or not isinstance(cat_str, str):
        return None, None, None
    parts = [p.strip() for p in cat_str.split(_CAT_SEP)]
    l1 = parts[0] if len(parts) > 0 else None
    l2 = parts[1] if len(parts) > 1 else None
    l3 = parts[2] if len(parts) > 2 else None
    return l1, l2, l3


def _flag_image_urls(urls_str: str) -> tuple[int, bool]:
    """Return (url_count, any_broken)."""
    if not urls_str or not isinstance(urls_str, str):
        return 0, False
    urls = [u.strip() for u in urls_str.split(_IMG_SEP) if u.strip()]
    broken = any(
        "broken-cdn.invalid" in u or not _URL_RE.match(u)
        for u in urls
    )
    return len(urls), broken


def _parse_specs(pid: str, spec_text: str) -> list[dict[str, Any]]:
    """Parse free-text spec field into stable-id rows.

    Supports separators: newline, " | ", "; ".
    Supports kv formats: "Key: Value", "Key - Value", "Key:Value".
    Stable id: spec:{product_id}:{n} (1-indexed, deterministic given input order).
    """
    if not spec_text or not isinstance(spec_text, str):
        return []

    # Detect dominant separator
    if "\n" in spec_text:
        raw_lines = spec_text.split("\n")
    elif " | " in spec_text:
        raw_lines = spec_text.split(" | ")
    elif "; " in spec_text:
        raw_lines = spec_text.split("; ")
    else:
        raw_lines = [spec_text]

    rows: list[dict[str, Any]] = []
    seq = 0
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        seq += 1
        # Try to split into key/value
        key: str | None = None
        value: str | None = None
        unit: str | None = None
        for sep in (":", " - "):
            if sep in line:
                parts = line.split(sep, 1)
                key = parts[0].strip()
                val_raw = parts[1].strip()
                # Extract trailing unit (e.g. "16GB", "15.6 inch")
                m = re.search(r"^([\d.]+)\s*([A-Za-z]+)$", val_raw)
                if m:
                    value = m.group(1)
                    unit = m.group(2)
                else:
                    value = val_raw
                break
        rows.append({
            "spec_id": f"spec:{pid}:{seq}",
            "product_id": pid,
            "seq": seq,
            "key": key,
            "value": value,
            "unit": unit,
            "original_line": line,
        })
    return rows


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

CleanResult = dict[str, Any]


def clean_product_row(raw: dict[str, Any]) -> tuple[CleanResult, list[dict[str, Any]], dict[str, int]]:
    """Clean one raw product row.

    Returns:
        product_row  — dict ready for sqlite_store.insert_products()
        spec_rows    — list of dicts ready for insert_specs()
        counters     — {"pii_hits": int, "injection_flag": int, "anomaly": int}
    """
    now = datetime.now(tz=UTC).isoformat()
    pid = str(raw.get(COL["id"], "")).strip()
    name_raw = str(raw.get(COL["name"], "") or "").strip()
    brand = str(raw.get(COL["brand"], "") or "").strip() or None
    cat_raw = str(raw.get(COL["cat"], "") or "").strip()
    desc_raw = str(raw.get(COL["desc"], "") or "").strip() or None
    spec_raw = str(raw.get(COL["specs"], "") or "").strip() or None
    images_raw = str(raw.get(COL["images"], "") or "").strip() or None

    # Price
    retail = _parse_price(raw.get(COL["price_retail"]))
    disc = _parse_price(raw.get(COL["price_disc"]))

    price_unknown = False
    price_anomaly = False
    effective: float | None = None

    if disc is not None and retail is not None:
        if disc > retail:
            price_anomaly = True
            effective = retail   # WHY: distrust anomalous discount, use retail
        else:
            effective = disc
    elif disc is not None:
        effective = disc
    elif retail is not None:
        effective = retail
    else:
        price_unknown = True

    # Category
    l1, l2, l3 = _parse_category(cat_raw)

    # Images
    img_count, img_broken = _flag_image_urls(images_raw or "")

    # PII redaction
    pii_hits = 0
    if desc_raw:
        pii_result = redact(desc_raw)
        desc_raw = pii_result.redacted_text
        pii_hits += sum(pii_result.hit_counts.values())
    if spec_raw:
        pii_result = redact(spec_raw)
        spec_raw = pii_result.redacted_text
        pii_hits += sum(pii_result.hit_counts.values())

    # Injection flagging
    inj_flag = is_injection(desc_raw or "") or is_injection(spec_raw or "")

    # Spec parsing
    spec_rows = _parse_specs(pid, spec_raw or "")

    product_row = {
        "product_id": pid,
        "name": name_raw or None,
        "brand": brand,
        "cat_l1": l1,
        "cat_l2": l2,
        "cat_l3": l3,
        "retail_price_inr": retail,
        "discounted_price_inr": disc,
        "effective_price_inr": effective,
        "price_unknown": int(price_unknown),
        "price_anomaly": int(price_anomaly),
        "description": desc_raw,
        "image_urls": images_raw,
        "image_url_count": img_count,
        "image_url_broken": int(img_broken),
        "alias_ids": json.dumps([]),   # populated by dedup pass
        "is_canonical": 1,
        "ingested_at": now,
    }

    counters = {
        "pii_hits": pii_hits,
        "injection_flag": int(inj_flag),
        "anomaly": int(price_anomaly),
    }

    return product_row, spec_rows, counters


# ---------------------------------------------------------------------------
# Deduplication pass
# ---------------------------------------------------------------------------

def dedup_products(
    rows: list[CleanResult],
) -> tuple[list[CleanResult], dict[str, str]]:
    """Identify duplicates; mark alias rows; return (canonical_rows, alias_map).

    alias_map: {alias_product_id: canonical_product_id}

    Strategy (per owner decision 2026-09-29):
      - Key = normalised (name, brand, category_tree).
      - First-seen product_id becomes canonical.
      - Subsequent matches: mark is_canonical=0, alias_ids on canonical updated.
      - alias_map passed to clean_reviews.py to re-point review foreign keys.
    """
    seen: dict[str, str] = {}           # norm_key → canonical_id
    alias_map: dict[str, str] = {}      # alias_id  → canonical_id
    canonical_alias_ids: dict[str, list[str]] = {}  # canonical_id → [alias_ids]
    result: list[CleanResult] = []

    for row in rows:
        key = _normalise_key(
            row.get("name") or "",
            row.get("brand") or "",
            # Reconstruct category_tree from cleaned fields for the key
            f"{row.get('cat_l1','')} >> {row.get('cat_l2','')} >> {row.get('cat_l3','')}",
        )
        pid = row["product_id"]

        if key not in seen:
            seen[key] = pid
            canonical_alias_ids[pid] = []
            result.append(row)
        else:
            canonical_id = seen[key]
            alias_map[pid] = canonical_id
            canonical_alias_ids[canonical_id].append(pid)
            # Mark this row as non-canonical (still inserted for audit trail)
            dup_row = dict(row)
            dup_row["is_canonical"] = 0
            result.append(dup_row)

    # Patch alias_ids onto canonical rows
    for row in result:
        if row["is_canonical"] == 1:
            pid = row["product_id"]
            aliases = canonical_alias_ids.get(pid, [])
            row["alias_ids"] = json.dumps(aliases)

    return result, alias_map
