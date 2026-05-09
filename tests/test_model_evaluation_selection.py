from __future__ import annotations

import pandas as pd

from account_health.evaluation import (
    CaveatRecord,
    MetricRecord,
    compute_utility_sensitivity,
    select_champions,
)


def topk_record(
    *,
    target: str,
    model_family: str,
    candidate_type: str,
    metric_name: str,
    metric_value: float,
    run_id: str | None = None,
) -> MetricRecord:
    return MetricRecord(
        target=target,
        model_family=model_family,
        candidate_type=candidate_type,
        mlflow_run_id=run_id,
        model_artifact_uri=f"runs:/{run_id}/model" if run_id else None,
        score_source=(
            "ml_probability"
            if candidate_type == "ml"
            else "baseline_ranking_score"
        ),
        metric_name=metric_name,
        metric_value=metric_value,
        slice_type="overall",
        slice_value="fixed_holdout",
        row_count=100,
        positive_count=20,
        base_positive_rate=0.2,
        k_value=0.10,
        k_type="percent",
    )


def topk_records_for_group(
    *,
    target: str,
    model_family: str,
    candidate_type: str,
    precision: float,
    lift: float,
    capture: float,
    run_id: str | None = None,
) -> list[MetricRecord]:
    values = {
        "accounts_selected": 10.0,
        "positives_captured": capture * 20,
        "precision_at_k": precision,
        "recall_at_k": capture,
        "lift_at_k": lift,
        "capture_rate_at_k": capture,
        "base_positive_rate": 0.2,
    }
    return [
        topk_record(
            target=target,
            model_family=model_family,
            candidate_type=candidate_type,
            metric_name=metric_name,
            metric_value=metric_value,
            run_id=run_id,
        )
        for metric_name, metric_value in values.items()
    ]


def utility_score_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "acct_a",
                "observation_month": pd.Timestamp("2024-04-01"),
                "target": "churn_90d",
                "model_family": "logistic_regression",
                "candidate_type": "ml",
                "mlflow_run_id": "run_123",
                "model_artifact_uri": "runs:/run_123/model",
                "score_source": "ml_probability",
                "label": 1,
                "score": 0.9,
            },
            {
                "account_id": "acct_b",
                "observation_month": pd.Timestamp("2024-04-01"),
                "target": "churn_90d",
                "model_family": "logistic_regression",
                "candidate_type": "ml",
                "mlflow_run_id": "run_123",
                "model_artifact_uri": "runs:/run_123/model",
                "score_source": "ml_probability",
                "label": 0,
                "score": 0.1,
            },
        ]
    )


def test_utility_sensitivity_is_illustrative() -> None:
    records, caveats = compute_utility_sensitivity(utility_score_frame())

    assert {record.metric_name for record in records} == {"illustrative_net_utility"}
    assert {record.slice_value for record in records} == {
        "conservative",
        "base",
        "optimistic",
    }
    assert {caveat.caveat for caveat in caveats} == {
        "illustrative_utility_not_real_roi"
    }


def test_select_champions_selects_ml_when_top10_beats_baseline() -> None:
    metric_records = [
        *topk_records_for_group(
            target="churn_90d",
            model_family="logistic_regression",
            candidate_type="ml",
            precision=0.8,
            lift=4.0,
            capture=0.4,
            run_id="run_123",
        ),
        *topk_records_for_group(
            target="churn_90d",
            model_family="rule_baseline",
            candidate_type="rule_baseline",
            precision=0.5,
            lift=2.5,
            capture=0.3,
        ),
    ]

    champions = select_champions(
        metric_records,
        caveats=[
            CaveatRecord(
                target="churn_90d",
                model_family="logistic_regression",
                candidate_type="ml",
                slice_type="calibration_bin",
                slice_value="bin_01_of_10",
                caveat="sparse_calibration_bin",
            )
        ],
        created_at_utc="2026-05-05T00:00:00+00:00",
        evaluation_version="package_6_evaluation_v1",
    )

    champion = champions[0]
    assert champion.selection_status == "ml_champion_selected"
    assert champion.selected_champion_model_family == "logistic_regression"
    assert champion.mlflow_run_id == "run_123"
    assert champion.primary_metric == "precision_at_top_10_pct"
    assert "bin_01_of_10: sparse_calibration_bin" in champion.calibration_caveats


def test_select_champions_can_retain_baseline_or_reject_weak_ml_gain() -> None:
    metric_records = [
        *topk_records_for_group(
            target="churn_90d",
            model_family="random_forest",
            candidate_type="ml",
            precision=0.6,
            lift=3.0,
            capture=0.3,
            run_id="run_churn",
        ),
        *topk_records_for_group(
            target="churn_90d",
            model_family="rule_baseline",
            candidate_type="rule_baseline",
            precision=0.7,
            lift=3.5,
            capture=0.35,
        ),
        *topk_records_for_group(
            target="expansion_90d",
            model_family="random_forest",
            candidate_type="ml",
            precision=0.51,
            lift=2.60,
            capture=0.30,
            run_id="run_expansion",
        ),
        *topk_records_for_group(
            target="expansion_90d",
            model_family="rule_baseline",
            candidate_type="rule_baseline",
            precision=0.50,
            lift=2.50,
            capture=0.30,
        ),
    ]

    champions = {
        champion.target: champion
        for champion in select_champions(
            metric_records,
            created_at_utc="2026-05-05T00:00:00+00:00",
            evaluation_version="package_6_evaluation_v1",
        )
    }

    assert champions["churn_90d"].selection_status == "baseline_retained"
    assert (
        champions["expansion_90d"].selection_status
        == "no_ml_candidate_sufficiently_beats_baseline"
    )
    assert champions["expansion_90d"].mlflow_run_id is None
