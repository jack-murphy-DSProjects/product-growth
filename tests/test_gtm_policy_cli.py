from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

from test_gtm_policy_outputs import create_gtm_policy_tables

ROOT = Path(__file__).resolve().parents[1]


def test_build_gtm_policy_cli_writes_tables_and_optional_export(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    export_dir = tmp_path / "exports"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_gtm_policy.py",
            "--warehouse-path",
            str(database_path),
            "--scoring-month",
            "2024-02-01",
            "--export-dir",
            str(export_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "policy_version: gtm_policy_v1" in result.stdout
    assert "scoring_month: 2024-02-01" in result.stdout
    assert "output_policy_row_count: 2" in result.stdout
    assert "observability_status: not_used" in result.stdout
    assert "output_policy_table: mart.account_month_gtm_policy" in result.stdout
    assert "output_audit_table: metadata.gtm_policy_audit" in result.stdout
    assert "output_policy_export:" in result.stdout
    assert len(list(export_dir.glob("account_month_gtm_policy_2024_02_01_*.csv"))) == 1

    with duckdb.connect(str(database_path), read_only=True) as connection:
        policy_count = connection.execute(
            "SELECT COUNT(*) FROM mart.account_month_gtm_policy"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM metadata.gtm_policy_audit"
        ).fetchone()[0]

    assert policy_count == 2
    assert audit_count == 1


def test_build_gtm_policy_cli_requires_explicit_selector(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_gtm_policy.py",
            "--warehouse-path",
            str(tmp_path / "warehouse.duckdb"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--scoring-month" in result.stderr
    assert "--latest" in result.stderr


def test_makefile_gtm_policy_targets_invoke_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "build-gtm-policy:" in makefile_text
    assert "build-gtm-policy-latest:" in makefile_text
    assert "scripts/build_gtm_policy.py" in makefile_text
    assert "GTM_POLICY_EXPORT_DIR" in makefile_text


def test_makefile_build_gtm_policy_latest_is_explicit() -> None:
    result = subprocess.run(
        ["make", "-n", "build-gtm-policy-latest"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scripts/build_gtm_policy.py" in result.stdout
    assert "--latest" in result.stdout


def test_makefile_build_gtm_policy_latest_preserves_ambiguous_selectors() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "build-gtm-policy-latest",
            "SCORING_MONTH=2024-02-01",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '--scoring-month "2024-02-01"' in result.stdout
    assert "--latest" in result.stdout
