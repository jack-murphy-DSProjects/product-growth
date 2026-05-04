"""Load Package 1 source CSVs into the local DuckDB warehouse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd

from account_health.synthetic.schemas import (
    FOREIGN_KEYS,
    PRIMARY_KEYS,
    REQUIRED_COLUMNS,
    SOURCE_TABLES,
)

DEFAULT_SOURCE_DIR = Path("data/generated")
DEFAULT_DATABASE_PATH = Path("data/warehouse/account_health.duckdb")
RAW_SCHEMA = "raw"
METADATA_SCHEMA = "metadata"
LOAD_AUDIT_TABLE = "load_audit"

DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "accounts": ("created_date",),
    "users": ("created_date",),
    "usage_events": ("event_timestamp",),
    "subscriptions": ("start_date", "end_date"),
    "invoices": ("invoice_date", "due_date", "paid_date"),
    "support_tickets": ("created_at", "resolved_at"),
    "crm_touchpoints": ("touchpoint_date",),
    "renewals": ("renewal_date",),
}

NULLABLE_DATE_COLUMNS = {
    ("subscriptions", "end_date"),
    ("invoices", "paid_date"),
    ("support_tickets", "resolved_at"),
}


@dataclass(frozen=True)
class WarehouseLoadResult:
    """Summary of one local warehouse rebuild."""

    load_id: str
    source_dir: Path
    database_path: Path
    table_row_counts: dict[str, int]


@dataclass(frozen=True)
class SourceValidationError:
    """One source-table contract validation failure."""

    table_name: str
    check_name: str
    message: str


class SourceContractError(ValueError):
    """Raised when generated source CSVs fail the Package 2 contract."""

    def __init__(self, errors: list[SourceValidationError]) -> None:
        self.errors = tuple(errors)
        detail = "; ".join(error.message for error in self.errors)
        super().__init__(f"source contract validation failed: {detail}")


def load_source_csvs_to_warehouse(
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> WarehouseLoadResult:
    """Rebuild raw source tables in a local DuckDB database from CSV files."""

    source_path = Path(source_dir)
    database_file = Path(database_path)

    frames = _read_source_frames(source_path)
    database_file.parent.mkdir(parents=True, exist_ok=True)
    load_id = uuid4().hex
    loaded_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()
    row_counts = {table: len(frame) for table, frame in frames.items()}

    with duckdb.connect(str(database_file)) as connection:
        _reset_schemas(connection)
        _create_load_audit_table(connection)

        for table in SOURCE_TABLES:
            frame = frames[table]
            relation_name = f"{table}_source_frame"
            connection.register(relation_name, frame)
            try:
                connection.execute(
                    f"CREATE TABLE {RAW_SCHEMA}.{table} AS SELECT * FROM {relation_name}"
                )
            finally:
                connection.unregister(relation_name)

            connection.execute(
                f"""
                INSERT INTO {METADATA_SCHEMA}.{LOAD_AUDIT_TABLE}
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    load_id,
                    loaded_at_utc,
                    str(source_path),
                    str(database_file),
                    f"{RAW_SCHEMA}.{table}",
                    row_counts[table],
                    "loaded",
                ],
            )

    return WarehouseLoadResult(
        load_id=load_id,
        source_dir=source_path,
        database_path=database_file,
        table_row_counts=row_counts,
    )


def _read_source_frames(source_dir: Path) -> dict[str, pd.DataFrame]:
    missing_errors = [
        SourceValidationError(
            table_name=table,
            check_name="required_file",
            message=f"missing required source file: {table}.csv",
        )
        for table in SOURCE_TABLES
        if not (source_dir / f"{table}.csv").is_file()
    ]
    if missing_errors:
        raise SourceContractError(missing_errors)

    frames: dict[str, pd.DataFrame] = {}
    for table in SOURCE_TABLES:
        frames[table] = pd.read_csv(source_dir / f"{table}.csv")

    _validate_required_columns_and_rows(frames)
    _validate_primary_keys(frames)
    _validate_foreign_keys(frames)
    _validate_dates_and_ordering(frames)
    return frames


def _validate_required_columns_and_rows(frames: dict[str, pd.DataFrame]) -> None:
    errors: list[SourceValidationError] = []

    for table in SOURCE_TABLES:
        frame = frames[table]
        missing_columns = [
            column for column in REQUIRED_COLUMNS[table] if column not in frame.columns
        ]
        if missing_columns:
            errors.append(
                SourceValidationError(
                    table_name=table,
                    check_name="required_columns",
                    message=(
                        f"{table}.csv is missing required column(s): "
                        f"{', '.join(missing_columns)}"
                    ),
                )
            )

        if frame.empty:
            errors.append(
                SourceValidationError(
                    table_name=table,
                    check_name="non_empty",
                    message=f"{table}.csv must contain at least one row",
                )
            )

    if errors:
        raise SourceContractError(errors)


