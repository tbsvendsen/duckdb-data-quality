# duckdb-data-quality

Data quality checks for DuckDB databases. Simple API, real database tests, typed results.

## Quick start

```python
import duckdb
from duckdb_data_quality import check, validate_schema, report

conn = duckdb.connect()

results = check(conn, "orders", [
    {"check": "nulls", "column": "order_id", "threshold": 0},
    {"check": "uniqueness", "column": "order_id"},
    {"check": "range", "column": "amount", "min": 0, "max": 100000},
    {"check": "referential_integrity", "column": "customer_id",
     "ref_table": "customers", "ref_column": "id"},
])

html = report(results)
```

## Available checks

| Check | Description | Parameters |
|-------|-------------|------------|
| `nulls` | Null percentage per column | `threshold` (max % allowed) |
| `duplicates` | Duplicate rows | `columns` (list, optional) |
| `uniqueness` | Unique value percentage | — |
| `range` | Values within min/max bounds | `min`, `max` |
| `regex` | Pattern matching (DuckDB SIMILAR TO, regex syntax) | `pattern` |
| `referential_integrity` | Foreign key validation | `ref_table`, `ref_column` |
| `freshness` | Data not older than threshold | `max_hours` |
| `composite` | Custom SQL check | `sql`, `expected` |

## Schema validation

```python
result = validate_schema(conn, "orders", [
    {"column": "id", "dtype": "INTEGER"},
    {"column": "amount", "dtype": "DOUBLE"},
    {"column": "status", "dtype": "VARCHAR"},
])
```

## Install

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
pytest --cov
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions.

## License

MIT
