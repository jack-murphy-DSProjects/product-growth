"""Package 8 raw batch score generation and local DuckDB writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import numpy as np
import pandas as pd

from account_health.registry import DEFAULT_PROMOTION_MANIFEST_PATH
from account_health.scoring.loading import (
    BATCH_SCORING_AUDIT_TABLE,
    DEFAULT_BATCH_SCORING_EXPORT_DIR,
    SCORE_OUTPUT_TABLE,
    SCORING_VERSION,
    BatchScoringError,
    BatchScoringInputs,
    PromotedScoringModel,
    load_batch_scoring_inputs,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BatchScoringResult:
    """Summary of one local Package 8 raw scoring run."""

    scoring_run_id: str
    scored_at_utc: str
    scoring_version: str
    scoring_month: pd.Timestamp
    selector: str
    row_count_read: int
    row_count_written: int
    score_frame: pd.DataFrame
    output_paths: dict[str, str]


def run_batch_scoring(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | pd.Timestamp | None = None,
    latest: bool = False,
    promotion_manifest_path: str | Path | None = DEFAULT_PROMOTION_MANIFEST_PATH,
    mlflow_tracking_uri: str | None = None,
    mlflow_registry_uri: str | None = None,
    export_dir: str | Path | None = None,
    write_tables: bool = True,
) -> BatchScoringResult:
    """Validate inputs, generate raw scores, and write local Package 8 tables."""

    inputs = load_batch_scoring_inputs(
        database_path,
        scoring_month=scoring_month,
        latest=latest,
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_registry_uri=mlflow_registry_uri,
    )
    result = score_batch_inputs(inputs)
    output_paths: dict[str, str] = {}
    if write_tables:
        write_batch_scoring_tables(database_path, inputs=inputs, result=result)
        output_paths = {
            "score_table": SCORE_OUTPUT_TABLE,
            "audit_table": BATCH_SCORING_AUDIT_TABLE,
        }
    if export_dir is not None:
        export_path = write_batch_scoring_export(export_dir, result)
        output_paths["score_export"] = str(export_path)
    return BatchScoringResult(
        scoring_run_id=result.scoring_run_id,
        scored_at_utc=result.scored_at_utc,
        scoring_version=result.scoring_version,
        scoring_month=result.scoring_month,
        selector=result.selector,
        row_count_read=result.row_count_read,
        row_count_written=result.row_count_written,
        score_frame=result.score_frame,
        output_paths=output_paths,
    )


def score_batch_inputs(
    inputs: BatchScoringInputs,
    *,
    scoring_run_id: str | None = None,
    scored_at_utc: str | None = None,
) -> BatchScoringResult:
    """Generate raw churn and expansion probabilities for validated inputs."""

    run_id = scoring_run_id or uuid4().hex
    scored_at = scored_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat()
    population = inputs.population.frame.reset_index(drop=True)
    churn_scores = predict_positive_probabilities(
        inputs.churn_model,
        population,
    )
    expansion_scores = predict_positive_probabilities(
        inputs.expansion_model,
        population,
    )

    score_frame = pd.DataFrame(
        {
            "scoring_run_id": run_id,
            "account_id": population["account_id"].astype(str),
            "observation_month": pd.to_datetime(
                population["observation_month"]
            ).dt.date,
            "churn_score": churn_scores,
            "expansion_score": expansion_scores,
            "churn_registered_model_name": (
                inputs.churn_model.registered_model_name
            ),
            "churn_model_version": inputs.churn_model.model_version,
            "expansion_registered_model_name": (
                inputs.expansion_model.registered_model_name
            ),
            "expansion_model_version": inputs.expansion_model.model_version,
            "scored_at_utc": scored_at,
            "scoring_version": SCORING_VERSION,
        }
    )
    _validate_score_frame(score_frame, population)
    return BatchScoringResult(
        scoring_run_id=run_id,
        scored_at_utc=scored_at,
        scoring_version=SCORING_VERSION,
        scoring_month=inputs.population.scoring_month,
        selector=inputs.population.selector,
        row_count_read=len(population),
        row_count_written=len(score_frame),
        score_frame=score_frame,
        output_paths={},
    )


def predict_positive_probabilities(
    promoted_model: PromotedScoringModel,
    scoring_frame: pd.DataFrame,
) -> pd.Series:
    """Predict and validate bounded class-1 probabilities for one target."""

    feature_frame = scoring_frame.loc[:, list(promoted_model.approved_features)]
    try:
        probabilities = promoted_model.model.predict_proba(feature_frame)
    except Exception as error:  # noqa: BLE001 - sklearn estimators vary.
        raise BatchScoringError(
            "Package 8 model inference failed for "
            f"{promoted_model.registered_model_name}"
        ) from error

    probability_array = np.asarray(probabilities)
    if probability_array.ndim != 2 or probability_array.shape[0] != len(scoring_frame):
        raise BatchScoringError(
            "Package 8 probability shape is invalid for "
            f"{promoted_model.registered_model_name}"
        )
    positive_index = _positive_probability_index(
        promoted_model,
        probability_array=probability_array,
    )
    values = pd.Series(probability_array[:, positive_index], index=scoring_frame.index)
    return validate_probability_values(values, target_key=promoted_model.target_key)


def validate_probability_values(values: pd.Series, *, target_key: str) -> pd.Series:
    """Validate numeric, finite, non-null, bounded Package 8 probabilities."""

    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.isna().any():
        raise BatchScoringError(
            f"Package 8 {target_key} probabilities contain null or non-numeric values"
        )
    if not np.isfinite(numeric_values.to_numpy(dtype=float)).all():
        raise BatchScoringError(
            f"Package 8 {target_key} probabilities contain non-finite values"
        )
    if not numeric_values.between(0.0, 1.0).all():
        raise BatchScoringError(
            f"Package 8 {target_key} probabilities must be bounded between 0 and 1"
        )
    return numeric_values.astype(float)


def write_batch_scoring_tables(
    database_path: str | Path,
    *,
    inputs: BatchScoringInputs,
    result: BatchScoringResult,
) -> None:
    """Replace selected-month scores and append local scoring audit metadata."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        frame_registered = False
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
            connection.execute(_create_score_output_table_sql())
            connection.execute(_create_batch_scoring_audit_table_sql())
            connection.execute(
                f"""
                DELETE FROM {SCORE_OUTPUT_TABLE}
                WHERE observation_month = ?
                """,
                [result.scoring_month.date()],
            )
            connection.register("batch_score_frame", result.score_frame)
            frame_registered = True
            connection.execute(
                f"""
                INSERT INTO {SCORE_OUTPUT_TABLE}
                SELECT
                    scoring_run_id,
                    account_id,
                    observation_month,
                    churn_score,
                    expansion_score,
                    churn_registered_model_name,
                    churn_model_version,
                    expansion_registered_model_name,
                    expansion_model_version,
                    scored_at_utc,
                    scoring_version
                FROM batch_score_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {BATCH_SCORING_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    result.scoring_run_id,
                    result.scored_at_utc,
                    result.scoring_version,
                    result.scoring_month.date(),
                    result.selector,
                    result.row_count_read,
                    result.row_count_written,
                    inputs.churn_model.registered_model_name,
                    inputs.churn_model.model_version,
                    inputs.churn_model.source_mlflow_run_id,
                    inputs.churn_model.feature_metadata_artifact,
                    inputs.expansion_model.registered_model_name,
                    inputs.expansion_model.model_version,
                    inputs.expansion_model.source_mlflow_run_id,
                    inputs.expansion_model.feature_metadata_artifact,
                    json.dumps(list(inputs.promotion_evidence_sources)),
                    "success",
                    None,
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            if frame_registered:
                connection.unregister("batch_score_frame")


def write_batch_scoring_export(
    export_dir: str | Path,
    result: BatchScoringResult,
) -> Path:
    """Write optional ignored local raw scoring export CSV."""

    export_path = Path(export_dir)
    _validate_export_dir(export_path)
    export_path.mkdir(parents=True, exist_ok=True)
    month_token = result.scoring_month.date().isoformat().replace("-", "_")
    score_path = export_path / f"account_month_scores_{month_token}_{result.scoring_run_id}.csv"
    result.score_frame.to_csv(score_path, index=False)
    return score_path


def _validate_export_dir(export_dir: Path) -> None:
    resolved = export_dir.resolve()
    project_root = PROJECT_ROOT.resolve()
    if not resolved.is_relative_to(project_root):
        return

    allowed_dir = (project_root / DEFAULT_BATCH_SCORING_EXPORT_DIR).resolve()
    if resolved.is_relative_to(allowed_dir):
        return
    raise BatchScoringError(
        "Package 8 scoring exports must be under ignored local output "
        f"directory {DEFAULT_BATCH_SCORING_EXPORT_DIR}"
    )


def _positive_probability_index(
    promoted_model: PromotedScoringModel,
    *,
    probability_array: np.ndarray,
) -> int:
    classes = getattr(promoted_model.model, "classes_", None)
    if classes is not None:
        class_values = list(classes)
        if 1 not in class_values:
            raise BatchScoringError(
                "Package 8 model classes do not include positive class 1 for "
                f"{promoted_model.registered_model_name}"
            )
        positive_index = class_values.index(1)
        if positive_index >= probability_array.shape[1]:
            raise BatchScoringError(
                "Package 8 probability shape does not align to model classes for "
                f"{promoted_model.registered_model_name}"
            )
        return positive_index
    if probability_array.shape[1] != 2:
        raise BatchScoringError(
            "Package 8 cannot identify positive probability column for "
            f"{promoted_model.registered_model_name}"
        )
    return 1


def _validate_score_frame(
    score_frame: pd.DataFrame,
    population: pd.DataFrame,
) -> None:
    if len(score_frame) != len(population):
        raise BatchScoringError("Package 8 score rows are not aligned to population")
    if score_frame["account_id"].tolist() != population["account_id"].astype(str).tolist():
        raise BatchScoringError("Package 8 score account order is not row-aligned")
    population_months = pd.to_datetime(population["observation_month"]).dt.date.tolist()
    if score_frame["observation_month"].tolist() != population_months:
        raise BatchScoringError("Package 8 score months are not row-aligned")
    if score_frame["account_id"].isna().any():
        raise BatchScoringError("Package 8 score output contains null account_id")
    validate_probability_values(score_frame["churn_score"], target_key="churn")
    validate_probability_values(score_frame["expansion_score"], target_key="expansion")


def _create_score_output_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORE_OUTPUT_TABLE} (
        scoring_run_id VARCHAR,
        account_id VARCHAR,
        observation_month DATE,
        churn_score DOUBLE,
        expansion_score DOUBLE,
        churn_registered_model_name VARCHAR,
        churn_model_version VARCHAR,
        expansion_registered_model_name VARCHAR,
        expansion_model_version VARCHAR,
        scored_at_utc VARCHAR,
        scoring_version VARCHAR
    )
    """


def _create_batch_scoring_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {BATCH_SCORING_AUDIT_TABLE} (
        scoring_run_id VARCHAR,
        scored_at_utc VARCHAR,
        scoring_version VARCHAR,
        scoring_month DATE,
        selector VARCHAR,
        row_count_read INTEGER,
        row_count_written INTEGER,
        churn_registered_model_name VARCHAR,
        churn_model_version VARCHAR,
        churn_source_mlflow_run_id VARCHAR,
        churn_feature_metadata_artifact VARCHAR,
        expansion_registered_model_name VARCHAR,
        expansion_model_version VARCHAR,
        expansion_source_mlflow_run_id VARCHAR,
        expansion_feature_metadata_artifact VARCHAR,
        promotion_evidence_sources_json VARCHAR,
        status VARCHAR,
        failure_reason VARCHAR
    )
    """
