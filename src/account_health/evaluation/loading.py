"""Load Package 6 evaluation inputs without scoring or retraining."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import unquote, urlparse

import duckdb
import pandas as pd

from account_health.baselines import BASELINE_OUTPUT_TABLE
from account_health.modeling import (
    DEFAULT_EXPERIMENT_NAME,
    DEFAULT_MODELING_FEATURE_SET,
    MODELING_SOURCE_TABLE,
    SUPPORTED_CANDIDATE_MODELS,
    TARGET_COLUMNS,
    ModelingDatasetError,
    ModelingFeatureSet,
    validate_modeling_feature_set,
    validate_modeling_source_columns,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH

EVALUATION_VERSION = "package_6_evaluation_v1"
LOCAL_MLFLOW_TRACKING_URI_SCHEMES = ("", "file", "sqlite")
REMOTE_MLFLOW_TRACKING_NAMES = {"databricks", "databricks-uc"}

BASELINE_SCORE_COLUMNS: dict[str, str] = {
    "churn_90d": "baseline_churn_score",
    "expansion_90d": "baseline_expansion_score",
}

SEGMENT_FIELDS: tuple[str, ...] = (
    "segment",
    "region",
    "current_plan",
    "company_size_band",
    "industry",
)

REQUIRED_SPLIT_CONFIG_KEYS: tuple[str, ...] = (
    "train_end_month",
    "train_row_count",
    "test_row_count",
    "train_observation_month_min",
    "train_observation_month_max",
    "test_observation_month_min",
    "test_observation_month_max",
)


@dataclass(frozen=True)
class LoadedCandidate:
    """Loaded local Package 5 candidate run and model artefact."""

    target: str
    candidate_model: str
    run_id: str
    train_end_month: pd.Timestamp
    model_artifact_uri: str
    model: object
    approved_features: tuple[str, ...]
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    split_config: dict[str, object]
    mlflow_metrics: dict[str, float]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (*self.numeric_features, *self.categorical_features)


@dataclass(frozen=True)
class EvaluationInputs:
    """All local inputs required before Package 6 scoring can begin."""

    account_month: pd.DataFrame
    baselines: pd.DataFrame
    candidates: tuple[LoadedCandidate, ...]
    experiment_name: str
    mlflow_tracking_uri: str
    train_end_month: pd.Timestamp


class EvaluationInputError(ValueError):
    """Raised when Package 6 evaluation inputs violate the local contract."""


def load_evaluation_inputs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    mlflow_tracking_uri: str | None = None,
    train_end_month: str | pd.Timestamp | None = None,
    targets: Iterable[str] = TARGET_COLUMNS,
    candidate_models: Iterable[str] = SUPPORTED_CANDIDATE_MODELS,
) -> EvaluationInputs:
    """Load warehouse inputs and existing local Package 5 MLflow candidates."""

    active_tracking_uri = _resolve_mlflow_tracking_uri(mlflow_tracking_uri)
    expected_targets = tuple(targets)
    expected_candidate_models = tuple(candidate_models)
    _validate_expected_dimensions(expected_targets, expected_candidate_models)

    account_month = _load_table(database_path, MODELING_SOURCE_TABLE)
    _validate_account_month(account_month)
    baselines = _load_table(database_path, BASELINE_OUTPUT_TABLE)
    _validate_baselines(baselines)

    candidates = _load_mlflow_candidates(
        experiment_name=experiment_name,
        mlflow_tracking_uri=active_tracking_uri,
        train_end_month=train_end_month,
        targets=expected_targets,
        candidate_models=expected_candidate_models,
        account_month_columns=tuple(account_month.columns),
    )
    selected_train_end_month = _validate_common_train_end_month(candidates)
    _validate_candidate_split_metadata_against_account_month(account_month, candidates)

    return EvaluationInputs(
        account_month=account_month,
        baselines=baselines,
        candidates=candidates,
        experiment_name=experiment_name,
        mlflow_tracking_uri=active_tracking_uri,
        train_end_month=selected_train_end_month,
    )


def validate_local_mlflow_tracking_uri(mlflow_tracking_uri: str) -> None:
    """Reject remote or hosted MLflow tracking for Package 6."""

    normalized_uri = mlflow_tracking_uri.strip()
    if normalized_uri in REMOTE_MLFLOW_TRACKING_NAMES:
        raise EvaluationInputError(
            "Package 6 MLflow tracking must remain local; "
            f"unsupported tracking URI: {normalized_uri}"
        )

    parsed_uri = urlparse(normalized_uri)
    if parsed_uri.scheme not in LOCAL_MLFLOW_TRACKING_URI_SCHEMES:
        raise EvaluationInputError(
            "Package 6 MLflow tracking must remain local; "
            f"unsupported tracking URI scheme: {parsed_uri.scheme}"
        )
    if parsed_uri.scheme == "file" and parsed_uri.netloc not in {"", "localhost"}:
        raise EvaluationInputError(
            "Package 6 MLflow file tracking URI must point to a local path"
        )
    if parsed_uri.scheme == "sqlite" and parsed_uri.netloc not in {"", "localhost"}:
        raise EvaluationInputError(
            "Package 6 MLflow sqlite tracking URI must point to a local path"
        )


def _resolve_mlflow_tracking_uri(mlflow_tracking_uri: str | None) -> str:
    import mlflow

    active_tracking_uri = (
        mlflow_tracking_uri
        if mlflow_tracking_uri is not None
        else mlflow.get_tracking_uri()
    )
    validate_local_mlflow_tracking_uri(active_tracking_uri)
    if mlflow_tracking_uri is not None:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    return active_tracking_uri


def _validate_expected_dimensions(
    targets: tuple[str, ...],
    candidate_models: tuple[str, ...],
) -> None:
    unsupported_targets = tuple(target for target in targets if target not in TARGET_COLUMNS)
    unsupported_candidates = tuple(
        candidate
        for candidate in candidate_models
        if candidate not in SUPPORTED_CANDIDATE_MODELS
    )
    if unsupported_targets:
        raise EvaluationInputError(
            "Package 6 received unsupported target(s): "
            + ", ".join(unsupported_targets)
        )
    if unsupported_candidates:
        raise EvaluationInputError(
            "Package 6 received unsupported candidate model(s): "
            + ", ".join(unsupported_candidates)
        )


def _load_table(database_path: str | Path, table_name: str) -> pd.DataFrame:
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            _validate_table_exists(connection, table_name)
            return connection.execute(
                f"""
                SELECT *
                FROM {table_name}
                ORDER BY account_id, observation_month
                """
            ).fetchdf()
    except duckdb.IOException as error:
        raise EvaluationInputError(
            f"{table_name} could not be read from {database_file}: {error}"
        ) from error


def _validate_table_exists(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> None:
    schema_name, local_table_name = _split_table_name(table_name)
    exists = connection.execute(
        """
        SELECT COUNT(*) > 0
        FROM information_schema.tables
        WHERE table_schema = ?
            AND table_name = ?
        """,
        [schema_name, local_table_name],
    ).fetchone()[0]
    if not exists:
        raise EvaluationInputError(f"{table_name} is required for Package 6")


def _validate_account_month(frame: pd.DataFrame) -> None:
    try:
        validate_modeling_source_columns(
            tuple(frame.columns),
            source_table=MODELING_SOURCE_TABLE,
            feature_set=DEFAULT_MODELING_FEATURE_SET,
        )
    except ModelingDatasetError as error:
        raise EvaluationInputError(str(error)) from error

    required_columns = {"observation_month_end", *SEGMENT_FIELDS}
    missing_columns = tuple(
        column for column in required_columns if column not in set(frame.columns)
    )
    if missing_columns:
        raise EvaluationInputError(
            f"{MODELING_SOURCE_TABLE} missing Package 6 evaluation column(s): "
            + ", ".join(missing_columns)
        )
    _validate_account_month_grain(frame, MODELING_SOURCE_TABLE)


def _validate_baselines(frame: pd.DataFrame) -> None:
    required_columns = {
        "account_id",
        "observation_month",
        *BASELINE_SCORE_COLUMNS.values(),
    }
    missing_columns = tuple(
        column for column in required_columns if column not in set(frame.columns)
    )
    if missing_columns:
        raise EvaluationInputError(
            f"{BASELINE_OUTPUT_TABLE} missing Package 6 baseline column(s): "
            + ", ".join(missing_columns)
        )
    _validate_account_month_grain(frame, BASELINE_OUTPUT_TABLE)


def _validate_account_month_grain(frame: pd.DataFrame, table_name: str) -> None:
    if frame.empty:
        raise EvaluationInputError(f"{table_name} is empty")
    duplicated = frame.duplicated(["account_id", "observation_month"])
    if duplicated.any():
        raise EvaluationInputError(
            f"{table_name} violates Package 6: duplicate account-month grain"
        )


def _load_mlflow_candidates(
    *,
    experiment_name: str,
    mlflow_tracking_uri: str,
    train_end_month: str | pd.Timestamp | None,
    targets: tuple[str, ...],
    candidate_models: tuple[str, ...],
    account_month_columns: tuple[str, ...],
) -> tuple[LoadedCandidate, ...]:
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise EvaluationInputError(
            "Package 6 expected local Package 5 MLflow experiment "
            f"'{experiment_name}' but it was not found"
        )

    runs = client.search_runs(
        [experiment.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["attributes.start_time DESC"],
    )
    selected_train_end_month = _select_candidate_train_end_month(
        runs,
        requested_train_end_month=train_end_month,
        targets=targets,
        candidate_models=candidate_models,
    )

    loaded_candidates: list[LoadedCandidate] = []
    for target in targets:
        for candidate_model in candidate_models:
            run = _select_latest_run_for_dimension(
                runs,
                target=target,
                candidate_model=candidate_model,
                train_end_month=selected_train_end_month,
            )
            if run is None:
                raise EvaluationInputError(
                    "Package 6 missing expected local Package 5 MLflow run: "
                    f"target={target}, candidate_model={candidate_model}, "
                    f"train_end_month={selected_train_end_month.date().isoformat()}"
                )
            loaded_candidates.append(
                _load_candidate_from_run(
                    client,
                    run,
                    account_month_columns=account_month_columns,
                )
            )

    return tuple(loaded_candidates)


def _select_candidate_train_end_month(
    runs,
    *,
    requested_train_end_month: str | pd.Timestamp | None,
    targets: tuple[str, ...],
    candidate_models: tuple[str, ...],
) -> pd.Timestamp:
    if requested_train_end_month is not None:
        requested = _parse_train_end_month(requested_train_end_month)
        if _has_complete_candidate_grid(
            runs,
            train_end_month=requested,
            targets=targets,
            candidate_models=candidate_models,
        ):
            return requested
        raise EvaluationInputError(
            "Package 6 missing complete local Package 5 candidate grid for "
            f"train_end_month={requested.date().isoformat()}"
        )

    train_end_months = sorted(
        {
            _parse_train_end_month(run.data.params["train_end_month"])
            for run in runs
            if _is_expected_candidate_run(run, targets, candidate_models)
            and "train_end_month" in run.data.params
        },
        reverse=True,
    )
    for candidate_train_end_month in train_end_months:
        if _has_complete_candidate_grid(
            runs,
            train_end_month=candidate_train_end_month,
            targets=targets,
            candidate_models=candidate_models,
        ):
            return candidate_train_end_month

    expected = ", ".join(
        f"{target}/{candidate}"
        for target in targets
        for candidate in candidate_models
    )
    raise EvaluationInputError(
        "Package 6 could not find a complete local Package 5 candidate grid "
        f"for expected runs: {expected}"
    )


def _has_complete_candidate_grid(
    runs,
    *,
    train_end_month: pd.Timestamp,
    targets: tuple[str, ...],
    candidate_models: tuple[str, ...],
) -> bool:
    available = {
        (run.data.params.get("target"), run.data.params.get("candidate_model"))
        for run in runs
        if _is_expected_candidate_run(run, targets, candidate_models)
        and "train_end_month" in run.data.params
        and _parse_train_end_month(run.data.params["train_end_month"])
        == train_end_month
    }
    expected = {
        (target, candidate)
        for target in targets
        for candidate in candidate_models
    }
    return expected <= available


def _is_expected_candidate_run(
    run,
    targets: tuple[str, ...],
    candidate_models: tuple[str, ...],
) -> bool:
    return (
        run.data.params.get("target") in targets
        and run.data.params.get("candidate_model") in candidate_models
    )


def _select_latest_run_for_dimension(
    runs,
    *,
    target: str,
    candidate_model: str,
    train_end_month: pd.Timestamp,
):
    matching_runs = [
        run
        for run in runs
        if run.data.params.get("target") == target
        and run.data.params.get("candidate_model") == candidate_model
        and "train_end_month" in run.data.params
        and _parse_train_end_month(run.data.params["train_end_month"])
        == train_end_month
    ]
    return matching_runs[0] if matching_runs else None


def _load_candidate_from_run(
    client,
    run,
    *,
    account_month_columns: tuple[str, ...],
) -> LoadedCandidate:
    import mlflow.sklearn

    params = run.data.params
    target = params.get("target")
    candidate_model = params.get("candidate_model")
    train_end_month = _parse_train_end_month(params.get("train_end_month"))

    features = _download_json_artifact(client, run.info.run_id, "features.json")
    split_config = _download_json_artifact(client, run.info.run_id, "split_config.json")
    approved_features = _validate_feature_metadata(
        features,
        account_month_columns=account_month_columns,
        run_id=run.info.run_id,
    )
    _validate_split_config(
        split_config,
        expected_train_end_month=train_end_month,
        run_id=run.info.run_id,
    )
    _validate_model_artifact_present(client, run.info.run_id)

    model_artifact_uri = f"runs:/{run.info.run_id}/model"
    try:
        model = mlflow.sklearn.load_model(model_artifact_uri)
    except Exception as error:  # noqa: BLE001 - MLflow wraps loader failures.
        raise EvaluationInputError(
            "Package 6 could not load Package 5 model artefact for "
            f"run_id={run.info.run_id}"
        ) from error
    if not hasattr(model, "predict_proba"):
        raise EvaluationInputError(
            f"Package 5 model artefact for run_id={run.info.run_id} "
            "does not expose predict_proba"
        )

    return LoadedCandidate(
        target=target,
        candidate_model=candidate_model,
        run_id=run.info.run_id,
        train_end_month=train_end_month,
        model_artifact_uri=model_artifact_uri,
        model=model,
        approved_features=approved_features["approved_features"],
        numeric_features=approved_features["numeric_features"],
        categorical_features=approved_features["categorical_features"],
        split_config=split_config,
        mlflow_metrics={key: float(value) for key, value in run.data.metrics.items()},
    )


def _download_json_artifact(client, run_id: str, artifact_path: str) -> dict[str, object]:
    try:
        with TemporaryDirectory() as temporary_directory:
            local_path = Path(
                client.download_artifacts(run_id, artifact_path, temporary_directory)
            )
            return json.loads(local_path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - MLflow raises several error types.
        raise EvaluationInputError(
            f"Package 6 missing required Package 5 artefact '{artifact_path}' "
            f"for run_id={run_id}"
        ) from error


def _validate_feature_metadata(
    features: dict[str, object],
    *,
    account_month_columns: tuple[str, ...],
    run_id: str,
) -> dict[str, tuple[str, ...]]:
    required_keys = ("approved_features", "numeric_features", "categorical_features")
    missing_keys = tuple(key for key in required_keys if key not in features)
    if missing_keys:
        raise EvaluationInputError(
            f"Package 5 features.json for run_id={run_id} missing key(s): "
            + ", ".join(missing_keys)
        )

    feature_lists: dict[str, tuple[str, ...]] = {}
    for key in required_keys:
        value = features[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise EvaluationInputError(
                f"Package 5 features.json for run_id={run_id} has invalid {key}"
            )
        feature_lists[key] = tuple(value)

    expected_approved = (
        *feature_lists["numeric_features"],
        *feature_lists["categorical_features"],
    )
    if feature_lists["approved_features"] != expected_approved:
        raise EvaluationInputError(
            f"Package 5 features.json for run_id={run_id} has inconsistent "
            "approved/numeric/categorical feature lists"
        )

    try:
        validate_modeling_feature_set(
            ModelingFeatureSet(
                numeric_features=feature_lists["numeric_features"],
                categorical_features=feature_lists["categorical_features"],
            )
        )
    except ModelingDatasetError as error:
        raise EvaluationInputError(str(error)) from error

    missing_columns = tuple(
        feature
        for feature in feature_lists["approved_features"]
        if feature not in set(account_month_columns)
    )
    if missing_columns:
        raise EvaluationInputError(
            f"Package 5 features.json for run_id={run_id} references "
            "missing mart.account_month column(s): "
            + ", ".join(missing_columns)
        )

    return feature_lists


def _validate_split_config(
    split_config: dict[str, object],
    *,
    expected_train_end_month: pd.Timestamp,
    run_id: str,
) -> None:
    missing_keys = tuple(key for key in REQUIRED_SPLIT_CONFIG_KEYS if key not in split_config)
    if missing_keys:
        raise EvaluationInputError(
            f"Package 5 split_config.json for run_id={run_id} missing key(s): "
            + ", ".join(missing_keys)
        )

    split_train_end_month = _parse_train_end_month(split_config["train_end_month"])
    if split_train_end_month != expected_train_end_month:
        raise EvaluationInputError(
            f"Package 5 split_config.json for run_id={run_id} does not match "
            "the run train_end_month"
        )

    for count_key in ("train_row_count", "test_row_count"):
        try:
            row_count = int(split_config[count_key])
        except (TypeError, ValueError) as error:
            raise EvaluationInputError(
                f"Package 5 split_config.json for run_id={run_id} has invalid "
                f"{count_key}"
            ) from error
        if row_count <= 0:
            raise EvaluationInputError(
                f"Package 5 split_config.json for run_id={run_id} has empty "
                f"{count_key}"
            )

    train_max = pd.Timestamp(split_config["train_observation_month_max"]).normalize()
    test_min = pd.Timestamp(split_config["test_observation_month_min"]).normalize()
    if train_max > expected_train_end_month or test_min <= expected_train_end_month:
        raise EvaluationInputError(
            f"Package 5 split_config.json for run_id={run_id} violates fixed "
            "temporal holdout semantics"
        )


def _validate_model_artifact_present(client, run_id: str) -> None:
    try:
        artifact_paths = {artifact.path for artifact in client.list_artifacts(run_id)}
    except Exception as error:  # noqa: BLE001 - MLflow raises several error types.
        raise EvaluationInputError(
            f"Package 6 could not inspect MLflow artefacts for run_id={run_id}"
        ) from error
    if "model" not in artifact_paths:
        raise EvaluationInputError(
            f"Package 6 missing required Package 5 model artefact for run_id={run_id}"
        )


def _validate_common_train_end_month(
    candidates: tuple[LoadedCandidate, ...],
) -> pd.Timestamp:
    train_end_months = {candidate.train_end_month for candidate in candidates}
    if len(train_end_months) != 1:
        formatted = ", ".join(
            sorted(month.date().isoformat() for month in train_end_months)
        )
        raise EvaluationInputError(
            "Package 6 requires a common fixed holdout train_end_month; found "
            + formatted
        )
    return next(iter(train_end_months))


def _validate_candidate_split_metadata_against_account_month(
    account_month: pd.DataFrame,
    candidates: tuple[LoadedCandidate, ...],
) -> None:
    frame = account_month.copy()
    frame["observation_month"] = pd.to_datetime(frame["observation_month"])
    if frame["observation_month"].isna().any():
        raise EvaluationInputError(
            "Package 6 cannot validate split metadata with null observation_month"
        )

    for candidate in candidates:
        eligible = frame[frame[candidate.target].notna()]
        train_frame = eligible[
            eligible["observation_month"] <= candidate.train_end_month
        ]
        test_frame = eligible[
            eligible["observation_month"] > candidate.train_end_month
        ]
        _validate_split_row_count(
            candidate,
            actual_row_count=len(train_frame),
            split_config_key="train_row_count",
        )
        _validate_split_row_count(
            candidate,
            actual_row_count=len(test_frame),
            split_config_key="test_row_count",
        )
        _validate_split_month_bound(
            candidate,
            frame=train_frame,
            split_config_key="train_observation_month_min",
            aggregation="min",
        )
        _validate_split_month_bound(
            candidate,
            frame=train_frame,
            split_config_key="train_observation_month_max",
            aggregation="max",
        )
        _validate_split_month_bound(
            candidate,
            frame=test_frame,
            split_config_key="test_observation_month_min",
            aggregation="min",
        )
        _validate_split_month_bound(
            candidate,
            frame=test_frame,
            split_config_key="test_observation_month_max",
            aggregation="max",
        )


def _validate_split_row_count(
    candidate: LoadedCandidate,
    *,
    actual_row_count: int,
    split_config_key: str,
) -> None:
    expected_row_count = int(candidate.split_config[split_config_key])
    if expected_row_count != actual_row_count:
        raise EvaluationInputError(
            "Package 5 split_config.json for "
            f"run_id={candidate.run_id} does not match current "
            f"mart.account_month eligible split rows for target={candidate.target}: "
            f"{split_config_key} expected {expected_row_count}, "
            f"found {actual_row_count}"
        )


def _validate_split_month_bound(
    candidate: LoadedCandidate,
    *,
    frame: pd.DataFrame,
    split_config_key: str,
    aggregation: str,
) -> None:
    expected_bound = _parse_split_month_value(
        candidate.split_config[split_config_key],
        field_name=split_config_key,
        run_id=candidate.run_id,
    )
    actual_value = getattr(frame["observation_month"], aggregation)()
    actual_bound = pd.Timestamp(actual_value).normalize()
    if expected_bound != actual_bound:
        raise EvaluationInputError(
            "Package 5 split_config.json for "
            f"run_id={candidate.run_id} does not match current "
            f"mart.account_month eligible split rows for target={candidate.target}: "
            f"{split_config_key} expected {expected_bound.date().isoformat()}, "
            f"found {actual_bound.date().isoformat()}"
        )


def _parse_train_end_month(value: object) -> pd.Timestamp:
    return _parse_split_month_value(
        value,
        field_name="train_end_month",
    )


def _parse_split_month_value(
    value: object,
    *,
    field_name: str,
    run_id: str | None = None,
) -> pd.Timestamp:
    if value is None:
        context = f" for run_id={run_id}" if run_id else ""
        raise EvaluationInputError(f"Package 5 run missing {field_name}{context}")
    try:
        resolved = pd.Timestamp(value).normalize()
    except (TypeError, ValueError) as error:
        context = f" for run_id={run_id}" if run_id else ""
        raise EvaluationInputError(
            f"Package 5 run has invalid {field_name}{context}"
        ) from error
    if pd.isna(resolved):
        context = f" for run_id={run_id}" if run_id else ""
        raise EvaluationInputError(
            f"Package 5 run has invalid {field_name}{context}"
        )
    if resolved.day != 1:
        raise EvaluationInputError(
            f"Package 5 {field_name} must be the first day of a calendar month"
        )
    return resolved


def _split_table_name(table_name: str) -> tuple[str, str]:
    parts = table_name.split(".")
    if len(parts) != 2 or not all(parts):
        raise EvaluationInputError(f"table must use schema.table form: {table_name}")
    return parts[0], parts[1]


def local_path_from_file_uri(uri: str) -> Path:
    """Resolve a local MLflow file URI for tests and diagnostics."""

    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return Path(uri)
    return Path(unquote(parsed.path))
