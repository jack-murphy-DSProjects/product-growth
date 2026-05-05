from __future__ import annotations

import pandas as pd
import pytest

from account_health.modeling import (
    ModelingDataset,
    ModelingSplitError,
    split_modeling_dataset,
)


def labelled_dataset(frame: pd.DataFrame) -> ModelingDataset:
    return ModelingDataset(
        source_table="mart.account_month",
        target="churn_90d",
        frame=frame,
        numeric_features=(),
        categorical_features=(),
    )


def multi_month_label_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in pd.date_range("2024-01-01", "2024-05-01", freq="MS"):
        for label in (0, 1):
            rows.append(
                {
                    "account_id": f"acct_{month:%Y_%m}_{label}",
                    "observation_month": month,
                    "churn_90d": label,
                }
            )
    return pd.DataFrame(rows)


def test_split_modeling_dataset_uses_explicit_temporal_boundary() -> None:
    dataset = labelled_dataset(multi_month_label_frame())

    split = split_modeling_dataset(dataset, train_end_month="2024-03-01")

    assert split.train_end_month == pd.Timestamp("2024-03-01")
    assert split.train_frame["observation_month"].max() == pd.Timestamp("2024-03-01")
    assert split.test_frame["observation_month"].min() == pd.Timestamp("2024-04-01")
    assert (
        split.train_frame["observation_month"] <= split.train_end_month
    ).all()
    assert (split.test_frame["observation_month"] > split.train_end_month).all()


def test_split_modeling_dataset_derives_default_train_end_month() -> None:
    dataset = labelled_dataset(multi_month_label_frame())

    split = split_modeling_dataset(dataset)

    assert split.train_end_month == pd.Timestamp("2024-02-01")
    assert split.train_frame["observation_month"].max() == pd.Timestamp("2024-02-01")
    assert split.test_frame["observation_month"].min() == pd.Timestamp("2024-03-01")


def test_split_modeling_dataset_rejects_non_first_day_train_end() -> None:
    dataset = labelled_dataset(multi_month_label_frame())

    with pytest.raises(ModelingSplitError, match="first day"):
        split_modeling_dataset(dataset, train_end_month="2024-03-15")


def test_split_modeling_dataset_rejects_non_first_day_observation_month() -> None:
    frame = multi_month_label_frame()
    frame.loc[0, "observation_month"] = pd.Timestamp("2024-01-15")

    with pytest.raises(ModelingSplitError, match="first day"):
        split_modeling_dataset(labelled_dataset(frame), train_end_month="2024-03-01")


@pytest.mark.parametrize(
    ("train_end_month", "message"),
    [
        ("2023-12-01", "empty train"),
        ("2025-01-01", "empty test"),
    ],
)
def test_split_modeling_dataset_rejects_empty_train_or_test(
    train_end_month: str,
    message: str,
) -> None:
    dataset = labelled_dataset(multi_month_label_frame())

    with pytest.raises(ModelingSplitError, match=message):
        split_modeling_dataset(dataset, train_end_month=train_end_month)


@pytest.mark.parametrize(
    ("months", "message"),
    [
        ({"2024-01-01", "2024-02-01"}, "single-class train"),
        ({"2024-03-01", "2024-04-01", "2024-05-01"}, "single-class test"),
    ],
)
def test_split_modeling_dataset_rejects_single_class_sides(
    months: set[str],
    message: str,
) -> None:
    frame = multi_month_label_frame()
    mask = frame["observation_month"].isin(pd.to_datetime(sorted(months)))
    frame.loc[mask, "churn_90d"] = 0

    with pytest.raises(ModelingSplitError, match=message):
        split_modeling_dataset(labelled_dataset(frame), train_end_month="2024-02-01")


def test_split_modeling_dataset_is_order_independent_not_random() -> None:
    frame = multi_month_label_frame()
    shuffled_frame = frame.sample(frac=1, random_state=123).reset_index(drop=True)

    split = split_modeling_dataset(
        labelled_dataset(shuffled_frame),
        train_end_month="2024-03-01",
    )

    assert set(split.train_frame["account_id"]) == set(
        frame.loc[
            frame["observation_month"] <= pd.Timestamp("2024-03-01"),
            "account_id",
        ]
    )
    assert set(split.test_frame["account_id"]) == set(
        frame.loc[
            frame["observation_month"] > pd.Timestamp("2024-03-01"),
            "account_id",
        ]
    )
