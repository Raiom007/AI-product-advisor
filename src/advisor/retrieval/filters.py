"""SQL-based constraint filtering — constraints → allow-list of product_ids.

This is the first-pass filter (§5.2 pipeline step 1): hard filters applied
directly in SQL before any keyword or semantic retrieval. SQL filters are
cheaper and faster than post-retrieval Python checks.

WHY: "Hard filters → allow-list of product_ids (SQL)" (§5.2).
The allow-list is passed to KeywordIndex.search() and VectorIndex.search()
as the `allow_ids` parameter so retrieval only scores eligible products.

Constraints that cannot be checked in SQL (e.g. must_have with a parsed
spec key) are returned as `residual_constraints` for Python-side gate() to
handle after retrieval.

Idempotency: this function is pure — same inputs → same SQL + same allow-list.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from advisor.core.schemas import Constraint

# Constraint kinds that can be filtered purely in SQL
_SQL_FILTERABLE = {"budget", "category", "brand_exclude"}

# Constraint kinds that require parsed spec data → Python gate post-retrieval
_PYTHON_ONLY = {"must_have", "weight_limit", "size_limit"}


def build_allow_list(
    conn: sqlite3.Connection,
    hard_constraints: list[Constraint],
    include_non_canonical: bool = False,
) -> tuple[list[str], list[Constraint]]:
    """Return (allow_list_product_ids, residual_constraints).

    SQL-filterable constraints are applied here.
    Residual constraints are passed to gate() after retrieval.

    Args:
        conn:                  open SQLite connection to advisor.db
        hard_constraints:      ParsedQuery.hard list
        include_non_canonical: if True, include alias products (default: False)

    Returns:
        allow_list:            sorted list of product_ids passing SQL filters
        residual:              constraints that need Python gate() post-retrieval
    """
    sql_constraints: list[Constraint] = []
    residual: list[Constraint] = []

    for c in hard_constraints:
        if c.kind in _SQL_FILTERABLE:
            sql_constraints.append(c)
        else:
            residual.append(c)

    # Base query
    where_clauses: list[str] = []
    params: list[Any] = []

    if not include_non_canonical:
        where_clauses.append("is_canonical = 1")

    for c in sql_constraints:
        clause, clause_params = _constraint_to_sql(c)
        if clause:
            where_clauses.append(clause)
            params.extend(clause_params)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    query = f"SELECT product_id FROM products WHERE {where_sql} ORDER BY product_id"  # noqa: S608

    rows = conn.execute(query, params).fetchall()
    allow_list = [row[0] for row in rows]

    return allow_list, residual


def _constraint_to_sql(c: Constraint) -> tuple[str, list[Any]]:
    """Convert one constraint to a SQL WHERE fragment.

    Returns ("", []) if the constraint cannot be expressed in SQL.
    """
    if c.kind == "budget":
        return _budget_sql(c)
    if c.kind == "category":
        return _category_sql(c)
    if c.kind == "brand_exclude":
        return _brand_exclude_sql(c)
    return "", []


def _budget_sql(c: Constraint) -> tuple[str, list[Any]]:
    """effective_price_inr compared against budget."""
    col = "effective_price_inr"
    val = c.value
    op = c.op

    if op == "lte":
        return f"{col} IS NOT NULL AND {col} <= ?", [float(val)]
    if op == "gte":
        return f"{col} IS NOT NULL AND {col} >= ?", [float(val)]
    if op == "between" and isinstance(val, dict):
        clauses = [f"{col} IS NOT NULL"]
        p: list[Any] = []
        if val.get("min_inr") is not None:
            clauses.append(f"{col} >= ?")
            p.append(float(val["min_inr"]))
        if val.get("max_inr") is not None:
            clauses.append(f"{col} <= ?")
            p.append(float(val["max_inr"]))
        return " AND ".join(clauses), p
    return "", []


def _category_sql(c: Constraint) -> tuple[str, list[Any]]:
    """Match against cat_l1, cat_l2, or cat_l3."""
    val = str(c.value).strip()
    if c.op == "eq":
        return (
            "(LOWER(cat_l2) = LOWER(?) OR LOWER(cat_l3) = LOWER(?) OR LOWER(cat_l1) = LOWER(?))",
            [val, val, val],
        )
    if c.op == "in" and isinstance(c.value, list):
        placeholders = ",".join("?" * len(c.value))
        vals = [str(v).strip() for v in c.value]
        return (
            f"(LOWER(cat_l2) IN ({placeholders}) OR LOWER(cat_l3) IN ({placeholders}) OR LOWER(cat_l1) IN ({placeholders}))",
            vals * 3,
        )
    return "", []


def _brand_exclude_sql(c: Constraint) -> tuple[str, list[Any]]:
    """Exclude products whose brand matches the excluded list."""
    if c.op in ("not_in", "eq"):
        excluded = c.value if isinstance(c.value, list) else [c.value]
        excluded_lower = [str(e).strip().lower() for e in excluded]
        placeholders = ",".join("?" * len(excluded_lower))
        # Products with NULL brand pass (they're unverifiable — handled by Python gate)
        return (
            f"(brand IS NULL OR LOWER(brand) NOT IN ({placeholders}))",
            excluded_lower,
        )
    return "", []
