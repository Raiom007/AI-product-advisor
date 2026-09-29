"""Ingest pipeline entry point.

Usage:
    python -m advisor.ingest                       # uses configs/data.yaml + ADVISOR_RAW_DIR
    python -m advisor.ingest --raw-dir ./data/dev_fixtures --db ./data/advisor.db

Outputs:
    data/advisor.db                    — SQLite database
    data/processed/cleaning_log.jsonl  — one JSON line per cleaning rule + counts
    docs/data_cleaning.md              — human-readable report for live defense

WHY: "Every decision is written to data/processed/cleaning_log.jsonl and
summarised (with counts) in docs/data_cleaning.md." (§5.1)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Lazy import of advisor modules to keep startup fast if called with --help
# ---------------------------------------------------------------------------
def _imports():
    from advisor.ingest.clean_products import clean_product_row, dedup_products
    from advisor.ingest.clean_reviews import (
        build_quarantine_row,
        clean_review_row,
        dedup_reviews,
    )
    from advisor.store.sqlite_store import (
        db_hash,
        insert_products,
        insert_quarantine,
        insert_reviews,
        insert_specs,
        insert_taxonomy,
        open_db,
        truncate_all,
    )
    return (
        clean_product_row, dedup_products,
        build_quarantine_row, clean_review_row, dedup_reviews,
        db_hash, insert_products, insert_quarantine, insert_reviews,
        insert_specs, insert_taxonomy, open_db, truncate_all,
    )


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

class CleaningLog:
    """Writes one JSONL line per cleaning rule. Never logs raw rows."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a", encoding="utf-8")

    def record(self, rule: str, **kwargs) -> None:
        entry = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "rule": rule,
            **kwargs,
        }
        self._fh.write(json.dumps(entry) + "\n")

    def close(self) -> None:
        self._fh.close()


