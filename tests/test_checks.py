"""Tests for individual data quality checks."""

from __future__ import annotations

import duckdb

from duckdb_data_quality.checks import (
    check_composite,
    check_duplicates,
    check_freshness,
    check_nulls,
    check_range,
    check_referential_integrity,
    check_regex,
    check_uniqueness,
)
from duckdb_data_quality.models import CheckConfig, CheckStatus


class TestNulls:
    def test_reports_percentage_for_nullable_column(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="nulls",
            table="customers",
            column="email",
            params={"threshold": 50},
        )
        result = check_nulls(conn, config)
        assert result.status == CheckStatus.PASS
        assert result.value is not None
        assert float(result.value) > 0

    def test_fails_when_nulls_exceed_threshold(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="nulls",
            table="customers",
            column="email",
            params={"threshold": 0},
        )
        result = check_nulls(conn, config)
        assert result.status == CheckStatus.FAIL

    def test_passes_for_non_null_column(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="nulls",
            table="customers",
            column="name",
            params={"threshold": 0},
        )
        result = check_nulls(conn, config)
        assert result.status == CheckStatus.PASS


class TestDuplicates:
    def test_no_duplicates_in_primary_key(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="duplicates",
            table="customers",
            params={"columns": ["id"]},
        )
        result = check_duplicates(conn, config)
        assert result.status == CheckStatus.PASS
        assert result.value == 0

    def test_detects_full_row_duplicates(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        conn.execute(
            "INSERT INTO customers VALUES "
            "(4, 'Alice', 'alice@example.com', '2026-11-01 10:00:00')"
        )
        config = CheckConfig(
            check_name="duplicates",
            table="customers",
            params={"columns": ["name", "email"]},
        )
        result = check_duplicates(conn, config)
        assert result.status == CheckStatus.FAIL


class TestUniqueness:
    def test_primary_key_is_unique(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="uniqueness",
            table="customers",
            column="id",
        )
        result = check_uniqueness(conn, config)
        assert result.status == CheckStatus.PASS
        assert result.value == 100.0

    def test_non_unique_column_reports_percentage(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="uniqueness",
            table="orders",
            column="customer_id",
        )
        result = check_uniqueness(conn, config)
        assert result.status == CheckStatus.FAIL
        assert result.value is not None
        assert float(result.value) < 100.0


class TestRange:
    def test_values_within_range(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="range",
            table="orders",
            column="amount",
            params={"min": -100, "max": 1000},
        )
        result = check_range(conn, config)
        assert result.status == CheckStatus.PASS

    def test_fails_when_below_minimum(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="range",
            table="orders",
            column="amount",
            params={"min": 0, "max": 1000},
        )
        result = check_range(conn, config)
        assert result.status == CheckStatus.FAIL
        assert "min" in result.message


class TestRegex:
    def test_email_pattern_matches(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="regex",
            table="customers",
            column="email",
            params={"pattern": ".*@.*\\..*"},
        )
        result = check_regex(conn, config)
        assert result.status == CheckStatus.PASS

    def test_invalid_pattern_fails(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="regex",
            table="orders",
            column="status",
            params={"pattern": "^completed$"},
        )
        result = check_regex(conn, config)
        assert result.status == CheckStatus.FAIL


class TestReferentialIntegrity:
    def test_valid_references_pass(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        conn.execute("""
            CREATE TABLE valid_orders AS
            SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers)
        """)
        config = CheckConfig(
            check_name="referential_integrity",
            table="valid_orders",
            column="customer_id",
            params={"ref_table": "customers", "ref_column": "id"},
        )
        result = check_referential_integrity(conn, config)
        assert result.status == CheckStatus.PASS

    def test_orphaned_rows_fail(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="referential_integrity",
            table="orders",
            column="customer_id",
            params={"ref_table": "customers", "ref_column": "id"},
        )
        result = check_referential_integrity(conn, config)
        assert result.status == CheckStatus.FAIL
        assert result.value is not None
        assert int(result.value) > 0


class TestFreshness:
    def test_recent_data_passes(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="freshness",
            table="customers",
            column="created_at",
            params={"max_hours": 9999},
        )
        result = check_freshness(conn, config)
        assert result.status == CheckStatus.PASS

    def test_stale_data_fails(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="freshness",
            table="customers",
            column="created_at",
            params={"max_hours": 0.001},
        )
        result = check_freshness(conn, config)
        assert result.status == CheckStatus.FAIL


class TestComposite:
    def test_custom_sql_passes(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="composite",
            table="orders",
            params={
                "sql": "SELECT COUNT(*) FROM orders WHERE amount < 0",
                "expected": 1,
            },
        )
        result = check_composite(conn, config)
        assert result.status == CheckStatus.PASS

    def test_custom_sql_fails(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        config = CheckConfig(
            check_name="composite",
            table="orders",
            params={
                "sql": "SELECT COUNT(*) FROM orders WHERE amount < 0",
                "expected": 0,
            },
        )
        result = check_composite(conn, config)
        assert result.status == CheckStatus.FAIL
