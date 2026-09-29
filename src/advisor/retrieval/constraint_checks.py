"""Constraint kind implementations — registered into the constraint_kinds registry.

Each kind exposes:
  check(product_row: dict, constraint: Constraint) -> bool | None
    True  = constraint satisfied (product passes)
    False = constraint violated (product is gated out)
    None  = unverifiable (spec not present; policy from ranking.yaml applies)

Imported here so registrations fire on `import advisor.retrieval.constraint_checks`.
The agent imports this module before running the gate.

WHY (§5.6): "Hard constraints remove a product before ranking and are re-checked
on the final output." The gate is deterministic — no LLM involved.

WHY (§4.1): Each kind is a registered plug-in. To add a new constraint kind,
add a @constraint_kind decorator here (or in a new module) and update
domain/electronics/spec_keys.yaml if it needs a new spec key.
"""
from __future__ import annotations

from typing import Any

from advisor.core.registries import constraint_kinds
from advisor.core.schemas import Constraint
from advisor.ingest.specs_parser import parse_specs

# ---------------------------------------------------------------------------
# Helper: extract parsed specs from a product_row dict
# WHY: product_row is a plain dict from the DB (sqlite3.Row → dict).
# Specs are stored as product_specs rows; the agent passes them in via
# the specs_parsed field on the product dict. Fallback: re-parse from
# specification_text if specs_parsed is absent (unit tests, profile runs).
# ---------------------------------------------------------------------------


def _get_specs(product: dict[str, Any]) -> dict[str, Any]:
    """Return parsed specs dict for a product row.

    If product already has key 'specs_parsed' (populated by retrieval),
    return that. Otherwise re-parse from specification_text (slower but safe).
    """
    if "specs_parsed" in product and product["specs_parsed"] is not None:
        return product["specs_parsed"]
    spec_text = product.get("specification_text") or ""
    pid = product.get("product_id", "")
    return parse_specs(spec_text, pid)


# ---------------------------------------------------------------------------
# budget — effective_price_inr vs Constraint.value (min_inr / max_inr)
# ---------------------------------------------------------------------------


