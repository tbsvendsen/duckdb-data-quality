"""Data quality checks for DuckDB databases."""

from duckdb_data_quality.api import check, report, validate_schema
from duckdb_data_quality.models import CheckResult, CheckStatus, SchemaExpectation

__version__ = "0.1.0"

__all__ = [
    "check",
    "report",
    "validate_schema",
    "CheckResult",
    "CheckStatus",
    "SchemaExpectation",
]
