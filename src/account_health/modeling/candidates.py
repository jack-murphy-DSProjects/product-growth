"""Candidate scikit-learn pipelines and validation metrics for Package 5."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from account_health.modeling.split import TemporalSplit

LOGISTIC_REGRESSION = "logistic_regression"
RANDOM_FOREST = "random_forest"
SUPPORTED_CANDIDATE_MODELS: tuple[str, ...] = (
    LOGISTIC_REGRESSION,
    RANDOM_FOREST,
)

REQUIRED_METRIC_KEYS: set[str] = {
    "roc_auc",
    "average_precision",
    "log_loss",
    "brier_score",
    "accuracy",
    "precision_at_top_10_pct",
}


@dataclass(frozen=True)
class CandidateTrainingResult:
    """Fitted candidate model and validation metrics."""

    candidate_model: str
    pipeline: Pipeline
    metrics: dict[str, float]
    test_probabilities: np.ndarray


class ModelingCandidateError(ValueError):
    """Raised when Package 5 candidate construction or evaluation fails."""


def build_candidate_pipeline(
    candidate_model: str,
    *,
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
    random_state: int = 42,
) -> Pipeline:
    """Build one approved Package 5 candidate pipeline."""

    if candidate_model not in SUPPORTED_CANDIDATE_MODELS:
        raise ModelingCandidateError(
            f"unsupported Package 5 candidate model: {candidate_model}"
        )

    include_scaler = candidate_model == LOGISTIC_REGRESSION
    preprocessor = _build_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        include_scaler=include_scaler,
    )

    if candidate_model == LOGISTIC_REGRESSION:
        classifier = LogisticRegression(
            max_iter=1000,
            random_state=random_state,
            solver="liblinear",
        )
    else:
        classifier = RandomForestClassifier(
            n_estimators=100,
            min_samples_leaf=1,
            random_state=random_state,
        )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def train_candidate_model(
    split: TemporalSplit,
    *,
    candidate_model: str,
    random_state: int = 42,
) -> CandidateTrainingResult:
    """Fit one approved candidate and evaluate it on the temporal test split."""

    pipeline = build_candidate_pipeline(
        candidate_model,
        numeric_features=split.numeric_features,
        categorical_features=split.categorical_features,
        random_state=random_state,
    )

    feature_names = split.feature_names
    x_train = split.train_frame.loc[:, feature_names]
    y_train = split.train_frame.loc[:, split.target].astype(int)
    x_test = split.test_frame.loc[:, feature_names]
    y_test = split.test_frame.loc[:, split.target].astype(int)

    pipeline.fit(x_train, y_train)
    probabilities = pipeline.predict_proba(x_test)[:, 1]
    metrics = evaluate_binary_metrics(y_test.to_numpy(), probabilities)

    return CandidateTrainingResult(
        candidate_model=candidate_model,
        pipeline=pipeline,
        metrics=metrics,
        test_probabilities=probabilities,
    )


def evaluate_binary_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, float]:
    """Return simple Package 5 validation metrics for binary probabilities."""

    y_true, probabilities = _validate_binary_metric_inputs(y_true, probabilities)
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(average_precision_score(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision_at_top_10_pct": float(
            _precision_at_top_fraction(y_true, probabilities, fraction=0.10)
        ),
    }


def _validate_binary_metric_inputs(
    y_true: np.ndarray,
    probabilities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    try:
        labels = np.asarray(y_true, dtype=float)
    except (TypeError, ValueError) as error:
        raise ModelingCandidateError(
            "metric labels must be numeric and binary"
        ) from error

    try:
        predicted_probabilities = np.asarray(probabilities, dtype=float)
    except (TypeError, ValueError) as error:
        raise ModelingCandidateError("metric probabilities must be numeric") from error

    if labels.ndim != 1 or predicted_probabilities.ndim != 1:
        raise ModelingCandidateError("metric labels and probabilities must be 1-D")
    if labels.size == 0:
        raise ModelingCandidateError("metric labels must not be empty")
    if labels.shape != predicted_probabilities.shape:
        raise ModelingCandidateError(
            "metric labels and probabilities must have the same length"
        )
    if not np.isfinite(labels).all():
        raise ModelingCandidateError("metric labels must be finite")
    if not np.isin(labels, [0, 1]).all():
        raise ModelingCandidateError("metric labels must be binary")
    if set(labels.astype(int)) != {0, 1}:
        raise ModelingCandidateError("metric labels must contain both classes")
    if not np.isfinite(predicted_probabilities).all():
        raise ModelingCandidateError("metric probabilities must be finite")
    if (
        (predicted_probabilities < 0).any()
        or (predicted_probabilities > 1).any()
    ):
        raise ModelingCandidateError(
            "metric probabilities must be bounded between 0 and 1"
        )

    return labels.astype(int), predicted_probabilities


def _build_preprocessor(
    *,
    numeric_features: tuple[str, ...],
    categorical_features: tuple[str, ...],
    include_scaler: bool,
) -> ColumnTransformer:
    numeric_steps: list[tuple[str, object]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if include_scaler:
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_pipeline = Pipeline(steps=numeric_steps)
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot_encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, list(numeric_features)),
            ("categorical", categorical_pipeline, list(categorical_features)),
        ],
        remainder="drop",
    )


def _precision_at_top_fraction(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    fraction: float,
) -> float:
    row_count = len(probabilities)
    top_count = max(1, int(ceil(row_count * fraction)))
    top_indices = np.argsort(probabilities)[::-1][:top_count]
    top_predictions = np.zeros(row_count, dtype=int)
    top_predictions[top_indices] = 1
    return precision_score(y_true, top_predictions, zero_division=0)
