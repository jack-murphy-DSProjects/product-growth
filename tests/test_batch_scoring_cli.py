from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

from test_batch_scoring_loading import create_promoted_scoring_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_score_account_month_cli_writes_tables_and_optional_export(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    export_dir = tmp_path / "exports"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/score_account_month.py",
            "--warehouse-path",
            str(database_path),
            "--scoring-month",
            "2024-02-01",
            "--promotion-manifest-path",
            str(promotion_manifest_path),
            "--mlflow-tracking-uri",
            str(tracking_dir),
            "--mlflow-registry-uri",
            str(tracking_dir),
            "--export-dir",
            str(export_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scoring_version: package_8_batch_scoring_v1" in result.stdout
    assert "scoring_month: 2024-02-01" in result.stdout
    assert "row_count_written: 2" in result.stdout
    assert "output_score_table: mart.account_month_scores" in result.stdout
    assert "output_audit_table: metadata.batch_scoring_audit" in result.stdout
    assert "output_score_export:" in result.stdout
    assert len(list(export_dir.glob("account_month_scores_2024_02_01_*.csv"))) == 1

    with duckdb.connect(str(database_path), read_only=True) as connection:
        score_count = connection.execute(
            "SELECT COUNT(*) FROM mart.account_month_scores"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM metadata.batch_scoring_audit"
        ).fetchone()[0]

    assert score_count == 2
    assert audit_count == 1


def test_score_account_month_cli_requires_explicit_selector(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/score_account_month.py",
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


def test_makefile_score_account_month_target_invokes_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "score-account-month:" in makefile_text
    assert "scripts/score_account_month.py" in makefile_text
    assert "SCORING_MONTH" in makefile_text
    assert "BATCH_SCORING_LATEST" in makefile_text
    assert "BATCH_SCORING_EXPORT_DIR" in makefile_text


def test_makefile_score_account_month_preserves_ambiguous_selectors() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "score-account-month",
            "SCORING_MONTH=2024-02-01",
            "BATCH_SCORING_LATEST=1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '--scoring-month "2024-02-01"' in result.stdout
    assert "--latest" in result.stdout
