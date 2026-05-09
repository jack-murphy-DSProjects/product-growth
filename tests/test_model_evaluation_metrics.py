from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from account_health.evaluation import (
    EvaluationMetricError,
    EvaluationInputs,
    LoadedCandidate,
    evaluate_overall_metrics,
    score_fixed_holdout,
    select_top_k_rows,
)


class CurrentMrrProbabilityModel:
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = (frame["current_mrr"].to_numpy(dtype=float) / 1000).clip(0, 1)
        return np.column_stack([1 - probabilities, probabilities])


def fixed_holdout_inputs() -> EvaluationInputs:
    account_month = pd.DataFrame(
        [
            {
                "account_id": "acct_train",
                "observation_month": pd.Timestamp("2024-01-01"),
                "observation_month_end": pd.Timestamp("2024-01-31"),
                "churn_90d": 0,
                "expansion_90d": 1,
                "current_mrr": 100.0,
                "segment": "smb",
                "region": "europe",
                "current_plan": "starter",
                "company_size_band": "1_50",
                "industry": "software",
            },
            {
                "account_id": "acct_holdout_a",
                "observation_month": pd.Timestamp("2024-02-01"),
                "observation_month_end": pd.Timestamp("2024-02-29"),
                "churn_90d": 0,
                "expansion_90d": 1,
                "current_mrr": 200.0,
                "segment": "smb",
                "region": "europe",
                "current_plan": "starter",
                "company_size_band": "1_50",
                "industry": "software",
            },
            {
                "account_id": "acct_holdout_b",
                "observation_month": pd.Timestamp("2024-02-01"),
                "observation_month_end": pd.Timestamp("2024-02-29"),
                "churn_90d": 1,
                "expansion_90d": 0,
                "current_mrr": 900.0,
                "segment": "enterprise",
                "region": "north_america",
                "current_plan": "enterprise",
                "company_size_band": "1001_5000",
                "industry": "financial_services",
            },
            {
                "account_id": "acct_null_label",
                "observation_month": pd.Timestamp("2024-03-01"),
                "observation_month_end": pd.Timestamp("2024-03-31"),
                "churn_90d": pd.NA,
                "expansion_90d": 0,
                "current_mrr": 500.0,
                "segment": "enterprise",
                "region": "north_america",
                "current_plan": "growth",
                "company_size_band": "201_1000",
                "industry": "software",
            },
        ]
    )
    baselines = pd.DataFrame(
        [
            {
                "account_id": "acct_train",
                "observation_month": pd.Timestamp("2024-01-01"),
                "baseline_churn_score": 10.0,
                "baseline_expansion_score": 80.0,
            },
            {
                "account_id": "acct_holdout_a",
                "observation_month": pd.Timestamp("2024-02-01"),
                "baseline_churn_score": 20.0,
                "baseline_expansion_score": 90.0,
            },
            {
                "account_id": "acct_holdout_b",
                "observation_month": pd.Timestamp("2024-02-01"),
                "baseline_churn_score": 90.0,
                "baseline_expansion_score": 20.0,
            },
            {
                "account_id": "acct_null_label",
                "observation_month": pd.Timestamp("2024-03-01"),
                "baseline_churn_score": 50.0,
                "baseline_expansion_score": 40.0,
            },
        ]
    )
    candidate = LoadedCandidate(
        target="churn_90d",
        candidate_model="logistic_regression",
        run_id="run_123",
        train_end_month=pd.Timestamp("2024-01-01"),
        model_artifact_uri="runs:/run_123/model",
        model=CurrentMrrProbabilityModel(),
        approved_features=("current_mrr",),
        numeric_features=("current_mrr",),
        categorical_features=(),
        split_config={"train_end_month": "2024-01-01"},
        mlflow_metrics={},
    )
    return EvaluationInputs(
        account_month=account_month,
        baselines=baselines,
        candidates=(candidate,),
        experiment_name="package-6",
        mlflow_tracking_uri=str("mlruns"),
        train_end_month=pd.Timestamp("2024-01-01"),
    )


def manual_score_frame() -> pd.DataFrame:
    rows = []
    for candidate_type, model_family, scores in [
        ("ml", "logistic_regression", [0.9, 0.9, 0.1, 0.2]),
        ("rule_baseline", "rule_baseline", [90.0, 80.0, 20.0, 10.0]),
    ]:
        for account_id, label, score in zip(
            ["acct_a", "acct_b", "acct_c", "acct_d"],
            [1, 0, 0, 1],
            scores,
            strict=True,
        ):
            rows.append(
                {
                    "account_id": account_id,
                    "observation_month": pd.Timestamp("2024-04-01"),
                    "target": "churn_90d",
                    "model_family": model_family,
                    "candidate_type": candidate_type,
                    "mlflow_run_id": "run_123" if candidate_type == "ml" else None,
                    "model_artifact_uri": (
                        "runs:/run_123/model" if candidate_type == "ml" else None
                    ),
                    "score_source": (
                        "ml_probability"
                        if candidate_type == "ml"
                        else "baseline_ranking_score"
                    ),
                    "label": label,
                    "score": score,
                }
            )
    return pd.DataFrame(rows)


def test_score_fixed_holdout_scores_ml_and_joins_baselines() -> None:
    score_frame = score_fixed_holdout(fixed_holdout_inputs())

    assert set(score_frame["candidate_type"]) == {"ml", "rule_baseline"}
    assert set(score_frame["account_id"]) == {"acct_holdout_a", "acct_holdout_b"}
    assert score_frame.loc[
        score_frame["candidate_type"] == "ml",
        "score",
    ].between(0, 1).all()
    assert (
        score_frame.loc[
            score_frame["candidate_type"] == "rule_baseline",
            "score_source",
        ]
        == "baseline_ranking_score"
    ).all()


def test_select_top_k_rows_uses_account_id_tie_breaking() -> None:
    tied_frame = manual_score_frame().query("candidate_type == 'ml'")

    selected = select_top_k_rows(tied_frame, k_count=1)

    assert selected["account_id"].tolist() == ["acct_a"]


def test_overall_metrics_exclude_baseline_probability_metrics() -> None:
    records = evaluate_overall_metrics(
        manual_score_frame(),
        top_k_percentages=(0.50,),
        top_k_counts=(25,),
    )

    baseline_metric_names = {
        record.metric_name
        for record in records
        if record.candidate_type == "rule_baseline"
    }
    ml_metric_names = {
        record.metric_name for record in records if record.candidate_type == "ml"
    }

    assert {"roc_auc", "average_precision", "precision_at_k"} <= baseline_metric_names
    assert "log_loss" not in baseline_metric_names
    assert "brier_score" not in baseline_metric_names
    assert {"log_loss", "brier_score", "accuracy"} <= ml_metric_names


def test_overall_metrics_reject_invalid_ml_probabilities() -> None:
    frame = manual_score_frame()
    frame.loc[
        (frame["candidate_type"] == "ml") & (frame["account_id"] == "acct_a"),
        "score",
    ] = 1.2

    with pytest.raises(EvaluationMetricError, match="ML probabilities"):
        evaluate_overall_metrics(frame)
