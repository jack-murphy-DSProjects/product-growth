from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from account_health.gtm_policy import GTMPolicyError, load_gtm_policy_inputs


def gtm_policy_score_frame() -> pd.DataFrame:
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


def create_gtm_policy_score_table(
    database_path: Path,
    *,
    score_frame: pd.DataFrame | None = None,
) -> None:
    score_frame = gtm_policy_score_frame() if score_frame is None else score_frame
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
        connection.register("score_frame", score_frame)
        try:
            connection.execute(
                """
                CREATE OR REPLACE TABLE mart.account_month_scores AS
                SELECT * FROM score_frame
                """
            )
        finally:
            connection.unregister("score_frame")


def test_load_gtm_policy_inputs_requires_explicit_selector(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_score_table(database_path)

    with pytest.raises(GTMPolicyError, match="scoring-month|latest"):
        load_gtm_policy_inputs(database_path)


def test_load_gtm_policy_inputs_latest_uses_latest_scored_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_score_table(database_path)

    inputs = load_gtm_policy_inputs(database_path, latest=True)

    assert inputs.selector == "latest"
    assert inputs.scoring_month == pd.Timestamp("2024-02-01")
    assert inputs.score_frame["account_id"].tolist() == ["acct_one", "acct_two"]


def test_load_gtm_policy_inputs_rejects_ambiguous_selectors(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_score_table(database_path)

    with pytest.raises(GTMPolicyError, match="exactly one selector"):
        load_gtm_policy_inputs(
            database_path,
            scoring_month="2024-02-01",
            latest=True,
        )


def test_load_gtm_policy_inputs_rejects_non_month_start(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_score_table(database_path)

    with pytest.raises(GTMPolicyError, match="YYYY-MM-01"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-15")


def test_load_gtm_policy_inputs_rejects_missing_required_table(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")

    with pytest.raises(GTMPolicyError, match="mart.account_month_scores"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")


def test_load_gtm_policy_inputs_rejects_missing_score_column(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = gtm_policy_score_frame().drop(columns=["expansion_score"])
    create_gtm_policy_score_table(database_path, score_frame=scores)

    with pytest.raises(GTMPolicyError, match="expansion_score"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")


def test_load_gtm_policy_inputs_latest_rejects_missing_month_column_clearly(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = gtm_policy_score_frame().drop(columns=["observation_month"])
    create_gtm_policy_score_table(database_path, score_frame=scores)

    with pytest.raises(GTMPolicyError, match="observation_month"):
        load_gtm_policy_inputs(database_path, latest=True)


def test_load_gtm_policy_inputs_rejects_empty_selected_month(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_score_table(database_path)

    with pytest.raises(GTMPolicyError, match="no score rows"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-03-01")


def test_load_gtm_policy_inputs_rejects_duplicate_score_grain(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    duplicate_scores = pd.concat(
        [gtm_policy_score_frame(), gtm_policy_score_frame().iloc[[1]]],
        ignore_index=True,
    )
    create_gtm_policy_score_table(database_path, score_frame=duplicate_scores)

    with pytest.raises(GTMPolicyError, match="duplicate account/month"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")


def test_load_gtm_policy_inputs_rejects_null_score_account_id(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = gtm_policy_score_frame()
    scores.loc[scores["account_id"] == "acct_two", "account_id"] = None
    create_gtm_policy_score_table(database_path, score_frame=scores)

    with pytest.raises(GTMPolicyError, match="null account_id"):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("churn_score", None, "null values"),
        ("expansion_score", "bad", "non-numeric values"),
        ("churn_score", np.inf, "non-finite values"),
        ("expansion_score", -0.1, r"\[0, 1\]"),
        ("churn_score", 1.1, r"\[0, 1\]"),
    ],
)
def test_load_gtm_policy_inputs_rejects_invalid_scores(
    tmp_path: Path,
    column: str,
    value: object,
    message: str,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = gtm_policy_score_frame()
    if isinstance(value, str):
        scores[column] = scores[column].astype(object)
    scores.loc[scores["account_id"] == "acct_two", column] = value
    create_gtm_policy_score_table(database_path, score_frame=scores)

    with pytest.raises(GTMPolicyError, match=message):
        load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")