@constraint_kinds.register("budget")
def check_budget(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Check price constraint.

    Constraint.value should be a dict with optional "min_inr" and "max_inr".
    Constraint.op: "lte" (max), "gte" (min), "between" (both).
    """
    price = product.get("effective_price_inr")
    if price is None:
        return None   # price_unknown=True → unverifiable

    val = constraint.value
    op = constraint.op

    if op == "lte":
        max_inr = float(val) if not isinstance(val, dict) else float(val.get("max_inr", val))
        return price <= max_inr

    if op == "gte":
        min_inr = float(val) if not isinstance(val, dict) else float(val.get("min_inr", val))
        return price >= min_inr

    if op == "between" and isinstance(val, dict):
        min_inr = val.get("min_inr")
        max_inr = val.get("max_inr")
        if min_inr is not None and price < float(min_inr):
            return False
        if max_inr is not None and price > float(max_inr):
            return False
        return True

    return None


# ---------------------------------------------------------------------------
# category — product.cat_l2 or cat_l3 vs Constraint.value
# ---------------------------------------------------------------------------


@constraint_kinds.register("category")
def check_category(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Check that the product belongs to the required category."""
    val = str(constraint.value).lower().strip()
    for col in ("cat_l3", "cat_l2", "cat_l1"):
        cat = (product.get(col) or "").lower().strip()
        if cat:
            if constraint.op == "eq":
                if cat == val or val in cat or cat in val:
                    return True
            elif constraint.op == "in":
                values = [str(v).lower().strip() for v in (constraint.value if isinstance(constraint.value, list) else [constraint.value])]
                if any(cat == v or v in cat for v in values):
                    return True
    # Category found in product but didn't match → False (not unverifiable)
    if any(product.get(col) for col in ("cat_l1", "cat_l2", "cat_l3")):
        return False
    return None


# ---------------------------------------------------------------------------
# brand_exclude — product.brand NOT in excluded list
# ---------------------------------------------------------------------------


@constraint_kinds.register("brand_exclude")
def check_brand_exclude(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Return False if product brand is in the excluded set."""
    brand = (product.get("brand") or "").lower().strip()
    if not brand:
        return None   # brand unknown → unverifiable

    excluded = constraint.value
    if isinstance(excluded, str):
        excluded = [excluded]
    excluded_lower = [str(e).lower().strip() for e in excluded]

    if constraint.op == "not_in":
        return brand not in excluded_lower

    # "eq" with brand_exclude means "exclude exactly this brand"
    if constraint.op == "eq":
        return brand != excluded_lower[0] if excluded_lower else True

    return None


# ---------------------------------------------------------------------------
# must_have — spec key must be present and match value
# ---------------------------------------------------------------------------


@constraint_kinds.register("must_have")
def check_must_have(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Check that the product has a required spec key with at least a minimum value.

    Constraint.key: canonical spec key (e.g. "hdmi_count", "5g", "noise_cancellation")
    Constraint.value: required value / minimum count / True
    Constraint.op: "eq", "gte", "contains", "eq" (boolean True)
    """
    specs = _get_specs(product)
    key = constraint.key

    if key not in specs:
        return None   # spec not present → unverifiable

    spec_val = specs[key].get("value")
    if spec_val is None:
        return None

    req = constraint.value
    op = constraint.op

    if op == "eq":
        if isinstance(spec_val, bool):
            return spec_val == bool(req)
        return str(spec_val).lower().strip() == str(req).lower().strip()

    if op == "gte":
        try:
            return float(spec_val) >= float(req)
        except (ValueError, TypeError):
            return None

    if op == "lte":
        try:
            return float(spec_val) <= float(req)
        except (ValueError, TypeError):
            return None

    if op == "contains":
        return str(req).lower() in str(spec_val).lower()

    return None


# ---------------------------------------------------------------------------
# weight_limit — product weight_kg <= Constraint.value
# ---------------------------------------------------------------------------


@constraint_kinds.register("weight_limit")
def check_weight_limit(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Check product weight against a maximum limit."""
    specs = _get_specs(product)
    weight_entry = specs.get("weight_kg")
    if weight_entry is None:
        return None
    weight = weight_entry.get("value")
    if weight is None:
        return None
    try:
        limit = float(constraint.value)
    except (ValueError, TypeError):
        return None

    if constraint.op == "lte":
        return float(weight) <= limit
    if constraint.op == "gte":
        return float(weight) >= limit
    return None


# ---------------------------------------------------------------------------
# size_limit — screen_inch <= Constraint.value
# ---------------------------------------------------------------------------


@constraint_kinds.register("size_limit")
def check_size_limit(product: dict[str, Any], constraint: Constraint) -> bool | None:
    """Check screen size against a limit (inches)."""
    specs = _get_specs(product)
    size_entry = specs.get("screen_inch")
    if size_entry is None:
        return None
    size = size_entry.get("value")
    if size is None:
        return None
    try:
        limit = float(constraint.value)
    except (ValueError, TypeError):
        return None

    if constraint.op == "lte":
        return float(size) <= limit
    if constraint.op == "gte":
        return float(size) >= limit
    return None


# ---------------------------------------------------------------------------
# Gate function — applies all hard constraints
# ---------------------------------------------------------------------------


def gate(
    product: dict[str, Any],
    hard_constraints: list[Constraint],
    unverifiable_policy: str = "exclude",
) -> tuple[bool, list[str]]:
    """Apply all hard constraints to one product.

    Args:
        product:              product row dict (with specs_parsed populated)
        hard_constraints:     list of Constraint objects (from ParsedQuery.hard)
        unverifiable_policy:  "exclude" | "include" (from configs/ranking.yaml)

    Returns:
        (passes: bool, reasons: list[str])
        reasons is empty when passes=True.

    WHY: §5.6 "gate(p) = 1 if p satisfies ALL hard constraints else 0".
    Gated-out products are removed before scoring. The gate is re-run as a
    post-condition on the final output (§1 principle 5, §5.7 abstention).
    """
    checker_map = {
        "budget": check_budget,
        "category": check_category,
        "brand_exclude": check_brand_exclude,
        "must_have": check_must_have,
        "weight_limit": check_weight_limit,
        "size_limit": check_size_limit,
    }

    reasons: list[str] = []
    for constraint in hard_constraints:
        checker = checker_map.get(constraint.kind)
        if checker is None:
            # Unknown kind — fail open (do not gate out) but log
            continue

        result = checker(product, constraint)

        if result is False:
            reasons.append(
                f"Constraint violated: kind={constraint.kind} "
                f"key={constraint.key} op={constraint.op} value={constraint.value}"
            )
        elif result is None:
            if unverifiable_policy == "exclude":
                reasons.append(
                    f"Constraint unverifiable (excluded by policy): "
                    f"kind={constraint.kind} key={constraint.key}"
                )

    passes = len(reasons) == 0
    return passes, reasons
