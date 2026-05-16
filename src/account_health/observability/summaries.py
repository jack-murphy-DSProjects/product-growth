"""Package 9 score validity checks and diagnostic distribution summaries."""

from __future__ import annotations

import numpy as np
import pandas as pd

from account_health.observability.loading import (
    SAFE_SEGMENT_COLUMNS,
    ScoreObservabilityError,
)

TARGET_SCORE_COLUMNS = {
    "churn": "churn_score",
    "expansion": "expansion_score",
}
PERCENTILE_LABELS = (
    ("p01", 0.01),
    ("p05", 0.05),
    ("p10", 0.10),
    ("p25", 0.25),
    ("p50", 0.50),
    ("p75", 0.75),
    ("p90", 0.90),
    ("p95", 0.95),
    ("p99", 0.99),
)


def validate_score_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate numeric, finite, non-null, bounded raw Package 8 scores."""

    normalized = frame.copy()
    for target, column in TARGET_SCORE_COLUMNS.items():
        values = normalized[column]
        if values.isna().any():
            raise ScoreObservabilityError(
                f"Package 9 {target} scores contain null values"
            )
        numeric_values = pd.to_numeric(values, errors="coerce")
        if numeric_values.isna().any():
            raise ScoreObservabilityError(
                f"Package 9 {target} scores contain non-numeric values"
            )
        if not np.isfinite(numeric_values.to_numpy(dtype=float)).all():
            raise ScoreObservabilityError(
                f"Package 9 {target} scores contain non-finite values"
            )
        if not numeric_values.between(0.0, 1.0).all():
            raise ScoreObservabilityError(
                f"Package 9 {target} scores must be inside [0, 1]"
            )
        normalized[column] = numeric_values.astype(float)
    return normalized


def summarize_score_distributions(
    frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> pd.DataFrame:
    """Summarize churn and expansion score distributions for one month."""

    validated = validate_score_values(frame)
    rows: list[dict[str, object]] = []
    for target, column in TARGET_SCORE_COLUMNS.items():
        values = validated[column]
        p90 = float(values.quantile(0.90))
        row: dict[str, object] = {
            "scoring_month": scoring_month.date(),
            "target": target,
            "account_count": int(len(values)),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "mean": float(values.mean()),
            "stddev": float(values.std(ddof=0)),
        }
        row.update(
            {
                label: float(values.quantile(quantile))
                for label, quantile in PERCENTILE_LABELS
            }
        )
        row["top_decile_threshold"] = p90
        row["top_decile_share"] = float((values >= p90).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def score_distribution_warning_codes(
    distribution_frame: pd.DataFrame,
    *,
    variance_tolerance: float = 1e-12,
) -> tuple[str, ...]:
    """Return diagnostic warning codes for nearly identical score distributions."""

    warnings: list[str] = []
    for row in distribution_frame.itertuples(index=False):
        if float(row.stddev) <= variance_tolerance:
            warnings.append(f"near_zero_variance_{row.target}")
    return tuple(warnings)


def compare_score_distributions(
    current_frame: pd.DataFrame,
    prior_frame: pd.DataFrame | None,
    *,
    prior_scoring_month: pd.Timestamp | None,
) -> pd.DataFrame:
    """Compare current target distributions with the nearest prior scored month."""

    current = current_frame.copy()
    if prior_frame is None or prior_scoring_month is None:
        comparison = current.copy()
        comparison["prior_scoring_month"] = pd.NaT
        for column in _comparison_metric_columns():
            comparison[f"prior_{column}"] = pd.NA
            comparison[f"{column}_delta"] = pd.NA
        return _ordered_comparison_columns(comparison)

    prior = prior_frame.drop(columns=["scoring_month"]).rename(
        columns={
            column: f"prior_{column}"
            for column in _comparison_metric_columns()
        }
    )
    comparison = current.merge(prior, on="target", how="left", validate="one_to_one")
    comparison["prior_scoring_month"] = prior_scoring_month.date()
    for column in _comparison_metric_columns():
        comparison[f"{column}_delta"] = (
            comparison[column] - comparison[f"prior_{column}"]
        )
    return _ordered_comparison_columns(comparison)


def prior_comparison_warning_codes(
    prior_scoring_month: pd.Timestamp | None,
) -> tuple[str, ...]:
    """Return warning codes for current-versus-prior comparison state."""

    if prior_scoring_month is None:
        return ("no_prior_scored_month",)
    return ()


def summarize_segment_distributions(
    score_frame: pd.DataFrame,
    population_frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
    small_segment_threshold: int = 30,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Summarize scores across safe descriptive Package 3 segment columns."""

    _validate_non_multiplying_segment_join(score_frame, population_frame)
    available_segment_columns = tuple(
        column for column in SAFE_SEGMENT_COLUMNS if column in population_frame.columns
    )
    warnings: list[str] = [
        f"missing_optional_segment_{column}"
        for column in SAFE_SEGMENT_COLUMNS
        if column not in available_segment_columns
    ]
    if not available_segment_columns:
        return _empty_segment_distribution_frame(), tuple(warnings)

    joined = score_frame.merge(
        population_frame[
            ["account_id", "observation_month", *available_segment_columns]
        ],
        on=["account_id", "observation_month"],
        how="left",
        validate="one_to_one",
    )
    rows: list[pd.DataFrame] = []
    for segment_column in available_segment_columns:
        saw_small_segment = False
        for segment_value, group in joined.groupby(segment_column, dropna=False):
            distribution = summarize_score_distributions(
                group,
                scoring_month=scoring_month,
            )
            distribution.insert(2, "segment_name", segment_column)
            distribution.insert(3, "segment_value", segment_value)
            distribution["is_small_segment"] = len(group) < small_segment_threshold
            saw_small_segment = saw_small_segment or len(group) < small_segment_threshold
            rows.append(distribution)
        if saw_small_segment:
            warnings.append(f"small_segment_{segment_column}")
    return pd.concat(rows, ignore_index=True), tuple(warnings)


def _validate_non_multiplying_segment_join(
    score_frame: pd.DataFrame,
    population_frame: pd.DataFrame,
) -> None:
    score_duplicates = score_frame.duplicated(
        subset=["account_id", "observation_month"]
    )
    population_duplicates = population_frame.duplicated(
        subset=["account_id", "observation_month"]
    )
    if score_duplicates.any() or population_duplicates.any():
        raise ScoreObservabilityError(
            "Package 9 segment join would multiply score rows"
        )


def _comparison_metric_columns() -> tuple[str, ...]:
    return (
        "account_count",
        "minimum",
        "maximum",
        "mean",
        "stddev",
        *(label for label, _ in PERCENTILE_LABELS),
        "top_decile_threshold",
        "top_decile_share",
    )


def _ordered_comparison_columns(frame: pd.DataFrame) -> pd.DataFrame:
    metric_columns = _comparison_metric_columns()
    ordered_columns = (
        "scoring_month",
        "target",
        *metric_columns,
        *(f"prior_{column}" for column in metric_columns),
        *(f"{column}_delta" for column in metric_columns),
        "prior_scoring_month",
    )
    return frame.loc[:, ordered_columns]


def _empty_segment_distribution_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "scoring_month",
            "target",
            "segment_name",
            "segment_value",
            *_comparison_metric_columns(),
            "is_small_segment",
        ]
    )
