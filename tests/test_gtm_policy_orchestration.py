from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.gtm_policy import (
    GTMPolicyError,
    GTM_POLICY_AUDIT_TABLE,
    GTM_POLICY_OUTPUT_TABLE,
    run_gtm_policy,
    write_gtm_policy_tables,
)
from test_gtm_policy_outputs import create_gtm_policy_tables


def test_run_gtm_policy_writes_policy_rows_and_audit(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)

    result = run_gtm_policy(database_path, scoring_month="2024-02-01")

    assert result.status == "success"
    assert result.input_score_row_count == 2
    assert result.output_policy_row_count == 2
    assert result.observability_status == "not_used"
    assert result.output_paths == {
        "policy_table": GTM_POLICY_OUTPUT_TABLE,
        "audit_table": GTM_POLICY_AUDIT_TABLE,
    }

    with duckdb.connect(str(database_path), read_only=True) as connection:
        policy_rows = connection.execute(
            """
            SELECT account_id, scoring_month, action_reason_code
            FROM mart.account_month_gtm_policy
            ORDER BY account_id
            """
        ).fetchall()
        audit_rows = connection.execute(
            """
            SELECT
                policy_version,
                scoring_month,
                input_score_row_count,
                output_policy_row_count,
                health_band_counts_json,
                recommended_action_counts_json,
                priority_counts_json,
                observability_status,
                status
            FROM metadata.gtm_policy_audit
            """
        ).fetchall()

    assert policy_rows == [
        (
            "acct_one",
            pd.Timestamp("2024-02-01").date(),
            "LOW_CHURN_HIGH_EXPANSION",
        ),
        (
            "acct_two",
            pd.Timestamp("2024-02-01").date(),
            "MEDIUM_CHURN_RISK_REVIEW",
        ),
    ]
    assert audit_rows == [
        (
            "gtm_policy_v1",
            pd.Timestamp("2024-02-01").date(),
            2,
            2,
            '{"Critical": 0, "At Risk": 1, "Stable": 0, "Growth Ready": 1}',
            '{"Executive save plan before expansion": 0, "Immediate retention intervention": 0, "Resolve risks before expansion outreach": 0, "Customer success risk review": 1, "Prioritise expansion outreach": 1, "Nurture for future expansion": 0, "Monitor in standard cadence": 0}',
            '{"P1": 1, "P2": 1, "P3": 0}',
            "not_used",
            "success",
        )
    ]