def _write_data_cleaning_md(log_path: Path, out_path: Path) -> None:
    """Generate docs/data_cleaning.md from cleaning_log.jsonl.

    WHY: §5.1 — "summarised (with counts) in docs/data_cleaning.md".
    No raw rows are included; only rules, counts, and justifications.
    """
    entries: list[dict] = []
    with log_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    lines = [
        "# Data Cleaning Decisions",
        "",
        "> Auto-generated from `data/processed/cleaning_log.jsonl`.",
        "> No raw rows included. Every count is reproducible by re-running `make ingest`.",
        "",
    ]
    for e in entries:
        lines.append(f"## Rule: {e['rule']}")
        lines.append("")
        for k, v in e.items():
            if k in ("ts", "rule"):
                continue
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run(raw_dir: Path, db_path: Path, log_path: Path, docs_path: Path) -> str:
    """Run the full ingest pipeline. Returns the final db_hash."""
    (
        clean_product_row, dedup_products,
        build_quarantine_row, clean_review_row, dedup_reviews,
        db_hash, insert_products, insert_quarantine, insert_reviews,
        insert_specs, insert_taxonomy, open_db, truncate_all,
    ) = _imports()

    # Discover CSVs
    products_csv = raw_dir / "products.csv"
    reviews_csv = raw_dir / "reviews.csv"
    if not products_csv.exists():
        sys.exit(f"ERROR: {products_csv} not found")

    clog = CleaningLog(log_path)
    t0 = time.perf_counter()

    # -----------------------------------------------------------------------
    # 1. Open DB and truncate (idempotent)
    # -----------------------------------------------------------------------
    conn = open_db(db_path)
    truncate_all(conn)

    # -----------------------------------------------------------------------
    # 2. Products pass 1: clean each row
    # -----------------------------------------------------------------------
    print("Cleaning products …")
    with products_csv.open(encoding="utf-8", newline="") as fh:
        raw_products = list(csv.DictReader(fh))

    n_raw = len(raw_products)
    cleaned_products: list[dict] = []
    all_spec_rows: list[dict] = []
    n_pii_hits = 0
    n_injection = 0
    n_anomaly = 0
    n_price_unknown = 0
    n_img_broken = 0

    for raw in raw_products:
        p_row, spec_rows, ctrs = clean_product_row(raw)
        cleaned_products.append(p_row)
        all_spec_rows.extend(spec_rows)
        n_pii_hits += ctrs["pii_hits"]
        n_injection += ctrs["injection_flag"]
        n_anomaly += ctrs["anomaly"]
        if p_row["price_unknown"]:
            n_price_unknown += 1
        if p_row["image_url_broken"]:
            n_img_broken += 1

    clog.record("products.loaded",
                raw_count=n_raw,
                note="row count before any dedup or filtering")
    clog.record("products.price.anomaly",
                discounted_gt_retail=n_anomaly,
                justification="Anomalous discounts treated as data error; retail used as effective price (§5.1)")
    clog.record("products.price.unknown",
                count=n_price_unknown,
                justification="Both retail and discounted missing; stored as NULL, never imputed (§5.1)")
    clog.record("products.pii",
                total_hits=n_pii_hits,
                justification="PII redacted before DB write (§5.8)")
    clog.record("products.injection",
                flagged=n_injection,
                justification="Injection phrases flagged, not deleted (§5.8)")
    clog.record("products.image.broken",
                count=n_img_broken,
                justification="Heuristic broken-URL flag; URL kept in record for P17 lazy validation (§5.1)")

    # -----------------------------------------------------------------------
    # 3. Deduplication
    # -----------------------------------------------------------------------
    print("Deduplicating products …")
    deduped, alias_map = dedup_products(cleaned_products)
    n_dupes = sum(1 for r in deduped if r["is_canonical"] == 0)
    n_canonical = sum(1 for r in deduped if r["is_canonical"] == 1)

    clog.record("products.dedup",
                raw_count=n_raw,
                canonical_count=n_canonical,
                duplicate_alias_count=n_dupes,
                justification="Exact-match on normalised (name, brand, category_tree); first-seen is canonical (§5.1)")

    # -----------------------------------------------------------------------
    # 4. Taxonomy
    # -----------------------------------------------------------------------
    taxonomy_rows = []
    seen_tax: set[tuple] = set()
    for p in deduped:
        t = (p["cat_l1"], p["cat_l2"], p["cat_l3"])
        if t not in seen_tax and all(t):
            taxonomy_rows.append({"cat_l1": t[0], "cat_l2": t[1], "cat_l3": t[2]})
            seen_tax.add(t)

    clog.record("taxonomy.built",
                unique_cat_triples=len(taxonomy_rows),
                justification="Unique (l1,l2,l3) tuples from split on ' >> '; used by parser for taxonomy resolution (§5.1)")

    # -----------------------------------------------------------------------
    # 5. Write products, specs, taxonomy
    # -----------------------------------------------------------------------
    print(f"Writing {n_canonical} canonical + {n_dupes} alias products …")
    insert_products(conn, deduped)
    insert_specs(conn, all_spec_rows)
    insert_taxonomy(conn, taxonomy_rows)

    clog.record("product_specs.written",
                total_spec_rows=len(all_spec_rows),
                justification="Stable ids spec:{pid}:{n} for grounding (§4 EvidenceRef.id format)")

    # -----------------------------------------------------------------------
    # 6. Reviews
    # -----------------------------------------------------------------------
    if not reviews_csv.exists():
        print("WARNING: reviews.csv not found — skipping review ingest")
        clog.record("reviews.skipped", reason="reviews.csv not found")
    else:
        print("Cleaning reviews …")
        with reviews_csv.open(encoding="utf-8", newline="") as fh:
            raw_reviews = list(csv.DictReader(fh))

        n_rev_raw = len(raw_reviews)
        canonical_ids = {p["product_id"] for p in deduped if p["is_canonical"] == 1}

        ok_rows: list[dict] = []
        quarantine_rows: list[dict] = []
        n_empty = 0
        n_rev_pii = 0
        n_rev_inj = 0

        for raw in raw_reviews:
            disposition, row = clean_review_row(raw, canonical_ids, alias_map)
            if disposition == "ok":
                n_rev_pii += row.pop("_pii_hits", 0)
                n_rev_inj += row.get("injection_flag", 0)
                ok_rows.append(row)
            elif disposition == "orphan":
                quarantine_rows.append(
                    build_quarantine_row(raw, "product_id_not_in_catalogue")
                )
            elif disposition == "empty_text":
                n_empty += 1

        clog.record("reviews.loaded",
                    raw_count=n_rev_raw,
                    ok_before_dedup=len(ok_rows),
                    orphan_count=len(quarantine_rows),
                    empty_text_dropped=n_empty,
                    justification="Orphans → quarantine; empty text dropped (§5.1)")
        clog.record("reviews.pii",
                    total_hits=n_rev_pii,
                    justification="PII redacted in title+text before DB write (§5.8)")
        clog.record("reviews.injection",
                    flagged=n_rev_inj,
                    justification="Injection phrases flagged, row kept for guardrail eval (§5.8)")

        # Dedup
        deduped_reviews, dup_count = dedup_reviews(ok_rows)

        clog.record("reviews.exact_dedup",
                    exact_dup_count_before_marking=dup_count,
                    justification=(
                        "Identical (reviewer_id, product_id, text) triples marked is_duplicate=1. "
                        "Cross-product near-duplicates NOT removed — fake-review signal (P11). (§5.1)"
                    ))

        n_repointed = sum(1 for r in deduped_reviews if r.get("original_product_id") is not None)
        clog.record("reviews.alias_repointed",
                    count=n_repointed,
                    justification="Reviews on alias product_ids re-pointed to canonical (§5.1)")

        print(f"Writing {len(deduped_reviews)} reviews + {len(quarantine_rows)} quarantine …")
        insert_reviews(conn, deduped_reviews)
        insert_quarantine(conn, quarantine_rows)

    # -----------------------------------------------------------------------
    # 7. Final hash and timing
    # -----------------------------------------------------------------------
    final_hash = db_hash(conn)
    elapsed = round(time.perf_counter() - t0, 2)

    clog.record("ingest.complete",
                elapsed_s=elapsed,
                db_hash=final_hash,
                note="Hash excludes timestamps; identical across idempotent re-runs")
    clog.close()

    _write_data_cleaning_md(log_path, docs_path)
    print(f"\nDone in {elapsed}s. DB hash: {final_hash[:16]}…")
    print(f"  DB:           {db_path}")
    print(f"  Cleaning log: {log_path}")
    print(f"  Report:       {docs_path}")

    conn.close()
    return final_hash


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and clean product + review CSVs.")
    parser.add_argument(
        "--raw-dir", type=Path,
        default=Path(os.environ.get("ADVISOR_RAW_DIR", "data/dev_fixtures")),
        help="Directory containing products.csv and reviews.csv (default: $ADVISOR_RAW_DIR or data/dev_fixtures)",
    )
    parser.add_argument(
        "--db", type=Path, default=Path("data/advisor.db"),
        help="Output SQLite database path",
    )
    parser.add_argument(
        "--log", type=Path, default=Path("data/processed/cleaning_log.jsonl"),
        help="Cleaning log output path",
    )
    parser.add_argument(
        "--docs", type=Path, default=Path("docs/data_cleaning.md"),
        help="data_cleaning.md output path",
    )
    args = parser.parse_args()

    if not args.raw_dir.is_dir():
        sys.exit(
            f"ERROR: raw-dir '{args.raw_dir}' is not a directory. "
            "Set $ADVISOR_RAW_DIR or pass --raw-dir."
        )

    run(args.raw_dir, args.db, args.log, args.docs)


if __name__ == "__main__":
    main()
