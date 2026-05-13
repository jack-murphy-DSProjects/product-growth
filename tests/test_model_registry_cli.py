from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
from mlflow.tracking import MlflowClient

from test_model_registry_loading import (
    champion_record,
    create_source_run,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def create_cli_inputs(tmp_path: Path) -> tuple[Path, Path]:
    tracking_dir, run_id, model_uri = create_source_run(
        tmp_path,
        target="churn_90d",
        candidate_model="logistic_regression",
        experiment_name="package-7-cli-test",
    )
    manifest_path = write_manifest(
        tmp_path / "champion_selection_manifest.json",
        [champion_record(run_id=run_id, model_uri=model_uri)],
    )
    return tracking_dir, manifest_path


def test_promote_model_registry_cli_writes_outputs_and_registry_alias(
    tmp_path: Path,
) -> None:
    tracking_dir, champion_manifest_path = create_cli_inputs(tmp_path)
    promotion_manifest_path = tmp_path / "promotion_manifest.json"
    warehouse_path = tmp_path / "warehouse.duckdb"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/promote_model_registry.py",
            "--champion-manifest-path",
            str(champion_manifest_path),
            "--warehouse-path",
            str(warehouse_path),
            "--promotion-manifest-path",
            str(promotion_manifest_path),
            "--mlflow-tracking-uri",
            str(tracking_dir),
            "--mlflow-registry-uri",
            str(tracking_dir),
            "--target",
            "churn",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "promoted_count: 1" in result.stdout
    assert "registered_model=account_health_churn_model" in result.stdout
    manifest_records = json.loads(promotion_manifest_path.read_text(encoding="utf-8"))
    assert [record["target_key"] for record in manifest_records] == ["churn"]

    client = MlflowClient(
        tracking_uri=str(tracking_dir),
        registry_uri=str(tracking_dir),
    )
    alias_version = client.get_model_version_by_alias(
        "account_health_churn_model",
        "champion",
    )
    assert alias_version.tags["account_health.package"] == "package_7"

    with duckdb.connect(str(warehouse_path), read_only=True) as connection:
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM metadata.model_promotion_audit"
        ).fetchone()[0]
        mart_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'mart'
                """
            ).fetchall()
        }

    assert audit_count == 1
    assert "account_scores" not in mart_tables
    assert "account_health_band" not in mart_tables


def test_promote_model_registry_cli_reports_validation_failures(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/promote_model_registry.py",
            "--champion-manifest-path",
            str(tmp_path / "missing.json"),
            "--warehouse-path",
            str(tmp_path / "warehouse.duckdb"),
            "--promotion-manifest-path",
            str(tmp_path / "promotion_manifest.json"),
            "--mlflow-tracking-uri",
            str(tmp_path / "mlruns"),
            "--mlflow-registry-uri",
            str(tmp_path / "mlruns"),
            "--target",
            "churn",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "Package 7 promotion failed:" in result.stderr
    assert not (tmp_path / "promotion_manifest.json").exists()


def test_makefile_promote_model_registry_target_invokes_cli() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "promote-model-registry:" in makefile_text
    assert "scripts/promote_model_registry.py" in makefile_text
    assert "CHAMPION_MANIFEST_PATH" in makefile_text
    assert "PROMOTION_MANIFEST_PATH" in makefile_text
    assert "PROMOTION_TARGETS" in makefile_text
