"""Baseline evaluation strategy.

WHY: §8 - SOW-defined baseline is keyword search over name+description,
sorted by rating. This lives in eval/ and shares only the DB.
"""
from __future__ import annotations

from pathlib import Path

from advisor.store.sqlite_store import open_db


def run_baseline(
    query: str,
    db_path: str = "data/advisor.db",
    k: int = 10,
) -> list[tuple[str, float]]:
    """Run baseline retrieval.
    
    Args:
        query: search terms.
        db_path: path to sqlite db.
        k: max results to return.
        
    Returns:
        List of (product_id, average_rating).
    """
    conn = open_db(Path(db_path))

    # Split query into terms
    terms = query.replace('"', ' ').split()
    if not terms:
        conn.close()
        return []

    conditions = []
    params = []
    for term in terms:
        conditions.append("(p.name LIKE ? OR p.description LIKE ?)")
        params.extend([f"%{term}%", f"%{term}%"])

    where_clause = " AND ".join(conditions)

    sql = f"""
        WITH avg_ratings AS (
            SELECT product_id, AVG(rating) as avg_rating
            FROM reviews
            GROUP BY product_id
        )
        SELECT p.product_id, COALESCE(r.avg_rating, 0.0) as score
        FROM products p
        LEFT JOIN avg_ratings r ON p.product_id = r.product_id
        WHERE {where_clause}
        ORDER BY score DESC
        LIMIT ?
    """
    params.append(k)

    rows = conn.execute(sql, params).fetchall()

    result = [(row["product_id"], float(row["score"])) for row in rows]
    conn.close()
    return result
