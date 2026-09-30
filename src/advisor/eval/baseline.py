"""Baseline evaluation strategy.

WHY: §8 - SOW-defined baseline is keyword search over name+description,
sorted by rating. This lives in eval/ and shares only the DB.
"""
from __future__ import annotations

import sqlite3
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

    # We clean the query for FTS MATCH syntax
    safe_query = " ".join(w for w in query.replace('"', ' ').split() if w.isalnum())
    if not safe_query:
        return []

    # We want keyword search over name and description only, sorted by average rating.
    # We can use FTS5 for the keyword part: {name description} : query
    fts_query = f"{{name description}} : {safe_query}"

    # Left join reviews to get average rating. If no reviews, rating is 0.
    sql = """
        WITH keyword_hits AS (
            SELECT product_id
            FROM products_fts
            WHERE products_fts MATCH ?
        ),
        avg_ratings AS (
            SELECT product_id, AVG(rating) as avg_rating
            FROM reviews
            GROUP BY product_id
        )
        SELECT h.product_id, COALESCE(r.avg_rating, 0.0) as score
        FROM keyword_hits h
        LEFT JOIN avg_ratings r ON h.product_id = r.product_id
        ORDER BY score DESC
        LIMIT ?
    """

    try:
        rows = conn.execute(sql, [fts_query, k]).fetchall()
    except sqlite3.OperationalError as e:
        import logging
        logging.getLogger(__name__).warning(f"Baseline FTS search failed: {e}")
        # Fallback to naive LIKE if FTS query syntax was invalid
        like_query = f"%{safe_query}%"
        fallback_sql = """
            WITH avg_ratings AS (
                SELECT product_id, AVG(rating) as avg_rating
                FROM reviews
                GROUP BY product_id
            )
            SELECT p.product_id, COALESCE(r.avg_rating, 0.0) as score
            FROM products p
            LEFT JOIN avg_ratings r ON p.product_id = r.product_id
            WHERE p.name LIKE ? OR p.description LIKE ?
            ORDER BY score DESC
            LIMIT ?
        """
        rows = conn.execute(fallback_sql, [like_query, like_query, k]).fetchall()

    result = [(row["product_id"], float(row["score"])) for row in rows]
    conn.close()
    return result
