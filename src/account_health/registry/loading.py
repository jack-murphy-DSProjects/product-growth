"""Package 7 champion manifest loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd

from account_health.modeling import SUPPORTED_CANDIDATE_MODELS

DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH = Path(
    "data/outputs/model_evaluation/champion_selection_manifest.json"
)
PROMOTION_VERSION = "package_7_promotion_v1"
CHAMPION_ALIAS = "champion"

LOCAL_MLFLOW_URI_SCHEMES = ("", "file", "sqlite")
REMOTE_MLFLOW_URI_NAMES = {"databricks", "databricks-uc"}

MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "target",
    "selection_status",
    "selected_champion_model_family",
    "mlflow_run_id",
    "model_artifact_uri",
    "primary_metric",
    "key_topk_metrics",
    "comparison_versus_baseline",
    "calibration_caveats",
    "segment_caveats",
    "temporal_caveats",
    "utility_caveats",
    "synthetic_data_caveat",
    "created_at_utc",
    "evaluation_version",
)

REQUIRED_FEATURE_KEYS: tuple[str, ...] = (
    "approved_features",
    "numeric_features",
    "categorical_features",
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

INELIGIBLE_SELECTION_REASONS: dict[str, str] = {
    "baseline_retained": "baseline retained",
    "no_ml_candidate_sufficiently_beats_baseline": "no ML champion selected",
    "insufficient_evidence": "insufficient evidence",
}


@dataclass(frozen=True)
class TargetRegistryPolicy:
    """Package 7 target mapping and registered model name."""

    target_key: str
    target_label: str
    registered_model_name: str


PACKAGE7_TARGETS: dict[str, TargetRegistryPolicy] = {
    "churn": TargetRegistryPolicy(
        target_key="churn",
        target_label="churn_90d",
        registered_model_name="account_health_churn_model",
    ),
    "expansion": TargetRegistryPolicy(
        target_key="expansion",
        target_label="expansion_90d",
        registered_model_name="account_health_expansion_model",
    ),
}

TARGET_LABEL_TO_KEY = {
    policy.target_label: target_key for target_key, policy in PACKAGE7_TARGETS.items()
}


@dataclass(frozen=True)
class PromotionCandidate:
    """Validated Package 6 ML champion evidence ready for Package 7 promotion."""

    target_key: str
    target_label: str
    registered_model_name: str
    selected_champion_model_family: str
    mlflow_run_id: str
    model_artifact_uri: str
    primary_metric: str
    key_topk_metrics: dict[str, object]
    comparison_versus_baseline: dict[str, object]
    calibration_caveats: tuple[str, ...]
    segment_caveats: tuple[str, ...]
    temporal_caveats: tuple[str, ...]
    utility_caveats: tuple[str, ...]
    synthetic_data_caveat: str
    package6_created_at_utc: str
    package6_evaluation_version: str
    package6_selection_status: str
    feature_metadata: dict[str, tuple[str, ...]]
    split_config: dict[str, object]


@dataclass(frozen=True)
class PromotionPlan:
    """Validated local Package 7 promotion plan without registry writes."""

    manifest_path: Path
    mlflow_tracking_uri: str
    mlflow_registry_uri: str
    promotion_version: str
    candidates: tuple[PromotionCandidate, ...]


class ModelRegistryError(ValueError):
    """Raised when Package 7 registry promotion inputs violate the contract."""


def load_promotion_plan(
    manifest_path: str | Path = DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH,
    *,
    targets: Iterable[str] = PACKAGE7_TARGETS,
    mlflow_tracking_uri: str | None = None,
    mlflow_registry_uri: str | None = None,
) -> PromotionPlan:
    """Load and validate Package 6 ML champion evidence for Package 7."""

    active_tracking_uri, active_registry_uri = _resolve_mlflow_uris(
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_registry_uri=mlflow_registry_uri,
    )
    target_keys = _validate_requested_targets(tuple(targets))
    manifest_file = Path(manifest_path)
    records = _read_manifest_records(manifest_file)
    records_by_target = _records_by_target(records)

    candidates: list[PromotionCandidate] = []
    for target_key in target_keys:
        policy = PACKAGE7_TARGETS[target_key]
        record = _record_for_target(records_by_target, policy)
        candidates.append(
            _validate_candidate_record(
                record,
                policy=policy,
                manifest_path=manifest_file,
                mlflow_tracking_uri=active_tracking_uri,
            )
        )

    return PromotionPlan(
        manifest_path=manifest_file,
        mlflow_tracking_uri=active_tracking_uri,
        mlflow_registry_uri=active_registry_uri,
        promotion_version=PROMOTION_VERSION,
        candidates=tuple(candidates),
    )


def validate_local_mlflow_uri(uri: str, *, purpose: str) -> None:
    """Reject remote or hosted MLflow tracking/registry URIs."""

    normalized_uri = uri.strip()
    if not normalized_uri:
        raise ModelRegistryError(
            f"Package 7 MLflow {purpose} URI is missing or ambiguous"
        )
    if normalized_uri in REMOTE_MLFLOW_URI_NAMES:
        raise ModelRegistryError(
            f"Package 7 MLflow {purpose} must remain local; "
            f"unsupported URI: {normalized_uri}"
        )

    parsed_uri = urlparse(normalized_uri)
    if parsed_uri.scheme not in LOCAL_MLFLOW_URI_SCHEMES:
        raise ModelRegistryError(
            f"Package 7 MLflow {purpose} must remain local; "
            f"unsupported URI scheme: {parsed_uri.scheme}"
        )
    if parsed_uri.scheme in {"file", "sqlite"} and parsed_uri.netloc not in {
        "",
        "localhost",
    }:
        raise ModelRegistryError(
            f"Package 7 MLflow {purpose} URI must point to a local path"
        )


def _resolve_mlflow_uris(
    *,
    mlflow_tracking_uri: str | None,
    mlflow_registry_uri: str | None,
) -> tuple[str, str]:
    import mlflow

    active_tracking_uri = (
        mlflow_tracking_uri
        if mlflow_tracking_uri is not None
        else mlflow.get_tracking_uri()
    )
    active_registry_uri = (
        mlflow_registry_uri
        if mlflow_registry_uri is not None
        else mlflow.get_registry_uri()
    )
    validate_local_mlflow_uri(active_tracking_uri, purpose="tracking")
    validate_local_mlflow_uri(active_registry_uri, purpose="registry")
    if mlflow_tracking_uri is not None:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    if mlflow_registry_uri is not None:
        mlflow.set_registry_uri(mlflow_registry_uri)
    return active_tracking_uri, active_registry_uri


def _validate_requested_targets(targets: tuple[str, ...]) -> tuple[str, ...]:
    if not targets:
        raise ModelRegistryError("Package 7 requires at least one requested target")
    unsupported = tuple(target for target in targets if target not in PACKAGE7_TARGETS)
    if unsupported:
        raise ModelRegistryError(
            "Package 7 received unsupported target key(s): " + ", ".join(unsupported)
        )
    duplicated = _duplicates(targets)
    if duplicated:
        raise ModelRegistryError(
            "Package 7 received duplicate target key(s): " + ", ".join(duplicated)
        )
    return targets


def _read_manifest_records(manifest_path: Path) -> tuple[dict[str, object], ...]:
    if not manifest_path.is_file():
        raise ModelRegistryError(
            "Package 7 expected Package 6 champion-selection manifest at "
            f"{manifest_path}, but it was not found"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ModelRegistryError(
            f"Package 6 champion-selection manifest is malformed JSON: {manifest_path}"
        ) from error
    if not isinstance(payload, list):
        raise ModelRegistryError(
            "Package 6 champion-selection manifest is malformed: expected a "
            "list of target records"
        )
    records: list[dict[str, object]] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise ModelRegistryError(
                "Package 6 champion-selection manifest is malformed: "
                f"record {index} is not an object"
            )
        records.append(record)
    if not records:
        raise ModelRegistryError("Package 6 champion-selection manifest is empty")
    return tuple(records)


def _records_by_target(
    records: tuple[dict[str, object], ...],
) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        _validate_manifest_record_shape(record)
        target = _required_string(record, "target")
        if target not in TARGET_LABEL_TO_KEY:
            raise ModelRegistryError(
                "Package 6 champion-selection manifest contains unsupported "
                f"target: {target}"
            )
        grouped.setdefault(target, []).append(record)

    duplicates = tuple(target for target, values in grouped.items() if len(values) > 1)
    if duplicates:
        raise ModelRegistryError(
            "Package 6 champion-selection manifest has ambiguous duplicate "
            "target evidence for: "
            + ", ".join(sorted(duplicates))
        )

    return {target: values[0] for target, values in grouped.items()}


def _validate_manifest_record_shape(record: dict[str, object]) -> None:
    missing = tuple(field for field in MANIFEST_REQUIRED_FIELDS if field not in record)
    if missing:
        target = record.get("target", "<unknown>")
        raise ModelRegistryError(
            "Package 6 champion-selection manifest record for "
            f"{target} missing required field(s): "
            + ", ".join(missing)
        )
    _required_dict(record, "key_topk_metrics")
    _required_dict(record, "comparison_versus_baseline")
    for field in (
        "calibration_caveats",
        "segment_caveats",
        "temporal_caveats",
        "utility_caveats",
    ):
        _required_string_sequence(record, field)


def _record_for_target(
    records_by_target: dict[str, dict[str, object]],
    policy: TargetRegistryPolicy,
) -> dict[str, object]:
    record = records_by_target.get(policy.target_label)
    if record is None:
        raise ModelRegistryError(
            "Package 6 champion-selection manifest missing required target "
            f"evidence for {policy.target_label}"
        )
    return record


def _validate_candidate_record(
    record: dict[str, object],
    *,
    policy: TargetRegistryPolicy,
    manifest_path: Path,
    mlflow_tracking_uri: str,
) -> PromotionCandidate:
    status = _required_string(record, "selection_status")
    if status != "ml_champion_selected":
        reason = INELIGIBLE_SELECTION_REASONS.get(status, status)
        raise ModelRegistryError(
            "Package 7 cannot promote target "
            f"{policy.target_label}: Package 6 outcome is {reason}"
        )

    model_family = _required_string(record, "selected_champion_model_family")
    if model_family not in SUPPORTED_CANDIDATE_MODELS:
        raise ModelRegistryError(
            "Package 7 cannot promote target "
            f"{policy.target_label}: selected champion model family "
            f"'{model_family}' is not an approved Package 5 ML candidate"
        )

    mlflow_run_id = _required_string(record, "mlflow_run_id")
    model_artifact_uri = _required_string(record, "model_artifact_uri")
    artifact_run_id, artifact_path = _parse_runs_model_uri(model_artifact_uri)
    if artifact_run_id != mlflow_run_id:
        raise ModelRegistryError(
            "Package 7 source model URI is ambiguous: model_artifact_uri "
            "does not reference the selected mlflow_run_id"
        )

    source_metadata = _validate_source_run_and_artifacts(
        mlflow_tracking_uri=mlflow_tracking_uri,
        run_id=mlflow_run_id,
        expected_target=policy.target_label,
        expected_model_family=model_family,
        artifact_path=artifact_path,
        model_artifact_uri=model_artifact_uri,
    )

    return PromotionCandidate(
        target_key=policy.target_key,
        target_label=policy.target_label,
        registered_model_name=policy.registered_model_name,
        selected_champion_model_family=model_family,
        mlflow_run_id=mlflow_run_id,
        model_artifact_uri=model_artifact_uri,
        primary_metric=_required_string(record, "primary_metric"),
        key_topk_metrics=_required_dict(record, "key_topk_metrics"),
        comparison_versus_baseline=_required_dict(
            record,
            "comparison_versus_baseline",
        ),
        calibration_caveats=_required_string_sequence(record, "calibration_caveats"),
        segment_caveats=_required_string_sequence(record, "segment_caveats"),
        temporal_caveats=_required_string_sequence(record, "temporal_caveats"),
        utility_caveats=_required_string_sequence(record, "utility_caveats"),
        synthetic_data_caveat=_required_string(record, "synthetic_data_caveat"),
        package6_created_at_utc=_required_string(record, "created_at_utc"),
        package6_evaluation_version=_required_string(record, "evaluation_version"),
        package6_selection_status=status,
        feature_metadata=source_metadata["feature_metadata"],
        split_config=source_metadata["split_config"],
    )


def _validate_source_run_and_artifacts(
    *,
    mlflow_tracking_uri: str,
    run_id: str,
    expected_target: str,
    expected_model_family: str,
    artifact_path: str,
    model_artifact_uri: str,
) -> dict[str, object]:
    import mlflow
    import mlflow.pyfunc
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    try:
        run = client.get_run(run_id)
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise ModelRegistryError(
            f"Package 7 could not find local Package 5 MLflow source run: {run_id}"
        ) from error

    params = run.data.params
    if params.get("target") != expected_target:
        raise ModelRegistryError(
            "Package 7 source run target does not match Package 6 evidence "
            f"for run_id={run_id}"
        )
    if params.get("candidate_model") != expected_model_family:
        raise ModelRegistryError(
            "Package 7 source run candidate_model does not match Package 6 "
            f"evidence for run_id={run_id}"
        )

    _validate_artifact_path_present(client, run_id=run_id, artifact_path=artifact_path)
    feature_metadata = _validate_feature_metadata(
        _download_json_artifact(client, run_id, "features.json"),
        run_id=run_id,
    )
    split_config = _validate_split_config(
        _download_json_artifact(client, run_id, "split_config.json"),
        run_id=run_id,
    )
    try:
        mlflow.pyfunc.load_model(model_artifact_uri)
    except Exception as error:  # noqa: BLE001 - MLflow wraps model load errors.
        raise ModelRegistryError(
            "Package 7 could not load Package 5 source model artefact for "
            f"run_id={run_id}"
        ) from error

    return {
        "feature_metadata": feature_metadata,
        "split_config": split_config,
    }


def _parse_runs_model_uri(model_artifact_uri: str) -> tuple[str, str]:
    parsed = urlparse(model_artifact_uri)
    if parsed.scheme != "runs":
        raise ModelRegistryError(
            "Package 7 requires model_artifact_uri to reference a local "
            "Package 5 MLflow run using runs:/<run_id>/<artifact_path>"
        )
    path_parts = tuple(part for part in parsed.path.split("/") if part)
    if len(path_parts) < 2:
        raise ModelRegistryError(
            "Package 7 model_artifact_uri is missing run ID or artifact path"
        )
    return path_parts[0], "/".join(path_parts[1:])


def _validate_artifact_path_present(client, *, run_id: str, artifact_path: str) -> None:
    root_artifact = artifact_path.split("/", maxsplit=1)[0]
    try:
        artifact_paths = {artifact.path for artifact in client.list_artifacts(run_id)}
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise ModelRegistryError(
            f"Package 7 could not inspect source run artefacts for run_id={run_id}"
        ) from error
    if root_artifact not in artifact_paths:
        raise ModelRegistryError(
            f"Package 7 missing source model artefact '{artifact_path}' "
            f"for run_id={run_id}"
        )


def _download_json_artifact(client, run_id: str, artifact_path: str) -> dict[str, object]:
    try:
        with TemporaryDirectory() as temporary_directory:
            local_path = Path(
                client.download_artifacts(run_id, artifact_path, temporary_directory)
            )
            payload = json.loads(local_path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise ModelRegistryError(
            f"Package 7 missing required Package 5 artefact '{artifact_path}' "
            f"for run_id={run_id}"
        ) from error
    if not isinstance(payload, dict):
        raise ModelRegistryError(
            f"Package 5 artefact '{artifact_path}' for run_id={run_id} "
            "must be a JSON object"
        )
    return payload


def _validate_feature_metadata(
    features: dict[str, object],
    *,
    run_id: str,
) -> dict[str, tuple[str, ...]]:
    missing = tuple(key for key in REQUIRED_FEATURE_KEYS if key not in features)
    if missing:
        raise ModelRegistryError(
            f"Package 5 features.json for run_id={run_id} missing key(s): "
            + ", ".join(missing)
        )

    feature_lists: dict[str, tuple[str, ...]] = {}
    for key in REQUIRED_FEATURE_KEYS:
        value = features[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise ModelRegistryError(
                f"Package 5 features.json for run_id={run_id} has invalid {key}"
            )
        feature_lists[key] = tuple(value)

    expected_approved = (
        *feature_lists["numeric_features"],
        *feature_lists["categorical_features"],
    )
    if feature_lists["approved_features"] != expected_approved:
        raise ModelRegistryError(
            f"Package 5 features.json for run_id={run_id} has inconsistent "
            "approved/numeric/categorical feature lists"
        )
    return feature_lists


def _validate_split_config(
    split_config: dict[str, object],
    *,
    run_id: str,
) -> dict[str, object]:
    missing = tuple(key for key in REQUIRED_SPLIT_CONFIG_KEYS if key not in split_config)
    if missing:
        raise ModelRegistryError(
            f"Package 5 split_config.json for run_id={run_id} missing key(s): "
            + ", ".join(missing)
        )

    train_end_month = _parse_month(
        split_config["train_end_month"],
        field_name="train_end_month",
        run_id=run_id,
    )
    for field in (
        "train_observation_month_min",
        "train_observation_month_max",
        "test_observation_month_min",
        "test_observation_month_max",
    ):
        _parse_month(split_config[field], field_name=field, run_id=run_id)

    for field in ("train_row_count", "test_row_count"):
        try:
            row_count = int(split_config[field])
        except (TypeError, ValueError) as error:
            raise ModelRegistryError(
                f"Package 5 split_config.json for run_id={run_id} has invalid {field}"
            ) from error
        if row_count <= 0:
            raise ModelRegistryError(
                f"Package 5 split_config.json for run_id={run_id} has empty {field}"
            )
    if train_end_month.day != 1:
        raise ModelRegistryError(
            f"Package 5 split_config.json for run_id={run_id} has invalid "
            "train_end_month"
        )
    return split_config


def _parse_month(value: object, *, field_name: str, run_id: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value).normalize()
    except (TypeError, ValueError) as error:
        raise ModelRegistryError(
            f"Package 5 split_config.json for run_id={run_id} has invalid {field_name}"
        ) from error
    if pd.isna(parsed):
        raise ModelRegistryError(
            f"Package 5 split_config.json for run_id={run_id} has invalid {field_name}"
        )
    return parsed


def _required_string(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        target = record.get("target", "<unknown>")
        raise ModelRegistryError(
            "Package 6 champion-selection manifest record for "
            f"{target} has missing or invalid {field}"
        )
    return value.strip()


def _required_dict(record: dict[str, object], field: str) -> dict[str, object]:
    value = record.get(field)
    if not isinstance(value, dict):
        target = record.get("target", "<unknown>")
        raise ModelRegistryError(
            "Package 6 champion-selection manifest record for "
            f"{target} has missing or invalid {field}"
        )
    return value


def _required_string_sequence(
    record: dict[str, object],
    field: str,
) -> tuple[str, ...]:
    value = record.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        target = record.get("target", "<unknown>")
        raise ModelRegistryError(
            "Package 6 champion-selection manifest record for "
            f"{target} has missing or invalid {field}"
        )
    return tuple(value)


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))
