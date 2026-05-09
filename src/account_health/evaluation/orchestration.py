"""Package 6 local evaluation orchestration, outputs, and DuckDB tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import numpy as np
import pandas as pd

from account_health.evaluation.loading import (
    EVALUATION_VERSION,
    EvaluationInputs,
    load_evaluation_inputs,
)
from account_health.evaluation.metrics import (
    MetricRecord,
    evaluate_overall_metrics,
    score_fixed_holdout,
)
from account_health.evaluation.robustness import (
    CaveatRecord,
    compute_calibration_metrics,
    compute_holdout_month_robustness,
    compute_segment_robustness,
)
from account_health.evaluation.selection import (
    ChampionRecord,
    compute_utility_sensitivity,
    select_champions,
)
from account_health.modeling import DEFAULT_EXPERIMENT_NAME
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

DEFAULT_EVALUATION_OUTPUT_DIR = Path("data/outputs/model_evaluation")
MODEL_EVALUATION_AUDIT_TABLE = "metadata.model_evaluation_audit"
MODEL_EVALUATION_SUMMARY_TABLE = "mart.model_evaluation_summary"
MODEL_CHAMPION_SELECTION_TABLE = "mart.model_champion_selection"


@dataclass(frozen=True)
class ModelEvaluationResult:
    """Summary of one local Package 6 evaluation run."""

    evaluation_id: str
    evaluated_at_utc: str
    evaluation_version: str
    experiment_name: str
    train_end_month: pd.Timestamp
    target_count: int
    candidate_count: int
    metric_records: tuple[MetricRecord, ...]
    caveats: tuple[CaveatRecord, ...]
    champions: tuple[ChampionRecord, ...]
    output_paths: dict[str, str]


def run_model_evaluation(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    mlflow_tracking_uri: str | None = None,
    train_end_month: str | pd.Timestamp | None = None,
    output_dir: str | Path = DEFAULT_EVALUATION_OUTPUT_DIR,
    write_outputs: bool = True,
    write_tables: bool = True,
) -> ModelEvaluationResult:
    """Run Package 6 layered evaluation against existing local candidates."""

    evaluated_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()
    evaluation_id = uuid4().hex
    inputs = load_evaluation_inputs(
        database_path,
        experiment_name=experiment_name,
        mlflow_tracking_uri=mlflow_tracking_uri,
        train_end_month=train_end_month,
    )
    score_frame = score_fixed_holdout(inputs)

    overall_records = evaluate_overall_metrics(score_frame)
    calibration_records, calibration_caveats = compute_calibration_metrics(score_frame)
    segment_records, segment_caveats = compute_segment_robustness(score_frame)
    month_records, month_caveats = compute_holdout_month_robustness(score_frame)
    utility_records, utility_caveats = compute_utility_sensitivity(score_frame)

    metric_records = (
        *overall_records,
        *calibration_records,
        *segment_records,
        *month_records,
        *utility_records,
    )
    caveats = (
        *calibration_caveats,
        *segment_caveats,
        *month_caveats,
        *utility_caveats,
    )
    champions = select_champions(
        metric_records,
        caveats,
        created_at_utc=evaluated_at_utc,
        evaluation_version=EVALUATION_VERSION,
    )

    result = ModelEvaluationResult(
        evaluation_id=evaluation_id,
        evaluated_at_utc=evaluated_at_utc,
        evaluation_version=EVALUATION_VERSION,
        experiment_name=inputs.experiment_name,
        train_end_month=inputs.train_end_month,
        target_count=len({candidate.target for candidate in inputs.candidates}),
        candidate_count=len(inputs.candidates),
        metric_records=metric_records,
        caveats=caveats,
        champions=champions,
        output_paths={},
    )

    output_paths: dict[str, str] = {}
    if write_tables:
        write_evaluation_tables(database_path, result)
    if write_outputs:
        output_paths = write_evaluation_outputs(output_dir, result)

    return ModelEvaluationResult(
        evaluation_id=result.evaluation_id,
        evaluated_at_utc=result.evaluated_at_utc,
        evaluation_version=result.evaluation_version,
        experiment_name=result.experiment_name,
        train_end_month=result.train_end_month,
        target_count=result.target_count,
        candidate_count=result.candidate_count,
        metric_records=result.metric_records,
        caveats=result.caveats,
        champions=result.champions,
        output_paths=output_paths,
    )


def write_evaluation_tables(
    database_path: str | Path,
    result: ModelEvaluationResult,
) -> None:
    """Write minimal local Package 6 DuckDB evaluation tables."""

    database_file = Path(database_path)
    summary_frame = _metric_records_frame(result)
    champion_frame = _champion_records_frame(result)
    with duckdb.connect(str(database_file)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
        connection.register("model_evaluation_summary_frame", summary_frame)
        connection.register("model_champion_selection_frame", champion_frame)
        try:
            connection.execute(
                f"""
                CREATE OR REPLACE TABLE {MODEL_EVALUATION_SUMMARY_TABLE} AS
                SELECT * FROM model_evaluation_summary_frame
                """
            )
            connection.execute(
                f"""
                CREATE OR REPLACE TABLE {MODEL_CHAMPION_SELECTION_TABLE} AS
                SELECT * FROM model_champion_selection_frame
                """
            )
        finally:
            connection.unregister("model_evaluation_summary_frame")
            connection.unregister("model_champion_selection_frame")

        connection.execute(_create_evaluation_audit_table_sql())
        connection.execute(
            f"""
            INSERT INTO {MODEL_EVALUATION_AUDIT_TABLE}
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.evaluation_id,
                result.evaluated_at_utc,
                result.evaluation_version,
                str(database_file),
                result.experiment_name,
                result.train_end_month.date(),
                result.target_count,
                result.candidate_count,
                "success",
            ],
        )


