"""Package 9 score observability orchestration and local DuckDB outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from account_health.observability.lineage import summarize_scoring_lineage
from account_health.observability.loading import (
    BATCH_SCORING_AUDIT_TABLE,
    SCORE_OUTPUT_TABLE,
    SCORING_SOURCE_TABLE,
    ScoreObservabilityError,
    load_score_observability_inputs,
    parse_observability_scoring_month,
)
from account_health.observability.summaries import (
    compare_score_distributions,
    prior_comparison_warning_codes,
    score_distribution_warning_codes,
    summarize_score_distributions,
    summarize_segment_distributions,
    validate_score_values,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parents[3]

OBSERVABILITY_VERSION = "package_9_score_observability_v1"
SCORE_OBSERVABILITY_AUDIT_TABLE = "metadata.score_observability_audit"
SCORE_OBSERVABILITY_SUMMARY_TABLE = "mart.score_observability_summary"
SCORE_DISTRIBUTION_BY_MONTH_TABLE = "mart.score_distribution_by_month"
SCORE_DISTRIBUTION_BY_SEGMENT_TABLE = "mart.score_distribution_by_segment"
SCORING_LINEAGE_SUMMARY_TABLE = "mart.scoring_lineage_summary"
DEFAULT_SCORE_OBSERVABILITY_EXPORT_DIR = Path("data/outputs/score_observability")

REQUIRED_INPUT_TABLES = (
    SCORE_OUTPUT_TABLE,
    BATCH_SCORING_AUDIT_TABLE,
    SCORING_SOURCE_TABLE,
)


@dataclass(frozen=True)
class ScoreObservabilityResult:
    """Summary of one local Package 9 observability run."""

    observability_run_id: str
    created_at_utc: str
    observability_version: str
    selector: str
    scoring_month: pd.Timestamp
    prior_scoring_month: pd.Timestamp | None
    status: str
    warning_codes: tuple[str, ...]
    export_requested: bool
    summary_frame: pd.DataFrame
    distribution_by_month_frame: pd.DataFrame
    distribution_by_segment_frame: pd.DataFrame
    lineage_summary_frame: pd.DataFrame
    output_paths: dict[str, str]


def run_score_observability(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | pd.Timestamp | None = None,
    latest: bool = False,
    export_dir: str | Path | None = None,
    write_tables: bool = True,
    small_segment_threshold: int = 30,
) -> ScoreObservabilityResult:
    """Validate Package 8 score outputs and write local Package 9 artefacts."""

    observability_run_id = uuid4().hex
    created_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()
    selector_hint = _selector_hint(scoring_month=scoring_month, latest=latest)
    requested_month = _requested_month_hint(scoring_month)

    try:
        inputs = load_score_observability_inputs(
            database_path,
            scoring_month=scoring_month,
            latest=latest,
        )
        validated_scores = validate_score_values(inputs.score_frame)
        current_distribution = summarize_score_distributions(
            validated_scores,
            scoring_month=inputs.scoring_month,
        )
        prior_distribution = (
            None
            if inputs.prior_score_frame is None
            else summarize_score_distributions(
                inputs.prior_score_frame,
                scoring_month=inputs.prior_scoring_month,
            )
        )
        distribution_by_month = compare_score_distributions(
            current_distribution,
            prior_distribution,
            prior_scoring_month=inputs.prior_scoring_month,
        )
        distribution_by_segment, segment_warnings = summarize_segment_distributions(
            validated_scores,
            inputs.expected_population_frame,
            scoring_month=inputs.scoring_month,
            small_segment_threshold=small_segment_threshold,
        )
        lineage_summary = summarize_scoring_lineage(
            validated_scores,
            inputs.batch_scoring_audit_frame,
            scoring_month=inputs.scoring_month,
        )
        warning_codes = _dedupe_warning_codes(
            (
                *prior_comparison_warning_codes(inputs.prior_scoring_month),
                *score_distribution_warning_codes(current_distribution),
                *segment_warnings,
            )
        )
        status = "success_with_warnings" if warning_codes else "success"
        summary = _build_summary_frame(
            observability_run_id=observability_run_id,
            created_at_utc=created_at_utc,
            selector=inputs.selector,
            scoring_month=inputs.scoring_month,
            prior_scoring_month=inputs.prior_scoring_month,
            expected_account_count=inputs.expected_account_count,
            scored_account_count=inputs.scored_account_count,
            status=status,
            warning_codes=warning_codes,
        )
        result = ScoreObservabilityResult(
            observability_run_id=observability_run_id,
            created_at_utc=created_at_utc,
            observability_version=OBSERVABILITY_VERSION,
            selector=inputs.selector,
            scoring_month=inputs.scoring_month,
            prior_scoring_month=inputs.prior_scoring_month,
            status=status,
            warning_codes=warning_codes,
            export_requested=export_dir is not None,
            summary_frame=summary,
            distribution_by_month_frame=distribution_by_month,
            distribution_by_segment_frame=distribution_by_segment,
            lineage_summary_frame=lineage_summary,
            output_paths={},
        )
    except ScoreObservabilityError as error:
        if write_tables:
            _write_failed_observability_audit_if_safe(
                database_path,
                observability_run_id=observability_run_id,
                created_at_utc=created_at_utc,
                selector=selector_hint,
                scoring_month=requested_month,
                failure_reason=str(error),
                export_requested=export_dir is not None,
            )
        raise

    output_paths: dict[str, str] = {}
    if write_tables:
        write_score_observability_tables(database_path, result=result)
        output_paths = {
            "summary_table": SCORE_OBSERVABILITY_SUMMARY_TABLE,
            "distribution_by_month_table": SCORE_DISTRIBUTION_BY_MONTH_TABLE,
            "distribution_by_segment_table": SCORE_DISTRIBUTION_BY_SEGMENT_TABLE,
            "lineage_summary_table": SCORING_LINEAGE_SUMMARY_TABLE,
            "audit_table": SCORE_OBSERVABILITY_AUDIT_TABLE,
        }
    if export_dir is not None:
        output_paths.update(write_score_observability_exports(export_dir, result))
    return ScoreObservabilityResult(
        observability_run_id=result.observability_run_id,
        created_at_utc=result.created_at_utc,
        observability_version=result.observability_version,
        selector=result.selector,
        scoring_month=result.scoring_month,
        prior_scoring_month=result.prior_scoring_month,
        status=result.status,
        warning_codes=result.warning_codes,
        export_requested=result.export_requested,
        summary_frame=result.summary_frame,
        distribution_by_month_frame=result.distribution_by_month_frame,
        distribution_by_segment_frame=result.distribution_by_segment_frame,
        lineage_summary_frame=result.lineage_summary_frame,
        output_paths=output_paths,
    )


def write_score_observability_tables(
    database_path: str | Path,
    *,
    result: ScoreObservabilityResult,
) -> None:
    """Replace selected-month summary rows and append observability audit."""

    database_file = Path(database_path)
    frames = {
        "summary_frame": result.summary_frame,
        "distribution_by_month_frame": result.distribution_by_month_frame,
        "distribution_by_segment_frame": result.distribution_by_segment_frame,
        "lineage_summary_frame": result.lineage_summary_frame,
    }
    with duckdb.connect(str(database_file)) as connection:
        registered: list[str] = []
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
            for statement in _create_output_table_sql():
                connection.execute(statement)
            for frame_name, frame in frames.items():
                connection.register(frame_name, frame)
                registered.append(frame_name)
            for table_name in (
                SCORE_OBSERVABILITY_SUMMARY_TABLE,
                SCORE_DISTRIBUTION_BY_MONTH_TABLE,
                SCORE_DISTRIBUTION_BY_SEGMENT_TABLE,
                SCORING_LINEAGE_SUMMARY_TABLE,
            ):
                connection.execute(
                    f"DELETE FROM {table_name} WHERE scoring_month = ?",
                    [result.scoring_month.date()],
                )
            connection.execute(
                f"""
                INSERT INTO {SCORE_OBSERVABILITY_SUMMARY_TABLE}
                SELECT * FROM summary_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {SCORE_DISTRIBUTION_BY_MONTH_TABLE}
                SELECT * FROM distribution_by_month_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {SCORE_DISTRIBUTION_BY_SEGMENT_TABLE}
                SELECT * FROM distribution_by_segment_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {SCORING_LINEAGE_SUMMARY_TABLE}
                SELECT * FROM lineage_summary_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {SCORE_OBSERVABILITY_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    result.observability_run_id,
                    result.created_at_utc,
                    result.observability_version,
                    result.selector,
                    result.scoring_month.date(),
                    (
                        None
                        if result.prior_scoring_month is None
                        else result.prior_scoring_month.date()
                    ),
                    json.dumps(list(REQUIRED_INPUT_TABLES)),
                    int(result.summary_frame["expected_account_count"].iloc[0]),
                    int(result.summary_frame["scored_account_count"].iloc[0]),
                    json.dumps(list(result.warning_codes)),
                    "[]",
                    result.export_requested,
                    result.status,
                    None,
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            for frame_name in registered:
                connection.unregister(frame_name)


def write_score_observability_exports(
    export_dir: str | Path,
    result: ScoreObservabilityResult,
) -> dict[str, str]:
    """Write optional ignored local CSV exports for human review."""

    export_path = Path(export_dir)
    _validate_export_dir(export_path)
    export_path.mkdir(parents=True, exist_ok=True)
    month_token = result.scoring_month.date().isoformat().replace("-", "_")
    exports = {
        "summary_export": (
            "score_observability_summary",
            result.summary_frame,
        ),
        "distribution_by_month_export": (
            "score_distribution_by_month",
            result.distribution_by_month_frame,
        ),
        "distribution_by_segment_export": (
            "score_distribution_by_segment",
            result.distribution_by_segment_frame,
        ),
        "lineage_summary_export": (
            "scoring_lineage_summary",
            result.lineage_summary_frame,
        ),
    }
    output_paths: dict[str, str] = {}
    for key, (stem, frame) in exports.items():
        path = export_path / (
            f"{stem}_{month_token}_{result.observability_run_id}.csv"
        )
        frame.to_csv(path, index=False)
        output_paths[key] = str(path)
    return output_paths


def _build_summary_frame(
    *,
    observability_run_id: str,
    created_at_utc: str,
    selector: str,
    scoring_month: pd.Timestamp,
    prior_scoring_month: pd.Timestamp | None,
    expected_account_count: int,
    scored_account_count: int,
    status: str,
    warning_codes: tuple[str, ...],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "observability_run_id": observability_run_id,
                "scoring_month": scoring_month.date(),
                "selector": selector,
                "prior_scoring_month": (
                    None
                    if prior_scoring_month is None
                    else prior_scoring_month.date()
                ),
                "expected_account_count": expected_account_count,
                "scored_account_count": scored_account_count,
                "population_matches_expected": (
                    expected_account_count == scored_account_count
                ),
                "status": status,
                "warning_codes_json": json.dumps(list(warning_codes)),
                "created_at_utc": created_at_utc,
                "observability_version": OBSERVABILITY_VERSION,
            }
        ]
    )


