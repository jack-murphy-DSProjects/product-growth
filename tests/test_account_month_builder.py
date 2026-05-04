from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

from account_health.features import build_account_month
from account_health.synthetic import SOURCE_TABLES

ROOT = Path(__file__).resolve().parents[1]


def create_raw_warehouse(
    database_path: Path,
    tables: dict[str, pd.DataFrame],
) -> None:
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA raw")
        for table_name in SOURCE_TABLES:
            relation_name = f"{table_name}_frame"
            connection.register(relation_name, tables[table_name])
            try:
                connection.execute(
                    f"CREATE TABLE raw.{table_name} AS SELECT * FROM {relation_name}"
                )
            finally:
                connection.unregister(relation_name)


def base_source_tables() -> dict[str, pd.DataFrame]:
    source_max = pd.Timestamp("2024-12-31")
    return {
        "accounts": pd.DataFrame(
            [
                {
                    "account_id": "acct_active",
                    "account_name": "Synthetic Account Active",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "industry": "software",
                    "region": "north_america",
                    "segment": "smb",
                    "company_size_band": "1_50",
                    "acquisition_channel": "inbound",
                    "initial_plan": "growth",
                    "synthetic_archetype": "healthy_growing",
                },
                {
                    "account_id": "acct_churned",
                    "account_name": "Synthetic Account Churned",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "industry": "software",
                    "region": "europe",
                    "segment": "smb",
                    "company_size_band": "1_50",
                    "acquisition_channel": "partner",
                    "initial_plan": "starter",
                    "synthetic_archetype": "price_sensitive",
                },
                {
                    "account_id": "acct_gap",
                    "account_name": "Synthetic Account Gap",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "industry": "retail",
                    "region": "north_america",
                    "segment": "mid_market",
                    "company_size_band": "51_200",
                    "acquisition_channel": "outbound",
                    "initial_plan": "business",
                    "synthetic_archetype": "steady_retained",
                },
                {
                    "account_id": "acct_new",
                    "account_name": "Synthetic Account New",
                    "created_date": pd.Timestamp("2024-09-15"),
                    "industry": "media",
                    "region": "asia_pacific",
                    "segment": "smb",
                    "company_size_band": "1_50",
                    "acquisition_channel": "product_led",
                    "initial_plan": "starter",
                    "synthetic_archetype": "implementation_risk",
                },
            ]
        ),
        "users": pd.DataFrame(
            [
                {
                    "user_id": "user_active",
                    "account_id": "acct_active",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "role_type": "admin",
                    "is_admin": True,
                },
                {
                    "user_id": "user_churned",
                    "account_id": "acct_churned",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "role_type": "admin",
                    "is_admin": True,
                },
                {
                    "user_id": "user_gap",
                    "account_id": "acct_gap",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "role_type": "admin",
                    "is_admin": True,
                },
                {
                    "user_id": "user_new",
                    "account_id": "acct_new",
                    "created_date": pd.Timestamp("2024-09-15"),
                    "role_type": "admin",
                    "is_admin": True,
                },
            ]
        ),
        "usage_events": pd.DataFrame(
            [
                {
                    "event_id": "evt_active",
                    "account_id": "acct_active",
                    "user_id": "user_active",
                    "event_timestamp": source_max,
                    "event_type": "login",
                    "event_value": 1,
                }
            ]
        ),
        "subscriptions": pd.DataFrame(
            [
                {
                    "subscription_id": "sub_active",
                    "account_id": "acct_active",
                    "plan": "growth",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.NaT,
                    "mrr": 700.0,
                    "billing_period": "monthly",
                    "status": "active",
                },
                {
                    "subscription_id": "sub_churned",
                    "account_id": "acct_churned",
                    "plan": "starter",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.Timestamp("2024-06-15"),
                    "mrr": 250.0,
                    "billing_period": "monthly",
                    "status": "cancelled",
                },
                {
                    "subscription_id": "sub_gap",
                    "account_id": "acct_gap",
                    "plan": "business",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.Timestamp("2024-04-15"),
                    "mrr": 1800.0,
                    "billing_period": "annual",
                    "status": "ended",
                },
                {
                    "subscription_id": "sub_new",
                    "account_id": "acct_new",
                    "plan": "starter",
                    "start_date": pd.Timestamp("2024-09-15"),
                    "end_date": pd.NaT,
                    "mrr": 250.0,
                    "billing_period": "monthly",
                    "status": "active",
                },
            ]
        ),
        "invoices": pd.DataFrame(
            [
                {
                    "invoice_id": "inv_active",
                    "account_id": "acct_active",
                    "invoice_date": source_max,
                    "due_date": source_max,
                    "paid_date": pd.NaT,
                    "amount": 700.0,
                    "status": "open",
                }
            ]
        ),
        "support_tickets": pd.DataFrame(
            [
                {
                    "ticket_id": "tkt_active",
                    "account_id": "acct_active",
                    "created_at": source_max,
                    "resolved_at": pd.NaT,
                    "priority": "low",
                    "category": "how_to",
                    "status": "open",
                    "csat_score": pd.NA,
                }
            ]
        ),
        "crm_touchpoints": pd.DataFrame(
            [
                {
                    "touchpoint_id": "crm_active",
                    "account_id": "acct_active",
                    "touchpoint_date": source_max,
                    "team": "customer_success",
                    "touchpoint_type": "business_review",
                    "outcome": "completed",
                }
            ]
        ),
        "renewals": pd.DataFrame(
            [
                {
                    "renewal_id": "ren_churned",
                    "account_id": "acct_churned",
                    "renewal_date": pd.Timestamp("2024-06-15"),
                    "outcome": "churned",
                    "previous_mrr": 250.0,
                    "new_mrr": 0.0,
                },
                {
                    "renewal_id": "ren_future",
                    "account_id": "acct_active",
                    "renewal_date": source_max,
                    "outcome": "renewed_flat",
                    "previous_mrr": 700.0,
                    "new_mrr": 700.0,
                },
            ]
        ),
    }


