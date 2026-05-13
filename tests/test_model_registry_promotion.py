from __future__ import annotations

from pathlib import Path

import pytest
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from account_health.registry import (
    CHAMPION_ALIAS,
    load_promotion_plan,
    promote_model_versions,
)
from test_model_registry_loading import (
    champion_record,
    create_source_run,
    write_manifest,
)


def build_valid_plan(
    tmp_path: Path,
    *,
    targets: tuple[str, ...] = ("churn", "expansion"),
):
    tracking_dir, churn_run_id, churn_uri = create_source_run(
        tmp_path,
        target="churn_90d",
        candidate_model="logistic_regression",
        experiment_name="package-7-promotion-test",
    )
    _, expansion_run_id, expansion_uri = create_source_run(
        tmp_path,
        target="expansion_90d",
        candidate_model="random_forest",
        experiment_name="package-7-promotion-test",
    )
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [
            champion_record(run_id=churn_run_id, model_uri=churn_uri),
            champion_record(
                target="expansion_90d",
                model_family="random_forest",
                run_id=expansion_run_id,
                model_uri=expansion_uri,
            ),
        ],
    )
    return (
        tracking_dir,
        load_promotion_plan(
            manifest_path,
            targets=targets,
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        ),
    )


def test_promote_model_versions_creates_target_specific_versions_and_aliases(
    tmp_path: Path,
) -> None:
    tracking_dir, plan = build_valid_plan(tmp_path)

    result = promote_model_versions(
        plan,
        promoted_at_utc="2026-05-10T00:00:00+00:00",
    )

    assert result.promotion_version == "package_7_promotion_v1"
    assert {
        promoted.registered_model_name for promoted in result.promoted_versions
    } == {
        "account_health_churn_model",
        "account_health_expansion_model",
    }

    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    for promoted in result.promoted_versions:
        registered_model = client.get_registered_model(promoted.registered_model_name)
        model_version = client.get_model_version(
            promoted.registered_model_name,
            promoted.model_version,
        )
        alias_version = client.get_model_version_by_alias(
            promoted.registered_model_name,
            CHAMPION_ALIAS,
        )

        assert registered_model.name == promoted.registered_model_name
        assert str(alias_version.version) == promoted.model_version
        assert model_version.run_id == promoted.source_mlflow_run_id
        assert model_version.current_stage == "None"
        assert model_version.tags["account_health.package"] == "package_7"
        assert model_version.tags["account_health.alias"] == CHAMPION_ALIAS
        assert model_version.tags["account_health.target_key"] == promoted.target_key
        assert (
            model_version.tags["account_health.source_mlflow_run_id"]
            == promoted.source_mlflow_run_id
        )
        assert (
            model_version.tags["account_health.package6_selection_status"]
            == "ml_champion_selected"
        )
        assert (
            model_version.tags["account_health.consumer"]
            == "package_8_local_batch_scoring"
        )
        assert model_version.tags["account_health.synthetic_data_only"] == "true"
        assert model_version.tags["account_health.train_end_month"] == "2024-02-01"


def test_promote_model_versions_respects_target_filtering(tmp_path: Path) -> None:
    tracking_dir, plan = build_valid_plan(tmp_path, targets=("churn",))

    result = promote_model_versions(plan)

    assert [promoted.target_key for promoted in result.promoted_versions] == ["churn"]
    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    assert (
        str(
            client.get_model_version_by_alias(
                "account_health_churn_model",
                CHAMPION_ALIAS,
            ).version
        )
        == result.promoted_versions[0].model_version
    )
    with pytest.raises(MlflowException):
        client.get_registered_model("account_health_expansion_model")


def test_promote_model_versions_rerun_creates_new_version_and_moves_alias(
    tmp_path: Path,
) -> None:
    tracking_dir, plan = build_valid_plan(tmp_path, targets=("churn",))

    first = promote_model_versions(
        plan,
        promoted_at_utc="2026-05-10T00:00:00+00:00",
    )
    second = promote_model_versions(
        plan,
        promoted_at_utc="2026-05-10T00:01:00+00:00",
    )

    first_version = first.promoted_versions[0].model_version
    second_version = second.promoted_versions[0].model_version
    assert int(second_version) > int(first_version)

    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    alias_version = client.get_model_version_by_alias(
        "account_health_churn_model",
        CHAMPION_ALIAS,
    )
    assert str(alias_version.version) == second_version
