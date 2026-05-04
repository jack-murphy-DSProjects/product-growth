"""Build deterministic Package 4 rule baseline benchmark tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from account_health.baselines.input_contract import (
    BASELINE_OUTPUT_TABLE,
    BASELINE_SOURCE_TABLE,
    BASELINE_VERSION,
    validate_baseline_input_contract_for_connection,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

BASELINE_BUILD_AUDIT_TABLE = "baseline_build_audit"
BASELINE_BUILD_AUDIT_FULL_TABLE = (
    f"{METADATA_SCHEMA}.{BASELINE_BUILD_AUDIT_TABLE}"
)


@dataclass(frozen=True)
class AccountMonthBaselineBuildResult:
    """Summary of one baseline table rebuild."""

    database_path: Path
    build_id: str
    source_table: str
    output_table: str
    audit_table: str
    baseline_version: str
    row_count: int
    account_count: int
    min_observation_month: date | None
    max_observation_month: date | None


def build_account_month_baselines(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> AccountMonthBaselineBuildResult:
    """Rebuild Package 4 deterministic rule baselines."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        validate_baseline_input_contract_for_connection(connection)
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
        build_id = uuid4().hex
        built_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()
        connection.execute(
            _build_rule_baseline_sql(),
            [BASELINE_VERSION, built_at_utc],
        )
        connection.execute(_create_baseline_build_audit_table_sql())
        (
            row_count,
            account_count,
            min_observation_month,
            max_observation_month,
        ) = connection.execute(
            _baseline_summary_sql()
        ).fetchone()
        connection.execute(
            f"""
            INSERT INTO {BASELINE_BUILD_AUDIT_FULL_TABLE}
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                build_id,
                built_at_utc,
                BASELINE_SOURCE_TABLE,
                BASELINE_OUTPUT_TABLE,
                BASELINE_VERSION,
                int(row_count),
                int(account_count),
                min_observation_month,
                max_observation_month,
                "success",
            ],
        )

    return AccountMonthBaselineBuildResult(
        database_path=database_file,
        build_id=build_id,
        source_table=BASELINE_SOURCE_TABLE,
        output_table=BASELINE_OUTPUT_TABLE,
        audit_table=BASELINE_BUILD_AUDIT_FULL_TABLE,
        baseline_version=BASELINE_VERSION,
        row_count=int(row_count),
        account_count=int(account_count),
        min_observation_month=min_observation_month,
        max_observation_month=max_observation_month,
    )


def _baseline_summary_sql() -> str:
    return f"""
    SELECT
        COUNT(*) AS row_count,
        COUNT(DISTINCT account_id) AS account_count,
        MIN(observation_month) AS min_observation_month,
        MAX(observation_month) AS max_observation_month
    FROM {BASELINE_OUTPUT_TABLE}
    """


def _create_baseline_build_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {BASELINE_BUILD_AUDIT_FULL_TABLE} (
        build_id VARCHAR,
        built_at_utc VARCHAR,
        source_table VARCHAR,
        output_table VARCHAR,
        baseline_version VARCHAR,
        row_count BIGINT,
        account_count BIGINT,
        min_observation_month DATE,
        max_observation_month DATE,
        status VARCHAR
    )
    """


def _build_rule_baseline_sql() -> str:
    return f"""
    CREATE OR REPLACE TABLE {BASELINE_OUTPUT_TABLE} AS
    WITH baseline_components AS (
        SELECT
            account_id,
            observation_month,
            observation_month_end,
            LEAST(
                30,
                CASE
                    WHEN COALESCE(usage_event_count_30d, 0) = 0 THEN 18
                    WHEN COALESCE(usage_event_count_30d, 0) < 3 THEN 12
                    WHEN COALESCE(usage_event_count_30d, 0) < 10 THEN 6
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(active_user_count_30d, 0) = 0 THEN 8
                    WHEN COALESCE(active_user_count_30d, 0) = 1 THEN 4
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(usage_event_count_90d, 0) > 0
                        AND COALESCE(usage_event_count_30d, 0) * 3
                            < COALESCE(usage_event_count_90d, 0)
                        THEN 4
                    ELSE 0
                END
            ) AS baseline_churn_component_usage_risk,
            LEAST(
                20,
                COALESCE(high_priority_ticket_count_90d, 0) * 4
                + COALESCE(open_ticket_count, 0) * 3
                + CASE
                    WHEN COALESCE(support_ticket_count_90d, 0) >= 5 THEN 5
                    WHEN COALESCE(support_ticket_count_90d, 0) >= 2 THEN 2
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(avg_resolution_hours_known, 0) > 72 THEN 5
                    WHEN COALESCE(avg_resolution_hours_known, 0) > 24 THEN 2
                    ELSE 0
                END
            ) AS baseline_churn_component_support_risk,
            LEAST(
                20,
                COALESCE(failed_invoice_count_90d, 0) * 6
                + COALESCE(unpaid_invoice_count_90d, 0) * 3
                + COALESCE(overdue_invoice_count, 0) * 4
                + CASE
                    WHEN COALESCE(avg_payment_delay_days_known, 0) > 14 THEN 4
                    WHEN COALESCE(avg_payment_delay_days_known, 0) > 7 THEN 2
                    ELSE 0
                END
            ) AS baseline_churn_component_billing_risk,
            LEAST(
                15,
                CASE
                    WHEN days_since_last_crm_touchpoint IS NULL THEN 8
                    WHEN days_since_last_crm_touchpoint > 90 THEN 8
                    WHEN days_since_last_crm_touchpoint > 45 THEN 5
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(cs_touchpoint_count_90d, 0) = 0 THEN 4
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(crm_touchpoint_count_90d, 0) = 0 THEN 3
                    ELSE 0
                END
            ) AS baseline_churn_component_relationship_risk,
            LEAST(
                15,
                CASE
                    WHEN current_plan = 'starter' THEN 5
                    WHEN current_plan = 'growth' THEN 2
                    ELSE 0
                END
                + CASE
                    WHEN current_billing_period = 'monthly' THEN 4
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(subscription_age_days, 0) < 90 THEN 3
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(current_mrr, 0) < 300 THEN 3
                    ELSE 0
                END
            ) AS baseline_churn_component_subscription_risk
            ,
            LEAST(
                35,
                CASE
                    WHEN COALESCE(usage_event_count_90d, 0) >= 300 THEN 18
                    WHEN COALESCE(usage_event_count_90d, 0) >= 100 THEN 12
                    WHEN COALESCE(usage_event_count_90d, 0) >= 25 THEN 6
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(active_user_count_90d, 0) >= 20 THEN 8
                    WHEN COALESCE(active_user_count_90d, 0) >= 5 THEN 4
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(usage_event_value_sum_90d, 0) >= 500 THEN 5
                    WHEN COALESCE(usage_event_value_sum_90d, 0) >= 100 THEN 2
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(usage_event_count_30d, 0) > 0
                        AND COALESCE(usage_event_count_30d, 0) * 3
                            >= COALESCE(usage_event_count_90d, 0)
                        THEN 4
                    ELSE 0
                END
            ) AS baseline_expansion_component_usage_strength,
            LEAST(
                20,
                CASE
                    WHEN current_plan IN ('starter', 'growth') THEN 6
                    WHEN current_plan = 'business' THEN 4
                    ELSE 1
                END
                + CASE
                    WHEN COALESCE(current_mrr, 0) >= 300
                        AND COALESCE(current_mrr, 0) < 2000 THEN 5
                    WHEN COALESCE(current_mrr, 0) >= 2000 THEN 3
                    ELSE 1
                END
                + CASE
                    WHEN segment IN ('mid_market', 'enterprise') THEN 4
                    ELSE 1
                END
                + CASE
                    WHEN current_billing_period = 'annual' THEN 2
                    ELSE 0
                END
                + CASE
                    WHEN company_size_band IN (
                        '201_1000',
                        '1001_5000',
                        '5001_plus'
                    ) THEN 3
                    ELSE 0
                END
            ) AS baseline_expansion_component_commercial_fit,
            LEAST(
                20,
                LEAST(COALESCE(sales_touchpoint_count_90d, 0) * 4, 8)
                + LEAST(COALESCE(cs_touchpoint_count_90d, 0) * 2, 6)
                + CASE
                    WHEN COALESCE(crm_touchpoint_count_30d, 0) > 0 THEN 3
                    ELSE 0
                END
                + CASE
                    WHEN days_since_last_crm_touchpoint IS NOT NULL
                        AND days_since_last_crm_touchpoint <= 30 THEN 3
                    ELSE 0
                END
            ) AS baseline_expansion_component_gtm_engagement,
            LEAST(
                15,
                CASE
                    WHEN COALESCE(failed_invoice_count_90d, 0) = 0
                        AND COALESCE(unpaid_invoice_count_90d, 0) = 0
                        AND COALESCE(overdue_invoice_count, 0) = 0 THEN 6
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(high_priority_ticket_count_90d, 0) = 0
                        AND COALESCE(open_ticket_count, 0) = 0 THEN 5
                    ELSE 0
                END
                + CASE
                    WHEN avg_resolution_hours_known IS NULL
                        OR avg_resolution_hours_known <= 24 THEN 2
                    ELSE 0
                END
                + CASE
                    WHEN avg_payment_delay_days_known IS NULL
                        OR avg_payment_delay_days_known <= 7 THEN 2
                    ELSE 0
                END
            ) AS baseline_expansion_component_low_friction,
            LEAST(
                10,
                CASE
                    WHEN COALESCE(subscription_age_days, 0) >= 90 THEN 4
                    ELSE 0
                END
                + CASE
                    WHEN COALESCE(account_age_days, 0) >= 180 THEN 3
                    ELSE 0
                END
                + CASE
                    WHEN current_plan != 'enterprise' THEN 3
                    ELSE 0
                END
            ) AS baseline_expansion_component_maturity
        FROM {BASELINE_SOURCE_TABLE}
    ),
    baseline_scores AS (
        SELECT
            account_id,
            observation_month,
            observation_month_end,
            baseline_churn_component_usage_risk,
            baseline_churn_component_support_risk,
            baseline_churn_component_billing_risk,
            baseline_churn_component_relationship_risk,
            baseline_churn_component_subscription_risk,
            ROUND(
                LEAST(
                    100,
                    GREATEST(
                        0,
                        baseline_churn_component_usage_risk
                        + baseline_churn_component_support_risk
                        + baseline_churn_component_billing_risk
                        + baseline_churn_component_relationship_risk
                        + baseline_churn_component_subscription_risk
                    )
                ),
                2
            ) AS baseline_churn_score,
            baseline_expansion_component_usage_strength,
            baseline_expansion_component_commercial_fit,
            baseline_expansion_component_gtm_engagement,
            baseline_expansion_component_low_friction,
            baseline_expansion_component_maturity,
            ROUND(
                LEAST(
                    100,
                    GREATEST(
                        0,
                        baseline_expansion_component_usage_strength
                        + baseline_expansion_component_commercial_fit
                        + baseline_expansion_component_gtm_engagement
                        + baseline_expansion_component_low_friction
                        + baseline_expansion_component_maturity
                    )
                ),
                2
            ) AS baseline_expansion_score
        FROM baseline_components
    )
    SELECT
        account_id,
        observation_month,
        observation_month_end,
        baseline_churn_component_usage_risk,
        baseline_churn_component_support_risk,
        baseline_churn_component_billing_risk,
        baseline_churn_component_relationship_risk,
        baseline_churn_component_subscription_risk,
        baseline_churn_score,
        baseline_expansion_component_usage_strength,
        baseline_expansion_component_commercial_fit,
        baseline_expansion_component_gtm_engagement,
        baseline_expansion_component_low_friction,
        baseline_expansion_component_maturity,
        baseline_expansion_score,
        RANK() OVER (
            PARTITION BY observation_month
            ORDER BY baseline_churn_score DESC, account_id
        ) AS baseline_churn_rank,
        RANK() OVER (
            PARTITION BY observation_month
            ORDER BY baseline_expansion_score DESC, account_id
        ) AS baseline_expansion_rank,
        NTILE(10) OVER (
            PARTITION BY observation_month
            ORDER BY baseline_churn_score DESC, account_id
        ) AS baseline_churn_decile,
        NTILE(10) OVER (
            PARTITION BY observation_month
            ORDER BY baseline_expansion_score DESC, account_id
        ) AS baseline_expansion_decile,
        ? AS baseline_version,
        ? AS baseline_created_at_utc
    FROM baseline_scores
    ORDER BY account_id, observation_month
    """
