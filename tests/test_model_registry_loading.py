from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import mlflow.sklearn
import pytest
from sklearn.dummy import DummyClassifier

from account_health.registry import ModelRegistryError, load_promotion_plan


def create_source_run(
    tmp_path: Path,
    *,
    target: str = "churn_90d",
    candidate_model: str = "logistic_regression",
    experiment_name: str = "package-7-loading-test",
    log_model: bool = True,
) -> tuple[Path, str, str]:
    tracking_dir = tmp_path / "mlruns"
    mlflow.set_tracking_uri(str(tracking_dir))
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "target": target,
                "candidate_model": candidate_model,
                "train_end_month": "2024-02-01",
            }
        )
        mlflow.log_dict(
            {
                "approved_features": ["feature_1"],
                "numeric_features": ["feature_1"],
                "categorical_features": [],
            },
            "features.json",
        )
        mlflow.log_dict(
            {
                "train_end_month": "2024-02-01",
                "train_row_count": 4,
                "test_row_count": 2,
                "train_observation_month_min": "2024-01-01",
                "train_observation_month_max": "2024-02-01",
                "test_observation_month_min": "2024-03-01",
                "test_observation_month_max": "2024-04-01",
            },
            "split_config.json",
        )
        if log_model:
            model = DummyClassifier(strategy="most_frequent")
            model.fit([[0.0], [1.0], [2.0], [3.0]], [0, 1, 0, 1])
            with TemporaryDirectory() as temporary_directory:
                model_path = Path(temporary_directory) / "model"
                mlflow.sklearn.save_model(model, path=str(model_path))
                mlflow.log_artifacts(str(model_path), artifact_path="model")
        else:
            mlflow.log_text("not an MLflow model", "model/not_a_model.txt")
        run_id = run.info.run_id
    return tracking_dir, run_id, f"runs:/{run_id}/model"


def champion_record(
    *,
    target: str = "churn_90d",
    model_family: str = "logistic_regression",
    run_id: str | None,
    model_uri: str | None,
    status: str = "ml_champion_selected",
) -> dict[str, object]:
    return {
        "target": target,
        "selected_champion_model_family": model_family,
        "mlflow_run_id": run_id,
        "model_artifact_uri": model_uri,
        "selection_status": status,
        "primary_metric": "precision_at_top_10_pct",
        "key_topk_metrics": {"precision_at_k": 0.8},
        "comparison_versus_baseline": {"precision_delta": 0.2},
        "calibration_caveats": [],
        "segment_caveats": [],
        "temporal_caveats": [],
        "utility_caveats": ["illustrative utility only"],
        "synthetic_data_caveat": "Synthetic data only.",
        "created_at_utc": "2026-05-10T00:00:00+00:00",
        "evaluation_version": "package_6_evaluation_v1",
    }


def write_manifest(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_load_promotion_plan_validates_churn_and_expansion(
    tmp_path: Path,
) -> None:
    tracking_dir, churn_run_id, churn_uri = create_source_run(
        tmp_path,
        target="churn_90d",
        candidate_model="logistic_regression",
    )
    _, expansion_run_id, expansion_uri = create_source_run(
        tmp_path,
        target="expansion_90d",
        candidate_model="random_forest",
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

    plan = load_promotion_plan(
        manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )

    assert {
        candidate.registered_model_name for candidate in plan.candidates
    } == {
        "account_health_churn_model",
        "account_health_expansion_model",
    }
    assert {candidate.target_key for candidate in plan.candidates} == {
        "churn",
        "expansion",
    }


def test_load_promotion_plan_supports_target_filtering(tmp_path: Path) -> None:
    tracking_dir, churn_run_id, churn_uri = create_source_run(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [champion_record(run_id=churn_run_id, model_uri=churn_uri)],
    )

    plan = load_promotion_plan(
        manifest_path,
        targets=("churn",),
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )

    assert [candidate.target_key for candidate in plan.candidates] == ["churn"]


def test_load_promotion_plan_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ModelRegistryError, match="manifest.*not found"):
        load_promotion_plan(
            tmp_path / "missing.json",
            targets=("churn",),
            mlflow_tracking_uri=str(tmp_path / "mlruns"),
            mlflow_registry_uri=str(tmp_path / "mlruns"),
        )


def test_load_promotion_plan_rejects_malformed_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "champions.json"
    manifest_path.write_text('{"target": "churn_90d"}', encoding="utf-8")

    with pytest.raises(ModelRegistryError, match="expected a list"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tmp_path / "mlruns"),
            mlflow_registry_uri=str(tmp_path / "mlruns"),
        )


