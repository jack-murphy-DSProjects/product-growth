"""Local MLflow orchestration for Package 5 candidate training."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd

from account_health.modeling.candidates import (
    SUPPORTED_CANDIDATE_MODELS,
    train_candidate_model,
)
from account_health.modeling.dataset import TARGET_COLUMNS, load_modeling_dataset
from account_health.modeling.split import TemporalSplit, split_modeling_dataset
from account_health.warehouse import DEFAULT_DATABASE_PATH

DEFAULT_EXPERIMENT_NAME = "account-health-candidate-training"
LOCAL_MLFLOW_TRACKING_URI_SCHEMES = ("", "file", "sqlite")


@dataclass(frozen=True)
class CandidateRunSummary:
    """Summary of one logged Package 5 candidate run."""

    target: str
    candidate_model: str
    run_id: str
    train_end_month: pd.Timestamp
    metrics: dict[str, float]
    train_row_count: int
    test_row_count: int
    train_positive_rate: float
    test_positive_rate: float


@dataclass(frozen=True)
class CandidateTrainingOrchestrationResult:
    """Summary of a local Package 5 MLflow training invocation."""

    experiment_name: str
    mlflow_tracking_uri: str | None
    runs: tuple[CandidateRunSummary, ...]


class ModelingTrainingError(ValueError):
    """Raised when Package 5 training orchestration violates its contract."""


def train_candidate_models(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    train_end_month: str | date | pd.Timestamp | None = None,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    mlflow_tracking_uri: str | None = None,
    random_state: int = 42,
    targets: Iterable[str] = TARGET_COLUMNS,
    candidate_models: Iterable[str] = SUPPORTED_CANDIDATE_MODELS,
) -> CandidateTrainingOrchestrationResult:
    """Train approved candidates and log one local MLflow run for each."""

    import mlflow

    active_tracking_uri = (
        mlflow_tracking_uri
        if mlflow_tracking_uri is not None
        else mlflow.get_tracking_uri()
    )
    _validate_local_mlflow_tracking_uri(active_tracking_uri)
    if mlflow_tracking_uri is not None:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    run_summaries: list[CandidateRunSummary] = []
    for target in targets:
        dataset = load_modeling_dataset(database_path, target=target)
        split = split_modeling_dataset(dataset, train_end_month=train_end_month)

        for candidate_model in candidate_models:
            run_summaries.append(
                _train_and_log_run(
                    split,
                    candidate_model=candidate_model,
                    experiment_name=experiment_name,
                    random_state=random_state,
                    source_table=dataset.source_table,
                )
            )

    return CandidateTrainingOrchestrationResult(
        experiment_name=experiment_name,
        mlflow_tracking_uri=mlflow_tracking_uri,
        runs=tuple(run_summaries),
    )


def _train_and_log_run(
    split: TemporalSplit,
    *,
    candidate_model: str,
    experiment_name: str,
    random_state: int,
    source_table: str,
) -> CandidateRunSummary:
    import mlflow
    import mlflow.sklearn

    run_name = f"{split.target}_{candidate_model}"
    with mlflow.start_run(run_name=run_name) as run:
        training_result = train_candidate_model(
            split,
            candidate_model=candidate_model,
            random_state=random_state,
        )
        split_config = _split_config(split)
        feature_lists = _feature_lists(split)
        train_positive_rate = _positive_rate(split.train_frame, split.target)
        test_positive_rate = _positive_rate(split.test_frame, split.target)

        mlflow.log_params(
            {
                "experiment_name": experiment_name,
                "source_table": source_table,
                "target": split.target,
                "candidate_model": candidate_model,
                "train_end_month": split.train_end_month.date().isoformat(),
                "random_state": random_state,
                "feature_count": len(split.feature_names),
                "numeric_feature_count": len(split.numeric_features),
                "categorical_feature_count": len(split.categorical_features),
                "train_observation_month_min": split_config[
                    "train_observation_month_min"
                ],
                "train_observation_month_max": split_config[
                    "train_observation_month_max"
                ],
                "test_observation_month_min": split_config[
                    "test_observation_month_min"
                ],
                "test_observation_month_max": split_config[
                    "test_observation_month_max"
                ],
            }
        )
        mlflow.log_metrics(training_result.metrics)
        mlflow.log_metrics(
            {
                "train_row_count": float(len(split.train_frame)),
                "test_row_count": float(len(split.test_frame)),
                "train_positive_rate": train_positive_rate,
                "test_positive_rate": test_positive_rate,
            }
        )
        mlflow.log_dict(feature_lists, "features.json")
        mlflow.log_dict(split_config, "split_config.json")
        with TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "model"
            mlflow.sklearn.save_model(training_result.pipeline, path=str(model_path))
            mlflow.log_artifacts(str(model_path), artifact_path="model")

        return CandidateRunSummary(
            target=split.target,
            candidate_model=candidate_model,
            run_id=run.info.run_id,
            train_end_month=split.train_end_month,
            metrics=training_result.metrics,
            train_row_count=len(split.train_frame),
            test_row_count=len(split.test_frame),
            train_positive_rate=train_positive_rate,
            test_positive_rate=test_positive_rate,
        )


def _feature_lists(split: TemporalSplit) -> dict[str, list[str]]:
    return {
        "approved_features": list(split.feature_names),
        "numeric_features": list(split.numeric_features),
        "categorical_features": list(split.categorical_features),
    }


def _split_config(split: TemporalSplit) -> dict[str, str | int]:
    return {
        "train_end_month": split.train_end_month.date().isoformat(),
        "train_row_count": len(split.train_frame),
        "test_row_count": len(split.test_frame),
        "train_observation_month_min": _month_bound(
            split.train_frame,
            "min",
        ),
        "train_observation_month_max": _month_bound(
            split.train_frame,
            "max",
        ),
        "test_observation_month_min": _month_bound(
            split.test_frame,
            "min",
        ),
        "test_observation_month_max": _month_bound(
            split.test_frame,
            "max",
        ),
    }


def _month_bound(frame: pd.DataFrame, aggregation: str) -> str:
    value = getattr(frame["observation_month"], aggregation)()
    return pd.Timestamp(value).date().isoformat()


def _positive_rate(frame: pd.DataFrame, target: str) -> float:
    return float(frame[target].astype(int).mean())


def _validate_local_mlflow_tracking_uri(mlflow_tracking_uri: str) -> None:
    parsed_uri = urlparse(mlflow_tracking_uri)
    if parsed_uri.scheme not in LOCAL_MLFLOW_TRACKING_URI_SCHEMES:
        raise ModelingTrainingError(
            "Package 5 MLflow tracking must remain local; "
            f"unsupported tracking URI scheme: {parsed_uri.scheme}"
        )
    if (
        parsed_uri.scheme == "file"
        and parsed_uri.netloc not in {"", "localhost"}
    ):
        raise ModelingTrainingError(
            "Package 5 MLflow file tracking URI must point to a local path"
        )
