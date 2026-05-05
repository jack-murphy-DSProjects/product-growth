from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
from mlflow.tracking import MlflowClient
import pandas as pd

from account_health.modeling import (
    APPROVED_CATEGORICAL_FEATURES,
    APPROVED_NUMERIC_FEATURES,
)

ROOT = Path(__file__).resolve().parents[1]


def cli_training_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month_index, month in enumerate(
        pd.date_range("2024-01-01", "2024-05-01", freq="MS"),
        start=1,
    ):
        for label in (0, 1):
            row: dict[str, object] = {
                "account_id": f"acct_{month:%Y_%m}_{label}",
                "observation_month": month,
                "observation_month_end": month + pd.offsets.MonthEnd(0),
                "is_churn_label_eligible": True,
                "is_expansion_label_eligible": True,
                "churn_90d": label,
                "expansion_90d": 1 - label,
            }
            for feature in APPROVED_CATEGORICAL_FEATURES:
                row[feature] = f"{feature}_value_{label}"
            for feature in APPROVED_NUMERIC_FEATURES:
                row[feature] = float(month_index * 10 + label)
            rows.append(row)
    return pd.DataFrame(rows)


def create_cli_training_table(database_path: Path) -> None:
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.register("cli_training_frame", cli_training_frame())
        try:
            connection.execute(
                """
                CREATE TABLE mart.account_month AS
                SELECT * FROM cli_training_frame
                """
            )
        finally:
            connection.unregister("cli_training_frame")


def test_train_candidate_models_cli_accepts_paths_and_mlflow_arguments(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    tracking_dir = tmp_path / "mlruns"
    experiment_name = "package-5-cli-test"
    create_cli_training_table(database_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/train_candidate_models.py",
            "--warehouse-path",
            str(database_path),
            "--train-end-month",
            "2024-02-01",
            "--experiment-name",
            experiment_name,
            "--mlflow-tracking-uri",
            str(tracking_dir),
            "--random-state",
            "17",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"experiment_name: {experiment_name}" in result.stdout
    assert f"mlflow_tracking_uri: {tracking_dir}" in result.stdout
    assert "run_count: 4" in result.stdout

    client = MlflowClient(tracking_uri=str(tracking_dir))
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None
    assert len(client.search_runs([experiment.experiment_id])) == 4

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

    assert mart_tables == {"account_month"}


def test_makefile_train_candidate_models_target_invokes_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "train-candidate-models:" in makefile_text
    assert "scripts/train_candidate_models.py" in makefile_text
