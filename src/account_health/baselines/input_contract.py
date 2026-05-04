"""Package 4 baseline input contract.

The contract defines which `mart.account_month` columns may feed deterministic
rule baselines. Labels and generator-only fields may exist upstream for
validation, but they must never be scoring inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from account_health.features import MART_SCHEMA
from account_health.warehouse import DEFAULT_DATABASE_PATH

BASELINE_VERSION = "rule_baseline_v1"
BASELINE_SOURCE_TABLE = f"{MART_SCHEMA}.account_month"
BASELINE_OUTPUT_TABLE = f"{MART_SCHEMA}.account_month_baselines"

BASELINE_CARRY_THROUGH_COLUMNS: tuple[str, ...] = (
    "account_id",
    "observation_month",
    "observation_month_end",
)

APPROVED_BASELINE_INPUT_COLUMNS: tuple[str, ...] = (
    "account_age_days",
    "industry",
    "region",
    "segment",
    "company_size_band",
    "acquisition_channel",
    "current_plan",
    "current_mrr",
    "current_billing_period",
    "subscription_age_days",
    "usage_event_count_30d",
    "usage_event_count_90d",
    "usage_event_count_180d",
    "active_user_count_30d",
    "active_user_count_90d",
    "active_user_count_180d",
    "usage_event_value_sum_90d",
    "support_ticket_count_30d",
    "support_ticket_count_90d",
    "support_ticket_count_180d",
    "high_priority_ticket_count_90d",
    "open_ticket_count",
    "avg_resolution_hours_known",
    "days_since_last_ticket",
    "invoice_count_90d",
    "invoice_count_180d",
    "invoice_amount_sum_90d",
    "invoice_amount_sum_180d",
    "unpaid_invoice_count_90d",
    "failed_invoice_count_90d",
    "overdue_invoice_count",
    "avg_payment_delay_days_known",
    "days_since_last_invoice",
    "crm_touchpoint_count_30d",
    "crm_touchpoint_count_90d",
    "crm_touchpoint_count_180d",
    "sales_touchpoint_count_90d",
    "cs_touchpoint_count_90d",
    "days_since_last_crm_touchpoint",
)

LABEL_COLUMNS: tuple[str, ...] = (
    "is_churn_label_eligible",
    "is_expansion_label_eligible",
    "churn_90d",
    "expansion_90d",
)

DATE_AUDIT_COLUMNS: tuple[str, ...] = (
    "account_created_date",
)

GENERATOR_ONLY_COLUMNS: tuple[str, ...] = (
    "synthetic_archetype",
    "accounts.synthetic_archetype",
)

OUTPUT_AUDIT_COLUMNS: tuple[str, ...] = (
    "baseline_version",
    "baseline_created_at_utc",
)

EXCLUDED_BASELINE_SOURCE_COLUMNS: tuple[str, ...] = (
    *BASELINE_CARRY_THROUGH_COLUMNS,
    *DATE_AUDIT_COLUMNS,
    *LABEL_COLUMNS,
    *GENERATOR_ONLY_COLUMNS,
)

FORBIDDEN_BASELINE_INPUT_COLUMNS: tuple[str, ...] = (
    *BASELINE_CARRY_THROUGH_COLUMNS,
    *DATE_AUDIT_COLUMNS,
    *LABEL_COLUMNS,
    *GENERATOR_ONLY_COLUMNS,
    *OUTPUT_AUDIT_COLUMNS,
)

REQUIRED_BASELINE_SOURCE_COLUMNS: tuple[str, ...] = (
    *BASELINE_CARRY_THROUGH_COLUMNS,
    *APPROVED_BASELINE_INPUT_COLUMNS,
)


@dataclass(frozen=True)
class BaselineInputContract:
    """Resolved Package 4 input contract for a source table."""

    source_table: str
    approved_scoring_columns: tuple[str, ...]
    carry_through_columns: tuple[str, ...]
    excluded_source_columns: tuple[str, ...]
    source_columns: tuple[str, ...]


class BaselineInputContractError(ValueError):
    """Raised when `mart.account_month` cannot satisfy the baseline contract."""


def validate_baseline_input_contract(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    source_table: str = BASELINE_SOURCE_TABLE,
) -> BaselineInputContract:
    """Validate the approved Package 4 input contract against DuckDB."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file), read_only=True) as connection:
        return validate_baseline_input_contract_for_connection(
            connection,
            source_table=source_table,
        )


def validate_baseline_input_contract_for_connection(
    connection: duckdb.DuckDBPyConnection,
    source_table: str = BASELINE_SOURCE_TABLE,
) -> BaselineInputContract:
    """Validate the Package 4 input contract using an existing connection."""

    source_columns = _source_columns(connection, source_table)
    contract = validate_baseline_source_columns(
        source_columns,
        source_table=source_table,
    )
    _validate_source_grain(connection, source_table)
    return contract


def validate_baseline_source_columns(
    source_columns: tuple[str, ...] | list[str],
    source_table: str = BASELINE_SOURCE_TABLE,
) -> BaselineInputContract:
    """Validate a source column list without connecting to DuckDB."""

    columns = tuple(source_columns)
    column_set = set(columns)
    missing_required_columns = tuple(
        column
        for column in REQUIRED_BASELINE_SOURCE_COLUMNS
        if column not in column_set
    )
    forbidden_scoring_columns = tuple(
        column
        for column in APPROVED_BASELINE_INPUT_COLUMNS
        if column in FORBIDDEN_BASELINE_INPUT_COLUMNS
    )
    forbidden_source_columns = tuple(
        column
        for column in GENERATOR_ONLY_COLUMNS
        if column in column_set
    )

    errors: list[str] = []
    if missing_required_columns:
        errors.append(
            "missing required baseline source columns: "
            + ", ".join(missing_required_columns)
        )
    if forbidden_scoring_columns:
        errors.append(
            "forbidden scoring columns in approved input list: "
            + ", ".join(forbidden_scoring_columns)
        )
    if forbidden_source_columns:
        errors.append(
            "generator-only columns present in baseline source table: "
            + ", ".join(forbidden_source_columns)
        )

    if errors:
        raise BaselineInputContractError(
            f"{source_table} violates Package 4: " + "; ".join(errors)
        )

    return BaselineInputContract(
        source_table=source_table,
        approved_scoring_columns=APPROVED_BASELINE_INPUT_COLUMNS,
        carry_through_columns=BASELINE_CARRY_THROUGH_COLUMNS,
        excluded_source_columns=EXCLUDED_BASELINE_SOURCE_COLUMNS,
        source_columns=columns,
    )


def _source_columns(
    connection: duckdb.DuckDBPyConnection,
    source_table: str,
) -> tuple[str, ...]:
    schema_name, table_name = _split_table_name(source_table)
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ?
            AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema_name, table_name],
    ).fetchall()

    if not rows:
        raise BaselineInputContractError(
            f"{source_table} does not exist or has no columns"
        )

    return tuple(row[0] for row in rows)


def _validate_source_grain(
    connection: duckdb.DuckDBPyConnection,
    source_table: str,
) -> None:
    duplicate_count = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT account_id, observation_month
            FROM {source_table}
            GROUP BY account_id, observation_month
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    if duplicate_count:
        raise BaselineInputContractError(
            f"{source_table} violates Package 4: duplicate account-month "
            "grain on account_id, observation_month"
        )


def _split_table_name(source_table: str) -> tuple[str, str]:
    parts = source_table.split(".")
    if len(parts) != 2 or not all(parts):
        raise BaselineInputContractError(
            f"source_table must use schema.table form: {source_table}"
        )
    return parts[0], parts[1]
