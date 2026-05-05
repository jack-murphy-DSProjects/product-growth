from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from account_health.modeling import (
    REQUIRED_METRIC_KEYS,
    SUPPORTED_CANDIDATE_MODELS,
    ModelingCandidateError,
    ModelingDataset,
    build_candidate_pipeline,
    evaluate_binary_metrics,
    split_modeling_dataset,
    train_candidate_model,
)


NUMERIC_FEATURES = ("current_mrr", "usage_event_count_30d")
CATEGORICAL_FEATURES = ("current_plan", "region")


def candidate_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month_index, month in enumerate(
        pd.date_range("2024-01-01", "2024-04-01", freq="MS"),
        start=1,
    ):
        for label in (0, 1):
            rows.append(
                {
                    "account_id": f"acct_{month:%Y_%m}_{label}",
                    "observation_month": month,
                    "churn_90d": label,
                    "current_mrr": float(500 + month_index * 100 + label * 50),
                    "usage_event_count_30d": float(20 + label * 5),
                    "current_plan": "growth" if label else "starter",
                    "region": "europe" if month_index == 4 else "north_america",
                }
            )
    return pd.DataFrame(rows)


def candidate_split():
    dataset = ModelingDataset(
        source_table="mart.account_month",
        target="churn_90d",
        frame=candidate_frame(),
        numeric_features=NUMERIC_FEATURES,
        categorical_features=CATEGORICAL_FEATURES,
    )
    return split_modeling_dataset(dataset, train_end_month="2024-02-01")


@pytest.mark.parametrize("candidate_model", SUPPORTED_CANDIDATE_MODELS)
def test_train_candidate_model_returns_bounded_probabilities_and_metrics(
    candidate_model: str,
) -> None:
    split = candidate_split()

    result = train_candidate_model(
        split,
        candidate_model=candidate_model,
        random_state=123,
    )

    assert result.candidate_model == candidate_model
    assert len(result.test_probabilities) == len(split.test_frame)
    assert (
        (result.test_probabilities >= 0) & (result.test_probabilities <= 1)
    ).all()
    assert REQUIRED_METRIC_KEYS <= set(result.metrics)


def test_build_candidate_pipeline_rejects_unsupported_model_family() -> None:
    with pytest.raises(ModelingCandidateError, match="xgboost"):
        build_candidate_pipeline(
            "xgboost",
            numeric_features=NUMERIC_FEATURES,
            categorical_features=CATEGORICAL_FEATURES,
        )


@pytest.mark.parametrize(
    ("labels", "probabilities", "message"),
    [
        (np.array([0, 1]), np.array([0.2, 1.2]), "bounded between 0 and 1"),
        (np.array([0, 1.5]), np.array([0.2, 0.8]), "binary"),
        (np.array([0, 1]), np.array([0.2]), "same length"),
    ],
)
def test_evaluate_binary_metrics_rejects_invalid_inputs(
    labels: np.ndarray,
    probabilities: np.ndarray,
    message: str,
) -> None:
    with pytest.raises(ModelingCandidateError, match=message):
        evaluate_binary_metrics(labels, probabilities)


def test_random_forest_candidate_is_deterministic_with_fixed_random_state() -> None:
    split = candidate_split()

    first = train_candidate_model(
        split,
        candidate_model="random_forest",
        random_state=7,
    )
    second = train_candidate_model(
        split,
        candidate_model="random_forest",
        random_state=7,
    )

    assert first.test_probabilities.tolist() == second.test_probabilities.tolist()


def test_logistic_regression_pipeline_includes_scaling_step() -> None:
    pipeline = build_candidate_pipeline(
        "logistic_regression",
        numeric_features=NUMERIC_FEATURES,
        categorical_features=CATEGORICAL_FEATURES,
    )

    numeric_pipeline = pipeline.named_steps["preprocessor"].transformers[0][1]
    assert "scaler" in numeric_pipeline.named_steps
