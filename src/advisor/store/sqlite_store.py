"""SQLite schema definition and loader.

Tables (§5.2):
  products            — cleaned canonical products
  product_specs       — parsed spec key-value pairs with stable ids spec:{pid}:{n}
  reviews             — cleaned, PII-redacted reviews (canonical product_id)
  review_flags        — fake-review detector output (empty until P11)
  taxonomy            — unique (cat_l1, cat_l2, cat_l3) tuples
  quarantine_reviews  — reviews whose product_id is not in the catalogue
  image_check_cache   — lazily populated by P17 vision verifier

WHY SQLite: §9 — "zero-ops, single file, ships with Python; FTS5 on-disk
filterable via SQL joins". FTS5 virtual tables (products_fts, reviews_fts)
are added after initial load in a separate migration step (P8).

Idempotency: create_schema() uses IF NOT EXISTS. The ingest pipeline
truncates and reloads, so running `make ingest` twice gives the same DB.

Stable hash: db_hash() reads back all rows in deterministic order and
returns sha256(json). This is what `make ingest` idempotency test uses.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS products (
    product_id            TEXT PRIMARY KEY,
    name                  TEXT,
    brand                 TEXT,
    cat_l1                TEXT,
    cat_l2                TEXT,
    cat_l3                TEXT,
    retail_price_inr      REAL,
    discounted_price_inr  REAL,
    effective_price_inr   REAL,
    price_unknown         INTEGER NOT NULL DEFAULT 0,  -- 1 if both prices missing
    price_anomaly         INTEGER NOT NULL DEFAULT 0,  -- 1 if discounted > retail
    description           TEXT,                        -- PII-redacted
    image_urls            TEXT,                        -- pipe-separated, kept as-is
    image_url_count       INTEGER,
    image_url_broken      INTEGER NOT NULL DEFAULT 0,  -- 1 if any URL heuristically bad
    alias_ids             TEXT,                        -- JSON array of merged product_ids
    is_canonical          INTEGER NOT NULL DEFAULT 1,
    ingested_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_specs (
    spec_id     TEXT PRIMARY KEY,  -- "spec:{product_id}:{n}"
    product_id  TEXT NOT NULL REFERENCES products(product_id),
    seq         INTEGER NOT NULL,
    key         TEXT,
    value       TEXT,
    unit        TEXT,
    original_line TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS taxonomy (
    cat_l1  TEXT NOT NULL,
    cat_l2  TEXT NOT NULL,
    cat_l3  TEXT NOT NULL,
    PRIMARY KEY (cat_l1, cat_l2, cat_l3)
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id           TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    original_product_id TEXT,    -- set if review was re-pointed from an alias
    rating              INTEGER,
    title               TEXT,    -- PII-redacted
    text                TEXT,    -- PII-redacted
    review_date         TEXT,
    reviewer_id         TEXT,
    helpful_votes       INTEGER,
    injection_flag      INTEGER NOT NULL DEFAULT 0,
    is_duplicate        INTEGER NOT NULL DEFAULT 0,
    ingested_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_flags (
    review_id   TEXT NOT NULL REFERENCES reviews(review_id),
    score       REAL,
    signals     TEXT,  -- JSON {"near_dup": 0.9, ...}
    reasons     TEXT,  -- JSON ["near identical to REV0000002"]
    action      TEXT,  -- "exclude" | "downweight" | "keep"
    flagged_at  TEXT,
    PRIMARY KEY (review_id)
);

CREATE TABLE IF NOT EXISTS quarantine_reviews (
    review_id           TEXT PRIMARY KEY,
    missing_product_id  TEXT NOT NULL,
    reason              TEXT NOT NULL,
    review_date         TEXT,
    ingested_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS image_check_cache (
    url_hash      TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    valid         INTEGER,        -- NULL = unchecked; 1 = ok; 0 = bad
    http_status   INTEGER,
    content_type  TEXT,
    checked_at    TEXT
);
"""

def build_fts_indexes(conn: sqlite3.Connection) -> None:
    """Create and populate FTS5 virtual tables.
    
    WHY: Doing this as a batch insert is much faster than triggers during ingest.
    """
    # Products FTS
    conn.execute("DROP TABLE IF EXISTS products_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE products_fts USING fts5(
            product_id UNINDEXED,
            name, brand, description, cat_l1, cat_l2, cat_l3,
            content=products, content_rowid=rowid
        )
    """)
    conn.execute("""
        INSERT INTO products_fts(rowid, product_id, name, brand, description, cat_l1, cat_l2, cat_l3)
        SELECT rowid, product_id, name, brand, description, cat_l1, cat_l2, cat_l3 FROM products
    """)

    # Reviews FTS
    conn.execute("DROP TABLE IF EXISTS reviews_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE reviews_fts USING fts5(
            review_id UNINDEXED,
            product_id UNINDEXED,
            title, text,
            content=reviews, content_rowid=rowid
        )
    """)
    conn.execute("""
        INSERT INTO reviews_fts(rowid, review_id, product_id, title, text)
        SELECT rowid, review_id, product_id, title, text FROM reviews
    """)

    conn.commit()



# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


def open_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the SQLite database; apply schema DDL."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_DDL)
    conn.commit()
    return conn


