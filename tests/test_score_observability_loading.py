from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.observability import (
    ScoreObservabilityError,
    load_score_observability_inputs,
)


def account_month_observability_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-01-01"),
                "churn_90d": 0,
                "expansion_90d": 1,
                "current_plan": "starter",
                "company_size_band": "1_50",
                "region": "europe",
                "industry": "software",
                "segment": "smb",
            },
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-02-01"),
                "churn_90d": 0,
                "expansion_90d": 1,
                "current_plan": "starter",
                "company_size_band": "1_50",
                "region": "europe",
                "industry": "software",
                "segment": "smb",
            },
            {
                "account_id": "acct_two",
                "observation_month": pd.Timestamp("2024-02-01"),
                "churn_90d": 1,
                "expansion_90d": None,
                "current_plan": "business",
                "company_size_band": "51_200",
                "region": "north_america",
                "industry": "retail",
                "segment": "mid_market",
            },
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-03-01"),
                "churn_90d": 0,
                "expansion_90d": 0,
                "current_plan": "business",
                "company_size_band": "1_50",
                "region": "europe",
                "industry": "software",
                "segment": "smb",
            },
        ]
    )


def score_observability_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scoring_run_id": "run_jan",
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-01-01"),
                "churn_score": 0.10,
                "expansion_score": 0.80,
                "churn_registered_model_name": "account_health_churn_model",
                "churn_model_version": "1",
                "expansion_registered_model_name": "account_health_expansion_model",
                "expansion_model_version": "2",
                "scored_at_utc": "2024-02-01T00:00:00+00:00",
                "scoring_version": "package_8_batch_scoring_v1",
            },
            {
                "scoring_run_id": "run_feb",
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-02-01"),
                "churn_score": 0.20,
                "expansion_score": 0.70,
                "churn_registered_model_name": "account_health_churn_model",
                "churn_model_version": "1",
                "expansion_registered_model_name": "account_health_expansion_model",
                "expansion_model_version": "2",
                "scored_at_utc": "2024-03-01T00:00:00+00:00",
                "scoring_version": "package_8_batch_scoring_v1",
            },
            {
                "scoring_run_id": "run_feb",
                "account_id": "acct_two",
                "observation_month": pd.Timestamp("2024-02-01"),
                "churn_score": 0.40,
                "expansion_score": 0.60,
                "churn_registered_model_name": "account_health_churn_model",
                "churn_model_version": "1",
                "expansion_registered_model_name": "account_health_expansion_model",
                "expansion_model_version": "2",
                "scored_at_utc": "2024-03-01T00:00:00+00:00",
                "scoring_version": "package_8_batch_scoring_v1",
            },
        ]
    )


def batch_scoring_audit_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scoring_run_id": "run_jan",
                "scored_at_utc": "2024-02-01T00:00:00+00:00",
                "scoring_version": "package_8_batch_scoring_v1",
                "scoring_month": pd.Timestamp("2024-01-01"),
                "selector": "scoring_month",
                "row_count_read": 1,
                "row_count_written": 1,
                "churn_registered_model_name": "account_health_churn_model",
                "churn_model_version": "1",
                "churn_source_mlflow_run_id": "churn_source_run",
                "churn_feature_metadata_artifact": "features.json",
                "expansion_registered_model_name": "account_health_expansion_model",
                "expansion_model_version": "2",
                "expansion_source_mlflow_run_id": "expansion_source_run",
                "expansion_feature_metadata_artifact": "features.json",
                "promotion_evidence_sources_json": "[]",
                "status": "success",
                "failure_reason": None,
            },
            {
                "scoring_run_id": "run_feb",
                "scored_at_utc": "2024-03-01T00:00:00+00:00",
                "scoring_version": "package_8_batch_scoring_v1",
                "scoring_month": pd.Timestamp("2024-02-01"),
                "selector": "scoring_month",
                "row_count_read": 2,
                "row_count_written": 2,
                "churn_registered_model_name": "account_health_churn_model",
                "churn_model_version": "1",
                "churn_source_mlflow_run_id": "churn_source_run",
                "churn_feature_metadata_artifact": "features.json",
                "expansion_registered_model_name": "account_health_expansion_model",
                "expansion_model_version": "2",
                "expansion_source_mlflow_run_id": "expansion_source_run",
                "expansion_feature_metadata_artifact": "features.json",
                "promotion_evidence_sources_json": "[]",
                "status": "success",
                "failure_reason": None,
            },
        ]
    )