def _write_failed_observability_audit_if_safe(
    database_path: str | Path,
    *,
    observability_run_id: str,
    created_at_utc: str,
    selector: str | None,
    scoring_month: pd.Timestamp | None,
    failure_reason: str,
    export_requested: bool,
) -> None:
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file)) as connection:
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
            connection.execute(_create_score_observability_audit_table_sql())
            connection.execute(
                f"""
                INSERT INTO {SCORE_OBSERVABILITY_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    observability_run_id,
                    created_at_utc,
                    OBSERVABILITY_VERSION,
                    selector,
                    None if scoring_month is None else scoring_month.date(),
                    None,
                    json.dumps(list(REQUIRED_INPUT_TABLES)),
                    None,
                    None,
                    "[]",
                    json.dumps(["score_observability_failed"]),
                    export_requested,
                    "failed",
                    failure_reason,
                ],
            )
    except Exception:  # noqa: BLE001 - failure audit is best-effort only.
        return


def _selector_hint(
    *,
    scoring_month: str | pd.Timestamp | None,
    latest: bool,
) -> str | None:
    if scoring_month is not None and not latest:
        return "scoring_month"
    if latest and scoring_month is None:
        return "latest"
    return None


def _requested_month_hint(
    scoring_month: str | pd.Timestamp | None,
) -> pd.Timestamp | None:
    if scoring_month is None:
        return None
    try:
        return parse_observability_scoring_month(scoring_month)
    except ScoreObservabilityError:
        return None


def _dedupe_warning_codes(warning_codes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(warning_codes))


def _validate_export_dir(export_dir: Path) -> None:
    resolved = export_dir.resolve()
    project_root = PROJECT_ROOT.resolve()
    if not resolved.is_relative_to(project_root):
        return

    allowed_dir = (project_root / DEFAULT_SCORE_OBSERVABILITY_EXPORT_DIR).resolve()
    if resolved.is_relative_to(allowed_dir):
        return
    raise ScoreObservabilityError(
        "Package 9 observability exports must be under ignored local output "
        f"directory {DEFAULT_SCORE_OBSERVABILITY_EXPORT_DIR}"
    )


def _create_output_table_sql() -> tuple[str, ...]:
    return (
        _create_score_observability_summary_table_sql(),
        _create_score_distribution_by_month_table_sql(),
        _create_score_distribution_by_segment_table_sql(),
        _create_scoring_lineage_summary_table_sql(),
        _create_score_observability_audit_table_sql(),
    )


def _create_score_observability_summary_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORE_OBSERVABILITY_SUMMARY_TABLE} (
        observability_run_id VARCHAR,
        scoring_month DATE,
        selector VARCHAR,
        prior_scoring_month DATE,
        expected_account_count BIGINT,
        scored_account_count BIGINT,
        population_matches_expected BOOLEAN,
        status VARCHAR,
        warning_codes_json VARCHAR,
        created_at_utc VARCHAR,
        observability_version VARCHAR
    )
    """


def _create_score_distribution_by_month_table_sql() -> str:
    metric_columns = _metric_column_sql(include_prior=True, include_delta=True)
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORE_DISTRIBUTION_BY_MONTH_TABLE} (
        scoring_month DATE,
        target VARCHAR,
        {metric_columns},
        prior_scoring_month DATE
    )
    """


def _create_score_distribution_by_segment_table_sql() -> str:
    metric_columns = _metric_column_sql(include_prior=False, include_delta=False)
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORE_DISTRIBUTION_BY_SEGMENT_TABLE} (
        scoring_month DATE,
        target VARCHAR,
        segment_name VARCHAR,
        segment_value VARCHAR,
        {metric_columns},
        is_small_segment BOOLEAN
    )
    """


