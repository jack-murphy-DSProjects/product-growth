"""Package 8 scoring input, registry handoff, and feature validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import duckdb
import pandas as pd

from account_health.features import MART_SCHEMA
from account_health.modeling import (
    ModelingDatasetError,
    ModelingFeatureSet,
    validate_modeling_feature_set,
)
from account_health.registry import (
    CHAMPION_ALIAS,
    DEFAULT_PROMOTION_MANIFEST_PATH,
    PACKAGE7_TARGETS,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH

SCORING_VERSION = "package_8_batch_scoring_v1"
SCORING_SOURCE_TABLE = f"{MART_SCHEMA}.account_month"
SCORE_OUTPUT_TABLE = f"{MART_SCHEMA}.account_month_scores"
BATCH_SCORING_AUDIT_TABLE = "metadata.batch_scoring_audit"
DEFAULT_BATCH_SCORING_EXPORT_DIR = Path("data/outputs/batch_scoring")

LOCAL_MLFLOW_URI_SCHEMES = ("", "file", "sqlite")
REMOTE_MLFLOW_URI_NAMES = {"databricks", "databricks-uc"}
REQUIRED_FEATURE_KEYS = (
    "approved_features",
    "numeric_features",
    "categorical_features",
)
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}-01$")


@dataclass(frozen=True)
class ScoringPopulation:
    """Selected label-free account-month rows for one Package 8 scoring run."""

    source_table: str
    selector: str
    scoring_month: pd.Timestamp
    frame: pd.DataFrame


@dataclass(frozen=True)
class PromotedScoringModel:
    """A Package 7-promoted model plus Package 5 feature metadata."""

    target_key: str
    target_label: str
    registered_model_name: str
    alias: str
    model_uri: str
    model_version: str
    source_mlflow_run_id: str
    source_model_artifact_uri: str
    feature_metadata_artifact: str
    approved_features: tuple[str, ...]
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    model: object


@dataclass(frozen=True)
class BatchScoringInputs:
    """Validated local inputs needed before Package 8 score generation."""

    population: ScoringPopulation
    churn_model: PromotedScoringModel
    expansion_model: PromotedScoringModel
    mlflow_tracking_uri: str
    mlflow_registry_uri: str
    promotion_evidence_sources: tuple[str, ...]


class BatchScoringError(ValueError):
    """Raised when Package 8 scoring inputs violate the local contract."""


def load_batch_scoring_inputs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | date | pd.Timestamp | None = None,
    latest: bool = False,
    promotion_manifest_path: str | Path | None = DEFAULT_PROMOTION_MANIFEST_PATH,
    mlflow_tracking_uri: str | None = None,
    mlflow_registry_uri: str | None = None,
) -> BatchScoringInputs:
    """Load and validate all non-output Package 8 scoring inputs."""

    active_tracking_uri, active_registry_uri = _resolve_mlflow_uris(
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_registry_uri=mlflow_registry_uri,
    )
    population = load_scoring_population(
        database_path,
        scoring_month=scoring_month,
        latest=latest,
    )
    evidence_records, evidence_sources = _load_promotion_evidence(
        database_path=database_path,
        promotion_manifest_path=promotion_manifest_path,
    )
    churn_model = _load_promoted_scoring_model(
        "churn",
        mlflow_tracking_uri=active_tracking_uri,
        mlflow_registry_uri=active_registry_uri,
        scoring_columns=tuple(population.frame.columns),
        evidence_records=evidence_records,
    )
    expansion_model = _load_promoted_scoring_model(
        "expansion",
        mlflow_tracking_uri=active_tracking_uri,
        mlflow_registry_uri=active_registry_uri,
        scoring_columns=tuple(population.frame.columns),
        evidence_records=evidence_records,
    )
    return BatchScoringInputs(
        population=population,
        churn_model=churn_model,
        expansion_model=expansion_model,
        mlflow_tracking_uri=active_tracking_uri,
        mlflow_registry_uri=active_registry_uri,
        promotion_evidence_sources=evidence_sources,
    )


def load_scoring_population(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | date | pd.Timestamp | None = None,
    latest: bool = False,
    source_table: str = SCORING_SOURCE_TABLE,
) -> ScoringPopulation:
    """Read selected Package 8 scoring rows without label filtering."""

    _validate_scoring_source_table(source_table)
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            selected_month, selector = resolve_scoring_month_for_connection(
                connection,
                scoring_month=scoring_month,
                latest=latest,
                source_table=source_table,
            )
            columns = _source_columns(connection, source_table)
            _validate_required_scoring_source_columns(columns, source_table)
            frame = connection.execute(
                f"""
                SELECT *
                FROM {source_table}
                WHERE observation_month = ?
                ORDER BY account_id, observation_month
                """,
                [selected_month.date()],
            ).fetchdf()
    except duckdb.IOException as error:
        raise BatchScoringError(
            f"{source_table} could not be read from {database_file}: {error}"
        ) from error

    _validate_scoring_population_frame(
        frame,
        source_table=source_table,
        scoring_month=selected_month,
    )
    return ScoringPopulation(
        source_table=source_table,
        selector=selector,
        scoring_month=selected_month,
        frame=frame,
    )


def resolve_scoring_month_for_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
    source_table: str = SCORING_SOURCE_TABLE,
) -> tuple[pd.Timestamp, str]:
    """Resolve explicit month or explicit latest-month selector."""

    _validate_selector(scoring_month=scoring_month, latest=latest)
    _validate_table_exists(connection, source_table)

    if scoring_month is not None:
        return parse_scoring_month(scoring_month), "scoring_month"

    latest_value = connection.execute(
        f"SELECT MAX(observation_month) FROM {source_table}"
    ).fetchone()[0]
    if latest_value is None:
        raise BatchScoringError(
            f"{source_table} has no rows, so Package 8 cannot resolve --latest"
        )
    latest_month = _normalize_month_value(
        latest_value,
        field_name="latest observation_month",
    )
    if latest_month.day != 1:
        raise BatchScoringError(
            "Package 8 latest observation_month must be the first day of a "
            "calendar month"
        )
    return latest_month, "latest"


def parse_scoring_month(value: str | date | pd.Timestamp) -> pd.Timestamp:
    """Parse the explicit `YYYY-MM-01` Package 8 scoring month."""

    if isinstance(value, str) and not MONTH_PATTERN.match(value):
        raise BatchScoringError(
            "Package 8 scoring month must use explicit YYYY-MM-01 format"
        )
    parsed = _normalize_month_value(value, field_name="scoring_month")
    if parsed.day != 1:
        raise BatchScoringError(
            "Package 8 scoring month must be the first day of a calendar month"
        )
    return parsed


def validate_feature_metadata(
    features: dict[str, object],
    *,
    scoring_columns: tuple[str, ...],
    run_id: str,
) -> dict[str, tuple[str, ...]]:
    """Validate Package 5 `features.json` for Package 8 scoring."""

    missing_keys = tuple(key for key in REQUIRED_FEATURE_KEYS if key not in features)
    if missing_keys:
        raise BatchScoringError(
            f"Package 5 features.json for run_id={run_id} missing key(s): "
            + ", ".join(missing_keys)
        )

    feature_lists: dict[str, tuple[str, ...]] = {}
    for key in REQUIRED_FEATURE_KEYS:
        value = features[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise BatchScoringError(
                f"Package 5 features.json for run_id={run_id} has invalid {key}"
            )
        feature_lists[key] = tuple(value)

    if not feature_lists["approved_features"]:
        raise BatchScoringError(
            f"Package 5 features.json for run_id={run_id} has no approved features"
        )

    expected_approved = (
        *feature_lists["numeric_features"],
        *feature_lists["categorical_features"],
    )
    if feature_lists["approved_features"] != expected_approved:
        raise BatchScoringError(
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
        raise BatchScoringError(str(error)) from error

    missing_columns = tuple(
        feature
        for feature in feature_lists["approved_features"]
        if feature not in set(scoring_columns)
    )
    if missing_columns:
        raise BatchScoringError(
            f"Package 5 features.json for run_id={run_id} references "
            "missing mart.account_month scoring column(s): "
            + ", ".join(missing_columns)
        )

    return feature_lists


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
    _validate_local_mlflow_uri(active_tracking_uri, purpose="tracking")
    _validate_local_mlflow_uri(active_registry_uri, purpose="registry")
    if mlflow_tracking_uri is not None:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    if mlflow_registry_uri is not None:
        mlflow.set_registry_uri(mlflow_registry_uri)
    return active_tracking_uri, active_registry_uri


def _validate_local_mlflow_uri(uri: str, *, purpose: str) -> None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        raise BatchScoringError(
            f"Package 8 MLflow {purpose} URI is missing or ambiguous"
        )
    if normalized_uri in REMOTE_MLFLOW_URI_NAMES:
        raise BatchScoringError(
            f"Package 8 MLflow {purpose} must remain local; "
            f"unsupported URI: {normalized_uri}"
        )

    parsed_uri = urlparse(normalized_uri)
    if parsed_uri.scheme not in LOCAL_MLFLOW_URI_SCHEMES:
        raise BatchScoringError(
            f"Package 8 MLflow {purpose} must remain local; "
            f"unsupported URI scheme: {parsed_uri.scheme}"
        )
    if parsed_uri.scheme in {"file", "sqlite"} and parsed_uri.netloc not in {
        "",
        "localhost",
    }:
        raise BatchScoringError(
            f"Package 8 MLflow {purpose} URI must point to a local path"
        )


def _load_promoted_scoring_model(
    target_key: str,
    *,
    mlflow_tracking_uri: str,
    mlflow_registry_uri: str,
    scoring_columns: tuple[str, ...],
    evidence_records: dict[str, tuple[dict[str, object], ...]],
) -> PromotedScoringModel:
    import mlflow
    import mlflow.sklearn
    from mlflow.tracking import MlflowClient

    policy = PACKAGE7_TARGETS[target_key]
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_registry_uri(mlflow_registry_uri)
    client = MlflowClient(
        tracking_uri=mlflow_tracking_uri,
        registry_uri=mlflow_registry_uri,
    )

    try:
        model_version = client.get_model_version_by_alias(
            policy.registered_model_name,
            CHAMPION_ALIAS,
        )
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise BatchScoringError(
            "Package 8 could not resolve required MLflow champion alias for "
            f"{policy.registered_model_name}"
        ) from error

    tags = dict(model_version.tags)
    _validate_model_version_tags(
        target_key=target_key,
        target_label=policy.target_label,
        registered_model_name=policy.registered_model_name,
        model_version=str(model_version.version),
        model_run_id=model_version.run_id,
        tags=tags,
    )
    source_run_id = tags["account_health.source_mlflow_run_id"]
    source_model_artifact_uri = tags["account_health.source_model_artifact_uri"]
    feature_metadata_artifact = tags["account_health.feature_metadata_artifact"]

    _cross_check_promotion_evidence(
        target_key=target_key,
        registered_model_name=policy.registered_model_name,
        model_version=str(model_version.version),
        source_mlflow_run_id=source_run_id,
        source_model_artifact_uri=source_model_artifact_uri,
        evidence_records=evidence_records,
    )
    features = validate_feature_metadata(
        _download_json_artifact(client, source_run_id, feature_metadata_artifact),
        scoring_columns=scoring_columns,
        run_id=source_run_id,
    )

    model_uri = f"models:/{policy.registered_model_name}@{CHAMPION_ALIAS}"
    try:
        model = mlflow.sklearn.load_model(model_uri)
    except Exception as error:  # noqa: BLE001 - MLflow wraps model load errors.
        raise BatchScoringError(
            "Package 8 could not load local MLflow champion model "
            f"{model_uri}"
        ) from error
    if not hasattr(model, "predict_proba"):
        raise BatchScoringError(
            f"Package 8 champion model {model_uri} does not expose predict_proba"
        )

    return PromotedScoringModel(
        target_key=target_key,
        target_label=policy.target_label,
        registered_model_name=policy.registered_model_name,
        alias=CHAMPION_ALIAS,
        model_uri=model_uri,
        model_version=str(model_version.version),
        source_mlflow_run_id=source_run_id,
        source_model_artifact_uri=source_model_artifact_uri,
        feature_metadata_artifact=feature_metadata_artifact,
        approved_features=features["approved_features"],
        numeric_features=features["numeric_features"],
        categorical_features=features["categorical_features"],
        model=model,
    )


def _validate_model_version_tags(
    *,
    target_key: str,
    target_label: str,
    registered_model_name: str,
    model_version: str,
    model_run_id: str,
    tags: dict[str, str],
) -> None:
    expected_tags = {
        "account_health.package": "package_7",
        "account_health.target_key": target_key,
        "account_health.target_label": target_label,
        "account_health.registered_model_name": registered_model_name,
        "account_health.alias": CHAMPION_ALIAS,
        "account_health.synthetic_data_only": "true",
        "account_health.consumer": "package_8_local_batch_scoring",
    }
    missing = tuple(key for key in expected_tags if key not in tags)
    mismatched = tuple(
        key for key, value in expected_tags.items() if tags.get(key) != value
    )
    required_lineage = (
        "account_health.source_mlflow_run_id",
        "account_health.source_model_artifact_uri",
        "account_health.selected_champion_model_family",
        "account_health.package6_selection_status",
        "account_health.package6_evaluation_version",
        "account_health.package6_manifest_path",
        "account_health.feature_metadata_artifact",
    )
    missing_lineage = tuple(key for key in required_lineage if key not in tags)
    errors: list[str] = []
    if missing:
        errors.append("missing tag(s): " + ", ".join(missing))
    if mismatched:
        errors.append("mismatched tag(s): " + ", ".join(mismatched))
    if missing_lineage:
        errors.append("missing lineage tag(s): " + ", ".join(missing_lineage))
    if tags.get("account_health.source_mlflow_run_id") != model_run_id:
        errors.append("source run tag does not match registered model version run_id")
    if errors:
        raise BatchScoringError(
            "Package 8 registry handoff validation failed for "
            f"{registered_model_name} version {model_version}: "
            + "; ".join(errors)
        )


def _load_promotion_evidence(
    *,
    database_path: str | Path,
    promotion_manifest_path: str | Path | None,
) -> tuple[dict[str, tuple[dict[str, object], ...]], tuple[str, ...]]:
    evidence: list[dict[str, object]] = []
    sources: list[str] = []
    if promotion_manifest_path is not None:
        manifest_file = Path(promotion_manifest_path)
        if manifest_file.is_file():
            evidence.extend(_read_promotion_manifest_records(manifest_file))
            sources.append(str(manifest_file))

    audit_records = _read_promotion_audit_records(database_path)
    if audit_records:
        evidence.extend(audit_records)
        sources.append("metadata.model_promotion_audit")

    if not evidence:
        raise BatchScoringError(
            "Package 8 requires Package 7 promotion manifest or audit evidence"
        )

    by_target: dict[str, list[dict[str, object]]] = {}
    for record in evidence:
        target_key = _required_evidence_string(record, "target_key")
        if target_key not in PACKAGE7_TARGETS:
            raise BatchScoringError(
                "Package 7 promotion evidence contains unsupported target_key: "
                f"{target_key}"
            )
        if _required_evidence_string(record, "promotion_status") != "promoted":
            continue
        by_target.setdefault(target_key, []).append(record)

    missing_targets = tuple(
        target_key for target_key in PACKAGE7_TARGETS if target_key not in by_target
    )
    if missing_targets:
        raise BatchScoringError(
            "Package 8 missing promoted Package 7 evidence for target(s): "
            + ", ".join(missing_targets)
        )

    latest_by_source: dict[str, list[dict[str, object]]] = {}
    for target_key, records in by_target.items():
        records_by_source: dict[str, list[dict[str, object]]] = {}
        for record in records:
            records_by_source.setdefault(str(record["_evidence_source"]), []).append(
                record
            )
        for source, source_records in records_by_source.items():
            latest_by_source.setdefault(target_key, []).append(
                _latest_evidence_record(source_records, source=source)
            )

    return (
        {key: tuple(value) for key, value in latest_by_source.items()},
        tuple(sources),
    )


def _read_promotion_manifest_records(manifest_path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BatchScoringError(
            f"Package 7 promotion manifest is malformed JSON: {manifest_path}"
        ) from error
    if not isinstance(payload, list):
        raise BatchScoringError(
            "Package 7 promotion manifest is malformed: expected a list"
        )
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in payload:
        if not isinstance(record, dict):
            raise BatchScoringError(
                "Package 7 promotion manifest is malformed: record is not an object"
            )
        target_key = _required_evidence_string(record, "target_key")
        if target_key in seen:
            raise BatchScoringError(
                "Package 7 promotion manifest has duplicate target evidence for "
                f"{target_key}"
            )
        seen.add(target_key)
        records.append({**record, "_evidence_source": str(manifest_path)})
    return records


def _read_promotion_audit_records(
    database_path: str | Path,
) -> list[dict[str, object]]:
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            if not _table_exists(connection, "metadata.model_promotion_audit"):
                return []
            frame = connection.execute(
                """
                SELECT
                    promotion_id,
                    promoted_at_utc,
                    promotion_version,
                    target_key,
                    target_label,
                    registered_model_name,
                    model_version,
                    alias,
                    source_mlflow_run_id,
                    source_model_artifact_uri,
                    package6_manifest_path,
                    package6_evaluation_version,
                    package6_selection_status,
                    promotion_status,
                    failure_reason
                FROM metadata.model_promotion_audit
                """
            ).fetchdf()
    except duckdb.IOException:
        return []
    return [
        {**record, "_evidence_source": "metadata.model_promotion_audit"}
        for record in frame.to_dict("records")
    ]


def _latest_evidence_record(
    records: list[dict[str, object]],
    *,
    source: str,
) -> dict[str, object]:
    if source.endswith("promotion_manifest.json") or source != "metadata.model_promotion_audit":
        if len(records) > 1:
            raise BatchScoringError(
                f"Package 7 promotion evidence from {source} is ambiguous"
            )
        return records[0]
    return sorted(
        records,
        key=lambda record: str(record.get("promoted_at_utc", "")),
        reverse=True,
    )[0]


def _cross_check_promotion_evidence(
    *,
    target_key: str,
    registered_model_name: str,
    model_version: str,
    source_mlflow_run_id: str,
    source_model_artifact_uri: str,
    evidence_records: dict[str, tuple[dict[str, object], ...]],
) -> None:
    records = evidence_records.get(target_key, ())
    if not records:
        raise BatchScoringError(
            f"Package 8 missing Package 7 promotion evidence for {target_key}"
        )
    for record in records:
        source = str(record["_evidence_source"])
        checks = {
            "registered_model_name": registered_model_name,
            "model_version": model_version,
            "source_mlflow_run_id": source_mlflow_run_id,
            "source_model_artifact_uri": source_model_artifact_uri,
        }
        mismatched = tuple(
            field
            for field, expected in checks.items()
            if str(record.get(field, "")) != str(expected)
        )
        if CHAMPION_ALIAS not in _evidence_aliases(record.get("alias")):
            mismatched = (*mismatched, "alias")
        if mismatched:
            raise BatchScoringError(
                "Package 8 registry alias disagrees with Package 7 promotion "
                f"evidence from {source} for target {target_key}: "
                + ", ".join(mismatched)
            )


def _download_json_artifact(client, run_id: str, artifact_path: str) -> dict[str, object]:
    try:
        with TemporaryDirectory() as temporary_directory:
            local_path = Path(
                client.download_artifacts(run_id, artifact_path, temporary_directory)
            )
            payload = json.loads(local_path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise BatchScoringError(
            f"Package 8 missing required Package 5 artefact '{artifact_path}' "
            f"for run_id={run_id}"
        ) from error
    if not isinstance(payload, dict):
        raise BatchScoringError(
            f"Package 5 artefact '{artifact_path}' for run_id={run_id} "
            "must be a JSON object"
        )
    return payload


def _validate_selector(
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
) -> None:
    if scoring_month is None and not latest:
        raise BatchScoringError(
            "Package 8 requires explicit --scoring-month YYYY-MM-01 or --latest"
        )
    if scoring_month is not None and latest:
        raise BatchScoringError(
            "Package 8 scoring selector is ambiguous: choose scoring month or latest"
        )


def _normalize_month_value(value: object, *, field_name: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value).normalize()
    except (TypeError, ValueError) as error:
        raise BatchScoringError(f"Package 8 has invalid {field_name}") from error
    if pd.isna(parsed):
        raise BatchScoringError(f"Package 8 has invalid {field_name}")
    return parsed


def _validate_scoring_source_table(source_table: str) -> None:
    if source_table != SCORING_SOURCE_TABLE:
        raise BatchScoringError(
            "Package 8 may only read mart.account_month; "
            f"received source_table={source_table}"
        )


def _source_columns(
    connection: duckdb.DuckDBPyConnection,
    source_table: str,
) -> tuple[str, ...]:
    schema_name, table_name = _split_table_name(source_table)
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ?
            AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema_name, table_name],
    ).fetchall()
    if not rows:
        raise BatchScoringError(f"{source_table} does not exist or has no columns")
    return tuple(row[0] for row in rows)


def _validate_required_scoring_source_columns(
    source_columns: tuple[str, ...],
    source_table: str,
) -> None:
    column_set = set(source_columns)
    required_columns = ("account_id", "observation_month")
    missing_columns = tuple(
        column for column in required_columns if column not in column_set
    )
    if missing_columns:
        raise BatchScoringError(
            f"{source_table} violates Package 8: missing required column(s): "
            + ", ".join(missing_columns)
        )


def _validate_scoring_population_frame(
    frame: pd.DataFrame,
    *,
    source_table: str,
    scoring_month: pd.Timestamp,
) -> None:
    if frame.empty:
        raise BatchScoringError(
            f"{source_table} has no rows for scoring_month="
            f"{scoring_month.date().isoformat()}"
        )
    if frame["account_id"].isna().any():
        raise BatchScoringError(
            f"{source_table} violates Package 8: null account_id"
        )
    frame_months = pd.to_datetime(frame["observation_month"]).dt.normalize()
    if frame_months.isna().any() or not (frame_months == scoring_month).all():
        raise BatchScoringError(
            f"{source_table} returned rows outside the selected scoring month"
        )
    duplicated = frame.duplicated(["account_id", "observation_month"])
    if duplicated.any():
        raise BatchScoringError(
            f"{source_table} violates Package 8: duplicate account-month grain"
        )


def _validate_table_exists(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> None:
    if not _table_exists(connection, table_name):
        raise BatchScoringError(f"{table_name} is required for Package 8")


def _table_exists(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> bool:
    schema_name, local_table_name = _split_table_name(table_name)
    return bool(
        connection.execute(
            """
            SELECT COUNT(*) > 0
            FROM information_schema.tables
            WHERE table_schema = ?
                AND table_name = ?
            """,
            [schema_name, local_table_name],
        ).fetchone()[0]
    )


def _split_table_name(table_name: str) -> tuple[str, str]:
    parts = table_name.split(".")
    if len(parts) != 2 or not all(parts):
        raise BatchScoringError(f"table must use schema.table form: {table_name}")
    return parts[0], parts[1]


def _required_evidence_string(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BatchScoringError(
            f"Package 7 promotion evidence missing or invalid field: {field}"
        )
    return value.strip()


def _evidence_aliases(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return set()
