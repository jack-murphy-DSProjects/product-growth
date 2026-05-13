"""Local MLflow registry promotion service for Package 7."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from account_health.registry.loading import (
    CHAMPION_ALIAS,
    ModelRegistryError,
    PromotionCandidate,
    PromotionPlan,
)


@dataclass(frozen=True)
class PromotedModelVersion:
    """One local MLflow registered model version promoted by Package 7."""

    target_key: str
    target_label: str
    registered_model_name: str
    model_version: str
    alias: str
    source_mlflow_run_id: str
    source_model_artifact_uri: str
    selected_champion_model_family: str
    tags: dict[str, str]


@dataclass(frozen=True)
class RegistryPromotionResult:
    """Result of local MLflow registry writes only."""

    promoted_at_utc: str
    promotion_version: str
    promoted_versions: tuple[PromotedModelVersion, ...]


def promote_model_versions(
    plan: PromotionPlan,
    *,
    promoted_at_utc: str | None = None,
) -> RegistryPromotionResult:
    """Register validated Package 6 ML champions in the local MLflow registry."""

    import mlflow
    from mlflow.tracking import MlflowClient

    promoted_at = promoted_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat()
    mlflow.set_tracking_uri(plan.mlflow_tracking_uri)
    mlflow.set_registry_uri(plan.mlflow_registry_uri)
    client = MlflowClient(
        tracking_uri=plan.mlflow_tracking_uri,
        registry_uri=plan.mlflow_registry_uri,
    )

    promoted_versions: list[PromotedModelVersion] = []
    for candidate in plan.candidates:
        tags = build_model_version_tags(
            candidate,
            plan=plan,
            promoted_at_utc=promoted_at,
        )
        model_version = _register_model_version(candidate)
        _write_registry_tags(
            client,
            candidate=candidate,
            model_version=str(model_version.version),
            tags=tags,
        )
        client.set_registered_model_alias(
            candidate.registered_model_name,
            CHAMPION_ALIAS,
            str(model_version.version),
        )
        promoted_versions.append(
            PromotedModelVersion(
                target_key=candidate.target_key,
                target_label=candidate.target_label,
                registered_model_name=candidate.registered_model_name,
                model_version=str(model_version.version),
                alias=CHAMPION_ALIAS,
                source_mlflow_run_id=candidate.mlflow_run_id,
                source_model_artifact_uri=candidate.model_artifact_uri,
                selected_champion_model_family=(
                    candidate.selected_champion_model_family
                ),
                tags=tags,
            )
        )

    return RegistryPromotionResult(
        promoted_at_utc=promoted_at,
        promotion_version=plan.promotion_version,
        promoted_versions=tuple(promoted_versions),
    )


def build_model_version_tags(
    candidate: PromotionCandidate,
    *,
    plan: PromotionPlan,
    promoted_at_utc: str,
) -> dict[str, str]:
    """Build documented Package 7 MLflow tags for a promoted model version."""

    tags = {
        "account_health.package": "package_7",
        "account_health.target_key": candidate.target_key,
        "account_health.target_label": candidate.target_label,
        "account_health.registered_model_name": candidate.registered_model_name,
        "account_health.alias": CHAMPION_ALIAS,
        "account_health.source_mlflow_run_id": candidate.mlflow_run_id,
        "account_health.source_model_artifact_uri": candidate.model_artifact_uri,
        "account_health.selected_champion_model_family": (
            candidate.selected_champion_model_family
        ),
        "account_health.package6_selection_status": (
            candidate.package6_selection_status
        ),
        "account_health.package6_evaluation_version": (
            candidate.package6_evaluation_version
        ),
        "account_health.package6_manifest_path": str(plan.manifest_path),
        "account_health.package6_created_at_utc": candidate.package6_created_at_utc,
        "account_health.package7_promotion_version": plan.promotion_version,
        "account_health.promoted_at_utc": promoted_at_utc,
        "account_health.synthetic_data_only": "true",
        "account_health.consumer": "package_8_local_batch_scoring",
    }
    train_end_month = candidate.split_config.get("train_end_month")
    if train_end_month is not None:
        tags["account_health.train_end_month"] = str(train_end_month)
    if candidate.feature_metadata:
        tags["account_health.feature_metadata_artifact"] = "features.json"
    if candidate.split_config:
        tags["account_health.split_config_artifact"] = "split_config.json"
    return tags


def _register_model_version(candidate: PromotionCandidate):
    import mlflow

    try:
        return mlflow.register_model(
            candidate.model_artifact_uri,
            candidate.registered_model_name,
            await_registration_for=60,
        )
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise ModelRegistryError(
            "Package 7 could not create local MLflow registered model version "
            f"for {candidate.registered_model_name}"
        ) from error


def _write_registry_tags(
    client,
    *,
    candidate: PromotionCandidate,
    model_version: str,
    tags: dict[str, str],
) -> None:
    try:
        client.set_registered_model_tag(
            candidate.registered_model_name,
            "account_health.package",
            "package_7",
        )
        client.set_registered_model_tag(
            candidate.registered_model_name,
            "account_health.target_key",
            candidate.target_key,
        )
        client.set_registered_model_tag(
            candidate.registered_model_name,
            "account_health.synthetic_data_only",
            "true",
        )
        for key, value in tags.items():
            client.set_model_version_tag(
                candidate.registered_model_name,
                model_version,
                key,
                value,
            )
    except Exception as error:  # noqa: BLE001 - MLflow raises backend-specific errors.
        raise ModelRegistryError(
            "Package 7 could not write local MLflow registry tags for "
            f"{candidate.registered_model_name} version {model_version}"
        ) from error