def test_load_promotion_plan_rejects_duplicate_target_evidence(
    tmp_path: Path,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [
            champion_record(run_id=run_id, model_uri=model_uri),
            champion_record(run_id=run_id, model_uri=model_uri),
        ],
    )

    with pytest.raises(ModelRegistryError, match="duplicate target evidence"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_promotion_plan_rejects_missing_target_entry(
    tmp_path: Path,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [champion_record(run_id=run_id, model_uri=model_uri)],
    )

    with pytest.raises(ModelRegistryError, match="missing required target"):
        load_promotion_plan(
            manifest_path,
            targets=("expansion",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("baseline_retained", "baseline retained"),
        (
            "no_ml_candidate_sufficiently_beats_baseline",
            "no ML champion selected",
        ),
        ("insufficient_evidence", "insufficient evidence"),
    ],
)
def test_load_promotion_plan_rejects_non_promotable_package_6_outcomes(
    tmp_path: Path,
    status: str,
    message: str,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [champion_record(run_id=run_id, model_uri=model_uri, status=status)],
    )

    with pytest.raises(ModelRegistryError, match=message):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_promotion_plan_rejects_baseline_model_family(
    tmp_path: Path,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [
            champion_record(
                model_family="rule_baseline",
                run_id=run_id,
                model_uri=model_uri,
            )
        ],
    )

    with pytest.raises(ModelRegistryError, match="not an approved Package 5 ML candidate"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("mlflow_run_id", None, "mlflow_run_id"),
        ("model_artifact_uri", None, "model_artifact_uri"),
        ("model_artifact_uri", "file:///tmp/model", "runs:/<run_id>"),
    ],
)
def test_load_promotion_plan_rejects_missing_or_invalid_source_references(
    tmp_path: Path,
    field: str,
    value: str | None,
    message: str,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    record = champion_record(run_id=run_id, model_uri=model_uri)
    record[field] = value
    manifest_path = write_manifest(tmp_path / "champions.json", [record])

    with pytest.raises(ModelRegistryError, match=message):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_promotion_plan_rejects_missing_source_run(tmp_path: Path) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path)
    missing_uri = model_uri.replace(run_id, "missing_run_id")
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [champion_record(run_id="missing_run_id", model_uri=missing_uri)],
    )

    with pytest.raises(ModelRegistryError, match="source run"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )


def test_load_promotion_plan_rejects_remote_mlflow_uris(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path / "champions.json", [])

    with pytest.raises(ModelRegistryError, match="must remain local"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri="https://example.com/mlflow",
            mlflow_registry_uri=str(tmp_path / "mlruns"),
        )
    with pytest.raises(ModelRegistryError, match="must remain local"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tmp_path / "mlruns"),
            mlflow_registry_uri="https://example.com/mlflow",
        )


def test_load_promotion_plan_rejects_empty_mlflow_uris(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path / "champions.json", [])

    with pytest.raises(ModelRegistryError, match="missing or ambiguous"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri="",
            mlflow_registry_uri=str(tmp_path / "mlruns"),
        )
    with pytest.raises(ModelRegistryError, match="missing or ambiguous"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tmp_path / "mlruns"),
            mlflow_registry_uri="",
        )


def test_load_promotion_plan_rejects_inherited_remote_tracking_uri(
    tmp_path: Path,
) -> None:
    old_tracking_uri = mlflow.get_tracking_uri()
    old_registry_uri = mlflow.get_registry_uri()
    mlflow.set_tracking_uri("https://example.com/mlflow")
    mlflow.set_registry_uri(str(tmp_path / "mlruns"))
    try:
        with pytest.raises(ModelRegistryError, match="must remain local"):
            load_promotion_plan(
                tmp_path / "missing.json",
                targets=("churn",),
            )
    finally:
        mlflow.set_tracking_uri(old_tracking_uri)
        mlflow.set_registry_uri(old_registry_uri)


def test_load_promotion_plan_rejects_unloadable_source_model(
    tmp_path: Path,
) -> None:
    tracking_dir, run_id, model_uri = create_source_run(tmp_path, log_model=False)
    manifest_path = write_manifest(
        tmp_path / "champions.json",
        [champion_record(run_id=run_id, model_uri=model_uri)],
    )

    with pytest.raises(ModelRegistryError, match="could not load"):
        load_promotion_plan(
            manifest_path,
            targets=("churn",),
            mlflow_tracking_uri=str(tracking_dir),
            mlflow_registry_uri=str(tracking_dir),
        )
