"""Fixed-holdout scoring and operating metrics for Package 6."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from account_health.evaluation.loading import (
    BASELINE_SCORE_COLUMNS,
    SEGMENT_FIELDS,
    EvaluationInputs,
)

DEFAULT_TOP_K_PERCENTAGES: tuple[float, ...] = (0.05, 0.10, 0.20)
DEFAULT_TOP_K_COUNTS: tuple[int, ...] = (25, 50, 100)

ML_CANDIDATE_TYPE = "ml"
BASELINE_CANDIDATE_TYPE = "rule_baseline"
ML_SCORE_SOURCE = "ml_probability"
BASELINE_SCORE_SOURCE = "baseline_ranking_score"
OVERALL_SLICE_TYPE = "overall"
FIXED_HOLDOUT_SLICE_VALUE = "fixed_holdout"


@dataclass(frozen=True)
class MetricRecord:
    """One Package 6 metric row, shaped for JSON and DuckDB output."""

    target: str
    model_family: str
    candidate_type: str
    mlflow_run_id: str | None
    model_artifact_uri: str | None
    score_source: str
    metric_name: str
    metric_value: float | None
    slice_type: str
    slice_value: str
    row_count: int
    positive_count: int
    base_positive_rate: float | None
    k_value: float | int | None = None
    k_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "model_family": self.model_family,
            "candidate_type": self.candidate_type,
            "mlflow_run_id": self.mlflow_run_id,
            "model_artifact_uri": self.model_artifact_uri,
            "score_source": self.score_source,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "slice_type": self.slice_type,
            "slice_value": self.slice_value,
            "row_count": self.row_count,
            "positive_count": self.positive_count,
            "base_positive_rate": self.base_positive_rate,
            "k_value": self.k_value,
            "k_type": self.k_type,
        }


class EvaluationMetricError(ValueError):
    """Raised when Package 6 scoring or metrics violate the contract."""


def score_fixed_holdout(inputs: EvaluationInputs) -> pd.DataFrame:
    """Score fixed Package 5 holdout rows for ML candidates and baselines."""

    account_month = inputs.account_month.copy()
    account_month["observation_month"] = pd.to_datetime(
        account_month["observation_month"]
    )
    baselines = inputs.baselines.copy()
    baselines["observation_month"] = pd.to_datetime(baselines["observation_month"])

    score_frames: list[pd.DataFrame] = []
    targets = tuple(dict.fromkeys(candidate.target for candidate in inputs.candidates))
    for target in targets:
        target_candidates = tuple(
            candidate for candidate in inputs.candidates if candidate.target == target
        )
        train_end_month = _target_train_end_month(target_candidates, target=target)
        holdout = account_month[
            (account_month[target].notna())
            & (account_month["observation_month"] > train_end_month)
        ].copy()
        if holdout.empty:
            raise EvaluationMetricError(
                f"Package 6 fixed holdout is empty for target={target}"
            )
        _validate_binary_labels(holdout[target], target=target)

        for candidate in target_candidates:
            probabilities = _predict_candidate_probabilities(candidate, holdout)
            score_frames.append(
                _base_score_frame(
                    holdout,
                    target=target,
                    model_family=candidate.candidate_model,
                    candidate_type=ML_CANDIDATE_TYPE,
                    mlflow_run_id=candidate.run_id,
                    model_artifact_uri=candidate.model_artifact_uri,
                    score_source=ML_SCORE_SOURCE,
                    score=probabilities,
                )
            )

        baseline_scores = _baseline_scores_for_holdout(
            holdout,
            baselines,
            target=target,
        )
        score_frames.append(
            _base_score_frame(
                holdout,
                target=target,
                model_family="rule_baseline",
                candidate_type=BASELINE_CANDIDATE_TYPE,
                mlflow_run_id=None,
                model_artifact_uri=None,
                score_source=BASELINE_SCORE_SOURCE,
                score=baseline_scores,
            )
        )

    if not score_frames:
        raise EvaluationMetricError("Package 6 found no candidates to score")
    return pd.concat(score_frames, ignore_index=True)


def evaluate_overall_metrics(
    score_frame: pd.DataFrame,
    *,
    top_k_percentages: Iterable[float] = DEFAULT_TOP_K_PERCENTAGES,
    top_k_counts: Iterable[int] = DEFAULT_TOP_K_COUNTS,
) -> tuple[MetricRecord, ...]:
    """Compute overall fixed-holdout metrics for ML candidates and baselines."""

    _validate_score_frame(score_frame)
    records: list[MetricRecord] = []
    for _, group in _score_groups(score_frame):
        records.extend(
            _standard_metric_records(
                group,
                slice_type=OVERALL_SLICE_TYPE,
                slice_value=FIXED_HOLDOUT_SLICE_VALUE,
            )
        )
        records.extend(
            _top_k_metric_records(
                group,
                slice_type=OVERALL_SLICE_TYPE,
                slice_value=FIXED_HOLDOUT_SLICE_VALUE,
                top_k_percentages=top_k_percentages,
                top_k_counts=top_k_counts,
            )
        )
    return tuple(records)


def select_top_k_rows(score_frame: pd.DataFrame, *, k_count: int) -> pd.DataFrame:
    """Select top-K rows with deterministic account-month tie-breaking."""

    if k_count <= 0:
        raise EvaluationMetricError("Package 6 top-K count must be positive")
    sorted_frame = score_frame.sort_values(
        ["score", "account_id", "observation_month"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    return sorted_frame.head(k_count).copy()


def _target_train_end_month(candidates, *, target: str) -> pd.Timestamp:
    train_end_months = {candidate.train_end_month for candidate in candidates}
    if len(train_end_months) != 1:
        raise EvaluationMetricError(
            f"Package 6 requires one fixed holdout boundary for target={target}"
        )
    return next(iter(train_end_months))


def _predict_candidate_probabilities(candidate, holdout: pd.DataFrame) -> np.ndarray:
    missing_features = tuple(
        feature for feature in candidate.feature_names if feature not in holdout.columns
    )
    if missing_features:
        raise EvaluationMetricError(
            f"Package 6 cannot score run_id={candidate.run_id}; missing "
            "feature column(s): "
            + ", ".join(missing_features)
        )

    probabilities = candidate.model.predict_proba(holdout.loc[:, candidate.feature_names])
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 2 or probabilities.shape[1] < 2:
        raise EvaluationMetricError(
            f"Package 5 model for run_id={candidate.run_id} returned invalid "
            "predict_proba output"
        )
    return _validate_scores(probabilities[:, 1], score_name="ML probabilities")


def _baseline_scores_for_holdout(
    holdout: pd.DataFrame,
    baselines: pd.DataFrame,
    *,
    target: str,
) -> np.ndarray:
    baseline_score_column = BASELINE_SCORE_COLUMNS[target]
    joined = holdout[["account_id", "observation_month"]].merge(
        baselines[["account_id", "observation_month", baseline_score_column]],
        on=["account_id", "observation_month"],
        how="left",
        validate="one_to_one",
    )
    if joined[baseline_score_column].isna().any():
        raise EvaluationMetricError(
            "Package 6 baseline join is missing account-month rows for "
            f"target={target}"
        )
    return _validate_scores(
        joined[baseline_score_column].to_numpy(),
        score_name=f"{baseline_score_column} ranking scores",
        require_probability_bounds=False,
    )


def _base_score_frame(
    holdout: pd.DataFrame,
    *,
    target: str,
    model_family: str,
    candidate_type: str,
    mlflow_run_id: str | None,
    model_artifact_uri: str | None,
    score_source: str,
    score: np.ndarray,
) -> pd.DataFrame:
    carry_columns = [
        "account_id",
        "observation_month",
        *[field for field in SEGMENT_FIELDS if field in holdout.columns],
    ]
    frame = holdout.loc[:, carry_columns].copy()
    frame["target"] = target
    frame["model_family"] = model_family
    frame["candidate_type"] = candidate_type
    frame["mlflow_run_id"] = mlflow_run_id
    frame["model_artifact_uri"] = model_artifact_uri
    frame["score_source"] = score_source
    frame["label"] = holdout[target].astype(int).to_numpy()
    frame["score"] = score
    return frame


def _standard_metric_records(
    group: pd.DataFrame,
    *,
    slice_type: str,
    slice_value: str,
) -> list[MetricRecord]:
    labels = group["label"].astype(int).to_numpy()
    scores = group["score"].astype(float).to_numpy()
    row_count, positive_count, base_positive_rate = _label_summary(labels)
    if len(set(labels)) < 2:
        return []

    records = [
        _metric_record(
            group,
            metric_name="roc_auc",
            metric_value=float(roc_auc_score(labels, scores)),
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_positive_rate,
        ),
        _metric_record(
            group,
            metric_name="average_precision",
            metric_value=float(average_precision_score(labels, scores)),
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_positive_rate,
        ),
    ]
    if _group_value(group, "candidate_type") == ML_CANDIDATE_TYPE:
        predictions = (scores >= 0.5).astype(int)
        records.extend(
            [
                _metric_record(
                    group,
                    metric_name="log_loss",
                    metric_value=float(log_loss(labels, scores, labels=[0, 1])),
                    slice_type=slice_type,
                    slice_value=slice_value,
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_positive_rate,
                ),
                _metric_record(
                    group,
                    metric_name="brier_score",
                    metric_value=float(brier_score_loss(labels, scores)),
                    slice_type=slice_type,
                    slice_value=slice_value,
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_positive_rate,
                ),
                _metric_record(
                    group,
                    metric_name="accuracy",
                    metric_value=float(accuracy_score(labels, predictions)),
                    slice_type=slice_type,
                    slice_value=slice_value,
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_positive_rate,
                ),
            ]
        )
    return records


def _top_k_metric_records(
    group: pd.DataFrame,
    *,
    slice_type: str,
    slice_value: str,
    top_k_percentages: Iterable[float],
    top_k_counts: Iterable[int],
) -> list[MetricRecord]:
    records: list[MetricRecord] = []
    row_count = len(group)
    for percentage in top_k_percentages:
        if percentage <= 0 or percentage > 1:
            raise EvaluationMetricError("Package 6 top-K percentage must be in (0, 1]")
        k_count = max(1, int(ceil(row_count * percentage)))
        records.extend(
            _top_k_records_for_count(
                group,
                k_count=k_count,
                k_value=float(percentage),
                k_type="percent",
                slice_type=slice_type,
                slice_value=slice_value,
            )
        )
    for count in top_k_counts:
        if row_count >= count:
            records.extend(
                _top_k_records_for_count(
                    group,
                    k_count=int(count),
                    k_value=int(count),
                    k_type="count",
                    slice_type=slice_type,
                    slice_value=slice_value,
                )
            )
    return records


def _top_k_records_for_count(
    group: pd.DataFrame,
    *,
    k_count: int,
    k_value: float | int,
    k_type: str,
    slice_type: str,
    slice_value: str,
) -> list[MetricRecord]:
    labels = group["label"].astype(int).to_numpy()
    row_count, positive_count, base_positive_rate = _label_summary(labels)
    selected = select_top_k_rows(group, k_count=k_count)
    selected_positive_count = int(selected["label"].astype(int).sum())
    accounts_selected = len(selected)
    precision = (
        selected_positive_count / accounts_selected
        if accounts_selected
        else None
    )
    recall = selected_positive_count / positive_count if positive_count else None
    lift = (
        precision / base_positive_rate
        if precision is not None and base_positive_rate
        else None
    )
    metric_values: dict[str, float | int | None] = {
        "accounts_selected": accounts_selected,
        "positives_captured": selected_positive_count,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "lift_at_k": lift,
        "capture_rate_at_k": recall,
        "base_positive_rate": base_positive_rate,
    }
    return [
        _metric_record(
            group,
            metric_name=metric_name,
            metric_value=None if metric_value is None else float(metric_value),
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_positive_rate,
            k_value=k_value,
            k_type=k_type,
        )
        for metric_name, metric_value in metric_values.items()
    ]


def _metric_record(
    group: pd.DataFrame,
    *,
    metric_name: str,
    metric_value: float | None,
    slice_type: str,
    slice_value: str,
    row_count: int,
    positive_count: int,
    base_positive_rate: float | None,
    k_value: float | int | None = None,
    k_type: str | None = None,
) -> MetricRecord:
    return MetricRecord(
        target=_group_value(group, "target"),
        model_family=_group_value(group, "model_family"),
        candidate_type=_group_value(group, "candidate_type"),
        mlflow_run_id=_optional_group_value(group, "mlflow_run_id"),
        model_artifact_uri=_optional_group_value(group, "model_artifact_uri"),
        score_source=_group_value(group, "score_source"),
        metric_name=metric_name,
        metric_value=metric_value,
        slice_type=slice_type,
        slice_value=slice_value,
        row_count=row_count,
        positive_count=positive_count,
        base_positive_rate=base_positive_rate,
        k_value=k_value,
        k_type=k_type,
    )


def _score_groups(score_frame: pd.DataFrame):
    group_columns = [
        "target",
        "model_family",
        "candidate_type",
        "mlflow_run_id",
        "model_artifact_uri",
        "score_source",
    ]
    return score_frame.groupby(group_columns, dropna=False, sort=False)


def _label_summary(labels: np.ndarray) -> tuple[int, int, float | None]:
    row_count = int(len(labels))
    positive_count = int(labels.sum())
    base_positive_rate = positive_count / row_count if row_count else None
    return row_count, positive_count, base_positive_rate


def _validate_score_frame(score_frame: pd.DataFrame) -> None:
    required_columns = {
        "account_id",
        "observation_month",
        "target",
        "model_family",
        "candidate_type",
        "mlflow_run_id",
        "model_artifact_uri",
        "score_source",
        "label",
        "score",
    }
    missing_columns = tuple(
        column for column in required_columns if column not in set(score_frame.columns)
    )
    if missing_columns:
        raise EvaluationMetricError(
            "Package 6 score frame missing column(s): " + ", ".join(missing_columns)
        )
    _validate_binary_labels(score_frame["label"], target="score_frame")
    _validate_scores(
        score_frame["score"].to_numpy(),
        score_name="scores",
        require_probability_bounds=False,
    )
    ml_score_mask = score_frame["candidate_type"] == ML_CANDIDATE_TYPE
    if ml_score_mask.any():
        _validate_scores(
            score_frame.loc[ml_score_mask, "score"].to_numpy(),
            score_name="ML probabilities",
        )


def _validate_binary_labels(values: pd.Series, *, target: str) -> None:
    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.isna().any() or not numeric_values.isin([0, 1]).all():
        raise EvaluationMetricError(
            f"Package 6 fixed holdout labels must be binary for target={target}"
        )


def _validate_scores(
    values,
    *,
    score_name: str,
    require_probability_bounds: bool = True,
) -> np.ndarray:
    try:
        scores = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as error:
        raise EvaluationMetricError(f"Package 6 {score_name} must be numeric") from error
    if scores.ndim != 1 or scores.size == 0:
        raise EvaluationMetricError(f"Package 6 {score_name} must be a non-empty vector")
    if not np.isfinite(scores).all():
        raise EvaluationMetricError(f"Package 6 {score_name} must be finite")
    if require_probability_bounds and ((scores < 0).any() or (scores > 1).any()):
        raise EvaluationMetricError(
            f"Package 6 {score_name} must be bounded between 0 and 1"
        )
    return scores


def _group_value(group: pd.DataFrame, column: str) -> str:
    value = group[column].iloc[0]
    return str(value)


def _optional_group_value(group: pd.DataFrame, column: str) -> str | None:
    value = group[column].iloc[0]
    if pd.isna(value):
        return None
    return str(value)