def truncate_all(conn: sqlite3.Connection) -> None:
    """Delete all rows from all tables (preserves schema).

    WHY: Ingest is designed to be idempotent — running twice produces the
    same DB. Truncate-then-reload is simpler than upsert logic here.
    """
    tables = [
        "image_check_cache", "quarantine_reviews", "review_flags",
        "reviews", "product_specs", "taxonomy", "products",
    ]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")  # noqa: S608 — table names are literals, not user input
    conn.commit()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def insert_products(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO products (
            product_id, name, brand, cat_l1, cat_l2, cat_l3,
            retail_price_inr, discounted_price_inr, effective_price_inr,
            price_unknown, price_anomaly, description,
            image_urls, image_url_count, image_url_broken,
            alias_ids, is_canonical, ingested_at
        ) VALUES (
            :product_id, :name, :brand, :cat_l1, :cat_l2, :cat_l3,
            :retail_price_inr, :discounted_price_inr, :effective_price_inr,
            :price_unknown, :price_anomaly, :description,
            :image_urls, :image_url_count, :image_url_broken,
            :alias_ids, :is_canonical, :ingested_at
        )
        """,
        rows,
    )
    conn.commit()


def insert_specs(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO product_specs
            (spec_id, product_id, seq, key, value, unit, original_line)
        VALUES
            (:spec_id, :product_id, :seq, :key, :value, :unit, :original_line)
        """,
        rows,
    )
    conn.commit()


def insert_taxonomy(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO taxonomy (cat_l1, cat_l2, cat_l3) VALUES (:cat_l1, :cat_l2, :cat_l3)",
        rows,
    )
    conn.commit()


def insert_reviews(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO reviews (
            review_id, product_id, original_product_id,
            rating, title, text, review_date, reviewer_id,
            helpful_votes, injection_flag, is_duplicate, ingested_at
        ) VALUES (
            :review_id, :product_id, :original_product_id,
            :rating, :title, :text, :review_date, :reviewer_id,
            :helpful_votes, :injection_flag, :is_duplicate, :ingested_at
        )
        """,
        rows,
    )
    conn.commit()


def insert_quarantine(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR IGNORE INTO quarantine_reviews
            (review_id, missing_product_id, reason, review_date, ingested_at)
        VALUES
            (:review_id, :missing_product_id, :reason, :review_date, :ingested_at)
        """,
        rows,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Stable hash (for idempotency testing)
# ---------------------------------------------------------------------------

_HASH_TABLES = [
    ("products",       "product_id"),
    ("product_specs",  "spec_id"),
    ("taxonomy",       "cat_l1, cat_l2, cat_l3"),
    ("reviews",        "review_id"),
    ("quarantine_reviews", "review_id"),
]


def db_hash(conn: sqlite3.Connection) -> str:
    """Return sha256 of all hashable tables in deterministic sorted order.

    WHY: Timestamps in ingested_at would make the hash differ across runs.
    We exclude ingested_at and flagged_at from the hash payload so that
    running `make ingest` twice gives the same hash as long as the data and
    code are identical (§5.9 reproducibility requirement).
    """
    parts: list[str] = []
    for table, order_cols in _HASH_TABLES:
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY {order_cols}"  # noqa: S608
        ).fetchall()
        for row in rows:
            d = dict(row)
            # Exclude timestamp columns from hash payload
            d.pop("ingested_at", None)
            d.pop("flagged_at", None)
            d.pop("checked_at", None)
            parts.append(json.dumps(d, sort_keys=True, default=str))
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# KeywordIndex implementation
# ---------------------------------------------------------------------------

class SQLiteKeywordIndex:
    """KeywordIndex implementation using FTS5 virtual tables."""

    def __init__(self, conn: sqlite3.Connection, table: str = "products_fts"):
        """Initialize with a connection and target FTS table (products_fts or reviews_fts)."""
        self._conn = conn
        self._table = table

    def search(
        self,
        query: str,
        allow_ids: list[str],
        k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search using FTS5 bm25().
        
        If allow_ids is empty, returns empty list.
        Returns: [(product_id, bm25_score), ...]
        """
        if not allow_ids:
            return []

        # SQLite FTS5 query syntax can be strict. A naive approach is to use standard MATCH.
        # Clean query by removing quotes/special characters that break FTS5
        safe_query = " ".join(w for w in query.replace('"', ' ').split() if w.isalnum())
        if not safe_query:
            return []

        # Build SQL IN clause for allow_ids
        placeholders = ",".join("?" for _ in allow_ids)

        # FTS5 returns negative scores for bm25() (more negative = better),
        # so we multiply by -1 to return a positive score where higher is better.
        sql = f"""
            SELECT product_id, -bm25({self._table}) as score
            FROM {self._table}
            WHERE {self._table} MATCH ?
              AND product_id IN ({placeholders})
            ORDER BY bm25({self._table})
            LIMIT ?
        """

        try:
            rows = self._conn.execute(sql, [safe_query] + allow_ids + [k]).fetchall()
        except sqlite3.OperationalError as e:
            import logging
            logging.getLogger(__name__).warning(f"FTS5 search failed: {e}")
            return []

        return [(row["product_id"], float(row["score"])) for row in rows]

