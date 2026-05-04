"""Build the Package 3 account-month modelling table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

from account_health.warehouse import DEFAULT_DATABASE_PATH, METADATA_SCHEMA

MART_SCHEMA = "mart"
ACCOUNT_MONTH_TABLE = "account_month"
OUTPUT_TABLE = f"{MART_SCHEMA}.{ACCOUNT_MONTH_TABLE}"
FEATURE_BUILD_AUDIT_TABLE = "feature_build_audit"
FEATURE_BUILD_AUDIT_FULL_TABLE = f"{METADATA_SCHEMA}.{FEATURE_BUILD_AUDIT_TABLE}"


@dataclass(frozen=True)
class AccountMonthBuildResult:
    """Summary of one account-month table rebuild."""

    build_id: str
    database_path: Path
    output_table: str
    audit_table: str
    row_count: int
    account_count: int
    min_observation_month: date | None
    max_observation_month: date | None
    churn_eligible_count: int
    churn_positive_count: int
    expansion_eligible_count: int
    expansion_positive_count: int
    source_max_date: date | None


def build_account_month(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> AccountMonthBuildResult:
    """Rebuild the Package 3 account-month table in DuckDB."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {MART_SCHEMA}")
        connection.execute(_build_account_month_sql())
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {METADATA_SCHEMA}")
        connection.execute(_create_feature_build_audit_table_sql())

        (
            row_count,
            account_count,
            min_observation_month,
            max_observation_month,
            churn_eligible_count,
            churn_positive_count,
            expansion_eligible_count,
            expansion_positive_count,
        ) = connection.execute(_account_month_summary_sql()).fetchone()
        source_max_date = connection.execute(_source_max_date_sql()).fetchone()[0]
        build_id = uuid4().hex
        built_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat()

        connection.execute(
            f"""
            INSERT INTO {FEATURE_BUILD_AUDIT_FULL_TABLE}
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                build_id,
                built_at_utc,
                OUTPUT_TABLE,
                int(row_count),
                int(account_count),
                min_observation_month,
                max_observation_month,
                int(churn_eligible_count),
                int(churn_positive_count),
                int(expansion_eligible_count),
                int(expansion_positive_count),
                source_max_date,
            ],
        )

    return AccountMonthBuildResult(
        build_id=build_id,
        database_path=database_file,
        output_table=OUTPUT_TABLE,
        audit_table=FEATURE_BUILD_AUDIT_FULL_TABLE,
        row_count=int(row_count),
        account_count=int(account_count),
        min_observation_month=min_observation_month,
        max_observation_month=max_observation_month,
        churn_eligible_count=int(churn_eligible_count),
        churn_positive_count=int(churn_positive_count),
        expansion_eligible_count=int(expansion_eligible_count),
        expansion_positive_count=int(expansion_positive_count),
        source_max_date=source_max_date,
    )


def _account_month_summary_sql() -> str:
    return f"""
    SELECT
        COUNT(*) AS row_count,
        COUNT(DISTINCT account_id) AS account_count,
        MIN(observation_month) AS min_observation_month,
        MAX(observation_month) AS max_observation_month,
        COALESCE(
            SUM(CASE WHEN is_churn_label_eligible THEN 1 ELSE 0 END),
            0
        ) AS churn_eligible_count,
        COALESCE(
            SUM(CASE WHEN churn_90d = 1 THEN 1 ELSE 0 END),
            0
        ) AS churn_positive_count,
        COALESCE(
            SUM(CASE WHEN is_expansion_label_eligible THEN 1 ELSE 0 END),
            0
        ) AS expansion_eligible_count,
        COALESCE(
            SUM(CASE WHEN expansion_90d = 1 THEN 1 ELSE 0 END),
            0
        ) AS expansion_positive_count
    FROM {OUTPUT_TABLE}
    """


def _create_feature_build_audit_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {FEATURE_BUILD_AUDIT_FULL_TABLE} (
        build_id VARCHAR,
        built_at_utc VARCHAR,
        output_table VARCHAR,
        row_count BIGINT,
        account_count BIGINT,
        min_observation_month DATE,
        max_observation_month DATE,
        churn_eligible_count BIGINT,
        churn_positive_count BIGINT,
        expansion_eligible_count BIGINT,
        expansion_positive_count BIGINT,
        source_max_date DATE
    )
    """


def _source_max_date_sql() -> str:
    return """
    WITH source_dates AS (
        SELECT CAST(MAX(created_date) AS DATE) AS source_date FROM raw.accounts
        UNION ALL
        SELECT CAST(MAX(created_date) AS DATE) AS source_date FROM raw.users
        UNION ALL
        SELECT CAST(MAX(event_timestamp) AS DATE) AS source_date FROM raw.usage_events
        UNION ALL
        SELECT CAST(MAX(start_date) AS DATE) AS source_date FROM raw.subscriptions
        UNION ALL
        SELECT CAST(MAX(end_date) AS DATE) AS source_date FROM raw.subscriptions
        UNION ALL
        SELECT CAST(MAX(invoice_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(due_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(paid_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(created_at) AS DATE) AS source_date FROM raw.support_tickets
        UNION ALL
        SELECT CAST(MAX(resolved_at) AS DATE) AS source_date FROM raw.support_tickets
        UNION ALL
        SELECT CAST(MAX(touchpoint_date) AS DATE) AS source_date
        FROM raw.crm_touchpoints
        UNION ALL
        SELECT CAST(MAX(renewal_date) AS DATE) AS source_date FROM raw.renewals
    )
    SELECT CAST(MAX(source_date) AS DATE) AS source_max_date
    FROM source_dates
    WHERE source_date IS NOT NULL
    """


def _build_account_month_sql() -> str:
    return f"""
    CREATE OR REPLACE TABLE {OUTPUT_TABLE} AS
    WITH source_dates AS (
        SELECT CAST(MAX(created_date) AS DATE) AS source_date FROM raw.accounts
        UNION ALL
        SELECT CAST(MAX(created_date) AS DATE) AS source_date FROM raw.users
        UNION ALL
        SELECT CAST(MAX(event_timestamp) AS DATE) AS source_date FROM raw.usage_events
        UNION ALL
        SELECT CAST(MAX(start_date) AS DATE) AS source_date FROM raw.subscriptions
        UNION ALL
        SELECT CAST(MAX(end_date) AS DATE) AS source_date FROM raw.subscriptions
        UNION ALL
        SELECT CAST(MAX(invoice_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(due_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(paid_date) AS DATE) AS source_date FROM raw.invoices
        UNION ALL
        SELECT CAST(MAX(created_at) AS DATE) AS source_date FROM raw.support_tickets
        UNION ALL
        SELECT CAST(MAX(resolved_at) AS DATE) AS source_date FROM raw.support_tickets
        UNION ALL
        SELECT CAST(MAX(touchpoint_date) AS DATE) AS source_date
        FROM raw.crm_touchpoints
        UNION ALL
        SELECT CAST(MAX(renewal_date) AS DATE) AS source_date FROM raw.renewals
    ),
    bounds AS (
        SELECT
            CAST(DATE_TRUNC('month', MIN(CAST(created_date AS DATE))) AS DATE)
                AS first_observation_month,
            CAST(MAX(source_date) - INTERVAL '90 days' AS DATE)
                AS latest_observation_month_end
        FROM raw.accounts
        CROSS JOIN source_dates
        WHERE source_date IS NOT NULL
    ),
    observation_months AS (
        SELECT
            CAST(month_start AS DATE) AS observation_month,
            CAST(month_start + INTERVAL '1 month' - INTERVAL '1 day' AS DATE)
                AS observation_month_end
        FROM bounds
        CROSS JOIN generate_series(
            first_observation_month,
            CAST(DATE_TRUNC('month', latest_observation_month_end) AS DATE),
            INTERVAL '1 month'
        ) AS months(month_start)
    ),
    spine AS (
        SELECT
            accounts.account_id,
            months.observation_month,
            months.observation_month_end,
            TRUE AS is_churn_label_eligible,
            TRUE AS is_expansion_label_eligible,
            CAST(accounts.created_date AS DATE) AS account_created_date,
            DATE_DIFF(
                'day',
                CAST(accounts.created_date AS DATE),
                months.observation_month_end
            ) AS account_age_days
        FROM raw.accounts AS accounts
        CROSS JOIN observation_months AS months
        CROSS JOIN bounds
        WHERE accounts.account_id IS NOT NULL
            AND months.observation_month_end <= bounds.latest_observation_month_end
            AND CAST(accounts.created_date AS DATE) <= months.observation_month_end
            AND EXISTS (
                SELECT 1
                FROM raw.subscriptions AS subscriptions
                WHERE subscriptions.account_id = accounts.account_id
                    AND CAST(subscriptions.start_date AS DATE)
                        <= months.observation_month_end
                    AND (
                        subscriptions.end_date IS NULL
                        OR CAST(subscriptions.end_date AS DATE)
                            >= months.observation_month_end
                    )
            )
            AND NOT EXISTS (
                SELECT 1
                FROM raw.renewals AS renewals
                WHERE renewals.account_id = accounts.account_id
                    AND CAST(renewals.renewal_date AS DATE)
                        <= months.observation_month_end
                    AND renewals.outcome = 'churned'
            )
    ),
    eligible_spine AS (
        SELECT *
        FROM spine
        WHERE account_age_days >= 30
    ),
    label_flags AS (
        SELECT
            eligible_spine.*,
            EXISTS (
                SELECT 1
                FROM raw.renewals AS renewals
                WHERE renewals.account_id = eligible_spine.account_id
                    AND CAST(renewals.renewal_date AS DATE)
                        > eligible_spine.observation_month_end
                    AND CAST(renewals.renewal_date AS DATE)
                        <= eligible_spine.observation_month_end + INTERVAL '90 days'
                    AND renewals.outcome = 'churned'
            ) AS churn_in_horizon,
            EXISTS (
                SELECT 1
                FROM raw.renewals AS renewals
                WHERE renewals.account_id = eligible_spine.account_id
                    AND CAST(renewals.renewal_date AS DATE)
                        > eligible_spine.observation_month_end
                    AND CAST(renewals.renewal_date AS DATE)
                        <= eligible_spine.observation_month_end + INTERVAL '90 days'
                    AND renewals.outcome = 'renewed_expanded'
                    AND renewals.new_mrr > renewals.previous_mrr
            ) AS expansion_in_horizon
        FROM eligible_spine
    ),
    labels AS (
        SELECT
            account_id,
            observation_month,
            observation_month_end,
            is_churn_label_eligible,
            NOT churn_in_horizon AS is_expansion_label_eligible,
            account_created_date,
            account_age_days,
            CASE
                WHEN churn_in_horizon THEN 1
                ELSE 0
            END AS churn_90d,
            CASE
                WHEN churn_in_horizon THEN NULL
                WHEN expansion_in_horizon THEN 1
                ELSE 0
            END AS expansion_90d
        FROM label_flags
    )
    SELECT
        labels.account_id,
        labels.observation_month,
        labels.observation_month_end,
        labels.is_churn_label_eligible,
        labels.is_expansion_label_eligible,
        labels.churn_90d,
        labels.expansion_90d,
        labels.account_created_date,
        labels.account_age_days,
        accounts.industry,
        accounts.region,
        accounts.segment,
        accounts.company_size_band,
        accounts.acquisition_channel,
        (
            SELECT subscriptions.plan
            FROM raw.subscriptions AS subscriptions
            WHERE subscriptions.account_id = labels.account_id
                AND CAST(subscriptions.start_date AS DATE)
                    <= labels.observation_month_end
                AND (
                    subscriptions.end_date IS NULL
                    OR CAST(subscriptions.end_date AS DATE)
                        >= labels.observation_month_end
                )
            ORDER BY CAST(subscriptions.start_date AS DATE) DESC,
                subscriptions.subscription_id DESC
            LIMIT 1
        ) AS current_plan,
        (
            SELECT subscriptions.mrr
            FROM raw.subscriptions AS subscriptions
            WHERE subscriptions.account_id = labels.account_id
                AND CAST(subscriptions.start_date AS DATE)
                    <= labels.observation_month_end
                AND (
                    subscriptions.end_date IS NULL
                    OR CAST(subscriptions.end_date AS DATE)
                        >= labels.observation_month_end
                )
            ORDER BY CAST(subscriptions.start_date AS DATE) DESC,
                subscriptions.subscription_id DESC
            LIMIT 1
        ) AS current_mrr,
        (
            SELECT subscriptions.billing_period
            FROM raw.subscriptions AS subscriptions
            WHERE subscriptions.account_id = labels.account_id
                AND CAST(subscriptions.start_date AS DATE)
                    <= labels.observation_month_end
                AND (
                    subscriptions.end_date IS NULL
                    OR CAST(subscriptions.end_date AS DATE)
                        >= labels.observation_month_end
                )
            ORDER BY CAST(subscriptions.start_date AS DATE) DESC,
                subscriptions.subscription_id DESC
            LIMIT 1
        ) AS current_billing_period,
        (
            SELECT DATE_DIFF(
                'day',
                CAST(subscriptions.start_date AS DATE),
                labels.observation_month_end
            )
            FROM raw.subscriptions AS subscriptions
            WHERE subscriptions.account_id = labels.account_id
                AND CAST(subscriptions.start_date AS DATE)
                    <= labels.observation_month_end
                AND (
                    subscriptions.end_date IS NULL
                    OR CAST(subscriptions.end_date AS DATE)
                        >= labels.observation_month_end
                )
            ORDER BY CAST(subscriptions.start_date AS DATE) DESC,
                subscriptions.subscription_id DESC
            LIMIT 1
        ) AS subscription_age_days,
        (
            SELECT COUNT(*)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '30 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS usage_event_count_30d,
        (
            SELECT COUNT(*)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS usage_event_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS usage_event_count_180d,
        (
            SELECT COUNT(DISTINCT usage_events.user_id)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '30 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS active_user_count_30d,
        (
            SELECT COUNT(DISTINCT usage_events.user_id)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS active_user_count_90d,
        (
            SELECT COUNT(DISTINCT usage_events.user_id)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS active_user_count_180d,
        (
            SELECT COALESCE(SUM(usage_events.event_value), 0)
            FROM raw.usage_events AS usage_events
            WHERE usage_events.account_id = labels.account_id
                AND CAST(usage_events.event_timestamp AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(usage_events.event_timestamp AS DATE)
                    <= labels.observation_month_end
        ) AS usage_event_value_sum_90d,
        (
            SELECT COUNT(*)
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    > labels.observation_month_end - INTERVAL '30 days'
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
        ) AS support_ticket_count_30d,
        (
            SELECT COUNT(*)
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
        ) AS support_ticket_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
        ) AS support_ticket_count_180d,
        (
            SELECT COUNT(*)
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
                AND support_tickets.priority IN ('high', 'urgent')
        ) AS high_priority_ticket_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
                AND (
                    support_tickets.resolved_at IS NULL
                    OR CAST(support_tickets.resolved_at AS DATE)
                        > labels.observation_month_end
                )
        ) AS open_ticket_count,
        (
            SELECT AVG(DATE_DIFF(
                'hour',
                CAST(support_tickets.created_at AS TIMESTAMP),
                CAST(support_tickets.resolved_at AS TIMESTAMP)
            ))
            FROM raw.support_tickets AS support_tickets
            WHERE support_tickets.account_id = labels.account_id
                AND CAST(support_tickets.created_at AS DATE)
                    <= labels.observation_month_end
                AND support_tickets.resolved_at IS NOT NULL
                AND CAST(support_tickets.resolved_at AS DATE)
                    <= labels.observation_month_end
        ) AS avg_resolution_hours_known,
        DATE_DIFF(
            'day',
            (
                SELECT MAX(CAST(support_tickets.created_at AS DATE))
                FROM raw.support_tickets AS support_tickets
                WHERE support_tickets.account_id = labels.account_id
                    AND CAST(support_tickets.created_at AS DATE)
                        <= labels.observation_month_end
            ),
            labels.observation_month_end
        ) AS days_since_last_ticket,
        (
            SELECT COUNT(*)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
        ) AS invoice_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
        ) AS invoice_count_180d,
        (
            SELECT COALESCE(SUM(invoices.amount), 0)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
        ) AS invoice_amount_sum_90d,
        (
            SELECT COALESCE(SUM(invoices.amount), 0)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
        ) AS invoice_amount_sum_180d,
        (
            SELECT COUNT(*)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
                AND invoices.status != 'void'
                AND (
                    invoices.paid_date IS NULL
                    OR CAST(invoices.paid_date AS DATE)
                        > labels.observation_month_end
                )
        ) AS unpaid_invoice_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
                AND invoices.status = 'failed'
        ) AS failed_invoice_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND CAST(invoices.invoice_date AS DATE)
                    <= labels.observation_month_end
                AND CAST(invoices.due_date AS DATE)
                    <= labels.observation_month_end
                AND invoices.status != 'void'
                AND (
                    invoices.paid_date IS NULL
                    OR CAST(invoices.paid_date AS DATE)
                        > labels.observation_month_end
                )
        ) AS overdue_invoice_count,
        (
            SELECT AVG(DATE_DIFF(
                'day',
                CAST(invoices.invoice_date AS DATE),
                CAST(invoices.paid_date AS DATE)
            ))
            FROM raw.invoices AS invoices
            WHERE invoices.account_id = labels.account_id
                AND invoices.paid_date IS NOT NULL
                AND CAST(invoices.paid_date AS DATE)
                    <= labels.observation_month_end
        ) AS avg_payment_delay_days_known,
        DATE_DIFF(
            'day',
            (
                SELECT MAX(CAST(invoices.invoice_date AS DATE))
                FROM raw.invoices AS invoices
                WHERE invoices.account_id = labels.account_id
                    AND CAST(invoices.invoice_date AS DATE)
                        <= labels.observation_month_end
            ),
            labels.observation_month_end
        ) AS days_since_last_invoice,
        (
            SELECT COUNT(*)
            FROM raw.crm_touchpoints AS crm_touchpoints
            WHERE crm_touchpoints.account_id = labels.account_id
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    > labels.observation_month_end - INTERVAL '30 days'
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    <= labels.observation_month_end
        ) AS crm_touchpoint_count_30d,
        (
            SELECT COUNT(*)
            FROM raw.crm_touchpoints AS crm_touchpoints
            WHERE crm_touchpoints.account_id = labels.account_id
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    <= labels.observation_month_end
        ) AS crm_touchpoint_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.crm_touchpoints AS crm_touchpoints
            WHERE crm_touchpoints.account_id = labels.account_id
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    > labels.observation_month_end - INTERVAL '180 days'
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    <= labels.observation_month_end
        ) AS crm_touchpoint_count_180d,
        (
            SELECT COUNT(*)
            FROM raw.crm_touchpoints AS crm_touchpoints
            WHERE crm_touchpoints.account_id = labels.account_id
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    <= labels.observation_month_end
                AND crm_touchpoints.team = 'sales'
        ) AS sales_touchpoint_count_90d,
        (
            SELECT COUNT(*)
            FROM raw.crm_touchpoints AS crm_touchpoints
            WHERE crm_touchpoints.account_id = labels.account_id
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    > labels.observation_month_end - INTERVAL '90 days'
                AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                    <= labels.observation_month_end
                AND crm_touchpoints.team = 'customer_success'
        ) AS cs_touchpoint_count_90d,
        DATE_DIFF(
            'day',
            (
                SELECT MAX(CAST(crm_touchpoints.touchpoint_date AS DATE))
                FROM raw.crm_touchpoints AS crm_touchpoints
                WHERE crm_touchpoints.account_id = labels.account_id
                    AND CAST(crm_touchpoints.touchpoint_date AS DATE)
                        <= labels.observation_month_end
            ),
            labels.observation_month_end
        ) AS days_since_last_crm_touchpoint
    FROM labels
    INNER JOIN raw.accounts AS accounts
        ON accounts.account_id = labels.account_id
    ORDER BY labels.account_id, labels.observation_month
    """
