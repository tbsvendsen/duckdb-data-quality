"""Tests for the public API: check, validate_schema, report."""

from __future__ import annotations

import duckdb

from duckdb_data_quality.api import check, report, validate_schema
from duckdb_data_quality.models import CheckStatus


class TestCheckAPI:
    def test_runs_multiple_checks(self, conn: duckdb.DuckDBPyConnection) -> None:
        results = check(
            conn,
            "orders",
            [
                {"check": "nulls", "column": "amount", "threshold": 0},
                {"check": "uniqueness", "column": "id"},
            ],
        )
        assert len(results) == 2
        assert results[0].check_name == "nulls"
        assert results[1].check_name == "uniqueness"

    def test_unknown_check_returns_error(self, conn: duckdb.DuckDBPyConnection) -> None:
        results = check(conn, "orders", [{"check": "nonexistent"}])
        assert len(results) == 1
        assert results[0].status == CheckStatus.ERROR

    def test_handles_exception_in_check(self, conn: duckdb.DuckDBPyConnection) -> None:
        results = check(
            conn,
            "nonexistent_table",
            [{"check": "nulls", "column": "x", "threshold": 0}],
        )
        assert results[0].status == CheckStatus.ERROR


class TestValidateSchema:
    def test_matching_schema_passes(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = validate_schema(
            conn,
            "orders",
            [
                {"column": "id", "dtype": "INTEGER"},
                {"column": "amount", "dtype": "DOUBLE"},
                {"column": "status", "dtype": "VARCHAR"},
            ],
        )
        assert result.status == CheckStatus.PASS

    def test_missing_column_fails(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = validate_schema(
            conn,
            "orders",
            [{"column": "nonexistent", "dtype": "INTEGER"}],
        )
        assert result.status == CheckStatus.FAIL
        assert "missing column" in result.message

    def test_wrong_type_fails(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = validate_schema(
            conn,
            "orders",
            [{"column": "status", "dtype": "INTEGER"}],
        )
        assert result.status == CheckStatus.FAIL

    def test_nonexistent_table_errors(self, conn: duckdb.DuckDBPyConnection) -> None:
        result = validate_schema(
            conn, "no_such_table", [{"column": "x", "dtype": "INTEGER"}]
        )
        assert result.status == CheckStatus.ERROR


class TestReport:
    def test_generates_html(self, conn: duckdb.DuckDBPyConnection) -> None:
        results = check(
            conn,
            "orders",
            [
                {"check": "nulls", "column": "amount", "threshold": 0},
                {"check": "uniqueness", "column": "id"},
            ],
        )
        html = report(results)
        assert "<html>" in html
        assert "Data Quality Report" in html
        assert "nulls" in html
        assert "PASS" in html or "FAIL" in html

    def test_empty_results_produces_valid_html(self) -> None:
        html = report([])
        assert "<html>" in html
        assert "Total: 0" in html
