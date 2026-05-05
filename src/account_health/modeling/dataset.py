"""Load Package 5 modelling datasets from `mart.account_month`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from account_health.features import MART_SCHEMA
from account_health.warehouse import DEFAULT_DATABASE_PATH

MODELING_SOURCE_TABLE = f"{MART_SCHEMA}.account_month"

GRAIN_COLUMNS: tuple[str, ...] = ("account_id", "observation_month")
TARGET_COLUMNS: tuple[str, ...] = ("churn_90d", "expansion_90d")

APPROVED_CATEGORICAL_FEATURES: tuple[str, ...] = (
    "industry",
    "region",
    "segment",
    "company_size_band",
    "acquisition_channel",
    "current_plan",
    "current_billing_period",
)

APPROVED_NUMERIC_FEATURES: tuple[str, ...] = (
    "account_age_days",
    "current_mrr",
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

FORBIDDEN_MODELING_FEATURES: tuple[str, ...] = (
    "account_id",
    "observation_month",
    "observation_month_end",
    "churn_90d",
    "expansion_90d",
    "is_churn_label_eligible",
    "is_expansion_label_eligible",
    "synthetic_archetype",
)

FORBIDDEN_FEATURE_NAME_TERMS: tuple[str, ...] = (
    "renewal",
    "outcome",
    "future",
    "label",
    "target",
    "score",
    "rank",
    "decile",
)


@dataclass(frozen=True)
class ModelingFeatureSet:
    """Explicit Package 5 feature allowlist."""

    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (*self.numeric_features, *self.categorical_features)


DEFAULT_MODELING_FEATURE_SET = ModelingFeatureSet(
    numeric_features=APPROVED_NUMERIC_FEATURES,
    categorical_features=APPROVED_CATEGORICAL_FEATURES,
)


@dataclass(frozen=True)
class ModelingDataset:
    """A target-specific labelled modelling frame."""

    source_table: str
    target: str
    frame: pd.DataFrame
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (*self.numeric_features, *self.categorical_features)


class ModelingDatasetError(ValueError):
    """Raised when `mart.account_month` violates the Package 5 contract."""


def load_modeling_dataset(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    *,
    target: str,
    source_table: str = MODELING_SOURCE_TABLE,
    feature_set: ModelingFeatureSet = DEFAULT_MODELING_FEATURE_SET,
) -> ModelingDataset:
    """Load labelled rows for one Package 5 target from `mart.account_month`."""

    if target not in TARGET_COLUMNS:
        raise ModelingDatasetError(f"unsupported modelling target: {target}")
    _validate_modeling_source_table(source_table)

    database_file = Path(database_path)
    try:
        with duckdb.connect(str(database_file), read_only=True) as connection:
            return load_modeling_dataset_for_connection(
                connection,
                target=target,
                source_table=source_table,
                feature_set=feature_set,
            )
    except duckdb.IOException as error:
        raise ModelingDatasetError(
            f"{source_table} could not be read from {database_file}: {error}"
        ) from error


def load_modeling_dataset_for_connection(
    connection: duckdb.DuckDBPyConnection,
    *,
    target: str,
    source_table: str = MODELING_SOURCE_TABLE,
    feature_set: ModelingFeatureSet = DEFAULT_MODELING_FEATURE_SET,
) -> ModelingDataset:
    """Load labelled rows for one target using an existing DuckDB connection."""

    if target not in TARGET_COLUMNS:
        raise ModelingDatasetError(f"unsupported modelling target: {target}")
    _validate_modeling_source_table(source_table)

    columns = _source_columns(connection, source_table)
    validate_modeling_source_columns(
        columns,
        source_table=source_table,
        feature_set=feature_set,
    )
    _validate_source_grain(connection, source_table)

    select_columns = (*GRAIN_COLUMNS, target, *feature_set.feature_names)
    frame = connection.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM {source_table}
        WHERE {target} IS NOT NULL
        ORDER BY account_id, observation_month
        """
    ).fetchdf()

    _validate_binary_target(frame, target)

    return ModelingDataset(
        source_table=source_table,
        target=target,
        frame=frame,
        numeric_features=feature_set.numeric_features,
        categorical_features=feature_set.categorical_features,
    )


def validate_modeling_source_columns(
    source_columns: tuple[str, ...] | list[str],
    *,
    source_table: str = MODELING_SOURCE_TABLE,
    feature_set: ModelingFeatureSet = DEFAULT_MODELING_FEATURE_SET,
) -> None:
    """Validate required Package 5 source and feature columns."""

    validate_modeling_feature_set(feature_set)

    columns = tuple(source_columns)
    column_set = set(columns)
    required_columns = (*GRAIN_COLUMNS, *TARGET_COLUMNS, *feature_set.feature_names)
    missing_columns = tuple(
        column for column in required_columns if column not in column_set
    )

    if missing_columns:
        raise ModelingDatasetError(
            f"{source_table} violates Package 5: missing required column(s): "
            + ", ".join(missing_columns)
        )


def validate_modeling_feature_set(feature_set: ModelingFeatureSet) -> None:
    """Validate that an explicit feature allowlist contains no forbidden names."""

    feature_names = feature_set.feature_names
    duplicate_features = tuple(
        feature
        for index, feature in enumerate(feature_names)
        if feature in feature_names[:index]
    )
    forbidden_features = tuple(
        feature for feature in feature_names if _is_forbidden_feature(feature)
    )

    errors: list[str] = []
    if duplicate_features:
        errors.append("duplicate feature(s): " + ", ".join(duplicate_features))
    if forbidden_features:
        errors.append("forbidden feature(s): " + ", ".join(forbidden_features))

    if errors:
        raise ModelingDatasetError(
            "Package 5 modelling feature allowlist is invalid: "
            + "; ".join(errors)
        )


def _is_forbidden_feature(feature_name: str) -> bool:
    normalized = feature_name.lower()
    return (
        feature_name in FORBIDDEN_MODELING_FEATURES
        or normalized.startswith("baseline_")
        or any(term in normalized for term in FORBIDDEN_FEATURE_NAME_TERMS)
    )


def _validate_modeling_source_table(source_table: str) -> None:
    if source_table != MODELING_SOURCE_TABLE:
        raise ModelingDatasetError(
            "Package 5 may only read mart.account_month; "
            f"received source_table={source_table}"
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
        raise ModelingDatasetError(f"{source_table} does not exist or has no columns")

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
        raise ModelingDatasetError(
            f"{source_table} violates Package 5: duplicate account-month "
            "grain on account_id, observation_month"
        )


def _validate_binary_target(frame: pd.DataFrame, target: str) -> None:
    values = frame[target].dropna()
    if values.empty:
        raise ModelingDatasetError(
            f"{target} violates Package 5: no non-null eligible labels remain"
        )

    numeric_values = pd.to_numeric(values, errors="coerce")
    if numeric_values.isna().any() or not numeric_values.isin([0, 1]).all():
        raise ModelingDatasetError(
            f"{target} violates Package 5: eligible labels must be binary"
        )


def _split_table_name(source_table: str) -> tuple[str, str]:
    parts = source_table.split(".")
    if len(parts) != 2 or not all(parts):
        raise ModelingDatasetError(
            f"source_table must use schema.table form: {source_table}"
        )
    return parts[0], parts[1]
