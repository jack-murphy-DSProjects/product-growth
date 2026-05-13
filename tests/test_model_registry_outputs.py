from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from account_health.registry import (
    CHAMPION_ALIAS,
    ModelRegistryError,
    run_model_registry_promotion,
)
from test_model_registry_loading import (
    champion_record,
    create_source_run,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def create_promotion_inputs(tmp_path: Path) -> tuple[Path, Path]:
    tracking_dir, churn_run_id, churn_uri = create_source_run(
        tmp_path,
        target="churn_90d",
        candidate_model="logistic_regression",
        experiment_name="package-7-output-test",
    )
    _, expansion_run_id, expansion_uri = create_source_run(
        tmp_path,
        target="expansion_90d",
        candidate_model="random_forest",
        experiment_name="package-7-output-test",
    )
    manifest_path = write_manifest(
        tmp_path / "champion_selection_manifest.json",
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
    return tracking_dir, manifest_path


def test_run_model_registry_promotion_writes_manifest_and_audit(
    tmp_path: Path,
) -> None:
    tracking_dir, champion_manifest_path = create_promotion_inputs(tmp_path)
    promotion_manifest_path = (
        tmp_path / "data" / "outputs" / "model_registry" / "promotion_manifest.json"
    )
    database_path = tmp_path / "warehouse.duckdb"

    result = run_model_registry_promotion(
        champion_manifest_path=champion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
        promotion_manifest_path=promotion_manifest_path,
        database_path=database_path,
    )

    assert result.output_paths["promotion_manifest"] == str(promotion_manifest_path)
    assert result.output_paths["promotion_audit_table"] == (
        "metadata.model_promotion_audit"
    )
    manifest_records = json.loads(promotion_manifest_path.read_text(encoding="utf-8"))
    assert len(manifest_records) == 2
    assert {record["target_key"] for record in manifest_records} == {
        "churn",
        "expansion",
    }
    for record in manifest_records:
        assert record["promotion_id"] == result.promotion_id
        assert record["promotion_version"] == "package_7_promotion_v1"
        assert record["promotion_status"] == "promoted"
        assert record["failure_reason"] is None
        assert record["alias"] == CHAMPION_ALIAS
        assert record["synthetic_data_only"] is True
        assert record["package6_selection_status"] == "ml_champion_selected"

    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = {
            (row[0], row[1])
            for row in connection.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                """
            ).fetchall()
        }
        audit_rows = connection.execute(
            """
            SELECT target_key, promotion_status, alias
            FROM metadata.model_promotion_audit
            ORDER BY target_key
            """
        ).fetchall()

    assert ("metadata", "model_promotion_audit") in tables
    assert ("mart", "account_scores") not in tables
    assert ("mart", "account_health_band") not in tables
    assert audit_rows == [
        ("churn", "promoted", CHAMPION_ALIAS),
        ("expansion", "promoted", CHAMPION_ALIAS),
    ]

    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    assert client.get_model_version_by_alias(
        "account_health_churn_model",
        CHAMPION_ALIAS,
    )
    assert client.get_model_version_by_alias(
        "account_health_expansion_model",
        CHAMPION_ALIAS,
    )


def test_run_model_registry_promotion_writes_one_record_for_filtered_target(
    tmp_path: Path,
) -> None:
    tracking_dir, champion_manifest_path = create_promotion_inputs(tmp_path)
    promotion_manifest_path = tmp_path / "promotion_manifest.json"

    result = run_model_registry_promotion(
        champion_manifest_path=champion_manifest_path,
        targets=("churn",),
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
        promotion_manifest_path=promotion_manifest_path,
        database_path=tmp_path / "warehouse.duckdb",
    )

    manifest_records = json.loads(promotion_manifest_path.read_text(encoding="utf-8"))
    assert [record["target_key"] for record in manifest_records] == ["churn"]
    assert [record["target_key"] for record in result.promotion_records] == ["churn"]


def test_run_model_registry_promotion_rejects_unignored_repo_manifest_path(
    tmp_path: Path,
) -> None:
    tracking_dir, champion_manifest_path = create_promotion_inputs(tmp_path)
    unsafe_manifest_path = ROOT / "promotion_manifest.json"

    with pytest.raises(ModelRegistryError, match="promotion manifest path"):
        run_model_registry_promotion(
            champion_manifest_path=champion_manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
            promotion_manifest_path=unsafe_manifest_path,
            database_path=tmp_path / "warehouse.duckdb",
        )

    assert not unsafe_manifest_path.exists()
    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    with pytest.raises(MlflowException):
        client.get_registered_model("account_health_churn_model")