def _validate_primary_keys(frames: dict[str, pd.DataFrame]) -> None:
    errors: list[SourceValidationError] = []

    for table, key in PRIMARY_KEYS.items():
        values = frames[table][key]
        missing_mask = _missing_value_mask(values)
        if bool(missing_mask.any()):
            errors.append(
                SourceValidationError(
                    table_name=table,
                    check_name="primary_key",
                    message=f"{table}.{key} must not contain null or blank values",
                )
            )

        duplicate_values = values.loc[~missing_mask & values.duplicated()]
        if not duplicate_values.empty:
            first_duplicate = str(duplicate_values.iloc[0])
            errors.append(
                SourceValidationError(
                    table_name=table,
                    check_name="primary_key",
                    message=(
                        f"{table}.{key} must be unique; duplicate value found: "
                        f"{first_duplicate}"
                    ),
                )
            )

    if errors:
        raise SourceContractError(errors)


def _validate_foreign_keys(frames: dict[str, pd.DataFrame]) -> None:
    errors: list[SourceValidationError] = []

    for child_table, key_map in FOREIGN_KEYS.items():
        for child_key, (parent_table, parent_key) in key_map.items():
            parent_values = set(frames[parent_table][parent_key].dropna())
            child_values = frames[child_table][child_key].dropna()
            invalid_values = sorted(set(child_values) - parent_values)
            if invalid_values:
                errors.append(
                    SourceValidationError(
                        table_name=child_table,
                        check_name="foreign_key",
                        message=(
                            f"{child_table}.{child_key} has value(s) not found in "
                            f"{parent_table}.{parent_key}: {invalid_values[0]}"
                        ),
                    )
                )

    event_users = frames["usage_events"][
        ["event_id", "account_id", "user_id"]
    ].merge(
        frames["users"][["user_id", "account_id"]],
        on="user_id",
        how="inner",
        suffixes=("_event", "_user"),
    )
    mismatched_events = event_users[
        event_users["account_id_event"] != event_users["account_id_user"]
    ]
    if not mismatched_events.empty:
        errors.append(
            SourceValidationError(
                table_name="usage_events",
                check_name="foreign_key",
                message=(
                    "usage_events.user_id must belong to the same account_id as "
                    "usage_events.account_id"
                ),
            )
        )

    if errors:
        raise SourceContractError(errors)


def _validate_dates_and_ordering(frames: dict[str, pd.DataFrame]) -> None:
    parsed_dates, parse_errors = _parse_date_columns(frames)
    if parse_errors:
        raise SourceContractError(parse_errors)

    ordering_errors = _date_order_errors(frames, parsed_dates)
    if ordering_errors:
        raise SourceContractError(ordering_errors)


def _parse_date_columns(
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, dict[str, pd.Series]], list[SourceValidationError]]:
    parsed_dates: dict[str, dict[str, pd.Series]] = {}
    errors: list[SourceValidationError] = []

    for table, columns in DATE_COLUMNS.items():
        parsed_dates[table] = {}
        for column in columns:
            raw_values = frames[table][column]
            present_mask = ~_missing_value_mask(raw_values)
            parsed = pd.to_datetime(raw_values, errors="coerce", format="mixed")
            parsed_dates[table][column] = parsed

            invalid_count = int((present_mask & parsed.isna()).sum())
            if invalid_count:
                errors.append(
                    SourceValidationError(
                        table_name=table,
                        check_name="date_parse",
                        message=(
                            f"{table}.{column} contains {invalid_count} invalid "
                            "date value(s)"
                        ),
                    )
                )

            if (table, column) not in NULLABLE_DATE_COLUMNS:
                missing_count = int((~present_mask).sum())
                if missing_count:
                    errors.append(
                        SourceValidationError(
                            table_name=table,
                            check_name="date_parse",
                            message=(
                                f"{table}.{column} contains {missing_count} missing "
                                "date value(s)"
                            ),
                        )
                    )

    return parsed_dates, errors


