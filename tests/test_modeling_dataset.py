from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.modeling import (
    APPROVED_CATEGORICAL_FEATURES,
    APPROVED_NUMERIC_FEATURES,
    ModelingDatasetError,
    ModelingFeatureSet,
    load_modeling_dataset,
    validate_modeling_feature_set,
)


def account_month_modeling_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    labels = [
        ("acct_one", "2024-01-01", 0, 1),
        ("acct_two", "2024-01-01", 1, 0),
        ("acct_three", "2024-01-01", pd.NA, 1),
    ]
    for index, (account_id, observation_month, churn, expansion) in enumerate(
        labels,
        start=1,
    ):
        row: dict[str, object] = {
            "account_id": account_id,
            "observation_month": pd.Timestamp(observation_month),
            "observation_month_end": pd.Timestamp(observation_month)
            + pd.offsets.MonthEnd(0),
            "is_churn_label_eligible": churn is not pd.NA,
            "is_expansion_label_eligible": True,
            "churn_90d": churn,
            "expansion_90d": expansion,
        }
        for feature in APPROVED_CATEGORICAL_FEATURES:
            row[feature] = f"{feature}_value"
        for feature in APPROVED_NUMERIC_FEATURES:
            row[feature] = float(index)
        rows.append(row)
    return pd.DataFrame(rows)


def create_account_month_table(
    database_path: Path,
    frame: pd.DataFrame | None = None,
    *,
    omit_columns: set[str] | None = None,
) -> None:
    frame = account_month_modeling_frame() if frame is None else frame
    if omit_columns:
        frame = frame.drop(columns=list(omit_columns))

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


def test_load_modeling_dataset_excludes_null_target_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    dataset = load_modeling_dataset(database_path, target="churn_90d")

    assert dataset.source_table == "mart.account_month"
    assert dataset.target == "churn_90d"
    assert len(dataset.frame) == 2
    assert set(dataset.frame["account_id"]) == {"acct_one", "acct_two"}
    assert set(dataset.frame["churn_90d"]) == {0, 1}
    assert dataset.numeric_features == APPROVED_NUMERIC_FEATURES
    assert dataset.categorical_features == APPROVED_CATEGORICAL_FEATURES


def test_load_modeling_dataset_does_not_require_baseline_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        baseline_table_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'mart'
                AND table_name = 'account_month_baselines'
            """
        ).fetchone()[0]

    assert baseline_table_count == 0
    assert (
        len(load_modeling_dataset(database_path, target="expansion_90d").frame)
        == 3
    )


def test_load_modeling_dataset_rejects_non_account_month_source_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path)

    with pytest.raises(ModelingDatasetError, match="only read mart.account_month"):
        load_modeling_dataset(
            database_path,
            target="churn_90d",
            source_table="raw.renewals",
        )


def test_load_modeling_dataset_rejects_missing_account_month_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"

    with pytest.raises(ModelingDatasetError, match="mart.account_month"):
        load_modeling_dataset(database_path, target="churn_90d")


@pytest.mark.parametrize(
    "missing_column",
    ["account_id", "observation_month", "churn_90d", "current_mrr"],
)
def test_load_modeling_dataset_rejects_missing_required_columns(
    tmp_path: Path,
    missing_column: str,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_table(database_path, omit_columns={missing_column})

    with pytest.raises(ModelingDatasetError, match=missing_column):
        load_modeling_dataset(database_path, target="churn_90d")


def test_load_modeling_dataset_rejects_duplicate_account_month_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    frame = account_month_modeling_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    create_account_month_table(database_path, frame)

    with pytest.raises(ModelingDatasetError, match="duplicate account-month"):
        load_modeling_dataset(database_path, target="churn_90d")


def test_load_modeling_dataset_rejects_fractional_target_labels(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    frame = account_month_modeling_frame()
    frame.loc[0, "churn_90d"] = 0.5
    create_account_month_table(database_path, frame)

    with pytest.raises(ModelingDatasetError, match="binary"):
        load_modeling_dataset(database_path, target="churn_90d")


@pytest.mark.parametrize(
    "feature",
    [
        "account_id",
        "is_churn_label_eligible",
        "baseline_churn_score",
        "renewal_days_until_next",
        "future_usage_count",
        "model_rank",
    ],
)
def test_modeling_feature_set_rejects_forbidden_features(feature: str) -> None:
    feature_set = ModelingFeatureSet(
        numeric_features=(*APPROVED_NUMERIC_FEATURES, feature),
        categorical_features=APPROVED_CATEGORICAL_FEATURES,
    )

    with pytest.raises(ModelingDatasetError, match=feature):
        validate_modeling_feature_set(feature_set)
