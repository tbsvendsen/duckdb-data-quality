"""Public API: check, validate_schema, report."""

from __future__ import annotations

from typing import Any

import duckdb

from duckdb_data_quality.checks import CHECKS
from duckdb_data_quality.models import (
    CheckConfig,
    CheckResult,
    CheckStatus,
    SchemaExpectation,
)


def check(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    checks: list[dict[str, Any]],
) -> list[CheckResult]:
    results: list[CheckResult] = []

    for check_spec in checks:
        check_name = check_spec["check"]
        check_fn_obj = CHECKS.get(check_name)
        if check_fn_obj is None:
            results.append(
                CheckResult(
                    check_name=check_name,
                    table=table,
                    status=CheckStatus.ERROR,
                    message=f"Unknown check: {check_name}",
                )
            )
            continue

        check_fn = check_fn_obj

        config = CheckConfig(
            check_name=check_name,
            table=table,
            column=check_spec.get("column"),
            params={
                k: v for k, v in check_spec.items() if k not in ("check", "column")
            },
        )

        try:
            result = check_fn(conn, config)
        except Exception as e:
            result = CheckResult(
                check_name=check_name,
                table=table,
                column=config.column,
                status=CheckStatus.ERROR,
                message=str(e),
            )

        results.append(result)

    return results


def validate_schema(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    expected: list[dict[str, Any]],
) -> CheckResult:
    expectations = [SchemaExpectation(**e) for e in expected]

    try:
        actual_schema = conn.execute(f'DESCRIBE "{table}"').fetchall()
    except duckdb.CatalogException:
        return CheckResult(
            check_name="schema",
            table=table,
            status=CheckStatus.ERROR,
            message=f"Table '{table}' does not exist",
        )

    actual_cols = {row[0]: row[1] for row in actual_schema}
    issues: list[str] = []

    for exp in expectations:
        if exp.column not in actual_cols:
            issues.append(f"missing column: {exp.column}")
            continue

        actual_type = actual_cols[exp.column].upper()
        expected_type = exp.dtype.upper()

        if actual_type != expected_type:
            issues.append(f"{exp.column}: expected {expected_type}, got {actual_type}")

    return CheckResult(
        check_name="schema",
        table=table,
        status=CheckStatus.PASS if not issues else CheckStatus.FAIL,
        message="; ".join(issues) if issues else "Schema matches",
    )


def report(results: list[CheckResult]) -> str:
    lines = [
        "<html><head><style>",
        "body { font-family: system-ui; margin: 2rem; }",
        "table { border-collapse: collapse; width: 100%; }",
        "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
        "th { background: #f5f5f5; }",
        ".pass { color: #22863a; }",
        ".fail { color: #cb2431; }",
        ".error { color: #e36209; }",
        "</style></head><body>",
        "<h1>Data Quality Report</h1>",
        "<table>",
        "<tr><th>Check</th><th>Table</th><th>Column</th>"
        "<th>Status</th><th>Message</th></tr>",
    ]

    for r in results:
        css = r.status.value
        lines.append(
            f"<tr><td>{r.check_name}</td><td>{r.table}</td>"
            f"<td>{r.column or '-'}</td>"
            f'<td class="{css}">{r.status.value.upper()}</td>'
            f"<td>{r.message}</td></tr>"
        )

    total = len(results)
    passed = sum(1 for r in results if r.status == CheckStatus.PASS)
    failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
    errors = sum(1 for r in results if r.status == CheckStatus.ERROR)

    lines.extend(
        [
            "</table>",
            f"<p>Total: {total} | "
            f'<span class="pass">Pass: {passed}</span> | '
            f'<span class="fail">Fail: {failed}</span> | '
            f'<span class="error">Error: {errors}</span></p>',
            "</body></html>",
        ]
    )

    return "\n".join(lines)
