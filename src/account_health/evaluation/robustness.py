"""Calibration, segment, and holdout-month robustness checks for Package 6."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from account_health.evaluation.loading import SEGMENT_FIELDS
from account_health.evaluation.metrics import (
    BASELINE_CANDIDATE_TYPE,
    ML_CANDIDATE_TYPE,
    MetricRecord,
    select_top_k_rows,
)

DEFAULT_CALIBRATION_BIN_COUNT = 10
DEFAULT_MIN_ROBUSTNESS_SUPPORT = 10
DEFAULT_ROBUSTNESS_TOP_K_PERCENTAGE = 0.10


@dataclass(frozen=True)
class CaveatRecord:
    """A target-specific caveat emitted instead of misleading slice metrics."""

    target: str
    model_family: str
    candidate_type: str
    slice_type: str
    slice_value: str
    caveat: str

    def to_dict(self) -> dict[str, str]:
        return {
            "target": self.target,
            "model_family": self.model_family,
            "candidate_type": self.candidate_type,
            "slice_type": self.slice_type,
            "slice_value": self.slice_value,
            "caveat": self.caveat,
        }


def compute_calibration_metrics(
    score_frame: pd.DataFrame,
    *,
    bin_count: int = DEFAULT_CALIBRATION_BIN_COUNT,
    min_bin_size: int = DEFAULT_MIN_ROBUSTNESS_SUPPORT,
) -> tuple[tuple[MetricRecord, ...], tuple[CaveatRecord, ...]]:
    """Compute ML-only calibration bins and sparse-bin caveats."""

    if bin_count <= 1:
        raise ValueError("Package 6 calibration bin_count must be greater than 1")

    records: list[MetricRecord] = []
    caveats: list[CaveatRecord] = []
    ml_scores = score_frame[score_frame["candidate_type"] == ML_CANDIDATE_TYPE]
    for _, group in _score_groups(ml_scores):
        probabilities = group["score"].astype(float)
        if not probabilities.between(0, 1).all():
            raise ValueError("Package 6 ML calibration requires probabilities")
        binned = group.copy()
        binned["calibration_bin"] = pd.cut(
            probabilities,
            bins=np.linspace(0.0, 1.0, bin_count + 1),
            labels=False,
            include_lowest=True,
        )
        for bin_index, bin_frame in binned.groupby("calibration_bin", sort=True):
            if pd.isna(bin_index):
                continue
            bin_number = int(bin_index) + 1
            slice_value = f"bin_{bin_number:02d}_of_{bin_count}"
            labels = bin_frame["label"].astype(int)
            row_count = int(len(bin_frame))
            positive_count = int(labels.sum())
            base_rate = _safe_rate(positive_count, row_count)
            records.extend(
                [
                    _metric_record(
                        bin_frame,
                        metric_name="calibration_mean_predicted_rate",
                        metric_value=float(bin_frame["score"].mean()),
                        slice_type="calibration_bin",
                        slice_value=slice_value,
                        row_count=row_count,
                        positive_count=positive_count,
                        base_positive_rate=base_rate,
                    ),
                    _metric_record(
                        bin_frame,
                        metric_name="calibration_observed_positive_rate",
                        metric_value=base_rate,
                        slice_type="calibration_bin",
                        slice_value=slice_value,
                        row_count=row_count,
                        positive_count=positive_count,
                        base_positive_rate=base_rate,
                    ),
                    _metric_record(
                        bin_frame,
                        metric_name="calibration_bin_row_count",
                        metric_value=float(row_count),
                        slice_type="calibration_bin",
                        slice_value=slice_value,
                        row_count=row_count,
                        positive_count=positive_count,
                        base_positive_rate=base_rate,
                    ),
                    _metric_record(
                        bin_frame,
                        metric_name="calibration_bin_positive_count",
                        metric_value=float(positive_count),
                        slice_type="calibration_bin",
                        slice_value=slice_value,
                        row_count=row_count,
                        positive_count=positive_count,
                        base_positive_rate=base_rate,
                    ),
                ]
            )
            if row_count < min_bin_size:
                caveats.append(
                    _caveat(
                        bin_frame,
                        slice_type="calibration_bin",
                        slice_value=slice_value,
                        caveat="sparse_calibration_bin",
                    )
                )
    return tuple(records), tuple(caveats)


def compute_segment_robustness(
    score_frame: pd.DataFrame,
    *,
    segment_fields: Iterable[str] = SEGMENT_FIELDS,
    min_support: int = DEFAULT_MIN_ROBUSTNESS_SUPPORT,
    top_k_percentage: float = DEFAULT_ROBUSTNESS_TOP_K_PERCENTAGE,
) -> tuple[tuple[MetricRecord, ...], tuple[CaveatRecord, ...]]:
    """Compute segment slice ranking and capacity metrics with caveats."""

    records: list[MetricRecord] = []
    caveats: list[CaveatRecord] = []
    requested_fields = tuple(segment_fields)
    unsupported_fields = tuple(
        field for field in requested_fields if field not in SEGMENT_FIELDS
    )
    if unsupported_fields:
        raise ValueError(
            "Package 6 segment robustness may only use approved segment "
            "column(s): "
            + ", ".join(SEGMENT_FIELDS)
        )
    missing_fields = tuple(
        field for field in requested_fields if field not in score_frame.columns
    )
    if missing_fields:
        raise ValueError(
            "Package 6 segment robustness missing column(s): "
            + ", ".join(missing_fields)
        )
    for _, group in _score_groups(score_frame):
        for field in requested_fields:
            for value, slice_frame in group.groupby(field, dropna=False, sort=True):
                slice_value = f"{field}={_format_slice_value(value)}"
                slice_records, slice_caveats = _robustness_slice_records(
                    slice_frame,
                    slice_type="segment",
                    slice_value=slice_value,
                    min_support=min_support,
                    top_k_percentage=top_k_percentage,
                )
                records.extend(slice_records)
                caveats.extend(slice_caveats)
    return tuple(records), tuple(caveats)


def compute_holdout_month_robustness(
    score_frame: pd.DataFrame,
    *,
    min_support: int = DEFAULT_MIN_ROBUSTNESS_SUPPORT,
    top_k_percentage: float = DEFAULT_ROBUSTNESS_TOP_K_PERCENTAGE,
) -> tuple[tuple[MetricRecord, ...], tuple[CaveatRecord, ...]]:
    """Compute fixed-holdout month slices without rolling retraining."""

    records: list[MetricRecord] = []
    caveats: list[CaveatRecord] = []
    frame = score_frame.copy()
    frame["observation_month"] = pd.to_datetime(frame["observation_month"])
    for _, group in _score_groups(frame):
        for month, slice_frame in group.groupby("observation_month", sort=True):
            slice_value = pd.Timestamp(month).date().isoformat()
            slice_records, slice_caveats = _robustness_slice_records(
                slice_frame,
                slice_type="holdout_month",
                slice_value=slice_value,
                min_support=min_support,
                top_k_percentage=top_k_percentage,
            )
            records.extend(slice_records)
            caveats.extend(slice_caveats)
            caveats.append(
                _caveat(
                    slice_frame,
                    slice_type="holdout_month",
                    slice_value=slice_value,
                    caveat="fixed_holdout_month_slice_not_rolling_backtest",
                )
            )
    return tuple(records), tuple(caveats)


def _robustness_slice_records(
    slice_frame: pd.DataFrame,
    *,
    slice_type: str,
    slice_value: str,
    min_support: int,
    top_k_percentage: float,
) -> tuple[list[MetricRecord], list[CaveatRecord]]:
    labels = slice_frame["label"].astype(int).to_numpy()
    row_count = int(len(slice_frame))
    positive_count = int(labels.sum())
    base_rate = _safe_rate(positive_count, row_count)
    records = [
        _metric_record(
            slice_frame,
            metric_name="slice_row_count",
            metric_value=float(row_count),
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_rate,
        ),
        _metric_record(
            slice_frame,
            metric_name="slice_positive_count",
            metric_value=float(positive_count),
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_rate,
        ),
        _metric_record(
            slice_frame,
            metric_name="slice_base_positive_rate",
            metric_value=base_rate,
            slice_type=slice_type,
            slice_value=slice_value,
            row_count=row_count,
            positive_count=positive_count,
            base_positive_rate=base_rate,
        ),
    ]
    caveats: list[CaveatRecord] = []
    if len(set(labels)) < 2:
        caveats.append(
            _caveat(
                slice_frame,
                slice_type=slice_type,
                slice_value=slice_value,
                caveat="one_class_slice_auc_skipped",
            )
        )
    else:
        records.extend(
            [
                _metric_record(
                    slice_frame,
                    metric_name="roc_auc",
                    metric_value=float(roc_auc_score(labels, slice_frame["score"])),
                    slice_type=slice_type,
                    slice_value=slice_value,
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_rate,
                ),
                _metric_record(
                    slice_frame,
                    metric_name="average_precision",
                    metric_value=float(
                        average_precision_score(labels, slice_frame["score"])
                    ),
                    slice_type=slice_type,
                    slice_value=slice_value,
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_rate,
                ),
            ]
        )

    if row_count < min_support:
        caveats.append(
            _caveat(
                slice_frame,
                slice_type=slice_type,
                slice_value=slice_value,
                caveat="low_support_slice_topk_skipped",
            )
        )
        return records, caveats

    if positive_count == 0:
        caveats.append(
            _caveat(
                slice_frame,
                slice_type=slice_type,
                slice_value=slice_value,
                caveat="zero_positive_slice_capture_caveated",
            )
        )
        return records, caveats

    k_count = max(1, int(ceil(row_count * top_k_percentage)))
    selected = select_top_k_rows(slice_frame, k_count=k_count)
    selected_positive_count = int(selected["label"].astype(int).sum())
    precision = _safe_rate(selected_positive_count, len(selected))
    recall = _safe_rate(selected_positive_count, positive_count)
    lift = precision / base_rate if precision is not None and base_rate else None
    for metric_name, metric_value in {
        "accounts_selected": len(selected),
        "positives_captured": selected_positive_count,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "lift_at_k": lift,
        "capture_rate_at_k": recall,
    }.items():
        records.append(
            _metric_record(
                slice_frame,
                metric_name=metric_name,
                metric_value=None if metric_value is None else float(metric_value),
                slice_type=slice_type,
                slice_value=slice_value,
                row_count=row_count,
                positive_count=positive_count,
                base_positive_rate=base_rate,
                k_value=float(top_k_percentage),
                k_type="percent",
            )
        )
    return records, caveats


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
        target=str(group["target"].iloc[0]),
        model_family=str(group["model_family"].iloc[0]),
        candidate_type=str(group["candidate_type"].iloc[0]),
        mlflow_run_id=_optional_value(group["mlflow_run_id"].iloc[0]),
        model_artifact_uri=_optional_value(group["model_artifact_uri"].iloc[0]),
        score_source=str(group["score_source"].iloc[0]),
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


def _caveat(
    group: pd.DataFrame,
    *,
    slice_type: str,
    slice_value: str,
    caveat: str,
) -> CaveatRecord:
    return CaveatRecord(
        target=str(group["target"].iloc[0]),
        model_family=str(group["model_family"].iloc[0]),
        candidate_type=str(group["candidate_type"].iloc[0]),
        slice_type=slice_type,
        slice_value=slice_value,
        caveat=caveat,
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


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return float(numerator / denominator)


def _optional_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    return str(value)


def _format_slice_value(value: object) -> str:
    if pd.isna(value):
        return "missing"
    return str(value)
