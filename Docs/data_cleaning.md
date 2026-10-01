# Data Cleaning Decisions

> Auto-generated from `data/processed/cleaning_log.jsonl`.
> No raw rows included. Every count is reproducible by re-running `make ingest`.

## Rule: products.loaded

- **raw_count**: 20000
- **note**: row count before any dedup or filtering

## Rule: products.price.anomaly

- **discounted_gt_retail**: 0
- **justification**: Anomalous discounts treated as data error; retail used as effective price (§5.1)

## Rule: products.price.unknown

- **count**: 7880
- **justification**: Both retail and discounted missing; stored as NULL, never imputed (§5.1)

## Rule: products.pii

- **total_hits**: 164
- **justification**: PII redacted before DB write (§5.8)

## Rule: products.injection

- **flagged**: 254
- **justification**: Injection phrases flagged, not deleted (§5.8)

## Rule: products.image.broken

- **count**: 20000
- **justification**: Heuristic broken-URL flag; URL kept in record for P17 lazy validation (§5.1)

## Rule: products.dedup

- **raw_count**: 20000
- **canonical_count**: 19962
- **duplicate_alias_count**: 38
- **justification**: Exact-match on normalised (name, brand, category_tree); first-seen is canonical (§5.1)

## Rule: taxonomy.built

- **unique_cat_triples**: 145
- **justification**: Unique (l1,l2,l3) tuples from split on ' >> '; used by parser for taxonomy resolution (§5.1)

## Rule: product_specs.written

- **total_spec_rows**: 94359
- **justification**: Stable ids spec:{pid}:{n} for grounding (§4 EvidenceRef.id format)

## Rule: reviews.loaded

- **raw_count**: 34000
- **ok_before_dedup**: 33992
- **orphan_count**: 0
- **empty_text_dropped**: 8
- **justification**: Orphans → quarantine; empty text dropped (§5.1)

## Rule: reviews.pii

- **total_hits**: 15
- **justification**: PII redacted in title+text before DB write (§5.8)

## Rule: reviews.injection

- **flagged**: 202
- **justification**: Injection phrases flagged, row kept for guardrail eval (§5.8)

## Rule: reviews.exact_dedup

- **exact_dup_count_before_marking**: 10
- **justification**: Identical (reviewer_id, product_id, text) triples marked is_duplicate=1. Cross-product near-duplicates NOT removed — fake-review signal (P11). (§5.1)

## Rule: reviews.alias_repointed

- **count**: 66
- **justification**: Reviews on alias product_ids re-pointed to canonical (§5.1)

## Rule: ingest.complete

- **elapsed_s**: 43.36
- **db_hash**: 226880a684e90e06134bce28111791191b73e1c79ac50e4ed41d9a6a9f97a73e
- **note**: Hash excludes timestamps; identical across idempotent re-runs
