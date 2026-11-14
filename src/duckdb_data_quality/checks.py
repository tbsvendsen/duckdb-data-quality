"""Individual data quality check implementations."""

from __future__ import annotations

from collections.abc import Callable

import duckdb

from duckdb_data_quality.models import CheckConfig, CheckResult, CheckStatus

ParamValue = float | int | str | bool | list[str]


def _float_param(params: dict[str, ParamValue], key: str, default: float) -> float:
    val = params.get(key, default)
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        return float(val)
    return default


def check_nulls(conn: duckdb.DuckDBPyConnection, config: CheckConfig) -> CheckResult:
    table = config.table
    column = config.column
    threshold = _float_param(config.params, "threshold", 0.0)

    result = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN "{column}" IS NULL THEN 1 ELSE 0 END) AS nulls
        FROM "{table}"
        """
    ).fetchone()

    if result is None or result[0] == 0:
        return CheckResult(
            check_name="nulls",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="Table is empty or does not exist",
        )

    total, nulls = result
    pct = nulls / total * 100

    return CheckResult(
        check_name="nulls",
        table=table,
        column=column,
        status=CheckStatus.PASS if pct <= threshold else CheckStatus.FAIL,
        message=f"{pct:.1f}% null ({nulls}/{total})",
        value=round(pct, 2),
        threshold=threshold,
    )


def check_duplicates(
    conn: duckdb.DuckDBPyConnection, config: CheckConfig
) -> CheckResult:
    table = config.table
    columns = config.params.get("columns", [])

    if isinstance(columns, list) and columns:
        col_list = ", ".join(f'"{c}"' for c in columns)
    else:
        col_list = "*"

    result = conn.execute(
        f"""
        SELECT COUNT(*) - COUNT(DISTINCT ({col_list}))
        FROM "{table}"
        """
    ).fetchone()

    if result is None:
        return CheckResult(
            check_name="duplicates",
            table=table,
            status=CheckStatus.ERROR,
            message="Could not check duplicates",
        )

    dup_count = result[0]
    return CheckResult(
        check_name="duplicates",
        table=table,
        status=CheckStatus.PASS if dup_count == 0 else CheckStatus.FAIL,
        message=f"{dup_count} duplicate rows",
        value=dup_count,
    )


def check_uniqueness(
    conn: duckdb.DuckDBPyConnection, config: CheckConfig
) -> CheckResult:
    table = config.table
    column = config.column

    result = conn.execute(
        f"""
        SELECT
            COUNT("{column}") AS total,
            COUNT(DISTINCT "{column}") AS distinct_count
        FROM "{table}"
        """
    ).fetchone()

    if result is None or result[0] == 0:
        return CheckResult(
            check_name="uniqueness",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="Column is empty",
        )

    total, distinct = result
    pct = distinct / total * 100

    return CheckResult(
        check_name="uniqueness",
        table=table,
        column=column,
        status=CheckStatus.PASS if pct == 100.0 else CheckStatus.FAIL,
        message=f"{pct:.1f}% unique ({distinct}/{total})",
        value=round(pct, 2),
    )


def check_range(conn: duckdb.DuckDBPyConnection, config: CheckConfig) -> CheckResult:
    table = config.table
    column = config.column
    min_val = config.params.get("min")
    max_val = config.params.get("max")

    result = conn.execute(
        f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}"'
    ).fetchone()

    if result is None:
        return CheckResult(
            check_name="range",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="Could not check range",
        )

    actual_min, actual_max = result
    violations = []

    if min_val is not None and actual_min < min_val:
        violations.append(f"min {actual_min} < {min_val}")
    if max_val is not None and actual_max > max_val:
        violations.append(f"max {actual_max} > {max_val}")

    if violations:
        return CheckResult(
            check_name="range",
            table=table,
            column=column,
            status=CheckStatus.FAIL,
            message="; ".join(violations),
            value=f"[{actual_min}, {actual_max}]",
        )

    return CheckResult(
        check_name="range",
        table=table,
        column=column,
        status=CheckStatus.PASS,
        message=f"Range [{actual_min}, {actual_max}] within bounds",
        value=f"[{actual_min}, {actual_max}]",
    )


def check_regex(conn: duckdb.DuckDBPyConnection, config: CheckConfig) -> CheckResult:
    table = config.table
    column = config.column
    pattern = str(config.params.get("pattern", ".*"))

    result = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN "{column}"::VARCHAR
                NOT SIMILAR TO $1 THEN 1 ELSE 0 END) AS mismatches
        FROM "{table}"
        WHERE "{column}" IS NOT NULL
        """,
        [pattern],
    ).fetchone()

    if result is None or result[0] == 0:
        return CheckResult(
            check_name="regex",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="No non-null rows to check",
        )

    total, mismatches = result
    return CheckResult(
        check_name="regex",
        table=table,
        column=column,
        status=CheckStatus.PASS if mismatches == 0 else CheckStatus.FAIL,
        message=f"{mismatches}/{total} rows do not match pattern",
        value=mismatches,
    )


