from __future__ import annotations

import pandas as pd
import pytest

from account_health.observability import (
    ScoreObservabilityError,
    compare_score_distributions,
    prior_comparison_warning_codes,
    score_distribution_warning_codes,
    summarize_segment_distributions,
    summarize_score_distributions,
    validate_score_values,
)
from test_score_observability_loading import score_observability_frame
from test_score_observability_loading import account_month_observability_frame


def february_scores() -> pd.DataFrame:
    frame = score_observability_frame()
    return frame[frame["observation_month"] == pd.Timestamp("2024-02-01")].reset_index(
        drop=True
    )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("churn_score", None, "null"),
        ("expansion_score", "not-a-score", "non-numeric"),
        ("expansion_score", float("inf"), "non-finite"),
        ("churn_score", 1.2, r"\[0, 1\]"),
    ],
)
def test_validate_score_values_rejects_invalid_scores(
    column: str,
    value: object,
    message: str,
) -> None:
    scores = february_scores()
    if isinstance(value, str):
        scores[column] = scores[column].astype(object)
    scores.loc[0, column] = value

    with pytest.raises(ScoreObservabilityError, match=message):
        validate_score_values(scores)


def test_summarize_score_distributions_builds_target_specific_month_rows() -> None:
    summary = summarize_score_distributions(
        february_scores(),
        scoring_month=pd.Timestamp("2024-02-01"),
    )

    churn = summary.loc[summary["target"] == "churn"].iloc[0]
    expansion = summary.loc[summary["target"] == "expansion"].iloc[0]

    assert summary["target"].tolist() == ["churn", "expansion"]
    assert churn["scoring_month"] == pd.Timestamp("2024-02-01").date()
    assert churn["account_count"] == 2
    assert churn["minimum"] == pytest.approx(0.20)
    assert churn["maximum"] == pytest.approx(0.40)
    assert churn["mean"] == pytest.approx(0.30)
    assert churn["stddev"] == pytest.approx(0.10)
    assert churn["p50"] == pytest.approx(0.30)
    assert churn["p90"] == pytest.approx(0.38)
    assert churn["top_decile_threshold"] == pytest.approx(0.38)
    assert churn["top_decile_share"] == pytest.approx(0.50)
    assert expansion["mean"] == pytest.approx(0.65)
    assert expansion["stddev"] == pytest.approx(0.05)


def test_score_distribution_warning_codes_flags_near_zero_variance() -> None:
    scores = february_scores()
    scores["churn_score"] = 0.25

    summary = summarize_score_distributions(
        scores,
        scoring_month=pd.Timestamp("2024-02-01"),
    )

    assert score_distribution_warning_codes(summary) == ("near_zero_variance_churn",)


def test_compare_score_distributions_builds_current_vs_prior_deltas() -> None:
    frame = score_observability_frame()
    current = summarize_score_distributions(
        frame[frame["observation_month"] == pd.Timestamp("2024-02-01")],
        scoring_month=pd.Timestamp("2024-02-01"),
    )
    prior = summarize_score_distributions(
        frame[frame["observation_month"] == pd.Timestamp("2024-01-01")],
        scoring_month=pd.Timestamp("2024-01-01"),
    )

    comparison = compare_score_distributions(
        current,
        prior,
        prior_scoring_month=pd.Timestamp("2024-01-01"),
    )
    churn = comparison.loc[comparison["target"] == "churn"].iloc[0]

    assert churn["prior_scoring_month"] == pd.Timestamp("2024-01-01").date()
    assert churn["prior_account_count"] == 1
    assert churn["account_count_delta"] == 1
    assert churn["prior_mean"] == pytest.approx(0.10)
    assert churn["mean_delta"] == pytest.approx(0.20)
    assert churn["p50_delta"] == pytest.approx(0.20)


def test_compare_score_distributions_keeps_null_prior_fields_for_one_month_history() -> None:
    current = summarize_score_distributions(
        february_scores(),
        scoring_month=pd.Timestamp("2024-02-01"),
    )

    comparison = compare_score_distributions(
        current,
        None,
        prior_scoring_month=None,
    )

    assert comparison["prior_scoring_month"].isna().all()
    assert comparison["prior_account_count"].isna().all()
    assert comparison["mean_delta"].isna().all()
    assert prior_comparison_warning_codes(None) == ("no_prior_scored_month",)


def test_summarize_segment_distributions_uses_safe_descriptive_columns_only() -> None:
    score_frame = february_scores()
    population_frame = account_month_observability_frame()
    population_frame = population_frame[
        population_frame["observation_month"] == pd.Timestamp("2024-02-01")
    ].reset_index(drop=True)

    summary, warnings = summarize_segment_distributions(
        score_frame,
        population_frame,
        scoring_month=pd.Timestamp("2024-02-01"),
        small_segment_threshold=2,
    )

    assert set(summary["segment_name"]) == {
        "current_plan",
        "company_size_band",
        "region",
        "industry",
        "segment",
    }
    assert "churn_90d" not in set(summary["segment_name"])
    assert "expansion_90d" not in set(summary["segment_name"])
    assert summary["is_small_segment"].all()
    assert "small_segment_current_plan" in warnings
    assert "small_segment_region" in warnings


def test_summarize_segment_distributions_warns_on_missing_optional_columns() -> None:
    population_frame = account_month_observability_frame().drop(columns=["region"])
    population_frame = population_frame[
        population_frame["observation_month"] == pd.Timestamp("2024-02-01")
    ].reset_index(drop=True)

    _, warnings = summarize_segment_distributions(
        february_scores(),
        population_frame,
        scoring_month=pd.Timestamp("2024-02-01"),
    )

    assert "missing_optional_segment_region" in warnings


def test_summarize_segment_distributions_rejects_row_multiplying_joins() -> None:
    population_frame = account_month_observability_frame()
    population_frame = population_frame[
        population_frame["observation_month"] == pd.Timestamp("2024-02-01")
    ].reset_index(drop=True)
    population_frame = pd.concat(
        [population_frame, population_frame.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ScoreObservabilityError, match="multiply score rows"):
        summarize_segment_distributions(
            february_scores(),
            population_frame,
            scoring_month=pd.Timestamp("2024-02-01"),
        )
