"""Package 10 GTM policy input loading and score validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from account_health.scoring import SCORE_OUTPUT_TABLE
from account_health.scoring.loading import SCORING_SOURCE_TABLE
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
TARGET_SCORE_COLUMNS = {
    "churn": "churn_score",
    "expansion": "expansion_score",
}
SAFE_CONTEXT_COLUMNS = (
    "current_plan",
    "company_size_band",
    "region",
    "industry",
    "current_mrr",
)
REQUIRED_CONTEXT_COLUMNS = (
    "account_id",
    "observation_month",
    *SAFE_CONTEXT_COLUMNS,
)


class GTMPolicyError(ValueError):
    """Raised when Package 10 inputs violate the deterministic policy contract."""


@dataclass(frozen=True)
class GTMPolicyInputs:
    """Validated Package 8 score inputs for one Package 10 scoring month."""

    selector: str
    scoring_month: pd.Timestamp
    score_frame: pd.DataFrame


def load_gtm_policy_inputs(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | date | pd.Timestamp | None = None,
    latest: bool = False,
) -> GTMPolicyInputs:
    """Load and validate Package 8 raw score rows for one GTM policy run."""

    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            _validate_table_exists(connection, SCORE_OUTPUT_TABLE)
            _validate_required_columns(
                connection,
                SCORE_OUTPUT_TABLE,
                REQUIRED_SCORE_COLUMNS,
            )
            selected_month, selector = resolve_gtm_policy_scoring_month_for_connection(
                connection,
                scoring_month=scoring_month,
                latest=latest,
            )
            score_frame = connection.execute(
                f"""
                SELECT *
                FROM {SCORE_OUTPUT_TABLE}
                WHERE observation_month = ?
                ORDER BY account_id, observation_month
                """,
                [selected_month.date()],
            ).fetchdf()
    except duckdb.IOException as error:
        raise GTMPolicyError(
            f"Package 10 could not read required DuckDB inputs from {database_file}: "
            f"{error}"
        ) from error

    _validate_selected_score_population(
        score_frame,
        scoring_month=selected_month,
    )
    validated_scores = validate_gtm_policy_score_values(score_frame)
    return GTMPolicyInputs(
        selector=selector,
        scoring_month=selected_month,
        score_frame=validated_scores,
    )


def load_gtm_policy_context(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    scoring_month: str | date | pd.Timestamp,
) -> pd.DataFrame:
    """Load approved safe descriptive context for one Package 10 month."""

    selected_month = parse_gtm_policy_scoring_month(scoring_month)
    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            _validate_table_exists(connection, SCORING_SOURCE_TABLE)
            _validate_required_columns(
                connection,
                SCORING_SOURCE_TABLE,
                REQUIRED_CONTEXT_COLUMNS,
            )
            context_frame = connection.execute(
                f"""
                SELECT {", ".join(REQUIRED_CONTEXT_COLUMNS)}
                FROM {SCORING_SOURCE_TABLE}
                WHERE observation_month = ?
                ORDER BY account_id, observation_month
                """,
                [selected_month.date()],
            ).fetchdf()
    except duckdb.IOException as error:
        raise GTMPolicyError(
            f"Package 10 could not read safe context from {database_file}: {error}"
        ) from error

    _validate_context_population(
        context_frame,
        scoring_month=selected_month,
    )
    return context_frame


def resolve_gtm_policy_scoring_month_for_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
) -> tuple[pd.Timestamp, str]:
    """Resolve an explicit month or explicit latest scored month."""

    _validate_selector(scoring_month=scoring_month, latest=latest)
    _validate_table_exists(connection, SCORE_OUTPUT_TABLE)

    if scoring_month is not None:
        return parse_gtm_policy_scoring_month(scoring_month), "scoring_month"

    latest_value = connection.execute(
        f"SELECT MAX(observation_month) FROM {SCORE_OUTPUT_TABLE}"
    ).fetchone()[0]
    if latest_value is None:
        raise GTMPolicyError(
            f"{SCORE_OUTPUT_TABLE} has no rows, so Package 10 cannot resolve --latest"
        )
    latest_month = _normalize_month_value(
        latest_value,
        field_name="latest scored observation_month",
    )
    if latest_month.day != 1:
        raise GTMPolicyError(
            "Package 10 latest scored observation_month must be the first day of "
            "a calendar month"
        )
    return latest_month, "latest"


def parse_gtm_policy_scoring_month(
    value: str | date | pd.Timestamp,
) -> pd.Timestamp:
    """Parse the explicit `YYYY-MM-01` Package 10 scoring month."""

    if isinstance(value, str) and not MONTH_PATTERN.match(value):
        raise GTMPolicyError(
            "Package 10 scoring month must use explicit YYYY-MM-01 format"
        )
    parsed = _normalize_month_value(value, field_name="scoring_month")
    if parsed.day != 1:
        raise GTMPolicyError(
            "Package 10 scoring month must be the first day of a calendar month"
        )
    return parsed


def validate_gtm_policy_score_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate numeric, finite, non-null, bounded raw Package 8 scores."""

    missing_columns = tuple(
        column for column in TARGET_SCORE_COLUMNS.values() if column not in frame.columns
    )
    if missing_columns:
        raise GTMPolicyError(
            "Package 10 score inputs are missing column(s): "
            + ", ".join(missing_columns)
        )

    normalized = frame.copy()
    for target, column in TARGET_SCORE_COLUMNS.items():
        values = normalized[column]
        if values.isna().any():
            raise GTMPolicyError(f"Package 10 {target} scores contain null values")
        numeric_values = pd.to_numeric(values, errors="coerce")
        if numeric_values.isna().any():
            raise GTMPolicyError(
                f"Package 10 {target} scores contain non-numeric values"
            )
        if not np.isfinite(numeric_values.to_numpy(dtype=float)).all():
            raise GTMPolicyError(
                f"Package 10 {target} scores contain non-finite values"
            )
        if not numeric_values.between(0.0, 1.0).all():
            raise GTMPolicyError(
                f"Package 10 {target} scores must be inside [0, 1]"
            )
        normalized[column] = numeric_values.astype(float)
    return normalized


