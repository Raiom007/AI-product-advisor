"""Grounding validator — deterministic check that every statement is grounded (§5.7).

Rules:
1. Every evidence_id in a statement must exist in that product's evidence pool.
2. Every evidence_id must belong to the correct product (no cross-product leakage).
3. Every numeric / price / spec token in the statement text must appear verbatim in
   at least one cited evidence item's text.
   WHY: This is the §5.8 "Fabrication" row defence — the LLM cannot invent numbers.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass

from advisor.explain.composer import StatementOut, ProductComposition

logger = logging.getLogger(__name__)

# Match integers, floats, and unit-suffixed numbers (e.g. 40000, 15.6, 8GB, ₹40000, Rs40000)
_NUMBER_RE = re.compile(r'(?:\u20b9|Rs\.?\s*)?\b\d[\d,]*(?:\.\d+)?(?:\s*(?:GB|TB|MB|GHz|MHz|kg|g|W|mAh|inch))?\b')


@dataclass
class ValidationResult:
    ok: bool
    violations: list[str]


def _collect_evidence_text(evidence_ids: list[str], pool: dict[str, str]) -> str:
    """Concatenate text of all cited evidence items."""
    return " ".join(pool.get(eid, "") for eid in evidence_ids)


def validate_statement(
    stmt: StatementOut,
    product_id: str,
    evidence_pool: list[dict],
) -> ValidationResult:
    """Validate a single statement against the evidence pool for `product_id`."""
    # Build lookup: id → text, id → product_id
    id_to_text: dict[str, str] = {}
    id_to_pid: dict[str, str] = {}
    for ev in evidence_pool:
        eid = ev.get("id", "")
        id_to_text[eid] = ev.get("text", "")
        id_to_pid[eid] = ev.get("product_id", product_id)

    violations: list[str] = []

    for eid in stmt.evidence_ids:
        # Rule 1: id must exist
        if eid not in id_to_text:
            violations.append(f"Unknown evidence id '{eid}'")
            continue
        # Rule 2: id must belong to this product
        owner = id_to_pid.get(eid, product_id)
        if owner != product_id:
            violations.append(f"Cross-product evidence id '{eid}' (belongs to '{owner}')")

    # Rule 3: every number/price token in text must appear in cited evidence
    cited_text = _collect_evidence_text(stmt.evidence_ids, id_to_text)
    for tok in _NUMBER_RE.findall(stmt.text):
        tok_clean = tok.strip()
        if tok_clean and tok_clean not in cited_text:
            violations.append(f"Fabricated number/token '{tok_clean}' not found in cited evidence")

    return ValidationResult(ok=len(violations) == 0, violations=violations)


def validate_composition(
    composition: ProductComposition,
    evidence_pool: list[dict],
    valid_review_ids: set[str],
) -> tuple[list[dict], list[str], list[str]]:
    """Validate all statements and review_quote_ids for one product.

    Returns:
        (valid_statements, valid_review_quote_ids, violation_messages)
    """
    valid_stmts: list[dict] = []
    violations: list[str] = []

    for stmt in composition.statements:
        result = validate_statement(stmt, composition.product_id, evidence_pool)
        if result.ok:
            valid_stmts.append({"text": stmt.text, "evidence_ids": stmt.evidence_ids})
        else:
            violations.extend(result.violations)
            logger.warning(
                f"Statement dropped for {composition.product_id}: {result.violations}"
            )

    # Validate review_quote_ids
    valid_rids: list[str] = []
    for rid in composition.review_quote_ids:
        if rid in valid_review_ids:
            valid_rids.append(rid)
        else:
            violations.append(f"Unknown review quote id '{rid}'")

    # Clamp to 2-4
    valid_rids = valid_rids[:4]

    return valid_stmts, valid_rids, violations