def account_month_frame(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT *
            FROM mart.account_month
            ORDER BY account_id, observation_month
            """
        ).fetchdf()


def feature_build_audit_frame(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT *
            FROM metadata.feature_build_audit
            ORDER BY built_at_utc, build_id
            """
        ).fetchdf()


def build_frame_for_tables(
    tmp_path: Path,
    name: str,
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    database_path = tmp_path / f"{name}.duckdb"
    create_raw_warehouse(database_path, tables)
    build_account_month(database_path)
    return account_month_frame(database_path)


def account_month_row(
    frame: pd.DataFrame,
    account_id: str,
    observation_month: str = "2024-03-01",
) -> pd.Series:
    rows = frame[
        (frame["account_id"] == account_id)
        & (frame["observation_month"] == pd.Timestamp(observation_month))
    ]
    assert len(rows) == 1
    return rows.iloc[0]


def label_source_tables() -> dict[str, pd.DataFrame]:
    source_max = pd.Timestamp("2024-12-31")
    scenarios = [
        ("acct_churn_in_90", "churned", "2024-04-15", 700.0, 0.0),
        ("acct_churn_after_90", "churned", "2024-07-15", 700.0, 0.0),
        ("acct_churn_on_obs", "churned", "2024-03-31", 700.0, 0.0),
        ("acct_expand_in_90", "renewed_expanded", "2024-04-15", 700.0, 900.0),
        ("acct_expand_after_90", "renewed_expanded", "2024-07-15", 700.0, 900.0),
        ("acct_expand_on_obs", "renewed_expanded", "2024-03-31", 700.0, 900.0),
        ("acct_expand_no_mrr", "renewed_expanded", "2024-04-15", 700.0, 700.0),
    ]

    accounts = []
    users = []
    subscriptions = []
    renewals = []
    for index, (
        account_id,
        outcome,
        renewal_date,
        previous_mrr,
        new_mrr,
    ) in enumerate(scenarios, start=1):
        accounts.append(
            {
                "account_id": account_id,
                "account_name": f"Synthetic Account Label {index}",
                "created_date": pd.Timestamp("2024-01-01"),
                "industry": "software",
                "region": "north_america",
                "segment": "smb",
                "company_size_band": "1_50",
                "acquisition_channel": "inbound",
                "initial_plan": "growth",
                "synthetic_archetype": "healthy_growing",
            }
        )
        users.append(
            {
                "user_id": f"user_label_{index}",
                "account_id": account_id,
                "created_date": pd.Timestamp("2024-01-01"),
                "role_type": "admin",
                "is_admin": True,
            }
        )
        subscriptions.append(
            {
                "subscription_id": f"sub_label_{index}",
                "account_id": account_id,
                "plan": "growth",
                "start_date": pd.Timestamp("2024-01-01"),
                "end_date": pd.Timestamp(renewal_date),
                "mrr": previous_mrr,
                "billing_period": "monthly",
                "status": "cancelled" if outcome == "churned" else "ended",
            }
        )
        renewals.append(
            {
                "renewal_id": f"ren_label_{index}",
                "account_id": account_id,
                "renewal_date": pd.Timestamp(renewal_date),
                "outcome": outcome,
                "previous_mrr": previous_mrr,
                "new_mrr": new_mrr,
            }
        )

    return {
        "accounts": pd.DataFrame(accounts),
        "users": pd.DataFrame(users),
        "usage_events": pd.DataFrame(
            [
                {
                    "event_id": "evt_label_anchor",
                    "account_id": "acct_churn_in_90",
                    "user_id": "user_label_1",
                    "event_timestamp": source_max,
                    "event_type": "login",
                    "event_value": 1,
                }
            ]
        ),
        "subscriptions": pd.DataFrame(subscriptions),
        "invoices": pd.DataFrame(
            [
                {
                    "invoice_id": "inv_label_anchor",
                    "account_id": "acct_churn_in_90",
                    "invoice_date": source_max,
                    "due_date": source_max,
                    "paid_date": pd.NaT,
                    "amount": 700.0,
                    "status": "open",
                }
            ]
        ),
        "support_tickets": pd.DataFrame(
            [
                {
                    "ticket_id": "tkt_label_anchor",
                    "account_id": "acct_churn_in_90",
                    "created_at": source_max,
                    "resolved_at": pd.NaT,
                    "priority": "low",
                    "category": "how_to",
                    "status": "open",
                    "csat_score": pd.NA,
                }
            ]
        ),
        "crm_touchpoints": pd.DataFrame(
            [
                {
                    "touchpoint_id": "crm_label_anchor",
                    "account_id": "acct_churn_in_90",
                    "touchpoint_date": source_max,
                    "team": "customer_success",
                    "touchpoint_type": "business_review",
                    "outcome": "completed",
                }
            ]
        ),
        "renewals": pd.DataFrame(renewals),
    }


def feature_source_tables() -> dict[str, pd.DataFrame]:
    account_id = "acct_feature"
    source_max = pd.Timestamp("2024-12-31")
    return {
        "accounts": pd.DataFrame(
            [
                {
                    "account_id": account_id,
                    "account_name": "Synthetic Account Feature",
                    "created_date": pd.Timestamp("2024-01-01"),
                    "industry": "software",
                    "region": "europe",
                    "segment": "mid_market",
                    "company_size_band": "51_200",
                    "acquisition_channel": "partner",
                    "initial_plan": "growth",
                    "synthetic_archetype": "expansion_ready",
                }
            ]
        ),
        "users": pd.DataFrame(
            [
                {
                    "user_id": "user_feature_admin",
                    "account_id": account_id,
                    "created_date": pd.Timestamp("2024-01-01"),
                    "role_type": "admin",
                    "is_admin": True,
                },
                {
                    "user_id": "user_feature_member",
                    "account_id": account_id,
                    "created_date": pd.Timestamp("2024-01-01"),
                    "role_type": "manager",
                    "is_admin": False,
                },
            ]
        ),
        "usage_events": pd.DataFrame(
            [
                {
                    "event_id": "evt_usage_30",
                    "account_id": account_id,
                    "user_id": "user_feature_admin",
                    "event_timestamp": pd.Timestamp("2024-06-15 09:00:00"),
                    "event_type": "login",
                    "event_value": 1,
                },
                {
                    "event_id": "evt_usage_90",
                    "account_id": account_id,
                    "user_id": "user_feature_member",
                    "event_timestamp": pd.Timestamp("2024-04-15 10:00:00"),
                    "event_type": "workflow_run",
                    "event_value": 3,
                },
                {
                    "event_id": "evt_usage_180",
                    "account_id": account_id,
                    "user_id": "user_feature_admin",
                    "event_timestamp": pd.Timestamp("2024-01-15 11:00:00"),
                    "event_type": "api_call",
                    "event_value": 10,
                },
                {
                    "event_id": "evt_usage_future",
                    "account_id": account_id,
                    "user_id": "user_feature_admin",
                    "event_timestamp": pd.Timestamp("2024-07-01 00:00:00"),
                    "event_type": "login",
                    "event_value": 99,
                },
            ]
        ),
        "subscriptions": pd.DataFrame(
            [
                {
                    "subscription_id": "sub_feature_old",
                    "account_id": account_id,
                    "plan": "growth",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.Timestamp("2024-06-15"),
                    "mrr": 700.0,
                    "billing_period": "monthly",
                    "status": "ended",
                },
                {
                    "subscription_id": "sub_feature_current",
                    "account_id": account_id,
                    "plan": "business",
                    "start_date": pd.Timestamp("2024-06-16"),
                    "end_date": pd.NaT,
                    "mrr": 900.0,
                    "billing_period": "annual",
                    "status": "active",
                },
                {
                    "subscription_id": "sub_feature_future",
                    "account_id": account_id,
                    "plan": "enterprise",
                    "start_date": pd.Timestamp("2024-08-01"),
                    "end_date": pd.NaT,
                    "mrr": 2000.0,
                    "billing_period": "annual",
                    "status": "active",
                },
            ]
        ),
        "invoices": pd.DataFrame(
            [
                {
                    "invoice_id": "inv_paid_known",
                    "account_id": account_id,
                    "invoice_date": pd.Timestamp("2024-06-15"),
                    "due_date": pd.Timestamp("2024-06-25"),
                    "paid_date": pd.Timestamp("2024-06-20"),
                    "amount": 100.0,
                    "status": "paid",
                },
                {
                    "invoice_id": "inv_paid_future",
                    "account_id": account_id,
                    "invoice_date": pd.Timestamp("2024-06-25"),
                    "due_date": pd.Timestamp("2024-06-30"),
                    "paid_date": pd.Timestamp("2024-07-05"),
                    "amount": 200.0,
                    "status": "paid",
                },
                {
                    "invoice_id": "inv_failed",
                    "account_id": account_id,
                    "invoice_date": pd.Timestamp("2024-05-01"),
                    "due_date": pd.Timestamp("2024-05-31"),
                    "paid_date": pd.NaT,
                    "amount": 300.0,
                    "status": "failed",
                },
                {
                    "invoice_id": "inv_180",
                    "account_id": account_id,
                    "invoice_date": pd.Timestamp("2024-01-15"),
                    "due_date": pd.Timestamp("2024-02-14"),
                    "paid_date": pd.Timestamp("2024-01-20"),
                    "amount": 400.0,
                    "status": "paid",
                },
                {
                    "invoice_id": "inv_future",
                    "account_id": account_id,
                    "invoice_date": pd.Timestamp("2024-07-01"),
                    "due_date": pd.Timestamp("2024-07-31"),
                    "paid_date": pd.NaT,
                    "amount": 500.0,
                    "status": "open",
                },
            ]
        ),
        "support_tickets": pd.DataFrame(
            [
                {
                    "ticket_id": "tkt_resolved_known",
                    "account_id": account_id,
                    "created_at": pd.Timestamp("2024-06-10 10:00:00"),
                    "resolved_at": pd.Timestamp("2024-06-20 10:00:00"),
                    "priority": "medium",
                    "category": "how_to",
                    "status": "resolved",
                    "csat_score": 4,
                },
                {
                    "ticket_id": "tkt_resolved_future",
                    "account_id": account_id,
                    "created_at": pd.Timestamp("2024-06-29 10:00:00"),
                    "resolved_at": pd.Timestamp("2024-07-01 10:00:00"),
                    "priority": "high",
                    "category": "bug",
                    "status": "resolved",
                    "csat_score": 3,
                },
                {
                    "ticket_id": "tkt_open",
                    "account_id": account_id,
                    "created_at": pd.Timestamp("2024-06-20 10:00:00"),
                    "resolved_at": pd.NaT,
                    "priority": "low",
                    "category": "billing",
                    "status": "open",
                    "csat_score": pd.NA,
                },
                {
                    "ticket_id": "tkt_180",
                    "account_id": account_id,
                    "created_at": pd.Timestamp("2024-01-15 10:00:00"),
                    "resolved_at": pd.Timestamp("2024-01-16 10:00:00"),
                    "priority": "low",
                    "category": "how_to",
                    "status": "resolved",
                    "csat_score": 5,
                },
                {
                    "ticket_id": "tkt_future",
                    "account_id": account_id,
                    "created_at": pd.Timestamp("2024-07-01 10:00:00"),
                    "resolved_at": pd.NaT,
                    "priority": "urgent",
                    "category": "bug",
                    "status": "open",
                    "csat_score": pd.NA,
                },
            ]
        ),
        "crm_touchpoints": pd.DataFrame(
            [
                {
                    "touchpoint_id": "crm_30",
                    "account_id": account_id,
                    "touchpoint_date": pd.Timestamp("2024-06-20"),
                    "team": "sales",
                    "touchpoint_type": "expansion_discussion",
                    "outcome": "completed",
                },
                {
                    "touchpoint_id": "crm_90",
                    "account_id": account_id,
                    "touchpoint_date": pd.Timestamp("2024-04-15"),
                    "team": "customer_success",
                    "touchpoint_type": "business_review",
                    "outcome": "completed",
                },
                {
                    "touchpoint_id": "crm_180",
                    "account_id": account_id,
                    "touchpoint_date": pd.Timestamp("2024-01-15"),
                    "team": "growth",
                    "touchpoint_type": "training",
                    "outcome": "completed",
                },
                {
                    "touchpoint_id": "crm_future",
                    "account_id": account_id,
                    "touchpoint_date": pd.Timestamp("2024-07-01"),
                    "team": "sales",
                    "touchpoint_type": "expansion_discussion",
                    "outcome": "opportunity_created",
                },
            ]
        ),
        "renewals": pd.DataFrame(
            [
                {
                    "renewal_id": "ren_feature_future",
                    "account_id": account_id,
                    "renewal_date": source_max,
                    "outcome": "renewed_flat",
                    "previous_mrr": 900.0,
                    "new_mrr": 900.0,
                }
            ]
        ),
    }


def test_build_account_month_spine_enforces_grain_and_eligibility(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, base_source_tables())

    result = build_account_month(database_path)
    frame = account_month_frame(database_path)

    assert result.row_count == len(frame)
    assert result.output_table == "mart.account_month"
    assert frame["account_id"].notna().all()
    assert frame["observation_month"].notna().all()
    assert not frame.duplicated(["account_id", "observation_month"]).any()
    assert frame["observation_month"].dt.is_month_start.all()
    assert (
        frame["observation_month_end"]
        == frame["observation_month"] + pd.offsets.MonthEnd(0)
    ).all()
    assert frame["account_age_days"].min() >= 30
    assert set(frame["is_churn_label_eligible"].unique()) == {True}
    assert set(frame["is_expansion_label_eligible"].dropna().unique()) <= {
        False,
        True,
    }

    active_months = frame.loc[
        frame["account_id"] == "acct_active", "observation_month"
    ].dt.strftime("%Y-%m-%d")
    assert active_months.tolist() == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
        "2024-04-01",
        "2024-05-01",
        "2024-06-01",
        "2024-07-01",
        "2024-08-01",
        "2024-09-01",
    ]

    churned_months = frame.loc[
        frame["account_id"] == "acct_churned", "observation_month"
    ].dt.strftime("%Y-%m-%d")
    assert churned_months.tolist() == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
        "2024-04-01",
        "2024-05-01",
    ]

    gap_months = frame.loc[
        frame["account_id"] == "acct_gap", "observation_month"
    ].dt.strftime("%Y-%m-%d")
    assert gap_months.tolist() == [
        "2024-01-01",
        "2024-02-01",
        "2024-03-01",
    ]
    assert "acct_new" not in set(frame["account_id"])


