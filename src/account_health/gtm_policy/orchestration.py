"""Package 10 GTM policy orchestration, audit, and local exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from account_health.gtm_policy.loading import (
    GTMPolicyError,
    load_gtm_policy_context,
    load_gtm_policy_inputs,
    parse_gtm_policy_scoring_month,
)
from account_health.gtm_policy.matrix import POLICY_VERSION
from account_health.gtm_policy.outputs import (
    GTM_POLICY_OUTPUT_TABLE,
    OUTPUT_COLUMNS,
    _create_gtm_policy_output_table_sql,
    build_gtm_policy_output_frame,
)
from account_health.scoring import SCORE_OUTPUT_TABLE
from account_health.scoring.loading import SCORING_SOURCE_TABLE
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parents[3]

GTM_POLICY_AUDIT_TABLE = "metadata.gtm_policy_audit"
DEFAULT_GTM_POLICY_EXPORT_DIR = Path("data/outputs/gtm_policy")
OBSERVABILITY_STATUS_NOT_USED = "not_used"

HEALTH_BAND_VALUES = ("Critical", "At Risk", "Stable", "Growth Ready")
RECOMMENDED_ACTION_VALUES = (
    "Executive save plan before expansion",
    "Immediate retention intervention",
    "Resolve risks before expansion outreach",
    "Customer success risk review",
    "Prioritise expansion outreach",
    "Nurture for future expansion",
    "Monitor in standard cadence",
)
ACTION_PRIORITY_VALUES = ("P1", "P2", "P3")
REQUIRED_INPUT_TABLES = (SCORE_OUTPUT_TABLE, SCORING_SOURCE_TABLE)


@dataclass(frozen=True)
class GTMPolicyResult:
    """Summary of one deterministic local Package 10 policy run."""

    run_id: str
    policy_version: str
    selector: str
    scoring_month: pd.Timestamp
    started_at_utc: str
    completed_at_utc: str
    input_score_row_count: int
    output_policy_row_count: int
    status: str
    observability_status: str
    warning_codes: tuple[str, ...]
    export_requested: bool
    policy_frame: pd.DataFrame
    output_paths: dict[str, str]


def run_gtm_policy(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | pd.Timestamp | None = None,
    latest: bool = False,
    export_dir: str | Path | None = None,
    write_tables: bool = True,
) -> GTMPolicyResult:
    """Build deterministic Package 10 outputs and append local audit metadata."""

    run_id = uuid4().hex
    started_at_utc = _utc_now()
    selector_hint = _selector_hint(scoring_month=scoring_month, latest=latest)
    requested_month = _requested_month_hint(scoring_month)

    try:
        inputs = load_gtm_policy_inputs(
            database_path,
            scoring_month=scoring_month,
            latest=latest,
        )
        context = load_gtm_policy_context(
            database_path,
            scoring_month=inputs.scoring_month,
        )
        completed_at_utc = _utc_now()
        policy_frame = build_gtm_policy_output_frame(
            inputs.score_frame,
            context,
            scoring_month=inputs.scoring_month,
            created_at_utc=completed_at_utc,
        )
        result = GTMPolicyResult(
            run_id=run_id,
            policy_version=POLICY_VERSION,
            selector=inputs.selector,
            scoring_month=inputs.scoring_month,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            input_score_row_count=len(inputs.score_frame),
            output_policy_row_count=len(policy_frame),
            status="success",
            observability_status=OBSERVABILITY_STATUS_NOT_USED,
            warning_codes=(),
            export_requested=export_dir is not None,
            policy_frame=policy_frame,
            output_paths={},
        )
    except GTMPolicyError as error:
        if write_tables:
            _write_failed_gtm_policy_audit_if_safe(
                database_path,
                run_id=run_id,
                started_at_utc=started_at_utc,
                selector=selector_hint,
                scoring_month=requested_month,
                failure_reason=str(error),
                export_requested=export_dir is not None,
            )
        raise

    output_paths: dict[str, str] = {}
    if write_tables:
        write_gtm_policy_tables(database_path, result=result)
        output_paths = {
            "policy_table": GTM_POLICY_OUTPUT_TABLE,
            "audit_table": GTM_POLICY_AUDIT_TABLE,
        }
    if export_dir is not None:
        export_path = write_gtm_policy_export(export_dir, result)
        output_paths["policy_export"] = str(export_path)
    return GTMPolicyResult(
        run_id=result.run_id,
        policy_version=result.policy_version,
        selector=result.selector,
        scoring_month=result.scoring_month,
        started_at_utc=result.started_at_utc,
        completed_at_utc=result.completed_at_utc,
        input_score_row_count=result.input_score_row_count,
        output_policy_row_count=result.output_policy_row_count,
        status=result.status,
        observability_status=result.observability_status,
        warning_codes=result.warning_codes,
        export_requested=result.export_requested,
        policy_frame=result.policy_frame,
        output_paths=output_paths,
    )


def write_gtm_policy_tables(
    database_path: str | Path,
    *,
    result: GTMPolicyResult,
) -> None:
    """Replace selected-month policy rows and append GTM policy audit."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        frame_registered = False
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
            connection.execute(_create_gtm_policy_output_table_sql())
            connection.execute(_create_gtm_policy_audit_table_sql())
            connection.execute(
                f"DELETE FROM {GTM_POLICY_OUTPUT_TABLE} WHERE scoring_month = ?",
                [result.scoring_month.date()],
            )
            connection.register("gtm_policy_frame", result.policy_frame)
            frame_registered = True
            connection.execute(
                f"""
                INSERT INTO {GTM_POLICY_OUTPUT_TABLE}
                SELECT {", ".join(OUTPUT_COLUMNS)}
                FROM gtm_policy_frame
                """
            )
            connection.execute(
                f"""
                INSERT INTO {GTM_POLICY_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    result.run_id,
                    result.policy_version,
                    result.selector,
                    result.scoring_month.date(),
                    result.started_at_utc,
                    result.completed_at_utc,
                    json.dumps(list(REQUIRED_INPUT_TABLES)),
                    result.input_score_row_count,
                    result.output_policy_row_count,
                    _ordered_counts_json(
                        result.policy_frame["health_band"],
                        HEALTH_BAND_VALUES,
                    ),
                    _ordered_counts_json(
                        result.policy_frame["recommended_action"],
                        RECOMMENDED_ACTION_VALUES,
                    ),
                    _ordered_counts_json(
                        result.policy_frame["action_priority"],
                        ACTION_PRIORITY_VALUES,
                    ),
                    result.observability_status,
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
            if frame_registered:
                connection.unregister("gtm_policy_frame")


def write_gtm_policy_export(
    export_dir: str | Path,
    result: GTMPolicyResult,
) -> Path:
    """Write an optional ignored local GTM policy CSV export."""

    export_path = Path(export_dir)
    _validate_export_dir(export_path)
    export_path.mkdir(parents=True, exist_ok=True)
    month_token = result.scoring_month.date().isoformat().replace("-", "_")
    policy_path = export_path / (
        f"account_month_gtm_policy_{month_token}_{result.run_id}.csv"
    )
    result.policy_frame.to_csv(policy_path, index=False)
    return policy_path


def _write_failed_gtm_policy_audit_if_safe(
    database_path: str | Path,
    *,
    run_id: str,
    started_at_utc: str,
    selector: str | None,
    scoring_month: pd.Timestamp | None,
    failure_reason: str,
    export_requested: bool,
) -> None:
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file)) as connection:
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
            connection.execute(_create_gtm_policy_audit_table_sql())
            connection.execute(
                f"""
                INSERT INTO {GTM_POLICY_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    POLICY_VERSION,
                    selector,
                    None if scoring_month is None else scoring_month.date(),
                    started_at_utc,
                    _utc_now(),
                    json.dumps(list(REQUIRED_INPUT_TABLES)),
                    None,
                    None,
                    "{}",
                    "{}",
                    "{}",
                    OBSERVABILITY_STATUS_NOT_USED,
                    "[]",
                    json.dumps(["gtm_policy_failed"]),
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
        return parse_gtm_policy_scoring_month(scoring_month)
    except GTMPolicyError:
        return None


def _ordered_counts_json(
    values: pd.Series,
    expected_values: tuple[str, ...],
) -> str:
    counts = values.value_counts()
    ordered_counts = {
        expected_value: int(counts.get(expected_value, 0))
        for expected_value in expected_values
    }
    return json.dumps(ordered_counts)


def _validate_export_dir(export_dir: Path) -> None:
    resolved = export_dir.resolve()
    project_root = PROJECT_ROOT.resolve()
    if not resolved.is_relative_to(project_root):
        return

    allowed_dir = (project_root / DEFAULT_GTM_POLICY_EXPORT_DIR).resolve()
    if resolved.is_relative_to(allowed_dir):
        return
    raise GTMPolicyError(
        "Package 10 GTM policy exports must be under ignored local output "
        f"directory {DEFAULT_GTM_POLICY_EXPORT_DIR}"
    )


def _create_gtm_policy_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {GTM_POLICY_AUDIT_TABLE} (
        run_id VARCHAR,
        policy_version VARCHAR,
        selector VARCHAR,
        scoring_month DATE,
        started_at_utc VARCHAR,
        completed_at_utc VARCHAR,
        required_tables_json VARCHAR,
        input_score_row_count BIGINT,
        output_policy_row_count BIGINT,
        health_band_counts_json VARCHAR,
        recommended_action_counts_json VARCHAR,
        priority_counts_json VARCHAR,
        observability_status VARCHAR,
        warning_codes_json VARCHAR,
        failure_codes_json VARCHAR,
        export_requested BOOLEAN,
        status VARCHAR,
        failure_reason VARCHAR
    )
    """


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