def test_run_gtm_policy_replaces_selected_month_and_appends_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)

    first = run_gtm_policy(database_path, scoring_month="2024-02-01")
    second = run_gtm_policy(database_path, scoring_month="2024-02-01")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        policy_summary = connection.execute(
            """
            SELECT COUNT(*)
            FROM mart.account_month_gtm_policy
            WHERE scoring_month = DATE '2024-02-01'
            """
        ).fetchone()
        audit_summary = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT run_id)
            FROM metadata.gtm_policy_audit
            """
        ).fetchone()

    assert first.run_id != second.run_id
    assert policy_summary == (2,)
    assert audit_summary == (2, 2)


def test_write_gtm_policy_tables_rolls_back_month_replace_when_audit_fails(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    result = run_gtm_policy(
        database_path,
        scoring_month="2024-02-01",
        write_tables=False,
    )

    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS metadata")
        connection.execute(
            """
            CREATE TABLE mart.account_month_gtm_policy (
                account_id VARCHAR,
                scoring_month DATE,
                churn_score DOUBLE,
                expansion_score DOUBLE,
                health_band VARCHAR,
                lifecycle_motion VARCHAR,
                recommended_action VARCHAR,
                action_priority VARCHAR,
                action_reason_code VARCHAR,
                policy_version VARCHAR,
                created_at_utc VARCHAR,
                scoring_run_id VARCHAR,
                churn_registered_model_name VARCHAR,
                churn_model_version VARCHAR,
                expansion_registered_model_name VARCHAR,
                expansion_model_version VARCHAR,
                scored_at_utc VARCHAR,
                scoring_version VARCHAR,
                current_plan VARCHAR,
                company_size_band VARCHAR,
                region VARCHAR,
                industry VARCHAR,
                current_mrr DOUBLE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO mart.account_month_gtm_policy
            VALUES (
                'acct_old',
                DATE '2024-02-01',
                0.1,
                0.2,
                'Stable',
                'Maintain',
                'Monitor in standard cadence',
                'P3',
                'LOW_CHURN_LOW_EXPANSION_MAINTAIN',
                'gtm_policy_v1',
                '2024-03-01T00:00:00+00:00',
                'old_run',
                'account_health_churn_model',
                '1',
                'account_health_expansion_model',
                '2',
                '2024-03-01T00:00:00+00:00',
                'package_8_batch_scoring_v1',
                'starter',
                '1_50',
                'europe',
                'software',
                100.0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE metadata.gtm_policy_audit (
                run_id VARCHAR
            )
            """
        )

    with pytest.raises(duckdb.BinderException):
        write_gtm_policy_tables(database_path, result=result)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        policy_rows = connection.execute(
            """
            SELECT account_id, scoring_run_id
            FROM mart.account_month_gtm_policy
            WHERE scoring_month = DATE '2024-02-01'
            """
        ).fetchall()

    assert policy_rows == [("acct_old", "old_run")]


def test_run_gtm_policy_records_failed_audit_when_safe(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            """
            UPDATE mart.account_month_scores
            SET churn_score = 1.5
            WHERE observation_month = DATE '2024-02-01'
              AND account_id = 'acct_two'
            """
        )

    with pytest.raises(GTMPolicyError, match=r"\[0, 1\]"):
        run_gtm_policy(database_path, scoring_month="2024-02-01")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        audit_rows = connection.execute(
            """
            SELECT status, failure_codes_json, failure_reason
            FROM metadata.gtm_policy_audit
            """
        ).fetchall()

    assert len(audit_rows) == 1
    assert audit_rows[0][:2] == ("failed", '["gtm_policy_failed"]')
    assert "[0, 1]" in audit_rows[0][2]


def test_run_gtm_policy_failed_run_preserves_existing_policy_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    run_gtm_policy(database_path, scoring_month="2024-02-01")

    with duckdb.connect(str(database_path)) as connection:
        before = connection.execute(
            """
            SELECT account_id, action_reason_code
            FROM mart.account_month_gtm_policy
            WHERE scoring_month = DATE '2024-02-01'
            ORDER BY account_id
            """
        ).fetchall()
        connection.execute(
            """
            UPDATE mart.account_month_scores
            SET churn_score = 1.5
            WHERE observation_month = DATE '2024-02-01'
              AND account_id = 'acct_two'
            """
        )

    with pytest.raises(GTMPolicyError, match=r"\[0, 1\]"):
        run_gtm_policy(database_path, scoring_month="2024-02-01")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        after = connection.execute(
            """
            SELECT account_id, action_reason_code
            FROM mart.account_month_gtm_policy
            WHERE scoring_month = DATE '2024-02-01'
            ORDER BY account_id
            """
        ).fetchall()
        audit_statuses = connection.execute(
            """
            SELECT status
            FROM metadata.gtm_policy_audit
            """
        ).fetchall()

    assert after == before
    assert sorted(audit_statuses) == [("failed",), ("success",)]


def test_run_gtm_policy_preserves_package_8_and_9_outputs(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS metadata")
        connection.execute(
            """
            CREATE TABLE metadata.batch_scoring_audit AS
            SELECT
                'run_feb'::VARCHAR AS scoring_run_id,
                DATE '2024-02-01' AS scoring_month,
                'success'::VARCHAR AS status
            """
        )
        connection.execute(
            """
            CREATE TABLE metadata.score_observability_audit AS
            SELECT
                'obs_feb'::VARCHAR AS observability_run_id,
                DATE '2024-02-01' AS scoring_month,
                'success'::VARCHAR AS status
            """
        )
        connection.execute(
            """
            CREATE TABLE mart.score_observability_summary AS
            SELECT
                DATE '2024-02-01' AS scoring_month,
                'success'::VARCHAR AS status
            """
        )
        before = {
            "scores": connection.execute(
                """
                SELECT *
                FROM mart.account_month_scores
                ORDER BY account_id, observation_month
                """
            ).fetchall(),
            "batch_audit": connection.execute(
                "SELECT * FROM metadata.batch_scoring_audit"
            ).fetchall(),
            "observability_audit": connection.execute(
                "SELECT * FROM metadata.score_observability_audit"
            ).fetchall(),
            "observability_summary": connection.execute(
                "SELECT * FROM mart.score_observability_summary"
            ).fetchall(),
        }

    run_gtm_policy(database_path, scoring_month="2024-02-01")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        after = {
            "scores": connection.execute(
                """
                SELECT *
                FROM mart.account_month_scores
                ORDER BY account_id, observation_month
                """
            ).fetchall(),
            "batch_audit": connection.execute(
                "SELECT * FROM metadata.batch_scoring_audit"
            ).fetchall(),
            "observability_audit": connection.execute(
                "SELECT * FROM metadata.score_observability_audit"
            ).fetchall(),
            "observability_summary": connection.execute(
                "SELECT * FROM mart.score_observability_summary"
            ).fetchall(),
        }

    assert after == before