def _date_order_errors(
    frames: dict[str, pd.DataFrame],
    parsed_dates: dict[str, dict[str, pd.Series]],
) -> list[SourceValidationError]:
    errors: list[SourceValidationError] = []

    accounts = frames["accounts"][["account_id"]].copy()
    accounts["account_created_date"] = parsed_dates["accounts"]["created_date"]

    users = frames["users"][["user_id", "account_id"]].copy()
    users["user_created_date"] = parsed_dates["users"]["created_date"]
    user_dates = users.merge(accounts, on="account_id", how="inner")
    _append_date_order_error(
        errors,
        table="users",
        invalid_mask=user_dates["user_created_date"]
        < user_dates["account_created_date"],
        message="users.created_date must be on or after accounts.created_date",
    )

    events = frames["usage_events"][["event_id", "account_id", "user_id"]].copy()
    events["event_timestamp"] = parsed_dates["usage_events"]["event_timestamp"]
    event_dates = events.merge(accounts, on="account_id", how="inner").merge(
        users[["user_id", "user_created_date"]],
        on="user_id",
        how="inner",
    )
    _append_date_order_error(
        errors,
        table="usage_events",
        invalid_mask=event_dates["event_timestamp"]
        < event_dates["account_created_date"],
        message=(
            "usage_events.event_timestamp must be on or after "
            "accounts.created_date"
        ),
    )
    _append_date_order_error(
        errors,
        table="usage_events",
        invalid_mask=event_dates["event_timestamp"] < event_dates["user_created_date"],
        message=(
            "usage_events.event_timestamp must be on or after users.created_date"
        ),
    )

    subscriptions = frames["subscriptions"][["subscription_id", "account_id"]].copy()
    subscriptions["start_date"] = parsed_dates["subscriptions"]["start_date"]
    subscriptions["end_date"] = parsed_dates["subscriptions"]["end_date"]
    subscription_dates = subscriptions.merge(accounts, on="account_id", how="inner")
    _append_date_order_error(
        errors,
        table="subscriptions",
        invalid_mask=subscription_dates["start_date"]
        < subscription_dates["account_created_date"],
        message="subscriptions.start_date must be on or after accounts.created_date",
    )
    _append_date_order_error(
        errors,
        table="subscriptions",
        invalid_mask=subscription_dates["end_date"].notna()
        & (subscription_dates["end_date"] < subscription_dates["start_date"]),
        message="subscriptions.end_date must be on or after subscriptions.start_date",
    )

    invoices = frames["invoices"][["invoice_id"]].copy()
    invoices["invoice_date"] = parsed_dates["invoices"]["invoice_date"]
    invoices["due_date"] = parsed_dates["invoices"]["due_date"]
    invoices["paid_date"] = parsed_dates["invoices"]["paid_date"]
    _append_date_order_error(
        errors,
        table="invoices",
        invalid_mask=invoices["due_date"] < invoices["invoice_date"],
        message="invoices.due_date must be on or after invoices.invoice_date",
    )
    _append_date_order_error(
        errors,
        table="invoices",
        invalid_mask=invoices["paid_date"].notna()
        & (invoices["paid_date"] < invoices["invoice_date"]),
        message="invoices.paid_date must be on or after invoices.invoice_date",
    )

    tickets = frames["support_tickets"][["ticket_id"]].copy()
    tickets["created_at"] = parsed_dates["support_tickets"]["created_at"]
    tickets["resolved_at"] = parsed_dates["support_tickets"]["resolved_at"]
    _append_date_order_error(
        errors,
        table="support_tickets",
        invalid_mask=tickets["resolved_at"].notna()
        & (tickets["resolved_at"] < tickets["created_at"]),
        message=(
            "support_tickets.resolved_at must be on or after "
            "support_tickets.created_at"
        ),
    )

    touchpoints = frames["crm_touchpoints"][["touchpoint_id", "account_id"]].copy()
    touchpoints["touchpoint_date"] = parsed_dates["crm_touchpoints"][
        "touchpoint_date"
    ]
    touchpoint_dates = touchpoints.merge(accounts, on="account_id", how="inner")
    _append_date_order_error(
        errors,
        table="crm_touchpoints",
        invalid_mask=touchpoint_dates["touchpoint_date"]
        < touchpoint_dates["account_created_date"],
        message=(
            "crm_touchpoints.touchpoint_date must be on or after "
            "accounts.created_date"
        ),
    )

    renewals = frames["renewals"][["renewal_id", "account_id"]].copy()
    renewals["renewal_date"] = parsed_dates["renewals"]["renewal_date"]
    renewal_dates = renewals.merge(accounts, on="account_id", how="inner")
    _append_date_order_error(
        errors,
        table="renewals",
        invalid_mask=renewal_dates["renewal_date"]
        < renewal_dates["account_created_date"],
        message="renewals.renewal_date must be on or after accounts.created_date",
    )

    return errors


def _append_date_order_error(
    errors: list[SourceValidationError],
    table: str,
    invalid_mask: pd.Series,
    message: str,
) -> None:
    if bool(invalid_mask.any()):
        errors.append(
            SourceValidationError(
                table_name=table,
                check_name="date_order",
                message=message,
            )
        )


def _missing_value_mask(values: pd.Series) -> pd.Series:
    string_values = values.astype("string")
    return values.isna() | string_values.str.strip().eq("").fillna(False)


def _reset_schemas(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(f"DROP SCHEMA IF EXISTS {RAW_SCHEMA} CASCADE")
    connection.execute(f"DROP SCHEMA IF EXISTS {METADATA_SCHEMA} CASCADE")
    connection.execute(f"CREATE SCHEMA {RAW_SCHEMA}")
    connection.execute(f"CREATE SCHEMA {METADATA_SCHEMA}")


def _create_load_audit_table(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""
        CREATE TABLE {METADATA_SCHEMA}.{LOAD_AUDIT_TABLE} (
            load_id VARCHAR,
            loaded_at_utc VARCHAR,
            source_dir VARCHAR,
            database_path VARCHAR,
            table_name VARCHAR,
            row_count BIGINT,
            status VARCHAR
        )
        """
    )
