from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from account_health.baselines import (
    APPROVED_BASELINE_INPUT_COLUMNS,
    BASELINE_CARRY_THROUGH_COLUMNS,
    EXCLUDED_BASELINE_SOURCE_COLUMNS,
    BaselineInputContractError,
    validate_baseline_input_contract,
)


def create_account_month_contract_table(
    database_path: Path,
    *,
    omit_columns: set[str] | None = None,
    extra_columns: dict[str, str] | None = None,
) -> None:
    omit_columns = omit_columns or set()
    extra_columns = extra_columns or {}
    column_types = {
        "account_id": "VARCHAR",
        "observation_month": "DATE",
        "observation_month_end": "DATE",
        "is_churn_label_eligible": "BOOLEAN",
        "is_expansion_label_eligible": "BOOLEAN",
        "churn_90d": "INTEGER",
        "expansion_90d": "INTEGER",
        "account_created_date": "DATE",
        "account_age_days": "INTEGER",
        "industry": "VARCHAR",
        "region": "VARCHAR",
        "segment": "VARCHAR",
        "company_size_band": "VARCHAR",
        "acquisition_channel": "VARCHAR",
        "current_plan": "VARCHAR",
        "current_mrr": "DOUBLE",
        "current_billing_period": "VARCHAR",
        "subscription_age_days": "INTEGER",
        "usage_event_count_30d": "INTEGER",
        "usage_event_count_90d": "INTEGER",
        "usage_event_count_180d": "INTEGER",
        "active_user_count_30d": "INTEGER",
        "active_user_count_90d": "INTEGER",
        "active_user_count_180d": "INTEGER",
        "usage_event_value_sum_90d": "DOUBLE",
        "support_ticket_count_30d": "INTEGER",
        "support_ticket_count_90d": "INTEGER",
        "support_ticket_count_180d": "INTEGER",
        "high_priority_ticket_count_90d": "INTEGER",
        "open_ticket_count": "INTEGER",
        "avg_resolution_hours_known": "DOUBLE",
        "days_since_last_ticket": "INTEGER",
        "invoice_count_90d": "INTEGER",
        "invoice_count_180d": "INTEGER",
        "invoice_amount_sum_90d": "DOUBLE",
        "invoice_amount_sum_180d": "DOUBLE",
        "unpaid_invoice_count_90d": "INTEGER",
        "failed_invoice_count_90d": "INTEGER",
        "overdue_invoice_count": "INTEGER",
        "avg_payment_delay_days_known": "DOUBLE",
        "days_since_last_invoice": "INTEGER",
        "crm_touchpoint_count_30d": "INTEGER",
        "crm_touchpoint_count_90d": "INTEGER",
        "crm_touchpoint_count_180d": "INTEGER",
        "sales_touchpoint_count_90d": "INTEGER",
        "cs_touchpoint_count_90d": "INTEGER",
        "days_since_last_crm_touchpoint": "INTEGER",
        **extra_columns,
    }
    column_sql = ",\n".join(
        f"{column_name} {column_type}"
        for column_name, column_type in column_types.items()
        if column_name not in omit_columns
    )

    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.execute(f"CREATE TABLE mart.account_month ({column_sql})")


def test_baseline_input_contract_excludes_labels_and_generator_fields() -> None:
    forbidden_inputs = {
        "is_churn_label_eligible",
        "is_expansion_label_eligible",
        "churn_90d",
        "expansion_90d",
        "synthetic_archetype",
        "accounts.synthetic_archetype",
    }

    assert forbidden_inputs.isdisjoint(APPROVED_BASELINE_INPUT_COLUMNS)
    assert forbidden_inputs <= set(EXCLUDED_BASELINE_SOURCE_COLUMNS)
    assert set(BASELINE_CARRY_THROUGH_COLUMNS).isdisjoint(
        APPROVED_BASELINE_INPUT_COLUMNS
    )


def test_validate_baseline_input_contract_accepts_approved_columns(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_contract_table(database_path)

    contract = validate_baseline_input_contract(database_path)

    assert contract.source_table == "mart.account_month"
    assert contract.carry_through_columns == (
        "account_id",
        "observation_month",
        "observation_month_end",
    )
    assert "current_mrr" in contract.approved_scoring_columns
    assert "churn_90d" in contract.excluded_source_columns
    assert "expansion_90d" in contract.excluded_source_columns
    assert "churn_90d" not in contract.approved_scoring_columns
    assert "expansion_90d" not in contract.approved_scoring_columns


def test_validate_baseline_input_contract_rejects_missing_input_column(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_contract_table(
        database_path,
        omit_columns={"current_mrr"},
    )

    with pytest.raises(BaselineInputContractError, match="current_mrr"):
        validate_baseline_input_contract(database_path)


def test_validate_baseline_input_contract_rejects_generator_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_contract_table(
        database_path,
        extra_columns={"synthetic_archetype": "VARCHAR"},
    )

    with pytest.raises(BaselineInputContractError, match="synthetic_archetype"):
        validate_baseline_input_contract(database_path)