def create_score_observability_tables(
    database_path: Path,
    *,
    account_month_frame: pd.DataFrame | None = None,
    score_frame: pd.DataFrame | None = None,
    audit_frame: pd.DataFrame | None = None,
) -> None:
    account_month_frame = (
        account_month_observability_frame()
        if account_month_frame is None
        else account_month_frame
    )
    score_frame = score_observability_frame() if score_frame is None else score_frame
    audit_frame = batch_scoring_audit_frame() if audit_frame is None else audit_frame
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
        connection.execute("CREATE SCHEMA IF NOT EXISTS metadata")
        for name, frame in (
            ("account_month_frame", account_month_frame),
            ("score_frame", score_frame),
            ("audit_frame", audit_frame),
        ):
            connection.register(name, frame)
        try:
            connection.execute(
                """
                CREATE OR REPLACE TABLE mart.account_month AS
                SELECT * FROM account_month_frame
                """
            )
            connection.execute(
                """
                CREATE OR REPLACE TABLE mart.account_month_scores AS
                SELECT * FROM score_frame
                """
            )
            connection.execute(
                """
                CREATE OR REPLACE TABLE metadata.batch_scoring_audit AS
                SELECT * FROM audit_frame
                """
            )
        finally:
            connection.unregister("account_month_frame")
            connection.unregister("score_frame")
            connection.unregister("audit_frame")


def test_load_score_observability_inputs_requires_explicit_selector(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    with pytest.raises(ScoreObservabilityError, match="scoring-month|latest"):
        load_score_observability_inputs(database_path)


def test_load_score_observability_inputs_latest_uses_latest_scored_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    inputs = load_score_observability_inputs(database_path, latest=True)

    assert inputs.selector == "latest"
    assert inputs.scoring_month == pd.Timestamp("2024-02-01")
    assert inputs.expected_account_count == 2
    assert inputs.scored_account_count == 2
    assert inputs.prior_scoring_month == pd.Timestamp("2024-01-01")
    assert inputs.prior_score_frame is not None
    assert inputs.prior_score_frame["account_id"].tolist() == ["acct_one"]
    assert inputs.score_frame["account_id"].tolist() == ["acct_one", "acct_two"]
    assert "churn_90d" not in inputs.expected_population_frame.columns
    assert "expansion_90d" not in inputs.expected_population_frame.columns


def test_load_score_observability_inputs_rejects_non_month_start(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    with pytest.raises(ScoreObservabilityError, match="YYYY-MM-01"):
        load_score_observability_inputs(database_path, scoring_month="2024-02-15")


def test_load_score_observability_inputs_rejects_missing_required_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.register("account_month_frame", account_month_observability_frame())
        connection.execute(
            """
            CREATE TABLE mart.account_month AS
            SELECT * FROM account_month_frame
            """
        )
        connection.unregister("account_month_frame")

    with pytest.raises(ScoreObservabilityError, match="mart.account_month_scores"):
        load_score_observability_inputs(database_path, scoring_month="2024-02-01")


def test_load_score_observability_inputs_rejects_empty_selected_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    with pytest.raises(ScoreObservabilityError, match="no score rows"):
        load_score_observability_inputs(database_path, scoring_month="2024-03-01")


def test_load_score_observability_inputs_rejects_duplicate_score_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    duplicate_scores = pd.concat(
        [score_observability_frame(), score_observability_frame().iloc[[1]]],
        ignore_index=True,
    )
    create_score_observability_tables(database_path, score_frame=duplicate_scores)

    with pytest.raises(ScoreObservabilityError, match="duplicate account/month"):
        load_score_observability_inputs(database_path, scoring_month="2024-02-01")


def test_load_score_observability_inputs_rejects_null_score_account_id(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = score_observability_frame()
    scores.loc[scores["account_id"] == "acct_two", "account_id"] = None
    create_score_observability_tables(database_path, score_frame=scores)

    with pytest.raises(ScoreObservabilityError, match="null account_id"):
        load_score_observability_inputs(database_path, scoring_month="2024-02-01")


def test_load_score_observability_inputs_rejects_expected_population_mismatch(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = score_observability_frame()
    scores = scores[scores["account_id"] != "acct_two"].reset_index(drop=True)
    create_score_observability_tables(database_path, score_frame=scores)

    with pytest.raises(ScoreObservabilityError, match="expected population"):
        load_score_observability_inputs(database_path, scoring_month="2024-02-01")


def test_load_score_observability_inputs_prior_month_uses_nearest_scored_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = score_observability_frame()
    scores.loc[
        (scores["observation_month"] == pd.Timestamp("2024-02-01"))
        & (scores["account_id"] == "acct_one"),
        "observation_month",
    ] = pd.Timestamp("2024-03-01")
    scores = scores[
        ~(
            (scores["observation_month"] == pd.Timestamp("2024-02-01"))
            & (scores["account_id"] == "acct_two")
        )
    ].reset_index(drop=True)
    scores.loc[
        scores["observation_month"] == pd.Timestamp("2024-03-01"),
        "scoring_run_id",
    ] = "run_mar"
    create_score_observability_tables(database_path, score_frame=scores)

    inputs = load_score_observability_inputs(database_path, latest=True)

    assert inputs.scoring_month == pd.Timestamp("2024-03-01")
    assert inputs.prior_scoring_month == pd.Timestamp("2024-01-01")
