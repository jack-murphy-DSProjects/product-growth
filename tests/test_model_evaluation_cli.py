from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb

from test_model_evaluation_loading import prepare_package_6_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_evaluate_candidate_models_cli_writes_outputs_and_tables(
    tmp_path: Path,
) -> None:
    database_path, tracking_dir, experiment_name = prepare_package_6_inputs(
        tmp_path,
        experiment_name="package-6-cli-test",
    )
    output_dir = tmp_path / "evaluation_outputs"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_candidate_models.py",
            "--warehouse-path",
            str(database_path),
            "--experiment-name",
            experiment_name,
            "--mlflow-tracking-uri",
            str(tracking_dir),
            "--train-end-month",
            "2024-02-01",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "metric_count:" in result.stdout
    assert "champion_count: 2" in result.stdout
    assert (output_dir / "evaluation_summary.json").exists()
    assert (output_dir / "champion_selection_manifest.json").exists()
    assert (output_dir / "evaluation_report.md").exists()

    with duckdb.connect(str(database_path), read_only=True) as connection:
        mart_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'mart'
                """
            ).fetchall()
        }
        summary_count = connection.execute(
            "SELECT COUNT(*) FROM mart.model_evaluation_summary"
        ).fetchone()[0]
        champion_count = connection.execute(
            "SELECT COUNT(*) FROM mart.model_champion_selection"
        ).fetchone()[0]

    assert {
        "model_evaluation_summary",
        "model_champion_selection",
    } <= mart_tables
    assert "account_health_band" not in mart_tables
    assert "recommended_gtm_action" not in mart_tables
    assert summary_count > 0
    assert champion_count == 2


def test_makefile_evaluate_candidate_models_target_invokes_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "evaluate-candidate-models:" in makefile_text
    assert "scripts/evaluate_candidate_models.py" in makefile_text
    assert "EVALUATION_OUTPUT_DIR" in makefile_text
