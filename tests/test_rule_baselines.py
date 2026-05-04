from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.baselines import (
    BaselineInputContractError,
    build_account_month_baselines,
)

ROOT = Path(__file__).resolve().parents[1]


def account_month_baseline_source_frame(
    *,
    churn_label: int = 0,
    expansion_label: int = 0,
) -> pd.DataFrame:
    rows = [
        {
            "account_id": "acct_high_churn",
            "observation_month": pd.Timestamp("2024-06-01"),
            "observation_month_end": pd.Timestamp("2024-06-30"),
            "is_churn_label_eligible": True,
            "is_expansion_label_eligible": True,
            "churn_90d": churn_label,
            "expansion_90d": expansion_label,
            "account_created_date": pd.Timestamp("2024-01-01"),
            "account_age_days": 181,
            "industry": "software",
            "region": "north_america",
            "segment": "smb",
            "company_size_band": "1_50",
            "acquisition_channel": "inbound",
            "current_plan": "starter",
            "current_mrr": 250.0,
            "current_billing_period": "monthly",
            "subscription_age_days": 60,
            "usage_event_count_30d": 0,
            "usage_event_count_90d": 30,
            "usage_event_count_180d": 90,
            "active_user_count_30d": 0,
            "active_user_count_90d": 3,
            "active_user_count_180d": 5,
            "usage_event_value_sum_90d": 30.0,
            "support_ticket_count_30d": 3,
            "support_ticket_count_90d": 6,
            "support_ticket_count_180d": 8,
            "high_priority_ticket_count_90d": 3,
            "open_ticket_count": 2,
            "avg_resolution_hours_known": 96.0,
            "days_since_last_ticket": 2,
            "invoice_count_90d": 3,
            "invoice_count_180d": 6,
            "invoice_amount_sum_90d": 750.0,
            "invoice_amount_sum_180d": 1500.0,
            "unpaid_invoice_count_90d": 2,
            "failed_invoice_count_90d": 1,
            "overdue_invoice_count": 2,
            "avg_payment_delay_days_known": 20.0,
            "days_since_last_invoice": 10,
            "crm_touchpoint_count_30d": 0,
            "crm_touchpoint_count_90d": 0,
            "crm_touchpoint_count_180d": 1,
            "sales_touchpoint_count_90d": 0,
            "cs_touchpoint_count_90d": 0,
            "days_since_last_crm_touchpoint": pd.NA,
        },
        {
            "account_id": "acct_low_churn",
            "observation_month": pd.Timestamp("2024-06-01"),
            "observation_month_end": pd.Timestamp("2024-06-30"),
            "is_churn_label_eligible": True,
            "is_expansion_label_eligible": True,
            "churn_90d": 1 - churn_label,
            "expansion_90d": 1 - expansion_label,
            "account_created_date": pd.Timestamp("2023-01-01"),
            "account_age_days": 546,
            "industry": "software",
            "region": "north_america",
            "segment": "enterprise",
            "company_size_band": "1001_5000",
            "acquisition_channel": "partner",
            "current_plan": "enterprise",
            "current_mrr": 5000.0,
            "current_billing_period": "annual",
            "subscription_age_days": 365,
            "usage_event_count_30d": 120,
            "usage_event_count_90d": 300,
            "usage_event_count_180d": 650,
            "active_user_count_30d": 50,
            "active_user_count_90d": 75,
            "active_user_count_180d": 90,
            "usage_event_value_sum_90d": 800.0,
            "support_ticket_count_30d": 0,
            "support_ticket_count_90d": 1,
            "support_ticket_count_180d": 2,
            "high_priority_ticket_count_90d": 0,
            "open_ticket_count": 0,
            "avg_resolution_hours_known": 8.0,
            "days_since_last_ticket": 60,
            "invoice_count_90d": 3,
            "invoice_count_180d": 6,
            "invoice_amount_sum_90d": 15000.0,
            "invoice_amount_sum_180d": 30000.0,
            "unpaid_invoice_count_90d": 0,
            "failed_invoice_count_90d": 0,
            "overdue_invoice_count": 0,
            "avg_payment_delay_days_known": 2.0,
            "days_since_last_invoice": 10,
            "crm_touchpoint_count_30d": 2,
            "crm_touchpoint_count_90d": 5,
            "crm_touchpoint_count_180d": 8,
            "sales_touchpoint_count_90d": 2,
            "cs_touchpoint_count_90d": 3,
            "days_since_last_crm_touchpoint": 5,
        },
    ]
    return pd.DataFrame(rows)


def multi_month_account_month_baseline_source_frame() -> pd.DataFrame:
    first_month = account_month_baseline_source_frame()
    second_month = first_month.copy(deep=True)
    second_month["observation_month"] = pd.Timestamp("2024-07-01")
    second_month["observation_month_end"] = pd.Timestamp("2024-07-31")
    return pd.concat([first_month, second_month], ignore_index=True)


