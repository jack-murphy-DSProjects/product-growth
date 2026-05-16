from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

from test_score_observability_loading import create_score_observability_tables

ROOT = Path(__file__).resolve().parents[1]


def test_monitor_account_scores_cli_writes_tables_and_optional_exports(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)
    export_dir = tmp_path / "exports"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/monitor_account_scores.py",
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
    assert "observability_version: package_9_score_observability_v1" in result.stdout
    assert "scoring_month: 2024-02-01" in result.stdout
    assert "status: success_with_warnings" in result.stdout
    assert "output_summary_table: mart.score_observability_summary" in result.stdout
    assert "output_audit_table: metadata.score_observability_audit" in result.stdout
    assert len(list(export_dir.glob("score_observability_summary_*.csv"))) == 1
    assert len(list(export_dir.glob("score_distribution_by_month_*.csv"))) == 1
    assert len(list(export_dir.glob("score_distribution_by_segment_*.csv"))) == 1
    assert len(list(export_dir.glob("scoring_lineage_summary_*.csv"))) == 1

    with duckdb.connect(str(database_path), read_only=True) as connection:
        summary_count = connection.execute(
            "SELECT COUNT(*) FROM mart.score_observability_summary"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM metadata.score_observability_audit"
        ).fetchone()[0]

    assert summary_count == 1
    assert audit_count == 1


def test_monitor_account_scores_cli_requires_explicit_selector(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/monitor_account_scores.py",
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


def test_monitor_account_scores_cli_rejects_ambiguous_selectors(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/monitor_account_scores.py",
            "--warehouse-path",
            str(tmp_path / "warehouse.duckdb"),
            "--scoring-month",
            "2024-02-01",
            "--latest",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "--latest" in result.stderr
    assert "--scoring-month" in result.stderr


def test_makefile_score_observability_targets_invoke_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "monitor-account-scores:" in makefile_text
    assert "monitor-account-scores-latest:" in makefile_text
    assert "scripts/monitor_account_scores.py" in makefile_text
    assert "SCORE_OBSERVABILITY_EXPORT_DIR" in makefile_text


def test_makefile_monitor_account_scores_latest_is_explicit() -> None:
    result = subprocess.run(
        ["make", "-n", "monitor-account-scores-latest"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scripts/monitor_account_scores.py" in result.stdout
    assert "--latest" in result.stdout


def test_makefile_monitor_account_scores_latest_preserves_ambiguous_selectors() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "monitor-account-scores-latest",
            "SCORING_MONTH=2024-02-01",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '--scoring-month "2024-02-01"' in result.stdout
    assert "--latest" in result.stdout