def test_build_account_month_spine_is_deterministic(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, base_source_tables())

    first_result = build_account_month(database_path)
    first_frame = account_month_frame(database_path)
    second_result = build_account_month(database_path)
    second_frame = account_month_frame(database_path)

    assert first_result.row_count == second_result.row_count
    pd.testing.assert_frame_equal(first_frame, second_frame)


def test_build_account_month_labels_use_renewal_horizon_and_null_policy(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, label_source_tables())

    build_account_month(database_path)
    frame = account_month_frame(database_path)

    churn_in_90 = account_month_row(frame, "acct_churn_in_90")
    assert churn_in_90["churn_90d"] == 1
    assert bool(churn_in_90["is_expansion_label_eligible"]) is False
    assert pd.isna(churn_in_90["expansion_90d"])

    churn_after_90 = account_month_row(frame, "acct_churn_after_90")
    assert churn_after_90["churn_90d"] == 0

    churn_on_obs = frame[
        (frame["account_id"] == "acct_churn_on_obs")
        & (frame["observation_month"] == pd.Timestamp("2024-03-01"))
    ]
    assert churn_on_obs.empty

    expand_in_90 = account_month_row(frame, "acct_expand_in_90")
    assert expand_in_90["expansion_90d"] == 1

    expand_after_90 = account_month_row(frame, "acct_expand_after_90")
    assert expand_after_90["expansion_90d"] == 0

    expand_on_obs = account_month_row(frame, "acct_expand_on_obs")
    assert expand_on_obs["expansion_90d"] == 0

    expand_no_mrr = account_month_row(frame, "acct_expand_no_mrr")
    assert expand_no_mrr["expansion_90d"] == 0

    assert set(frame["churn_90d"].dropna().unique()) <= {0, 1}
    eligible_expansion = frame[frame["is_expansion_label_eligible"]]
    assert set(eligible_expansion["expansion_90d"].dropna().unique()) <= {0, 1}
    ineligible_expansion = frame[~frame["is_expansion_label_eligible"]]
    assert ineligible_expansion["expansion_90d"].isna().all()


