from __future__ import annotations

from pathlib import Path

import duckdb
import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd
import pytest

from account_health.modeling import (
    APPROVED_CATEGORICAL_FEATURES,
    APPROVED_NUMERIC_FEATURES,
    ModelingTrainingError,
    REQUIRED_METRIC_KEYS,
    SUPPORTED_CANDIDATE_MODELS,
    TARGET_COLUMNS,
    train_candidate_models,
)


def account_month_training_frame() -> pd.DataFrame:
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


def create_account_month_training_table(database_path: Path) -> None:
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.register("account_month_training_frame", account_month_training_frame())
        try:
            connection.execute(
                """
                CREATE TABLE mart.account_month AS
                SELECT * FROM account_month_training_frame
                """
            )
        finally:
            connection.unregister("account_month_training_frame")


def test_train_candidate_models_logs_expected_mlflow_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    tracking_dir = tmp_path / "mlruns"
    experiment_name = "package-5-test-experiment"
    create_account_month_training_table(database_path)

    def fail_if_registry_is_used(*args, **kwargs):
        raise AssertionError("Package 5 must not use MLflow registry APIs")

    monkeypatch.setattr(mlflow, "register_model", fail_if_registry_is_used)

    result = train_candidate_models(
        database_path=database_path,
        train_end_month="2024-02-01",
        experiment_name=experiment_name,
        mlflow_tracking_uri=str(tracking_dir),
        random_state=123,
    )

    assert result.experiment_name == experiment_name
    assert len(result.runs) == 4
    assert {
        (run.target, run.candidate_model) for run in result.runs
    } == {
        (target, candidate)
        for target in TARGET_COLUMNS
        for candidate in SUPPORTED_CANDIDATE_MODELS
    }

    client = MlflowClient(tracking_uri=str(tracking_dir))
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None

    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 4
    for run in runs:
        params = run.data.params
        metrics = run.data.metrics
        assert params["source_table"] == "mart.account_month"
        assert params["train_end_month"] == "2024-02-01"
        assert params["target"] in TARGET_COLUMNS
        assert params["candidate_model"] in SUPPORTED_CANDIDATE_MODELS
        assert int(params["feature_count"]) == (
            len(APPROVED_NUMERIC_FEATURES) + len(APPROVED_CATEGORICAL_FEATURES)
        )
        assert REQUIRED_METRIC_KEYS <= set(metrics)
        assert {"train_row_count", "test_row_count"} <= set(metrics)
        assert {"train_positive_rate", "test_positive_rate"} <= set(metrics)

        artifact_paths = {
            artifact.path for artifact in client.list_artifacts(run.info.run_id)
        }
        assert {"features.json", "split_config.json"} <= artifact_paths
        assert any(path.startswith("model") for path in artifact_paths)


def test_train_candidate_models_rejects_remote_mlflow_tracking_uri(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"

    with pytest.raises(ModelingTrainingError, match="must remain local"):
        train_candidate_models(
            database_path=database_path,
            mlflow_tracking_uri="https://example.com/mlflow",
        )


def test_train_candidate_models_rejects_inherited_remote_mlflow_tracking_uri(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"

    monkeypatch.setattr(
        mlflow,
        "get_tracking_uri",
        lambda: "https://example.com/mlflow",
    )

    with pytest.raises(ModelingTrainingError, match="must remain local"):
        train_candidate_models(database_path=database_path)
