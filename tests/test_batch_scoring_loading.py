from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.scoring import (
    BatchScoringError,
    load_batch_scoring_inputs,
    load_scoring_population,
    validate_feature_metadata,
)
from account_health.scoring.loading import SCORING_SOURCE_TABLE
from account_health.registry import run_model_registry_promotion
from test_model_registry_loading import (
    champion_record,
    create_source_run,
    write_manifest,
)


def account_month_scoring_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-01-01"),
                "feature_1": 1.0,
            },
            {
                "account_id": "acct_two",
                "observation_month": pd.Timestamp("2024-02-01"),
                "feature_1": 2.0,
            },
            {
                "account_id": "acct_three",
                "observation_month": pd.Timestamp("2024-02-01"),
                "feature_1": 3.0,
            },
        ]
    )


def create_account_month_table(
    database_path: Path,
    frame: pd.DataFrame | None = None,
) -> None:
    frame = account_month_scoring_frame() if frame is None else frame
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
        connection.register("account_month_frame", frame)
        try:
            connection.execute(
                """
                CREATE OR REPLACE TABLE mart.account_month AS
                SELECT * FROM account_month_frame
                """
            )
        finally:
            connection.unregister("account_month_frame")


def create_promoted_scoring_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    tracking_dir, churn_run_id, churn_uri = create_source_run(
        tmp_path,
        target="churn_90d",
        candidate_model="logistic_regression",
        experiment_name="package-8-loading-test",
    )
    _, expansion_run_id, expansion_uri = create_source_run(
        tmp_path,
        target="expansion_90d",
        candidate_model="random_forest",
        experiment_name="package-8-loading-test",
    )
    champion_manifest_path = write_manifest(
        tmp_path / "champion_selection_manifest.json",
        [
            champion_record(run_id=churn_run_id, model_uri=churn_uri),
            champion_record(
                target="expansion_90d",
                model_family="random_forest",
                run_id=expansion_run_id,
                model_uri=expansion_uri,
            ),
        ],
    )
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)
    promotion_manifest_path = tmp_path / "promotion_manifest.json"
    run_model_registry_promotion(
        champion_manifest_path=champion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
        promotion_manifest_path=promotion_manifest_path,
        database_path=database_path,
    )
    return tracking_dir, promotion_manifest_path, database_path


def test_load_scoring_population_requires_explicit_selector(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    with pytest.raises(BatchScoringError, match="scoring-month|latest"):
        load_scoring_population(database_path)


def test_load_scoring_population_latest_selects_max_month_without_labels(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    population = load_scoring_population(database_path, latest=True)

    assert population.source_table == SCORING_SOURCE_TABLE
    assert population.selector == "latest"
    assert population.scoring_month == pd.Timestamp("2024-02-01")
    assert population.frame["account_id"].tolist() == ["acct_three", "acct_two"]
    assert "churn_90d" not in population.frame.columns
    assert "expansion_90d" not in population.frame.columns


def test_load_scoring_population_rejects_non_month_start(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    with pytest.raises(BatchScoringError, match="YYYY-MM-01"):
        load_scoring_population(database_path, scoring_month="2024-02-15")


def test_load_scoring_population_latest_rejects_non_month_start_source_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    frame = account_month_scoring_frame()
    frame.loc[frame["account_id"] == "acct_two", "observation_month"] = pd.Timestamp(
        "2024-02-15"
    )
    create_account_month_table(database_path, frame)

    with pytest.raises(BatchScoringError, match="latest observation_month"):
        load_scoring_population(database_path, latest=True)


def test_load_scoring_population_rejects_empty_selected_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    with pytest.raises(BatchScoringError, match="no rows"):
        load_scoring_population(database_path, scoring_month="2024-03-01")


def test_load_scoring_population_rejects_duplicate_account_month_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    frame = pd.concat(
        [account_month_scoring_frame(), account_month_scoring_frame().iloc[[0]]],
        ignore_index=True,
    )
    create_account_month_table(database_path, frame)

    with pytest.raises(BatchScoringError, match="duplicate account-month"):
        load_scoring_population(database_path, scoring_month="2024-01-01")


def test_load_scoring_population_rejects_null_account_id(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    frame = account_month_scoring_frame()
    frame.loc[frame["account_id"] == "acct_one", "account_id"] = None
    create_account_month_table(database_path, frame)

    with pytest.raises(BatchScoringError, match="null account_id"):
        load_scoring_population(database_path, scoring_month="2024-01-01")


def test_validate_feature_metadata_rejects_forbidden_features() -> None:
    with pytest.raises(BatchScoringError, match="churn_90d"):
        validate_feature_metadata(
            {
                "approved_features": ["churn_90d"],
                "numeric_features": ["churn_90d"],
                "categorical_features": [],
            },
            scoring_columns=("account_id", "observation_month", "churn_90d"),
            run_id="run_1",
        )


def test_load_batch_scoring_inputs_loads_champion_aliases_and_features(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )

    inputs = load_batch_scoring_inputs(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )

    assert inputs.population.frame["account_id"].tolist() == [
        "acct_three",
        "acct_two",
    ]
    assert inputs.churn_model.registered_model_name == "account_health_churn_model"
    assert inputs.expansion_model.registered_model_name == (
        "account_health_expansion_model"
    )
    assert inputs.churn_model.alias == "champion"
    assert inputs.expansion_model.alias == "champion"
    assert inputs.churn_model.approved_features == ("feature_1",)
    assert inputs.expansion_model.approved_features == ("feature_1",)
    assert hasattr(inputs.churn_model.model, "predict_proba")
    assert hasattr(inputs.expansion_model.model, "predict_proba")
    assert str(promotion_manifest_path) in inputs.promotion_evidence_sources
    assert "metadata.model_promotion_audit" in inputs.promotion_evidence_sources


def test_load_batch_scoring_inputs_rejects_missing_scoring_feature(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    create_account_month_table(
        database_path,
        account_month_scoring_frame().drop(columns=["feature_1"]),
    )

    with pytest.raises(BatchScoringError, match="feature_1"):
        load_batch_scoring_inputs(
            database_path,
            scoring_month="2024-02-01",
            promotion_manifest_path=promotion_manifest_path,
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_batch_scoring_inputs_rejects_manifest_alias_mismatch(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    records = json.loads(promotion_manifest_path.read_text(encoding="utf-8"))
    records[0]["model_version"] = "999"
    promotion_manifest_path.write_text(json.dumps(records), encoding="utf-8")

    with pytest.raises(BatchScoringError, match="disagrees"):
        load_batch_scoring_inputs(
            database_path,
            scoring_month="2024-02-01",
            promotion_manifest_path=promotion_manifest_path,
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_batch_scoring_inputs_rejects_remote_mlflow_uri(tmp_path: Path) -> None:
    _, promotion_manifest_path, database_path = create_promoted_scoring_inputs(tmp_path)

    with pytest.raises(BatchScoringError, match="must remain local"):
        load_batch_scoring_inputs(
            database_path,
            scoring_month="2024-02-01",
            promotion_manifest_path=promotion_manifest_path,
            mlflow_tracking_uri="https://example.com/mlflow",
        )