def check_referential_integrity(
    conn: duckdb.DuckDBPyConnection, config: CheckConfig
) -> CheckResult:
    table = config.table
    column = config.column
    ref_table = str(config.params.get("ref_table", ""))
    ref_column = str(config.params.get("ref_column", column or ""))

    result = conn.execute(
        f"""
        SELECT COUNT(*) FROM "{table}"
        WHERE "{column}" IS NOT NULL
          AND "{column}" NOT IN (SELECT "{ref_column}" FROM "{ref_table}")
        """
    ).fetchone()

    if result is None:
        return CheckResult(
            check_name="referential_integrity",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="Could not check referential integrity",
        )

    orphans = result[0]
    return CheckResult(
        check_name="referential_integrity",
        table=table,
        column=column,
        status=CheckStatus.PASS if orphans == 0 else CheckStatus.FAIL,
        message=f"{orphans} orphaned rows",
        value=orphans,
    )


def check_freshness(
    conn: duckdb.DuckDBPyConnection, config: CheckConfig
) -> CheckResult:
    table = config.table
    column = config.column
    max_hours = _float_param(config.params, "max_hours", 24.0)

    result = conn.execute(
        f"""
        SELECT
            MAX("{column}")::TIMESTAMP AS latest,
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX("{column}")::TIMESTAMP)) / 3600
                AS hours_old
        FROM "{table}"
        """
    ).fetchone()

    if result is None or result[0] is None:
        return CheckResult(
            check_name="freshness",
            table=table,
            column=column,
            status=CheckStatus.ERROR,
            message="No timestamps found",
        )

    _, hours_old = result
    return CheckResult(
        check_name="freshness",
        table=table,
        column=column,
        status=CheckStatus.PASS if hours_old <= max_hours else CheckStatus.FAIL,
        message=f"Data is {hours_old:.1f} hours old (max {max_hours}h)",
        value=round(float(hours_old), 1),
        threshold=max_hours,
    )


def check_composite(
    conn: duckdb.DuckDBPyConnection, config: CheckConfig
) -> CheckResult:
    table = config.table
    sql = str(config.params.get("sql", ""))
    raw_expected = config.params.get("expected", 0)
    expected: float | int | str = (
        raw_expected if not isinstance(raw_expected, (bool, list)) else 0
    )

    result = conn.execute(sql).fetchone()
    if result is None:
        return CheckResult(
            check_name="composite",
            table=table,
            status=CheckStatus.ERROR,
            message="SQL returned no rows",
        )

    actual = result[0]
    return CheckResult(
        check_name="composite",
        table=table,
        status=CheckStatus.PASS if actual == expected else CheckStatus.FAIL,
        message=f"Got {actual}, expected {expected}",
        value=actual,
        threshold=expected,
    )


CHECKS: dict[
    str,
    Callable[[duckdb.DuckDBPyConnection, CheckConfig], CheckResult],
] = {
    "nulls": check_nulls,
    "duplicates": check_duplicates,
    "uniqueness": check_uniqueness,
    "range": check_range,
    "regex": check_regex,
    "referential_integrity": check_referential_integrity,
    "freshness": check_freshness,
    "composite": check_composite,
}
