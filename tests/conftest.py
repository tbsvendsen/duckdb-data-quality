"""Shared fixtures with real DuckDB connections."""

from __future__ import annotations

import duckdb
import pytest


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    db = duckdb.connect(":memory:")
    db.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            email VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        INSERT INTO customers VALUES
        (1, 'Alice', 'alice@example.com', '2026-11-01 10:00:00'),
        (2, 'Bob', 'bob@example.com', '2026-11-10 12:00:00'),
        (3, 'Charlie', NULL, '2026-11-14 08:00:00')
    """)

    db.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount DOUBLE,
            status VARCHAR,
            order_date DATE
        )
    """)
    db.execute("""
        INSERT INTO orders VALUES
        (1, 1, 99.99, 'completed', '2026-11-01'),
        (2, 2, 250.00, 'completed', '2026-11-05'),
        (3, 1, 15.50, 'pending', '2026-11-10'),
        (4, 999, 75.00, 'completed', '2026-11-12'),
        (5, 2, -10.00, 'cancelled', '2026-11-13')
    """)

    return db
