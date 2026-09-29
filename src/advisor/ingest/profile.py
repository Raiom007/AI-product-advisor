"""Data profiler — reads raw CSVs and writes ONLY aggregates.

Entry point:
    python -m advisor.ingest.profile          # uses $ADVISOR_RAW_DIR
    python -m advisor.ingest.profile --raw-dir /path/to/raw

Outputs (no raw rows anywhere):
    data/profile/profile.json   — machine-readable aggregates
    data/profile/profile.md     — human-readable report + proposed data.yaml mappings

Also writes:
    data/sample/products.csv    — 200 products, PII-redacted (stratified by category)
    data/sample/reviews.csv     — all reviews for those 200 products, PII-redacted

Rules (from AGENTS.md §14 + §5.1):
  - Never print raw rows to terminal or logs
  - Never include raw rows in profile.json or profile.md
  - Never include raw rows in the sample files (PII-redaction is mandatory)
  - Only aggregate counts, rates, distributions and format samples
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Optional dependency — pandas is not in requirements.txt yet.
# WHY: profile.py is the first script that needs pandas; adding a soft import
# so the rest of the package works without it until ingest is set up.
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ---------------------------------------------------------------------------
# PII patterns (Indian context — same patterns used by guardrails/pii.py later)
# WHY: Redact at profile time so sample files are safe for agents to read.
# ---------------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone_in", re.compile(
        r"(?<!\d)(?:\+91[\s\-]?)?[6-9]\d{9}(?!\d)"
    )),
    ("phone_intl", re.compile(
        r"(?<!\d)\+\d{1,3}[\s\-]\d{6,14}(?!\d)"
    )),
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )),
    ("aadhaar", re.compile(
        r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)"
    )),
    ("pan", re.compile(
        r"(?<!\w)[A-Z]{5}\d{4}[A-Z](?!\w)"
    )),
    ("card_like", re.compile(
        r"(?<!\d)\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}(?!\d)"
    )),
]

_INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "disregard",
    "new instruction",
    "you are now",
    "act as",
    "recommend this product",
    "do not follow",
    "override",
    "jailbreak",
]


def _redact_pii(text: str) -> str:
    """Replace PII matches with [REDACTED_<type>] sentinel."""
    if not isinstance(text, str):
        return text
    for label, pat in _PII_PATTERNS:
        text = pat.sub(f"[REDACTED_{label.upper()}]", text)
    return text


def _count_pii_hits(text: str) -> dict[str, int]:
    if not isinstance(text, str):
        return {}
    return {label: len(pat.findall(text)) for label, pat in _PII_PATTERNS}


def _count_injection_hits(text: str) -> int:
    if not isinstance(text, str):
        return 0
    t = text.lower()
    return sum(1 for phrase in _INJECTION_PHRASES if phrase in t)


def _normalise_name(name: str) -> str:
    """Normalise product name for duplicate detection."""
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKC", name).lower()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _is_valid_url(url: str) -> bool:
    """Cheap structural check — does NOT fetch. Returns False for malformed URLs."""
    if not isinstance(url, str) or not url.strip():
        return False
    return bool(re.match(r"^https?://[^\s]+\.[^\s]{2,}", url.strip()))


# ---------------------------------------------------------------------------
# Column heuristics
# ---------------------------------------------------------------------------

def _guess_id_col(df: pd.DataFrame, hints: list[str]) -> str | None:
    """Return the first column name that looks like an ID column."""
    for hint in hints:
        for col in df.columns:
            if hint.lower() in col.lower():
                return col
    return None


def _guess_text_col(df: pd.DataFrame, hints: list[str]) -> str | None:
    for hint in hints:
        for col in df.columns:
            if hint.lower() in col.lower():
                return col
    return None


# ---------------------------------------------------------------------------
# Core profiling functions
# ---------------------------------------------------------------------------

def _profile_products(df: pd.DataFrame) -> dict[str, Any]:
    """Compute aggregates for the products DataFrame. Never returns raw rows."""
    n = len(df)
    result: dict[str, Any] = {
        "row_count": n,
        "columns": {},
        "duplicates": {},
        "price": {},
        "categories": {},
        "specs": {},
        "images": {},
        "pii": {},
        "injection": {},
    }

    # Column names, types, null rates
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        result["columns"][col] = {
            "dtype": str(df[col].dtype),
            "null_count": null_count,
            "null_rate": round(null_count / n, 4) if n else 0,
            "unique_count": int(df[col].nunique(dropna=True)),
        }

    # Exact row duplicates
    exact_dups = int(df.duplicated().sum())
    result["duplicates"]["exact_row_count"] = exact_dups
    result["duplicates"]["exact_row_rate"] = round(exact_dups / n, 4) if n else 0

    # Name+brand normalised duplicates
    name_col = _guess_text_col(df, ["product_name", "name", "title", "product"])
    brand_col = _guess_text_col(df, ["brand", "manufacturer", "make"])
    if name_col:
        normed_names = df[name_col].apply(_normalise_name)
        if brand_col:
            dup_key = normed_names + "|" + df[brand_col].fillna("").str.lower().str.strip()
        else:
            dup_key = normed_names
        name_brand_dups = int(dup_key.duplicated().sum())
        result["duplicates"]["name_brand_normalised_count"] = name_brand_dups
        result["duplicates"]["name_brand_normalised_rate"] = round(name_brand_dups / n, 4) if n else 0
        result["duplicates"]["name_col_guessed"] = name_col
        result["duplicates"]["brand_col_guessed"] = brand_col

    # Price stats
    price_candidates = [c for c in df.columns if any(
        kw in c.lower() for kw in ["price", "mrp", "cost", "rate", "discounted", "retail"]
    )]
    for col in price_candidates:
        raw = df[col].copy()
        # Strip ₹, commas, whitespace to detect non-numeric formats
        cleaned = raw.astype(str).str.replace(r"[₹,\s]", "", regex=True)
        non_numeric = int(cleaned.apply(lambda x: not re.match(r"^\d*\.?\d+$", x) if x not in ("nan", "") else False).sum())
        try:
            numeric = pd.to_numeric(cleaned, errors="coerce")
            result["price"][col] = {
                "non_numeric_count": non_numeric,
                "null_after_parse": int(numeric.isna().sum()),
                "min": float(numeric.min()) if numeric.notna().any() else None,
                "max": float(numeric.max()) if numeric.notna().any() else None,
                "median": float(numeric.median()) if numeric.notna().any() else None,
                "p25": float(numeric.quantile(0.25)) if numeric.notna().any() else None,
                "p75": float(numeric.quantile(0.75)) if numeric.notna().any() else None,
                "lte_zero_count": int((numeric <= 0).sum()),
            }
        except Exception:
            result["price"][col] = {"error": "parse_failed"}

    # Discounted > retail check
    disc_col = _guess_text_col(df, ["discounted_price", "sale_price", "discounted", "selling_price"])
    retail_col = _guess_text_col(df, ["actual_price", "retail_price", "mrp", "original_price"])
    if disc_col and retail_col:
        try:
            d = pd.to_numeric(df[disc_col].astype(str).str.replace(r"[₹,\s]", "", regex=True), errors="coerce")
            r = pd.to_numeric(df[retail_col].astype(str).str.replace(r"[₹,\s]", "", regex=True), errors="coerce")
            both_valid = d.notna() & r.notna()
            disc_gt_retail = int(((d > r) & both_valid).sum())
            result["price"]["discounted_gt_retail_count"] = disc_gt_retail
            result["price"]["discounted_col_guessed"] = disc_col
            result["price"]["retail_col_guessed"] = retail_col
        except Exception:
            pass

    # Category tree
    cat_candidates = [c for c in df.columns if any(
        kw in c.lower() for kw in ["category", "cat", "department", "type"]
    )]
    for col in cat_candidates[:3]:  # limit to first 3 matches
        try:
            # Detect separator style
            sample_vals = df[col].dropna().head(200).astype(str)
            sep_counts = {
                "|": int(sample_vals.str.contains(r"\|", regex=True).sum()),
                ">>": int(sample_vals.str.contains(">>").sum()),
                "/": int(sample_vals.str.contains("/").sum()),
                ",": int(sample_vals.str.contains(",").sum()),
            }
            top_sep = max(sep_counts, key=lambda k: sep_counts[k])
            top_sep_count = sep_counts[top_sep]
            if top_sep_count > 0:
                depths = sample_vals.apply(lambda x: len(x.split(top_sep)))
                l1_counts = sample_vals.apply(lambda x: x.split(top_sep)[0].strip()).value_counts()
            else:
                depths = pd.Series([1] * len(sample_vals))
                l1_counts = sample_vals.value_counts()
            result["categories"][col] = {
                "null_rate": round(df[col].isna().mean(), 4),
                "unique_count": int(df[col].nunique()),
                "likely_separator": top_sep if top_sep_count > 0 else "none_detected",
                "depth_distribution": depths.value_counts().to_dict(),
                "top_l1_categories": {
                    str(k): int(v) for k, v in l1_counts.head(15).items()
                },
            }
        except Exception as e:
            result["categories"][col] = {"error": str(e)}

    # Spec text format variants
    spec_candidates = [c for c in df.columns if any(
        kw in c.lower() for kw in ["spec", "feature", "description", "detail", "about"]
    )]
    for col in spec_candidates[:3]:
        try:
            sample = df[col].dropna().head(500).astype(str)
            patterns = {
                "key_colon_value": int(sample.str.contains(r"\w+\s*:\s*\w+", regex=True).sum()),
                "bullet_pipe": int(sample.str.contains(r"\|", regex=True).sum()),
                "newline_separated": int(sample.str.contains(r"\n", regex=True).sum()),
                "json_like": int(sample.str.contains(r'["{\[]', regex=True).sum()),
                "comma_separated": int(sample.str.contains(r",\s*\w+\s*:", regex=True).sum()),
            }
            avg_len = float(sample.str.len().mean())
            result["specs"][col] = {
                "format_pattern_counts": patterns,
                "avg_char_length": round(avg_len, 1),
                "null_rate": round(df[col].isna().mean(), 4),
            }
        except Exception as e:
            result["specs"][col] = {"error": str(e)}

    # Image URLs
    img_candidates = [c for c in df.columns if any(
        kw in c.lower() for kw in ["image", "img", "photo", "picture", "url"]
    )]
    for col in img_candidates[:3]:
        try:
            non_null = df[col].dropna().astype(str)
            # Detect separator
            sep_counts_img = {
                "|": int(non_null.str.contains(r"\|", regex=True).sum()),
                ",": int(non_null.str.contains(",").sum()),
                " ": int(non_null.str.contains(r" https?://", regex=True).sum()),
            }
            best_sep = max(sep_counts_img, key=lambda k: sep_counts_img[k])
            if sep_counts_img[best_sep] > 0:
                url_counts = non_null.apply(lambda x: len(x.split(best_sep)))
            else:
                url_counts = pd.Series([1] * len(non_null))
                best_sep = "single"

            # Malformed URL count (structural check only, no fetching)
            all_urls = []
            for val in non_null.head(500):
                if best_sep != "single":
                    all_urls.extend(val.split(best_sep))
                else:
                    all_urls.append(val)
            malformed = sum(1 for u in all_urls if u.strip() and not _is_valid_url(u))

            result["images"][col] = {
                "null_rate": round(df[col].isna().mean(), 4),
                "likely_separator": best_sep,
                "url_count_distribution": {
                    str(k): int(v) for k, v in url_counts.value_counts().head(10).items()
                },
                "malformed_url_count_in_sample_500": malformed,
                "total_urls_in_sample": len(all_urls),
            }
        except Exception as e:
            result["images"][col] = {"error": str(e)}

    # PII hit counts (aggregate only — no raw rows)
    text_cols = [c for c in df.columns
                 if df[c].dtype == object and c not in img_candidates][:5]
    pii_totals: dict[str, int] = {}
    for col in text_cols:
        for val in df[col].dropna().astype(str):
            for label, count in _count_pii_hits(val).items():
                pii_totals[label] = pii_totals.get(label, 0) + count
    result["pii"] = {
        "total_hits_by_type": pii_totals,
        "columns_scanned": text_cols,
    }

    # Injection phrase hit counts
    injection_total = 0
    for col in text_cols:
        for val in df[col].dropna().astype(str):
            injection_total += _count_injection_hits(val)
    result["injection"] = {
        "total_hits": injection_total,
        "columns_scanned": text_cols,
    }

    return result


def _profile_reviews(df_reviews: pd.DataFrame, df_products: pd.DataFrame) -> dict[str, Any]:
    """Compute review aggregates."""
    n = len(df_reviews)
    result: dict[str, Any] = {
        "row_count": n,
        "columns": {},
        "coverage": {},
        "pii": {},
        "injection": {},
    }

    for col in df_reviews.columns:
        null_count = int(df_reviews[col].isna().sum())
        result["columns"][col] = {
            "dtype": str(df_reviews[col].dtype),
            "null_count": null_count,
            "null_rate": round(null_count / n, 4) if n else 0,
            "unique_count": int(df_reviews[col].nunique(dropna=True)),
        }

    # Product ID join analysis
    prod_id_col_r = _guess_id_col(df_reviews, ["product_id", "asin", "item_id", "prod_id"])
    prod_id_col_p = _guess_id_col(df_products, ["product_id", "asin", "item_id", "id"])
    if prod_id_col_r and prod_id_col_p:
        review_ids = set(df_reviews[prod_id_col_r].dropna().astype(str))
        product_ids = set(df_products[prod_id_col_p].dropna().astype(str))
        orphan_count = len(review_ids - product_ids)
        result["coverage"]["product_id_col_reviews"] = prod_id_col_r
        result["coverage"]["product_id_col_products"] = prod_id_col_p
        result["coverage"]["orphan_review_product_ids"] = orphan_count
        result["coverage"]["orphan_rate"] = round(orphan_count / len(review_ids), 4) if review_ids else 0

        # Reviews per product distribution
        rpp = df_reviews[prod_id_col_r].value_counts()
        result["coverage"]["reviews_per_product"] = {
            "min": int(rpp.min()),
            "max": int(rpp.max()),
            "median": float(rpp.median()),
            "p25": float(rpp.quantile(0.25)),
            "p75": float(rpp.quantile(0.75)),
            "products_with_no_reviews": int(len(product_ids - review_ids)),
            "products_with_reviews": int(len(review_ids & product_ids)),
        }

    # Date range
    date_col = _guess_text_col(df_reviews, ["date", "review_date", "timestamp", "created"])
    if date_col:
        try:
            dates = pd.to_datetime(df_reviews[date_col], errors="coerce")
            result["coverage"]["date_range"] = {
                "min": str(dates.min()),
                "max": str(dates.max()),
                "unparseable_count": int(dates.isna().sum()),
            }
        except Exception:
            pass

    # Reviewer concentration
    reviewer_col = _guess_id_col(df_reviews, ["reviewer_id", "user_id", "reviewer", "author"])
    if reviewer_col:
        reviewer_counts = df_reviews[reviewer_col].value_counts()
        result["coverage"]["reviewer_concentration"] = {
            "unique_reviewers": int(df_reviews[reviewer_col].nunique()),
            "top_reviewer_count": int(reviewer_counts.iloc[0]) if len(reviewer_counts) else 0,
            "reviewers_with_gt5_reviews": int((reviewer_counts > 5).sum()),
            "reviewers_with_gt10_reviews": int((reviewer_counts > 10).sum()),
        }

    # PII and injection on review text
    text_col = _guess_text_col(df_reviews, ["review_body", "review_text", "text", "comment", "content"])
    pii_totals: dict[str, int] = {}
    injection_total = 0
    if text_col:
        for val in df_reviews[text_col].dropna().astype(str):
            for label, count in _count_pii_hits(val).items():
                pii_totals[label] = pii_totals.get(label, 0) + count
            injection_total += _count_injection_hits(val)
    result["pii"] = {
        "total_hits_by_type": pii_totals,
        "text_col_scanned": text_col,
    }
    result["injection"] = {
        "total_hits": injection_total,
        "text_col_scanned": text_col,
    }

    return result


def _make_sample(
    df_products: pd.DataFrame,
    df_reviews: pd.DataFrame,
    out_dir: Path,
    n_products: int = 200,
) -> None:
    """Write PII-redacted sample files. Never writes raw rows."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stratified sample by category if possible
    cat_col = _guess_text_col(df_products, ["category", "cat", "department"])
    if cat_col and df_products[cat_col].nunique() > 1:
        try:
            n_per_cat = max(1, n_products // df_products[cat_col].nunique())
            sample_products = (
                df_products.groupby(cat_col, group_keys=False)
                .apply(lambda g: g.sample(min(len(g), n_per_cat), random_state=42))
            )
            # Top up to n_products
            if len(sample_products) < n_products:
                remaining_ids = df_products.index.difference(sample_products.index)
                extra = df_products.loc[remaining_ids].sample(
                    min(n_products - len(sample_products), len(remaining_ids)),
                    random_state=42,
                )
                sample_products = pd.concat([sample_products, extra])
            sample_products = sample_products.head(n_products)
        except Exception:
            sample_products = df_products.sample(min(n_products, len(df_products)), random_state=42)
    else:
        sample_products = df_products.sample(min(n_products, len(df_products)), random_state=42)

    # PII-redact all string columns
    for col in sample_products.columns:
        if sample_products[col].dtype == object:
            sample_products = sample_products.copy()
            sample_products[col] = sample_products[col].apply(_redact_pii)

    sample_products.to_csv(out_dir / "products.csv", index=False)

    # Reviews for sample products
    prod_id_col_p = _guess_id_col(sample_products, ["product_id", "asin", "item_id", "id"])
    prod_id_col_r = _guess_id_col(df_reviews, ["product_id", "asin", "item_id", "prod_id"])
    if prod_id_col_p and prod_id_col_r:
        sample_ids = set(sample_products[prod_id_col_p].astype(str))
        sample_reviews = df_reviews[df_reviews[prod_id_col_r].astype(str).isin(sample_ids)].copy()
        for col in sample_reviews.columns:
            if sample_reviews[col].dtype == object:
                sample_reviews[col] = sample_reviews[col].apply(_redact_pii)
        sample_reviews.to_csv(out_dir / "reviews.csv", index=False)
        print(f"  Sample reviews: {len(sample_reviews)} rows for {len(sample_ids)} products")
    else:
        print("  WARNING: could not join reviews to sample products — no common ID column detected")

    print(f"  Sample products: {len(sample_products)} rows → {out_dir / 'products.csv'}")


def _propose_data_yaml(
    prod_profile: dict,
    rev_profile: dict,
) -> dict[str, Any]:
    """Propose configs/data.yaml column mappings based on the profile."""
    proposal: dict[str, Any] = {
        "products": {},
        "reviews": {},
        "_note": (
            "AUTO-PROPOSED by ingest/profile.py. "
            "Review every value; UNKNOWN = profiler could not determine."
        ),
    }

    def _best_guess(col_dict: dict[str, Any], *hints: str) -> str:
        for hint in hints:
            for col in col_dict:
                if hint.lower() in col.lower():
                    return col
        return "UNKNOWN"

    pc = prod_profile.get("columns", {})
    rc = rev_profile.get("columns", {})

    proposal["products"]["id_col"] = _best_guess(pc, "product_id", "asin", "item_id", "id")
    proposal["products"]["name_col"] = _best_guess(pc, "product_name", "name", "title")
    proposal["products"]["brand_col"] = _best_guess(pc, "brand", "manufacturer", "make")
    proposal["products"]["price_retail_col"] = _best_guess(pc, "actual_price", "mrp", "retail_price", "original_price")
    proposal["products"]["price_discounted_col"] = _best_guess(pc, "discounted_price", "sale_price", "selling_price", "discounted")
    proposal["products"]["category_col"] = _best_guess(pc, "category", "cat", "department")
    proposal["products"]["description_col"] = _best_guess(pc, "about_product", "description", "detail", "about")
    proposal["products"]["specs_col"] = _best_guess(pc, "product_details", "specifications", "specs", "features")
    proposal["products"]["image_urls_col"] = _best_guess(pc, "img_link", "image_url", "image", "img", "photo")

    # Image separator
    img_col = proposal["products"]["image_urls_col"]
    if img_col != "UNKNOWN" and img_col in prod_profile.get("images", {}):
        proposal["products"]["image_url_separator"] = prod_profile["images"][img_col].get("likely_separator", "|")
    else:
        proposal["products"]["image_url_separator"] = "UNKNOWN"

    proposal["reviews"]["id_col"] = _best_guess(rc, "review_id", "id")
    proposal["reviews"]["product_id_col"] = _best_guess(rc, "product_id", "asin", "item_id")
    proposal["reviews"]["text_col"] = _best_guess(rc, "review_body", "review_text", "text", "comment")
    proposal["reviews"]["rating_col"] = _best_guess(rc, "rating", "star", "score")
    proposal["reviews"]["date_col"] = _best_guess(rc, "review_date", "date", "timestamp", "created")
    proposal["reviews"]["helpful_votes_col"] = _best_guess(rc, "helpful_votes", "helpful", "votes")
    proposal["reviews"]["reviewer_id_col"] = _best_guess(rc, "reviewer_id", "user_id", "reviewer")

    proposal["cleaning"] = {
        "dedupe": True,
        "pii_redact": True,
        "injection_flag": True,
        "price_currency": "INR",
        "price_effective_field": "price_discounted",
    }

    return proposal


def _write_markdown_report(
    prod_profile: dict,
    rev_profile: dict,
    data_yaml_proposal: dict,
    out_path: Path,
) -> None:
    """Write the human-readable profile.md. Never includes raw rows."""
    lines: list[str] = [
        "# Data Profile Report",
        "",
        "> Auto-generated by `ingest/profile.py`. Contains ONLY aggregates — no raw rows.",
        "",
    ]

    # Products summary
    lines += [
        "## Products",
        "",
        f"- **Row count:** {prod_profile['row_count']:,}",
        f"- **Columns:** {len(prod_profile['columns'])}",
        "",
        "### Column null rates",
        "",
        "| Column | dtype | null_rate | unique_count |",
        "|--------|-------|-----------|--------------|",
    ]
    for col, info in prod_profile["columns"].items():
        lines.append(
            f"| `{col}` | {info['dtype']} | {info['null_rate']:.2%} | {info['unique_count']:,} |"
        )

    # Duplicates
    d = prod_profile.get("duplicates", {})
    lines += [
        "",
        "### Duplicates",
        "",
        f"- Exact row duplicates: {d.get('exact_row_count', 'N/A')} ({d.get('exact_row_rate', 0):.2%})",
        f"- Name+brand normalised duplicates: {d.get('name_brand_normalised_count', 'N/A')} ({d.get('name_brand_normalised_rate', 0):.2%})",
        f"  - Name col guessed: `{d.get('name_col_guessed', 'N/A')}`",
        f"  - Brand col guessed: `{d.get('brand_col_guessed', 'N/A')}`",
    ]

    # Price
    lines += ["", "### Price columns", ""]
    for col, info in prod_profile.get("price", {}).items():
        if isinstance(info, dict) and "error" not in info and not col.endswith("_guessed") and not col.endswith("_count"):
            lines.append(f"**`{col}`**: min={info.get('min')}, median={info.get('median')}, max={info.get('max')}, "
                         f"non-numeric={info.get('non_numeric_count', 0)}, ≤0={info.get('lte_zero_count', 0)}")
    disc_gt = prod_profile.get("price", {}).get("discounted_gt_retail_count")
    if disc_gt is not None:
        lines.append(f"\n- Discounted > retail: **{disc_gt}** rows")

    # Categories
    lines += ["", "### Category columns", ""]
    for col, info in prod_profile.get("categories", {}).items():
        if "error" not in info:
            lines.append(f"**`{col}`** — separator: `{info.get('likely_separator')}`, "
                         f"unique: {info.get('unique_count', 0):,}, null: {info.get('null_rate', 0):.2%}")
            top = info.get("top_l1_categories", {})
            if top:
                for cat, cnt in list(top.items())[:5]:
                    lines.append(f"  - {cat}: {cnt:,}")

    # Specs
    lines += ["", "### Spec text format variants", ""]
    for col, info in prod_profile.get("specs", {}).items():
        if "error" not in info:
            lines.append(f"**`{col}`** avg_len={info.get('avg_char_length')}, null={info.get('null_rate', 0):.2%}")
            for pat, cnt in info.get("format_pattern_counts", {}).items():
                lines.append(f"  - {pat}: {cnt:,}")

    # Images
    lines += ["", "### Image URL columns", ""]
    for col, info in prod_profile.get("images", {}).items():
        if "error" not in info:
            lines.append(f"**`{col}`** separator=`{info.get('likely_separator')}`, "
                         f"null={info.get('null_rate', 0):.2%}, "
                         f"malformed={info.get('malformed_url_count_in_sample_500', 0)}")

    # PII
    pii_hits = prod_profile.get("pii", {}).get("total_hits_by_type", {})
    lines += ["", "### PII hit counts (products)", ""]
    if pii_hits:
        for label, count in pii_hits.items():
            lines.append(f"- {label}: {count:,}")
    else:
        lines.append("- No PII detected in scanned columns.")

    inj = prod_profile.get("injection", {}).get("total_hits", 0)
    lines += ["", f"### Injection-phrase hits (products): {inj}", ""]

    # Reviews summary
    lines += [
        "---",
        "",
        "## Reviews",
        "",
        f"- **Row count:** {rev_profile['row_count']:,}",
        f"- **Columns:** {len(rev_profile['columns'])}",
        "",
        "### Column null rates",
        "",
        "| Column | dtype | null_rate | unique_count |",
        "|--------|-------|-----------|--------------|",
    ]
    for col, info in rev_profile["columns"].items():
        lines.append(
            f"| `{col}` | {info['dtype']} | {info['null_rate']:.2%} | {info['unique_count']:,} |"
        )

    cov = rev_profile.get("coverage", {})
    lines += [
        "",
        "### Review coverage",
        "",
        f"- Products with at least 1 review: {cov.get('products_with_reviews', 'N/A')}",
        f"- Products with NO reviews: {cov.get('products_with_no_reviews', 'N/A')}",
        f"- Orphan review product-IDs (not in products): {cov.get('orphan_review_product_ids', 'N/A')} ({cov.get('orphan_rate', 0):.2%})",
    ]
    rpp = cov.get("reviews_per_product", {})
    if rpp:
        lines += [
            f"- Reviews/product: min={rpp.get('min')}, median={rpp.get('median')}, max={rpp.get('max')}",
        ]
    dr = cov.get("date_range", {})
    if dr:
        lines += [f"- Date range: {dr.get('min')} → {dr.get('max')} (unparseable: {dr.get('unparseable_count', 0)})"]
    rc_conc = cov.get("reviewer_concentration", {})
    if rc_conc:
        lines += [
            f"- Unique reviewers: {rc_conc.get('unique_reviewers', 'N/A')}",
            f"- Reviewers with >5 reviews: {rc_conc.get('reviewers_with_gt5_reviews', 'N/A')}",
            f"- Reviewers with >10 reviews: {rc_conc.get('reviewers_with_gt10_reviews', 'N/A')}",
        ]

    rev_pii = rev_profile.get("pii", {}).get("total_hits_by_type", {})
    lines += ["", "### PII hit counts (reviews)", ""]
    if rev_pii:
        for label, count in rev_pii.items():
            lines.append(f"- {label}: {count:,}")
    else:
        lines.append("- No PII detected in scanned columns.")

    rev_inj = rev_profile.get("injection", {}).get("total_hits", 0)
    lines += ["", f"### Injection-phrase hits (reviews): {rev_inj}", ""]

    # Proposed data.yaml
    lines += [
        "---",
        "",
        "## Proposed `configs/data.yaml` column mappings",
        "",
        "```yaml",
    ]
    import yaml  # local import — pyyaml is a required dep
    lines.append(yaml.dump(data_yaml_proposal, default_flow_style=False, allow_unicode=True))
    lines += [
        "```",
        "",
        "> Review every mapping before using. `UNKNOWN` means the profiler could not determine the column.",
        "",
        "---",
        "_Stop here. Owner reviews before cleaning rules are set._",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(raw_dir: Path, out_profile_dir: Path, out_sample_dir: Path) -> None:
    if not HAS_PANDAS:
        sys.exit(
            "ERROR: pandas is required for profiling. "
            "Install it: pip install pandas"
        )

    # Discover CSV files
    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        sys.exit(
            f"ERROR: No CSV files found in {raw_dir}. "
            "Set $ADVISOR_RAW_DIR to the directory containing the raw CSVs."
        )

    print(f"Found {len(csv_files)} CSV file(s) in {raw_dir}:")
    for f in csv_files:
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    # Load files — heuristic: larger file is products, smaller is reviews
    # (or look for 'product' / 'review' in the filename)
    products_file = None
    reviews_file = None
    for f in csv_files:
        n = f.stem.lower()
        if any(kw in n for kw in ["product", "catalogue", "catalog", "item"]):
            products_file = f
        elif any(kw in n for kw in ["review", "rating", "feedback"]):
            reviews_file = f
    if products_file is None or reviews_file is None:
        # Fall back to size heuristic
        sorted_by_size = sorted(csv_files, key=lambda f: f.stat().st_size, reverse=True)
        if products_file is None:
            products_file = sorted_by_size[0]
        if reviews_file is None and len(sorted_by_size) > 1:
            reviews_file = sorted_by_size[1]

    if products_file is None:
        sys.exit("ERROR: Could not identify a products CSV. Rename the file to include 'product'.")

    print(f"\nLoading products: {products_file.name}")
    df_products = pd.read_csv(products_file, low_memory=False)
    print(f"  {len(df_products):,} rows × {len(df_products.columns)} columns")

    df_reviews = pd.DataFrame()
    if reviews_file:
        print(f"Loading reviews: {reviews_file.name}")
        df_reviews = pd.read_csv(reviews_file, low_memory=False)
        print(f"  {len(df_reviews):,} rows × {len(df_reviews.columns)} columns")
    else:
        print("WARNING: No reviews CSV found. Skipping review profiling.")

    # Profile
    print("\nProfiling products …")
    prod_profile = _profile_products(df_products)
    print("Profiling reviews …")
    rev_profile = _profile_reviews(df_reviews, df_products) if not df_reviews.empty else {"row_count": 0, "columns": {}, "coverage": {}, "pii": {}, "injection": {}}
    proposal = _propose_data_yaml(prod_profile, rev_profile)

    # Write outputs
    out_profile_dir.mkdir(parents=True, exist_ok=True)

    profile_json = {"products": prod_profile, "reviews": rev_profile, "proposed_data_yaml": proposal}
    (out_profile_dir / "profile.json").write_text(
        json.dumps(profile_json, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {out_profile_dir / 'profile.json'}")

    _write_markdown_report(prod_profile, rev_profile, proposal, out_profile_dir / "profile.md")
    print(f"Wrote {out_profile_dir / 'profile.md'}")

    # Write sample
    print("\nWriting PII-redacted sample …")
    _make_sample(df_products, df_reviews if not df_reviews.empty else pd.DataFrame(), out_sample_dir)

    print("\nDone. STOP — owner reviews profile.md before cleaning rules are set.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile raw CSVs; write aggregates only.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path(os.environ.get("ADVISOR_RAW_DIR", "")),
        help="Directory containing raw CSVs (default: $ADVISOR_RAW_DIR)",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path("data/profile"),
        help="Output directory for profile.json and profile.md",
    )
    parser.add_argument(
        "--sample-dir",
        type=Path,
        default=Path("data/sample"),
        help="Output directory for PII-redacted sample CSVs",
    )
    args = parser.parse_args()

    if not args.raw_dir or not args.raw_dir.is_dir():
        sys.exit(
            f"ERROR: raw-dir '{args.raw_dir}' is not a directory. "
            "Set $ADVISOR_RAW_DIR or pass --raw-dir."
        )

    run(args.raw_dir, args.profile_dir, args.sample_dir)


if __name__ == "__main__":
    main()
