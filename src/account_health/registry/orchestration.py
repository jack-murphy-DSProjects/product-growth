"""Package 7 promotion orchestration and local output writers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from account_health.registry.loading import (
    DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH,
    PACKAGE7_TARGETS,
    ModelRegistryError,
    PromotionPlan,
    load_promotion_plan,
)
from account_health.registry.promotion import (
    RegistryPromotionResult,
    promote_model_versions,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

DEFAULT_PROMOTION_MANIFEST_PATH = Path(
    "data/outputs/model_registry/promotion_manifest.json"
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMOTION_MANIFEST_REPO_DIR = Path("data/outputs/model_registry")
MODEL_PROMOTION_AUDIT_TABLE = "metadata.model_promotion_audit"


@dataclass(frozen=True)
class ModelRegistryPromotionResult:
    """Summary of one local Package 7 promotion run."""

    promotion_id: str
    promoted_at_utc: str
    promotion_version: str
    promotion_records: tuple[dict[str, object], ...]
    registry_result: RegistryPromotionResult
    output_paths: dict[str, str]


def run_model_registry_promotion(
    *,
    champion_manifest_path: str | Path = DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH,
    targets: tuple[str, ...] = tuple(PACKAGE7_TARGETS),
    mlflow_tracking_uri: str | None = None,
    mlflow_registry_uri: str | None = None,
    promotion_manifest_path: str | Path = DEFAULT_PROMOTION_MANIFEST_PATH,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    write_manifest: bool = True,
    write_audit: bool = True,
) -> ModelRegistryPromotionResult:
    """Validate, promote, and write local Package 7 promotion outputs."""

    promoted_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()
    promotion_id = uuid4().hex
    if write_manifest:
        validate_promotion_manifest_path(promotion_manifest_path)
    plan = load_promotion_plan(
        champion_manifest_path,
        targets=targets,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_registry_uri=mlflow_registry_uri,
    )
    registry_result = promote_model_versions(
        plan,
        promoted_at_utc=promoted_at_utc,
    )
    promotion_records = _promotion_records(
        promotion_id=promotion_id,
        plan=plan,
        registry_result=registry_result,
    )

    output_paths: dict[str, str] = {}
    if write_manifest:
        manifest_path = write_promotion_manifest(
            promotion_manifest_path,
            promotion_records,
        )
        output_paths["promotion_manifest"] = str(manifest_path)
    if write_audit:
        write_promotion_audit_table(database_path, promotion_records)
        output_paths["promotion_audit_table"] = MODEL_PROMOTION_AUDIT_TABLE

    return ModelRegistryPromotionResult(
        promotion_id=promotion_id,
        promoted_at_utc=promoted_at_utc,
        promotion_version=plan.promotion_version,
        promotion_records=promotion_records,
        registry_result=registry_result,
        output_paths=output_paths,
    )


def write_promotion_manifest(
    manifest_path: str | Path,
    promotion_records: tuple[dict[str, object], ...],
) -> Path:
    """Write the ignored local Package 7 promotion manifest."""

    output_path = Path(manifest_path)
    validate_promotion_manifest_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(list(promotion_records), indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def validate_promotion_manifest_path(manifest_path: str | Path) -> None:
    """Keep repo-local promotion manifests under the ignored Package 7 path."""

    output_path = Path(manifest_path).resolve()
    project_root = PROJECT_ROOT.resolve()
    if not output_path.is_relative_to(project_root):
        return

    allowed_dir = (project_root / PROMOTION_MANIFEST_REPO_DIR).resolve()
    if output_path.is_relative_to(allowed_dir):
        return

    raise ModelRegistryError(
        "Package 7 promotion manifest path must be under ignored local output "
        f"directory {PROMOTION_MANIFEST_REPO_DIR}"
    )


def write_promotion_audit_table(
    database_path: str | Path,
    promotion_records: tuple[dict[str, object], ...],
) -> None:
    """Append local Package 7 promotion audit records to DuckDB metadata."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
        connection.execute(_create_promotion_audit_table_sql())
        connection.executemany(
            f"""
            INSERT INTO {MODEL_PROMOTION_AUDIT_TABLE}
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record["promotion_id"],
                    record["promoted_at_utc"],
                    record["promotion_version"],
                    record["target_key"],
                    record["target_label"],
                    record["registered_model_name"],
                    record["model_version"],
                    record["alias"],
                    record["source_mlflow_run_id"],
                    record["source_model_artifact_uri"],
                    record["package6_manifest_path"],
                    record["package6_evaluation_version"],
                    record["package6_selection_status"],
                    record["promotion_status"],
                    record["failure_reason"],
                )
                for record in promotion_records
            ],
        )


def _promotion_records(
    *,
    promotion_id: str,
    plan: PromotionPlan,
    registry_result: RegistryPromotionResult,
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "promotion_id": promotion_id,
            "promotion_version": registry_result.promotion_version,
            "promoted_at_utc": registry_result.promoted_at_utc,
            "target_key": promoted.target_key,
            "target_label": promoted.target_label,
            "registered_model_name": promoted.registered_model_name,
            "model_version": promoted.model_version,
            "alias": promoted.alias,
            "source_mlflow_run_id": promoted.source_mlflow_run_id,
            "source_model_artifact_uri": promoted.source_model_artifact_uri,
            "selected_champion_model_family": (
                promoted.selected_champion_model_family
            ),
            "package6_manifest_path": str(plan.manifest_path),
            "package6_evaluation_version": _candidate_by_target(plan)[
                promoted.target_key
            ].package6_evaluation_version,
            "package6_selection_status": "ml_champion_selected",
            "package6_created_at_utc": _candidate_by_target(plan)[
                promoted.target_key
            ].package6_created_at_utc,
            "promotion_status": "promoted",
            "failure_reason": None,
            "synthetic_data_only": True,
        }
        for promoted in registry_result.promoted_versions
    )


def _candidate_by_target(plan: PromotionPlan):
    return {candidate.target_key: candidate for candidate in plan.candidates}


def _create_promotion_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {MODEL_PROMOTION_AUDIT_TABLE} (
        promotion_id VARCHAR,
        promoted_at_utc VARCHAR,
        promotion_version VARCHAR,
        target_key VARCHAR,
        target_label VARCHAR,
        registered_model_name VARCHAR,
        model_version VARCHAR,
        alias VARCHAR,
        source_mlflow_run_id VARCHAR,
        source_model_artifact_uri VARCHAR,
        package6_manifest_path VARCHAR,
        package6_evaluation_version VARCHAR,
        package6_selection_status VARCHAR,
        promotion_status VARCHAR,
        failure_reason VARCHAR
    )
    """
