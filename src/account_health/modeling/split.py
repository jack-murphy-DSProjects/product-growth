"""Temporal train/test splitting for Package 5 modelling datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from account_health.modeling.dataset import ModelingDataset


@dataclass(frozen=True)
class TemporalSplit:
    """Deterministic time split for one target-specific modelling dataset."""

    target: str
    train_end_month: pd.Timestamp
    train_frame: pd.DataFrame
    test_frame: pd.DataFrame
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (*self.numeric_features, *self.categorical_features)


class ModelingSplitError(ValueError):
    """Raised when a modelling dataset cannot be split temporally."""


def split_modeling_dataset(
    dataset: ModelingDataset,
    *,
    train_end_month: str | date | pd.Timestamp | None = None,
) -> TemporalSplit:
    """Split rows by `observation_month` using a fixed temporal boundary."""

    frame = dataset.frame.copy()
    _validate_observation_months(frame)
    resolved_train_end_month = _resolve_train_end_month(
        frame,
        train_end_month=train_end_month,
    )

    train_frame = frame[
        frame["observation_month"] <= resolved_train_end_month
    ].copy()
    test_frame = frame[
        frame["observation_month"] > resolved_train_end_month
    ].copy()

    if train_frame.empty:
        raise ModelingSplitError("Package 5 temporal split produced empty train rows")
    if test_frame.empty:
        raise ModelingSplitError("Package 5 temporal split produced empty test rows")

    _validate_both_classes(train_frame, dataset.target, side="train")
    _validate_both_classes(test_frame, dataset.target, side="test")

    return TemporalSplit(
        target=dataset.target,
        train_end_month=resolved_train_end_month,
        train_frame=train_frame,
        test_frame=test_frame,
        numeric_features=dataset.numeric_features,
        categorical_features=dataset.categorical_features,
    )


def _resolve_train_end_month(
    frame: pd.DataFrame,
    *,
    train_end_month: str | date | pd.Timestamp | None,
) -> pd.Timestamp:
    if train_end_month is not None:
        resolved = pd.Timestamp(train_end_month).normalize()
    else:
        max_observation_month = frame["observation_month"].max()
        resolved = max_observation_month - pd.DateOffset(months=3)

    if resolved.day != 1:
        raise ModelingSplitError(
            "Package 5 train_end_month must be the first day of a calendar month"
        )
    return resolved


def _validate_observation_months(frame: pd.DataFrame) -> None:
    if "observation_month" not in frame.columns:
        raise ModelingSplitError("Package 5 split requires observation_month")

    frame["observation_month"] = pd.to_datetime(frame["observation_month"])
    if frame["observation_month"].isna().any():
        raise ModelingSplitError("Package 5 observation_month contains null values")
    if not (frame["observation_month"].dt.day == 1).all():
        raise ModelingSplitError(
            "Package 5 observation_month must be the first day of a calendar month"
        )


def _validate_both_classes(frame: pd.DataFrame, target: str, *, side: str) -> None:
    target_values = pd.to_numeric(frame[target].dropna(), errors="coerce")
    if target_values.isna().any() or not target_values.isin([0, 1]).all():
        raise ModelingSplitError(
            f"Package 5 temporal split produced non-binary {side} target"
        )

    unique_values = set(target_values.astype(int).unique())
    if unique_values != {0, 1}:
        raise ModelingSplitError(
            f"Package 5 temporal split produced single-class {side} target"
        )
