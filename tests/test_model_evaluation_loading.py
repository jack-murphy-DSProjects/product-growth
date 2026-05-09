from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import mlflow
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient

from account_health.baselines import build_account_month_baselines
from account_health.evaluation import (
    EvaluationInputError,
    load_evaluation_inputs,
    validate_local_mlflow_tracking_uri,
)
from account_health.evaluation.loading import local_path_from_file_uri
from account_health.modeling import (
    APPROVED_CATEGORICAL_FEATURES,
    APPROVED_NUMERIC_FEATURES,
    SUPPORTED_CANDIDATE_MODELS,
    TARGET_COLUMNS,
    train_candidate_models,
)


def package_6_account_month_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month_index, month in enumerate(
        pd.date_range("2024-01-01", "2024-05-01", freq="MS"),
        start=1,
    ):
        for label in (0, 1):
            account_id = f"acct_{month:%Y_%m}_{label}"
            row: dict[str, object] = {
                "account_id": account_id,
                "observation_month": month,
                "observation_month_end": month + pd.offsets.MonthEnd(0),
                "is_churn_label_eligible": True,
                "is_expansion_label_eligible": True,
                "churn_90d": label,
                "expansion_90d": 1 - label,
                "account_created_date": pd.Timestamp("2023-01-01"),
                "account_age_days": 365 + month_index,
                "industry": "software" if label else "financial_services",
                "region": "north_america" if label else "europe",
                "segment": "enterprise" if label else "smb",
                "company_size_band": "1001_5000" if label else "1_50",
                "acquisition_channel": "partner" if label else "inbound",
                "current_plan": "enterprise" if label else "starter",
                "current_mrr": float(5000 if label else 250),
                "current_billing_period": "annual" if label else "monthly",
                "subscription_age_days": 240 + month_index,
                "usage_event_count_30d": 100 + label,
                "usage_event_count_90d": 300 + label,
                "usage_event_count_180d": 600 + label,
                "active_user_count_30d": 20 + label,
                "active_user_count_90d": 40 + label,
                "active_user_count_180d": 80 + label,
                "usage_event_value_sum_90d": 750.0 + label,
                "support_ticket_count_30d": label,
                "support_ticket_count_90d": label,
                "support_ticket_count_180d": label,
                "high_priority_ticket_count_90d": 0,
                "open_ticket_count": 0,
                "avg_resolution_hours_known": 8.0,
                "days_since_last_ticket": 30,
                "invoice_count_90d": 3,
                "invoice_count_180d": 6,
                "invoice_amount_sum_90d": float(15000 if label else 750),
                "invoice_amount_sum_180d": float(30000 if label else 1500),
                "unpaid_invoice_count_90d": 0,
                "failed_invoice_count_90d": 0,
                "overdue_invoice_count": 0,
                "avg_payment_delay_days_known": 2.0,
                "days_since_last_invoice": 10,
                "crm_touchpoint_count_30d": 2,
                "crm_touchpoint_count_90d": 5,
                "crm_touchpoint_count_180d": 8,
                "sales_touchpoint_count_90d": 2,
                "cs_touchpoint_count_90d": 3,
                "days_since_last_crm_touchpoint": 5,
            }
            for feature in APPROVED_NUMERIC_FEATURES:
                row.setdefault(feature, float(month_index * 10 + label))
            for feature in APPROVED_CATEGORICAL_FEATURES:
                row.setdefault(feature, f"{feature}_value_{label}")
            rows.append(row)
    return pd.DataFrame(rows)


def create_package_6_account_month_table(database_path: Path) -> None:
    frame = package_6_account_month_frame()
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.register("account_month_frame", frame)
        try:
            connection.execute(
                """
                CREATE TABLE mart.account_month AS
                SELECT * FROM account_month_frame
                """
            )
        finally:
            connection.unregister("account_month_frame")


def prepare_package_6_inputs(
    tmp_path: Path,
    *,
    experiment_name: str = "package-6-loading-test",
) -> tuple[Path, Path, str]:
    database_path = tmp_path / "warehouse.duckdb"
    tracking_dir = tmp_path / "mlruns"
    create_package_6_account_month_table(database_path)
    build_account_month_baselines(database_path)
    train_candidate_models(
        database_path=database_path,
        train_end_month="2024-02-01",
        experiment_name=experiment_name,
        mlflow_tracking_uri=str(tracking_dir),
        random_state=17,
    )
    return database_path, tracking_dir, experiment_name


