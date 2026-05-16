"""Package 9 score observability input loading and structural validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from account_health.scoring.loading import (
    BATCH_SCORING_AUDIT_TABLE,
    SCORE_OUTPUT_TABLE,
    SCORING_SOURCE_TABLE,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}-01$")

REQUIRED_SCORE_COLUMNS = (
    "scoring_run_id",
    "account_id",
    "observation_month",
    "churn_score",
    "expansion_score",
    "churn_registered_model_name",
    "churn_model_version",
    "expansion_registered_model_name",
    "expansion_model_version",
    "scored_at_utc",
    "scoring_version",
)
REQUIRED_BATCH_AUDIT_COLUMNS = (
    "scoring_run_id",
    "scored_at_utc",
    "scoring_version",
    "scoring_month",
    "selector",
    "row_count_read",
    "row_count_written",
    "churn_registered_model_name",
    "churn_model_version",
    "churn_source_mlflow_run_id",
    "churn_feature_metadata_artifact",
    "expansion_registered_model_name",
    "expansion_model_version",
    "expansion_source_mlflow_run_id",
    "expansion_feature_metadata_artifact",
    "promotion_evidence_sources_json",
    "status",
    "failure_reason",
)
REQUIRED_EXPECTED_POPULATION_COLUMNS = ("account_id", "observation_month")
SAFE_SEGMENT_COLUMNS = (
    "current_plan",
    "company_size_band",
    "region",
    "industry",
    "segment",
)


class ScoreObservabilityError(ValueError):
    """Raised when Package 9 score observability inputs violate the contract."""


@dataclass(frozen=True)
class ScoreObservabilityInputs:
    """Validated score/audit inputs for exactly one observed scoring month."""

    selector: str
    scoring_month: pd.Timestamp
    prior_scoring_month: pd.Timestamp | None
    score_frame: pd.DataFrame
    prior_score_frame: pd.DataFrame | None
    batch_scoring_audit_frame: pd.DataFrame
    expected_population_frame: pd.DataFrame
    expected_account_count: int
    scored_account_count: int


def load_score_observability_inputs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | date | pd.Timestamp | None = None,
    latest: bool = False,
) -> ScoreObservabilityInputs:
    """Load and validate the Package 8 evidence needed by Package 9."""

    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            _validate_required_tables(connection)
            selected_month, selector = resolve_observability_scoring_month_for_connection(
                connection,
                scoring_month=scoring_month,
                latest=latest,
            )
            _validate_required_columns(
                connection,
                SCORE_OUTPUT_TABLE,
                REQUIRED_SCORE_COLUMNS,
            )
            _validate_required_columns(
                connection,
                BATCH_SCORING_AUDIT_TABLE,
                REQUIRED_BATCH_AUDIT_COLUMNS,
            )
            _validate_required_columns(
                connection,
                SCORING_SOURCE_TABLE,
                REQUIRED_EXPECTED_POPULATION_COLUMNS,
            )
            safe_population_columns = _safe_population_columns(connection)
            score_frame = connection.execute(
                f"""
                SELECT *
                FROM {SCORE_OUTPUT_TABLE}
                WHERE observation_month = ?
                ORDER BY account_id, observation_month
                """,
                [selected_month.date()],
            ).fetchdf()
            prior_scoring_month = _resolve_prior_scoring_month_for_connection(
                connection,
                scoring_month=selected_month,
            )
            prior_score_frame = (
                None
                if prior_scoring_month is None
                else connection.execute(
                    f"""
                    SELECT *
                    FROM {SCORE_OUTPUT_TABLE}
                    WHERE observation_month = ?
                    ORDER BY account_id, observation_month
                    """,
                    [prior_scoring_month.date()],
                ).fetchdf()
            )
            batch_audit_frame = connection.execute(
                f"""
                SELECT *
                FROM {BATCH_SCORING_AUDIT_TABLE}
                WHERE scoring_month = ?
                ORDER BY scored_at_utc, scoring_run_id
                """,
                [selected_month.date()],
            ).fetchdf()
            expected_population_frame = connection.execute(
                f"""
                SELECT {", ".join(safe_population_columns)}
                FROM {SCORING_SOURCE_TABLE}
                WHERE observation_month = ?
                ORDER BY account_id, observation_month
                """,
                [selected_month.date()],
            ).fetchdf()
    except duckdb.IOException as error:
        raise ScoreObservabilityError(
            f"Package 9 could not read required DuckDB inputs from {database_file}: "
            f"{error}"
        ) from error

    _validate_selected_score_population(score_frame, scoring_month=selected_month)
    if prior_score_frame is not None:
        _validate_selected_score_population(
            prior_score_frame,
            scoring_month=prior_scoring_month,
        )
    _validate_expected_population(
        expected_population_frame,
        scoring_month=selected_month,
    )
    _validate_expected_population_match(
        score_frame=score_frame,
        expected_population_frame=expected_population_frame,
        scoring_month=selected_month,
    )
    return ScoreObservabilityInputs(
        selector=selector,
        scoring_month=selected_month,
        prior_scoring_month=prior_scoring_month,
        score_frame=score_frame,
        prior_score_frame=prior_score_frame,
        batch_scoring_audit_frame=batch_audit_frame,
        expected_population_frame=expected_population_frame,
        expected_account_count=len(expected_population_frame),
        scored_account_count=len(score_frame),
    )


def resolve_observability_scoring_month_for_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
) -> tuple[pd.Timestamp, str]:
    """Resolve an explicit month or explicit latest scored month."""

    _validate_selector(scoring_month=scoring_month, latest=latest)
    _validate_table_exists(connection, SCORE_OUTPUT_TABLE)

    if scoring_month is not None:
        return parse_observability_scoring_month(scoring_month), "scoring_month"

    latest_value = connection.execute(
        f"SELECT MAX(observation_month) FROM {SCORE_OUTPUT_TABLE}"
    ).fetchone()[0]
    if latest_value is None:
        raise ScoreObservabilityError(
            f"{SCORE_OUTPUT_TABLE} has no rows, so Package 9 cannot resolve --latest"
        )
    latest_month = _normalize_month_value(
        latest_value,
        field_name="latest scored observation_month",
    )
    if latest_month.day != 1:
        raise ScoreObservabilityError(
            "Package 9 latest scored observation_month must be the first day of "
            "a calendar month"
        )
    return latest_month, "latest"


def parse_observability_scoring_month(
    value: str | date | pd.Timestamp,
) -> pd.Timestamp:
    """Parse the explicit `YYYY-MM-01` Package 9 scoring month."""

    if isinstance(value, str) and not MONTH_PATTERN.match(value):
        raise ScoreObservabilityError(
            "Package 9 scoring month must use explicit YYYY-MM-01 format"
        )
    parsed = _normalize_month_value(value, field_name="scoring_month")
    if parsed.day != 1:
        raise ScoreObservabilityError(
            "Package 9 scoring month must be the first day of a calendar month"
        )
    return parsed


def _resolve_prior_scoring_month_for_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    scoring_month: pd.Timestamp,
) -> pd.Timestamp | None:
    prior_value = connection.execute(
        f"""
        SELECT MAX(observation_month)
        FROM {SCORE_OUTPUT_TABLE}
        WHERE observation_month < ?
        """,
        [scoring_month.date()],
    ).fetchone()[0]
    if prior_value is None:
        return None
    prior_month = _normalize_month_value(
        prior_value,
        field_name="prior scored observation_month",
    )
    if prior_month.day != 1:
        raise ScoreObservabilityError(
            "Package 9 prior scored observation_month must be the first day of "
            "a calendar month"
        )
    return prior_month


def _validate_selector(
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
) -> None:
    if scoring_month is None and not latest:
        raise ScoreObservabilityError(
            "Package 9 requires either explicit --scoring-month or explicit --latest"
        )
    if scoring_month is not None and latest:
        raise ScoreObservabilityError(
            "Package 9 accepts exactly one selector: --scoring-month or --latest"
        )


def _validate_required_tables(connection: duckdb.DuckDBPyConnection) -> None:
    for table_name in (
        SCORE_OUTPUT_TABLE,
        BATCH_SCORING_AUDIT_TABLE,
        SCORING_SOURCE_TABLE,
    ):
        _validate_table_exists(connection, table_name)


def _validate_table_exists(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> None:
    schema_name, relation_name = table_name.split(".", maxsplit=1)
    exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema_name, relation_name],
    ).fetchone()[0]
    if exists == 0:
        raise ScoreObservabilityError(
            f"Package 9 required input table is missing: {table_name}"
        )


def _validate_required_columns(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    required_columns: tuple[str, ...],
) -> None:
    schema_name, relation_name = table_name.split(".", maxsplit=1)
    available_columns = {
        row[0]
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema_name, relation_name],
        ).fetchall()
    }
    missing_columns = tuple(
        column for column in required_columns if column not in available_columns
    )
    if missing_columns:
        raise ScoreObservabilityError(
            f"Package 9 required input table {table_name} is missing column(s): "
            + ", ".join(missing_columns)
        )


def _safe_population_columns(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[str, ...]:
    schema_name, relation_name = SCORING_SOURCE_TABLE.split(".", maxsplit=1)
    available_columns = {
        row[0]
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema_name, relation_name],
        ).fetchall()
    }
    segment_columns = tuple(
        column for column in SAFE_SEGMENT_COLUMNS if column in available_columns
    )
    return (*REQUIRED_EXPECTED_POPULATION_COLUMNS, *segment_columns)


def _validate_selected_score_population(
    frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> None:
    if frame.empty:
        raise ScoreObservabilityError(
            "Package 9 selected scoring month has no score rows: "
            f"{scoring_month.date().isoformat()}"
        )
    if frame["account_id"].isna().any():
        raise ScoreObservabilityError(
            "Package 9 score population contains null account_id"
        )
    normalized_months = pd.to_datetime(frame["observation_month"], errors="coerce")
    if normalized_months.isna().any():
        raise ScoreObservabilityError(
            "Package 9 score population contains invalid observation_month values"
        )
    if not (normalized_months.dt.day == 1).all():
        raise ScoreObservabilityError(
            "Package 9 score population contains non-month-start observation_month "
            "values"
        )
    duplicate_mask = frame.duplicated(subset=["account_id", "observation_month"])
    if duplicate_mask.any():
        raise ScoreObservabilityError(
            "Package 9 score population contains duplicate account/month rows"
        )


def _validate_expected_population(
    frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> None:
    if frame.empty:
        raise ScoreObservabilityError(
            "Package 9 expected population could not be resolved from "
            f"{SCORING_SOURCE_TABLE} for {scoring_month.date().isoformat()}"
        )
    if frame["account_id"].isna().any():
        raise ScoreObservabilityError(
            "Package 9 expected population contains null account_id"
        )
    duplicate_mask = frame.duplicated(subset=["account_id", "observation_month"])
    if duplicate_mask.any():
        raise ScoreObservabilityError(
            "Package 9 expected population contains duplicate account/month rows"
        )


def _validate_expected_population_match(
    *,
    score_frame: pd.DataFrame,
    expected_population_frame: pd.DataFrame,
    scoring_month: pd.Timestamp,
) -> None:
    scored_ids = set(score_frame["account_id"].astype(str))
    expected_ids = set(expected_population_frame["account_id"].astype(str))
    if len(score_frame) != len(expected_population_frame) or scored_ids != expected_ids:
        missing_from_scores = len(expected_ids - scored_ids)
        unexpected_scores = len(scored_ids - expected_ids)
        raise ScoreObservabilityError(
            "Package 9 scored population does not match expected population for "
            f"{scoring_month.date().isoformat()}: expected_count="
            f"{len(expected_population_frame)}, scored_count={len(score_frame)}, "
            f"missing_from_scores={missing_from_scores}, "
            f"unexpected_scores={unexpected_scores}"
        )


def _normalize_month_value(
    value: str | date | pd.Timestamp,
    *,
    field_name: str,
) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ScoreObservabilityError(
            f"Package 9 {field_name} is not a valid date"
        ) from error
    if pd.isna(parsed):
        raise ScoreObservabilityError(
            f"Package 9 {field_name} is not a valid date"
        )
    return parsed.normalize()