def test_build_account_month_features_are_point_in_time_and_sane(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, feature_source_tables())

    build_account_month(database_path)
    frame = account_month_frame(database_path)
    row = account_month_row(frame, "acct_feature", observation_month="2024-06-01")

    assert "synthetic_archetype" not in frame.columns
    assert row["industry"] == "software"
    assert row["region"] == "europe"
    assert row["segment"] == "mid_market"
    assert row["company_size_band"] == "51_200"
    assert row["acquisition_channel"] == "partner"

    assert row["current_plan"] == "business"
    assert row["current_mrr"] == 900.0
    assert row["current_billing_period"] == "annual"
    assert row["subscription_age_days"] == 14

    assert row["usage_event_count_30d"] == 1
    assert row["usage_event_count_90d"] == 2
    assert row["usage_event_count_180d"] == 3
    assert row["active_user_count_30d"] == 1
    assert row["active_user_count_90d"] == 2
    assert row["active_user_count_180d"] == 2
    assert row["usage_event_value_sum_90d"] == 4

    assert row["support_ticket_count_30d"] == 3
    assert row["support_ticket_count_90d"] == 3
    assert row["support_ticket_count_180d"] == 4
    assert row["high_priority_ticket_count_90d"] == 1
    assert row["open_ticket_count"] == 2
    assert row["avg_resolution_hours_known"] == 132.0
    assert row["days_since_last_ticket"] == 1

    assert row["invoice_count_90d"] == 3
    assert row["invoice_count_180d"] == 4
    assert row["invoice_amount_sum_90d"] == 600.0
    assert row["invoice_amount_sum_180d"] == 1000.0
    assert row["unpaid_invoice_count_90d"] == 2
    assert row["failed_invoice_count_90d"] == 1
    assert row["overdue_invoice_count"] == 2
    assert row["avg_payment_delay_days_known"] == 5.0
    assert row["days_since_last_invoice"] == 5

    assert row["crm_touchpoint_count_30d"] == 1
    assert row["crm_touchpoint_count_90d"] == 2
    assert row["crm_touchpoint_count_180d"] == 3
    assert row["sales_touchpoint_count_90d"] == 1
    assert row["cs_touchpoint_count_90d"] == 1
    assert row["days_since_last_crm_touchpoint"] == 10

    count_columns = [column for column in frame.columns if column.endswith("_count_90d")]
    count_columns.extend(
        [
            "usage_event_count_30d",
            "usage_event_count_180d",
            "active_user_count_30d",
            "active_user_count_180d",
            "support_ticket_count_30d",
            "support_ticket_count_180d",
            "open_ticket_count",
            "invoice_count_180d",
            "overdue_invoice_count",
            "crm_touchpoint_count_30d",
            "crm_touchpoint_count_180d",
        ]
    )
    for column in count_columns:
        assert (frame[column] >= 0).all()


