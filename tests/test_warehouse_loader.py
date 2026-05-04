from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.synthetic import SOURCE_TABLES, generate_synthetic_source_data
from account_health.warehouse import SourceContractError, load_source_csvs_to_warehouse

ROOT = Path(__file__).resolve().parents[1]


def write_generated_csvs(source_dir: Path) -> dict[str, pd.DataFrame]:
    source_dir.mkdir()
    tables = generate_synthetic_source_data(seed=202, n_accounts=8)
    for table_name, frame in tables.items():
        frame.to_csv(source_dir / f"{table_name}.csv", index=False)
    return tables


def raw_table_names(database_path: Path) -> set[str]:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'raw'
            """
        ).fetchall()
    return {row[0] for row in rows}


def table_row_count(database_path: Path, schema: str, table: str) -> int:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return int(
            connection.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        )


def test_load_source_csvs_creates_raw_tables_and_audit(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    source_tables = write_generated_csvs(source_dir)

    result = load_source_csvs_to_warehouse(
        source_dir=source_dir,
        database_path=database_path,
    )

    assert database_path.is_file()
    assert result.source_dir == source_dir
    assert result.database_path == database_path
    assert tuple(result.table_row_counts) == SOURCE_TABLES
    assert raw_table_names(database_path) == set(SOURCE_TABLES)

    for table_name in SOURCE_TABLES:
        assert result.table_row_counts[table_name] == len(source_tables[table_name])
        assert table_row_count(database_path, "raw", table_name) == len(
            source_tables[table_name]
        )

    assert table_row_count(database_path, "metadata", "load_audit") == len(SOURCE_TABLES)


def test_load_warehouse_cli_uses_explicit_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    write_generated_csvs(source_dir)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/load_warehouse.py",
            "--source-dir",
            str(source_dir),
            "--database-path",
            str(database_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "raw.accounts:" in result.stdout
    assert database_path.is_file()
    assert raw_table_names(database_path) == set(SOURCE_TABLES)


def test_missing_required_source_file_fails_clearly(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    write_generated_csvs(source_dir)
    (source_dir / "accounts.csv").unlink()

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert [validation.check_name for validation in error.value.errors] == [
        "required_file"
    ]
    assert "missing required source file: accounts.csv" in str(error.value)
    assert not database_path.exists()


def test_missing_required_column_fails_clearly(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    accounts = tables["accounts"].drop(columns=["account_name"])
    accounts.to_csv(source_dir / "accounts.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "accounts"
    assert error.value.errors[0].check_name == "required_columns"
    assert "accounts.csv is missing required column(s): account_name" in str(
        error.value
    )
    assert not database_path.exists()


def test_empty_required_source_table_fails_clearly(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    tables["accounts"].head(0).to_csv(source_dir / "accounts.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "accounts"
    assert error.value.errors[0].check_name == "non_empty"
    assert "accounts.csv must contain at least one row" in str(error.value)
    assert not database_path.exists()


def test_duplicate_primary_key_fails_validation(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    accounts = tables["accounts"].copy()
    accounts.loc[1, "account_id"] = accounts.loc[0, "account_id"]
    accounts.to_csv(source_dir / "accounts.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "accounts"
    assert error.value.errors[0].check_name == "primary_key"
    assert "accounts.account_id must be unique" in str(error.value)
    assert not database_path.exists()


def test_broken_foreign_key_fails_validation(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    users = tables["users"].copy()
    users.loc[0, "account_id"] = "acct_missing"
    users.to_csv(source_dir / "users.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "users"
    assert error.value.errors[0].check_name == "foreign_key"
    assert "users.account_id has value(s) not found in accounts.account_id" in str(
        error.value
    )
    assert not database_path.exists()


def test_invalid_date_value_fails_validation(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    accounts = tables["accounts"].copy()
    accounts["created_date"] = accounts["created_date"].astype(str)
    accounts.loc[0, "created_date"] = "not-a-date"
    accounts.to_csv(source_dir / "accounts.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "accounts"
    assert error.value.errors[0].check_name == "date_parse"
    assert "accounts.created_date contains 1 invalid date value(s)" in str(
        error.value
    )
    assert not database_path.exists()


def test_invalid_date_order_fails_validation(tmp_path: Path) -> None:
    source_dir = tmp_path / "generated"
    database_path = tmp_path / "warehouse" / "account_health.duckdb"
    tables = write_generated_csvs(source_dir)
    invoices = tables["invoices"].copy()
    invoices.loc[0, "due_date"] = pd.Timestamp(invoices.loc[0, "invoice_date"]) - (
        pd.Timedelta(days=1)
    )
    invoices.to_csv(source_dir / "invoices.csv", index=False)

    with pytest.raises(SourceContractError) as error:
        load_source_csvs_to_warehouse(source_dir=source_dir, database_path=database_path)

    assert error.value.errors[0].table_name == "invoices"
    assert error.value.errors[0].check_name == "date_order"
    assert "invoices.due_date must be on or after invoices.invoice_date" in str(
        error.value
    )
    assert not database_path.exists()