def test_load_evaluation_inputs_discovers_local_package_5_candidates(
    tmp_path: Path,
) -> None:
    database_path, tracking_dir, experiment_name = prepare_package_6_inputs(tmp_path)

    inputs = load_evaluation_inputs(
        database_path,
        experiment_name=experiment_name,
        mlflow_tracking_uri=str(tracking_dir),
    )

    assert inputs.experiment_name == experiment_name
    assert inputs.train_end_month == pd.Timestamp("2024-02-01")
    assert len(inputs.account_month) == 10
    assert len(inputs.baselines) == 10
    assert {
        (candidate.target, candidate.candidate_model)
        for candidate in inputs.candidates
    } == {
        (target, candidate)
        for target in TARGET_COLUMNS
        for candidate in SUPPORTED_CANDIDATE_MODELS
    }
    for candidate in inputs.candidates:
        assert candidate.model_artifact_uri == f"runs:/{candidate.run_id}/model"
        assert candidate.approved_features == candidate.feature_names
        assert hasattr(candidate.model, "predict_proba")


def test_load_evaluation_inputs_rejects_remote_mlflow_tracking_uri() -> None:
    with pytest.raises(EvaluationInputError, match="must remain local"):
        validate_local_mlflow_tracking_uri("https://example.com/mlflow")


def test_load_evaluation_inputs_rejects_inherited_remote_tracking_uri(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    monkeypatch.setattr(mlflow, "get_tracking_uri", lambda: "https://remote/mlflow")

    with pytest.raises(EvaluationInputError, match="must remain local"):
        load_evaluation_inputs(database_path)


def test_load_evaluation_inputs_fails_when_expected_runs_are_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    tracking_dir = tmp_path / "mlruns"
    experiment_name = "package-6-missing-runs-test"
    create_package_6_account_month_table(database_path)
    build_account_month_baselines(database_path)

    with pytest.raises(EvaluationInputError, match="MLflow experiment"):
        load_evaluation_inputs(
            database_path,
            experiment_name=experiment_name,
            mlflow_tracking_uri=str(tracking_dir),
        )


def test_load_evaluation_inputs_fails_when_model_artifact_is_missing(
    tmp_path: Path,
) -> None:
    database_path, tracking_dir, experiment_name = prepare_package_6_inputs(
        tmp_path,
        experiment_name="package-6-missing-model-test",
    )
    client = MlflowClient(tracking_uri=str(tracking_dir))
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None
    run = client.search_runs(
        [experiment.experiment_id],
        filter_string=(
            "params.target = 'churn_90d' and "
            "params.candidate_model = 'logistic_regression'"
        ),
    )[0]
    artifact_root = local_path_from_file_uri(run.info.artifact_uri)
    shutil.rmtree(artifact_root / "model")

    with pytest.raises(EvaluationInputError, match="model artefact"):
        load_evaluation_inputs(
            database_path,
            experiment_name=experiment_name,
            mlflow_tracking_uri=str(tracking_dir),
        )


def test_load_evaluation_inputs_rejects_split_metadata_row_mismatch(
    tmp_path: Path,
) -> None:
    database_path, tracking_dir, experiment_name = prepare_package_6_inputs(
        tmp_path,
        experiment_name="package-6-split-metadata-mismatch-test",
    )
    client = MlflowClient(tracking_uri=str(tracking_dir))
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None
    run = client.search_runs(
        [experiment.experiment_id],
        filter_string=(
            "params.target = 'churn_90d' and "
            "params.candidate_model = 'logistic_regression'"
        ),
    )[0]
    artifact_root = local_path_from_file_uri(run.info.artifact_uri)
    split_config_path = artifact_root / "split_config.json"
    split_config = json.loads(split_config_path.read_text(encoding="utf-8"))
    split_config["test_row_count"] = split_config["test_row_count"] + 1
    split_config_path.write_text(
        json.dumps(split_config),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationInputError, match="eligible split rows"):
        load_evaluation_inputs(
            database_path,
            experiment_name=experiment_name,
            mlflow_tracking_uri=str(tracking_dir),
        )
