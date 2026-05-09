from __future__ import annotations

import pandas as pd
import pytest

from account_health.evaluation import (
    compute_calibration_metrics,
    compute_holdout_month_robustness,
    compute_segment_robustness,
)


def robustness_score_frame() -> pd.DataFrame:
    rows = []
    for candidate_type, model_family, score_source, scores in [
        ("ml", "logistic_regression", "ml_probability", [0.9, 0.8, 0.2, 0.1]),
        (
            "rule_baseline",
            "rule_baseline",
            "baseline_ranking_score",
            [90.0, 20.0, 80.0, 10.0],
        ),
    ]:
        for account_id, month, segment, label, score in zip(
            ["acct_a", "acct_b", "acct_c", "acct_d"],
            [
                "2024-04-01",
                "2024-04-01",
                "2024-05-01",
                "2024-05-01",
            ],
            ["enterprise", "enterprise", "smb", "smb"],
            [1, 1, 0, 1],
            scores,
            strict=True,
        ):
            rows.append(
                {
                    "account_id": account_id,
                    "observation_month": pd.Timestamp(month),
                    "target": "churn_90d",
                    "model_family": model_family,
                    "candidate_type": candidate_type,
                    "mlflow_run_id": "run_123" if candidate_type == "ml" else None,
                    "model_artifact_uri": (
                        "runs:/run_123/model" if candidate_type == "ml" else None
                    ),
                    "score_source": score_source,
                    "label": label,
                    "score": score,
                    "segment": segment,
                    "region": "europe",
                    "current_plan": "enterprise" if segment == "enterprise" else "starter",
                    "company_size_band": "1001_5000" if segment == "enterprise" else "1_50",
                    "industry": "software",
                }
            )
    return pd.DataFrame(rows)


def test_calibration_metrics_apply_to_ml_candidates_only() -> None:
    records, caveats = compute_calibration_metrics(
        robustness_score_frame(),
        bin_count=2,
        min_bin_size=3,
    )

    assert records
    assert {record.candidate_type for record in records} == {"ml"}
    assert {
        "calibration_mean_predicted_rate",
        "calibration_observed_positive_rate",
    } <= {record.metric_name for record in records}
    assert {caveat.caveat for caveat in caveats} == {"sparse_calibration_bin"}


def test_calibration_metrics_reject_invalid_ml_probabilities() -> None:
    frame = robustness_score_frame()
    frame.loc[
        (frame["candidate_type"] == "ml") & (frame["account_id"] == "acct_a"),
        "score",
    ] = 1.2

    with pytest.raises(ValueError, match="ML calibration requires probabilities"):
        compute_calibration_metrics(frame)


def test_segment_robustness_emits_low_support_and_one_class_caveats() -> None:
    records, caveats = compute_segment_robustness(
        robustness_score_frame(),
        segment_fields=("segment",),
        min_support=3,
    )

    assert any(record.slice_type == "segment" for record in records)
    caveat_values = {caveat.caveat for caveat in caveats}
    assert "low_support_slice_topk_skipped" in caveat_values
    assert "one_class_slice_auc_skipped" in caveat_values


def test_segment_robustness_rejects_missing_or_unapproved_segment_fields() -> None:
    frame = robustness_score_frame()

    with pytest.raises(ValueError, match="missing column"):
        compute_segment_robustness(
            frame.drop(columns=["segment"]),
            segment_fields=("segment",),
        )

    with pytest.raises(ValueError, match="approved segment"):
        compute_segment_robustness(
            frame.assign(baseline_churn_score=1.0),
            segment_fields=("baseline_churn_score",),
        )


def test_holdout_month_robustness_is_fixed_holdout_not_rolling_backtest() -> None:
    records, caveats = compute_holdout_month_robustness(
        robustness_score_frame(),
        min_support=3,
    )

    assert {record.slice_type for record in records} == {"holdout_month"}
    assert "fixed_holdout_month_slice_not_rolling_backtest" in {
        caveat.caveat for caveat in caveats
    }