def _validate_selector(
    *,
    scoring_month: str | date | pd.Timestamp | None,
    latest: bool,
) -> None:
    if scoring_month is None and not latest:
        raise GTMPolicyError(
            "Package 10 requires either explicit --scoring-month or explicit --latest"
        )
    if scoring_month is not None and latest:
        raise GTMPolicyError(
            "Package 10 accepts exactly one selector: --scoring-month or --latest"
        )


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
        raise GTMPolicyError(
            f"Package 10 required input table is missing: {table_name}"
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
        raise GTMPolicyError(
            f"Package 10 required input table {table_name} is missing column(s): "
            + ", ".join(missing_columns)
        )


def _validate_selected_score_population(
    frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> None:
    if frame.empty:
        raise GTMPolicyError(
            "Package 10 selected scoring month has no score rows: "
            f"{scoring_month.date().isoformat()}"
        )
    if frame["account_id"].isna().any():
        raise GTMPolicyError("Package 10 score population contains null account_id")
    normalized_months = pd.to_datetime(frame["observation_month"], errors="coerce")
    if normalized_months.isna().any():
        raise GTMPolicyError(
            "Package 10 score population contains invalid observation_month values"
        )
    if not (normalized_months.dt.day == 1).all():
        raise GTMPolicyError(
            "Package 10 score population contains non-month-start observation_month "
            "values"
        )
    duplicate_mask = frame.duplicated(subset=["account_id", "observation_month"])
    if duplicate_mask.any():
        raise GTMPolicyError(
            "Package 10 score population contains duplicate account/month rows"
        )


def _validate_context_population(
    frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> None:
    if frame.empty:
        raise GTMPolicyError(
            "Package 10 safe context could not be resolved from "
            f"{SCORING_SOURCE_TABLE} for {scoring_month.date().isoformat()}"
        )
    if frame["account_id"].isna().any():
        raise GTMPolicyError("Package 10 safe context contains null account_id")
    duplicate_mask = frame.duplicated(subset=["account_id", "observation_month"])
    if duplicate_mask.any():
        raise GTMPolicyError(
            "Package 10 safe context contains duplicate account/month rows"
        )


def _normalize_month_value(
    value: str | date | pd.Timestamp,
    *,
    field_name: str,
) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise GTMPolicyError(f"Package 10 {field_name} is not a valid date")
    return pd.Timestamp(parsed).normalize()