def write_evaluation_outputs(
    output_dir: str | Path,
    result: ModelEvaluationResult,
) -> dict[str, str]:
    """Write ignored local JSON and Markdown evaluation artefacts."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "evaluation_summary.json"
    manifest_path = output_path / "champion_selection_manifest.json"
    report_path = output_path / "evaluation_report.md"

    summary_payload = {
        "evaluation_id": result.evaluation_id,
        "evaluated_at_utc": result.evaluated_at_utc,
        "evaluation_version": result.evaluation_version,
        "experiment_name": result.experiment_name,
        "train_end_month": result.train_end_month.date().isoformat(),
        "target_count": result.target_count,
        "candidate_count": result.candidate_count,
        "metrics": [record.to_dict() for record in result.metric_records],
        "caveats": [caveat.to_dict() for caveat in result.caveats],
    }
    manifest_payload = [champion.to_dict() for champion in result.champions]

    summary_path.write_text(
        json.dumps(summary_payload, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_evaluation_report_markdown(result), encoding="utf-8")

    return {
        "evaluation_summary": str(summary_path),
        "champion_selection_manifest": str(manifest_path),
        "evaluation_report": str(report_path),
    }


def _metric_records_frame(result: ModelEvaluationResult) -> pd.DataFrame:
    rows = []
    for record in result.metric_records:
        row = {
            "evaluation_id": result.evaluation_id,
            **record.to_dict(),
            "evaluation_version": result.evaluation_version,
            "created_at_utc": result.evaluated_at_utc,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _champion_records_frame(result: ModelEvaluationResult) -> pd.DataFrame:
    rows = []
    for champion in result.champions:
        row = champion.to_dict()
        row["evaluation_id"] = result.evaluation_id
        for json_column in (
            "key_topk_metrics",
            "comparison_versus_baseline",
            "calibration_caveats",
            "segment_caveats",
            "temporal_caveats",
            "utility_caveats",
        ):
            row[json_column] = json.dumps(row[json_column], default=_json_default)
        rows.append(row)
    return pd.DataFrame(rows)


def _create_evaluation_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {MODEL_EVALUATION_AUDIT_TABLE} (
        evaluation_id VARCHAR,
        evaluated_at_utc VARCHAR,
        evaluation_version VARCHAR,
        warehouse_path VARCHAR,
        experiment_name VARCHAR,
        train_end_month DATE,
        target_count INTEGER,
        candidate_count INTEGER,
        status VARCHAR
    )
    """


def _evaluation_report_markdown(result: ModelEvaluationResult) -> str:
    lines = [
        "# Package 6 Model Evaluation Report",
        "",
        f"- evaluation_id: {result.evaluation_id}",
        f"- evaluated_at_utc: {result.evaluated_at_utc}",
        f"- evaluation_version: {result.evaluation_version}",
        f"- train_end_month: {result.train_end_month.date().isoformat()}",
        "",
        "## Champion Selection",
        "",
    ]
    for champion in result.champions:
        lines.extend(
            [
                f"### {champion.target}",
                "",
                f"- selection_status: {champion.selection_status}",
                f"- selected_champion_model_family: {champion.selected_champion_model_family}",
                f"- primary_metric: {champion.primary_metric}",
                "",
            ]
        )
    lines.extend(
        [
            "## Caveats",
            "",
            "- Synthetic data cannot support real ROI, customer, or production claims.",
            "- Holdout-month slices are fixed-holdout robustness checks, not rolling retraining backtests.",
            "- Package 4 baseline scores are ranking scores, not calibrated probabilities.",
            "",
        ]
    )
    return "\n".join(lines)


def _json_default(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