def test_build_account_month_hardens_adversarial_feature_cutoffs(
    tmp_path: Path,
) -> None:
    frame = build_frame_for_tables(
        tmp_path,
        "adversarial_cutoffs",
        feature_source_tables(),
    )
    row = account_month_row(frame, "acct_feature", observation_month="2024-06-01")

    assert row["usage_event_count_30d"] == 1
    assert row["support_ticket_count_30d"] == 3
    assert row["high_priority_ticket_count_90d"] == 1
    assert row["open_ticket_count"] == 2
    assert row["avg_resolution_hours_known"] == 132.0
    assert row["invoice_count_90d"] == 3
    assert row["unpaid_invoice_count_90d"] == 2
    assert row["avg_payment_delay_days_known"] == 5.0
    assert row["crm_touchpoint_count_30d"] == 1
    assert row["sales_touchpoint_count_90d"] == 1


def test_renewal_events_affect_labels_but_not_features(tmp_path: Path) -> None:
    after_horizon_tables = {
        table_name: frame.copy()
        for table_name, frame in feature_source_tables().items()
    }
    after_horizon_tables["renewals"].loc[0, "outcome"] = "churned"
    after_horizon_tables["renewals"].loc[0, "new_mrr"] = 0.0

    inside_horizon_tables = {
        table_name: frame.copy()
        for table_name, frame in after_horizon_tables.items()
    }
    inside_horizon_tables["renewals"] = pd.concat(
        [
            inside_horizon_tables["renewals"],
            pd.DataFrame(
                [
                    {
                        "renewal_id": "ren_feature_inside_horizon",
                        "account_id": "acct_feature",
                        "renewal_date": pd.Timestamp("2024-07-15"),
                        "outcome": "churned",
                        "previous_mrr": 900.0,
                        "new_mrr": 0.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    after_horizon = build_frame_for_tables(
        tmp_path,
        "after_horizon",
        after_horizon_tables,
    )
    inside_horizon = build_frame_for_tables(
        tmp_path,
        "inside_horizon",
        inside_horizon_tables,
    )

    after_row = account_month_row(
        after_horizon,
        "acct_feature",
        observation_month="2024-06-01",
    )
    inside_row = account_month_row(
        inside_horizon,
        "acct_feature",
        observation_month="2024-06-01",
    )

    assert after_row["churn_90d"] == 0
    assert after_row["expansion_90d"] == 0
    assert inside_row["churn_90d"] == 1
    assert bool(inside_row["is_expansion_label_eligible"]) is False
    assert pd.isna(inside_row["expansion_90d"])

    label_columns = {
        "is_churn_label_eligible",
        "is_expansion_label_eligible",
        "churn_90d",
        "expansion_90d",
    }
    feature_columns = [
        column for column in after_horizon.columns if column not in label_columns
    ]
    pd.testing.assert_series_equal(
        after_row[feature_columns],
        inside_row[feature_columns],
        check_names=False,
    )


def test_build_account_month_records_feature_build_audit(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, feature_source_tables())

    result = build_account_month(database_path)
    output = account_month_frame(database_path)
    audit = feature_build_audit_frame(database_path)
    audit_row = audit.iloc[0]

    assert len(audit) == 1
    assert audit_row["build_id"] == result.build_id
    assert audit_row["output_table"] == "mart.account_month"
    assert audit_row["row_count"] == len(output)
    assert audit_row["row_count"] == result.row_count
    assert audit_row["account_count"] == result.account_count
    assert audit_row["churn_eligible_count"] == result.churn_eligible_count
    assert audit_row["churn_positive_count"] == result.churn_positive_count
    assert audit_row["expansion_eligible_count"] == result.expansion_eligible_count
    assert audit_row["expansion_positive_count"] == result.expansion_positive_count
    assert pd.Timestamp(audit_row["source_max_date"]) == pd.Timestamp("2024-12-31")


def test_build_account_month_cli_uses_explicit_database_path(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, feature_source_tables())

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_account_month.py",
            "--database-path",
            str(database_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "output_table: mart.account_month" in result.stdout
    assert "audit_table: metadata.feature_build_audit" in result.stdout
    assert len(account_month_frame(database_path)) > 0
    assert len(feature_build_audit_frame(database_path)) == 1


def test_build_account_month_make_target_uses_warehouse_path(tmp_path: Path) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_raw_warehouse(database_path, feature_source_tables())

    result = subprocess.run(
        [
            "make",
            "build-account-month",
            f"WAREHOUSE_PATH={database_path}",
            f"PYTHON={sys.executable}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "output_table: mart.account_month" in result.stdout
    assert len(account_month_frame(database_path)) > 0
    assert len(feature_build_audit_frame(database_path)) == 1