def _create_scoring_lineage_summary_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORING_LINEAGE_SUMMARY_TABLE} (
        scoring_month DATE,
        scoring_run_id VARCHAR,
        target VARCHAR,
        registered_model_name VARCHAR,
        model_version VARCHAR,
        source_mlflow_run_id VARCHAR,
        feature_metadata_artifact VARCHAR,
        scored_at_utc VARCHAR,
        scoring_version VARCHAR,
        scoring_status VARCHAR
    )
    """


def _create_score_observability_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {SCORE_OBSERVABILITY_AUDIT_TABLE} (
        observability_run_id VARCHAR,
        created_at_utc VARCHAR,
        observability_version VARCHAR,
        selector VARCHAR,
        scoring_month DATE,
        prior_scoring_month DATE,
        required_tables_json VARCHAR,
        expected_account_count BIGINT,
        scored_account_count BIGINT,
        warning_codes_json VARCHAR,
        failure_codes_json VARCHAR,
        export_requested BOOLEAN,
        status VARCHAR,
        failure_reason VARCHAR
    )
    """


def _metric_column_sql(*, include_prior: bool, include_delta: bool) -> str:
    base_metrics = (
        ("account_count", "BIGINT"),
        ("minimum", "DOUBLE"),
        ("maximum", "DOUBLE"),
        ("mean", "DOUBLE"),
        ("stddev", "DOUBLE"),
        ("p01", "DOUBLE"),
        ("p05", "DOUBLE"),
        ("p10", "DOUBLE"),
        ("p25", "DOUBLE"),
        ("p50", "DOUBLE"),
        ("p75", "DOUBLE"),
        ("p90", "DOUBLE"),
        ("p95", "DOUBLE"),
        ("p99", "DOUBLE"),
        ("top_decile_threshold", "DOUBLE"),
        ("top_decile_share", "DOUBLE"),
    )
    columns: list[str] = [
        f"{column_name} {column_type}" for column_name, column_type in base_metrics
    ]
    if include_prior:
        columns.extend(
            f"prior_{column_name} {column_type}"
            for column_name, column_type in base_metrics
        )
    if include_delta:
        columns.extend(
            f"{column_name}_delta {'BIGINT' if column_name == 'account_count' else 'DOUBLE'}"
            for column_name, _ in base_metrics
        )
    return ",\n        ".join(columns)