def create_account_month_source(database_path: Path, frame: pd.DataFrame) -> None:
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA mart")
        connection.register("account_month_frame", frame)
        try:
            connection.execute(
                """
                CREATE TABLE mart.account_month AS
                SELECT * FROM account_month_frame
                """
            )
        finally:
            connection.unregister("account_month_frame")


def table_exists(database_path: Path, schema_name: str, table_name: str) -> bool:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return bool(
            connection.execute(
                """
                SELECT COUNT(*) > 0
                FROM information_schema.tables
                WHERE table_schema = ?
                    AND table_name = ?
                """,
                [schema_name, table_name],
            ).fetchone()[0]
        )


def account_month_frame(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT *
            FROM mart.account_month
            ORDER BY account_id, observation_month
            """
        ).fetchdf()


def baseline_frame(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT *
            FROM mart.account_month_baselines
            ORDER BY account_id, observation_month
            """
        ).fetchdf()


def baseline_build_audit_frame(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT *
            FROM metadata.baseline_build_audit
            ORDER BY built_at_utc, build_id
            """
        ).fetchdf()


def baseline_score_columns(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if column.startswith("baseline_churn_component_")
        or column.startswith("baseline_expansion_component_")
        or column
        in {
            "baseline_churn_score",
            "baseline_expansion_score",
        }
    ]


def baseline_component_columns(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if column.startswith("baseline_churn_component_")
        or column.startswith("baseline_expansion_component_")
    ]


def test_build_churn_baseline_creates_bounded_score_and_components(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    result = build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    assert result.output_table == "mart.account_month_baselines"
    assert result.row_count == 2
    assert result.audit_table == "metadata.baseline_build_audit"
    assert len(frame) == 2
    assert frame["baseline_churn_score"].between(0, 100).all()

    component_columns = [
        column
        for column in frame.columns
        if column.startswith("baseline_churn_component_")
    ]
    assert component_columns == [
        "baseline_churn_component_usage_risk",
        "baseline_churn_component_support_risk",
        "baseline_churn_component_billing_risk",
        "baseline_churn_component_relationship_risk",
        "baseline_churn_component_subscription_risk",
    ]
    assert (frame[component_columns] >= 0).all().all()

    high_score = frame.loc[
        frame["account_id"] == "acct_high_churn",
        "baseline_churn_score",
    ].iloc[0]
    low_score = frame.loc[
        frame["account_id"] == "acct_low_churn",
        "baseline_churn_score",
    ].iloc[0]
    assert high_score > low_score


def test_build_expansion_baseline_creates_bounded_score_and_components(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    assert frame["baseline_expansion_score"].between(0, 100).all()
    component_columns = [
        column
        for column in frame.columns
        if column.startswith("baseline_expansion_component_")
    ]
    assert component_columns == [
        "baseline_expansion_component_usage_strength",
        "baseline_expansion_component_commercial_fit",
        "baseline_expansion_component_gtm_engagement",
        "baseline_expansion_component_low_friction",
        "baseline_expansion_component_maturity",
    ]
    assert (frame[component_columns] >= 0).all().all()

    high_score = frame.loc[
        frame["account_id"] == "acct_low_churn",
        "baseline_expansion_score",
    ].iloc[0]
    low_score = frame.loc[
        frame["account_id"] == "acct_high_churn",
        "baseline_expansion_score",
    ].iloc[0]
    assert high_score > low_score


def test_baseline_output_preserves_source_row_parity_and_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    source = account_month_baseline_source_frame()
    create_account_month_source(database_path, source)

    build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    assert len(frame) == len(source)
    assert not frame.duplicated(["account_id", "observation_month"]).any()
    assert set(frame["account_id"]) == set(source["account_id"])
    assert set(frame["observation_month"]) == set(source["observation_month"])
    assert "churn_90d" not in frame.columns
    assert "expansion_90d" not in frame.columns
    assert "synthetic_archetype" not in frame.columns
    assert "account_health_band" not in frame.columns
    assert "recommended_gtm_action" not in frame.columns


def test_baseline_output_has_prioritisation_helpers_not_policy(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    helper_columns = {
        "baseline_churn_rank",
        "baseline_expansion_rank",
        "baseline_churn_decile",
        "baseline_expansion_decile",
    }
    assert helper_columns <= set(frame.columns)
    assert frame["baseline_churn_rank"].min() == 1
    assert frame["baseline_expansion_rank"].min() == 1
    assert frame["baseline_churn_decile"].between(1, 10).all()
    assert frame["baseline_expansion_decile"].between(1, 10).all()


def test_baseline_prioritisation_helpers_reset_by_observation_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(
        database_path,
        multi_month_account_month_baseline_source_frame(),
    )

    build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    for _, month_frame in frame.groupby("observation_month"):
        assert set(month_frame["baseline_churn_rank"]) == {1, 2}
        assert set(month_frame["baseline_expansion_rank"]) == {1, 2}
        assert set(month_frame["baseline_churn_decile"]) == {1, 2}
        assert set(month_frame["baseline_expansion_decile"]) == {1, 2}

    high_churn_rows = frame[frame["account_id"] == "acct_high_churn"]
    low_churn_rows = frame[frame["account_id"] == "acct_low_churn"]
    assert set(high_churn_rows["baseline_churn_rank"]) == {1}
    assert set(low_churn_rows["baseline_churn_rank"]) == {2}
    assert set(low_churn_rows["baseline_expansion_rank"]) == {1}
    assert set(high_churn_rows["baseline_expansion_rank"]) == {2}


def test_churn_baseline_is_deterministic(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    build_account_month_baselines(database_path)
    first_frame = baseline_frame(database_path)
    build_account_month_baselines(database_path)
    second_frame = baseline_frame(database_path)

    deterministic_columns = [
        column
        for column in first_frame.columns
        if column != "baseline_created_at_utc"
    ]
    pd.testing.assert_frame_equal(
        first_frame[deterministic_columns],
        second_frame[deterministic_columns],
    )


def test_rule_baselines_do_not_use_label_columns(tmp_path: Path) -> None:
    first_database_path = tmp_path / "first.duckdb"
    second_database_path = tmp_path / "second.duckdb"
    create_account_month_source(
        first_database_path,
        account_month_baseline_source_frame(churn_label=0, expansion_label=0),
    )
    create_account_month_source(
        second_database_path,
        account_month_baseline_source_frame(churn_label=1, expansion_label=1),
    )

    build_account_month_baselines(first_database_path)
    build_account_month_baselines(second_database_path)

    first_frame = baseline_frame(first_database_path)
    second_frame = baseline_frame(second_database_path)
    pd.testing.assert_frame_equal(
        first_frame[baseline_score_columns(first_frame)],
        second_frame[baseline_score_columns(second_frame)],
    )


def test_build_rule_baselines_rejects_duplicate_input_grain(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    source = account_month_baseline_source_frame()
    duplicated_source = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    create_account_month_source(database_path, duplicated_source)

    with pytest.raises(
        BaselineInputContractError,
        match="duplicate account-month grain",
    ):
        build_account_month_baselines(database_path)

    assert not table_exists(database_path, "mart", "account_month_baselines")


def test_build_rule_baselines_rejects_missing_account_month_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"

    with pytest.raises(
        BaselineInputContractError,
        match="mart.account_month does not exist",
    ):
        build_account_month_baselines(database_path)

    assert not table_exists(database_path, "mart", "account_month_baselines")


def test_build_rule_baselines_does_not_mutate_account_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())
    before = account_month_frame(database_path)

    build_account_month_baselines(database_path)
    after = account_month_frame(database_path)

    pd.testing.assert_frame_equal(before, after)


def test_baseline_component_columns_are_complete(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)

    assert baseline_component_columns(frame) == [
        "baseline_churn_component_usage_risk",
        "baseline_churn_component_support_risk",
        "baseline_churn_component_billing_risk",
        "baseline_churn_component_relationship_risk",
        "baseline_churn_component_subscription_risk",
        "baseline_expansion_component_usage_strength",
        "baseline_expansion_component_commercial_fit",
        "baseline_expansion_component_gtm_engagement",
        "baseline_expansion_component_low_friction",
        "baseline_expansion_component_maturity",
    ]


def test_build_rule_baselines_records_minimal_audit(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    result = build_account_month_baselines(database_path)
    frame = baseline_frame(database_path)
    audit = baseline_build_audit_frame(database_path)
    audit_row = audit.iloc[0]

    assert len(audit) == 1
    assert audit_row["build_id"] == result.build_id
    assert audit_row["source_table"] == "mart.account_month"
    assert audit_row["output_table"] == "mart.account_month_baselines"
    assert audit_row["baseline_version"] == "rule_baseline_v1"
    assert audit_row["row_count"] == len(frame)
    assert audit_row["row_count"] == result.row_count
    assert audit_row["account_count"] == result.account_count
    assert audit_row["status"] == "success"
    assert set(frame["baseline_version"]) == {"rule_baseline_v1"}
    assert frame["baseline_created_at_utc"].notna().all()
    assert set(frame["baseline_created_at_utc"]) == {audit_row["built_at_utc"]}


def test_build_rule_baselines_cli_uses_explicit_database_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_rule_baselines.py",
            "--database-path",
            str(database_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "source_table: mart.account_month" in result.stdout
    assert "output_table: mart.account_month_baselines" in result.stdout
    assert "audit_table: metadata.baseline_build_audit" in result.stdout
    assert len(baseline_frame(database_path)) == 2
    assert len(baseline_build_audit_frame(database_path)) == 1


def test_build_rule_baselines_make_target_uses_warehouse_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_account_month_source(database_path, account_month_baseline_source_frame())

    result = subprocess.run(
        [
            "make",
            "build-rule-baselines",
            f"WAREHOUSE_PATH={database_path}",
            f"PYTHON={sys.executable}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "output_table: mart.account_month_baselines" in result.stdout
    assert len(baseline_frame(database_path)) == 2
    assert len(baseline_build_audit_frame(database_path)) == 1
