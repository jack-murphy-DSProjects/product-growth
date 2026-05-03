from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from account_health.synthetic import generate_synthetic_source_data
from account_health.synthetic.schemas import (
    ALLOWED_VALUES,
    FOREIGN_KEYS,
    PRIMARY_KEYS,
    REQUIRED_COLUMNS,
    SOURCE_TABLES,
)


DEFAULT_START = pd.Timestamp("2023-01-01")
DEFAULT_END = pd.Timestamp("2025-12-31")
SMALL_ACCOUNT_COUNT = 8


@pytest.fixture(scope="module")
def small_tables() -> dict[str, pd.DataFrame]:
    return generate_synthetic_source_data(seed=99, n_accounts=SMALL_ACCOUNT_COUNT)


def test_same_seed_produces_identical_tables() -> None:
    first = generate_synthetic_source_data(seed=123, n_accounts=SMALL_ACCOUNT_COUNT)
    second = generate_synthetic_source_data(seed=123, n_accounts=SMALL_ACCOUNT_COUNT)

    for table in SOURCE_TABLES:
        pd.testing.assert_frame_equal(first[table], second[table])


def test_different_seed_changes_output() -> None:
    first = generate_synthetic_source_data(seed=123, n_accounts=SMALL_ACCOUNT_COUNT)
    second = generate_synthetic_source_data(seed=456, n_accounts=SMALL_ACCOUNT_COUNT)

    assert any(not first[table].equals(second[table]) for table in SOURCE_TABLES)


def test_expected_tables_and_columns_are_present(
    small_tables: dict[str, pd.DataFrame],
) -> None:
    assert tuple(small_tables) == SOURCE_TABLES
    for table in SOURCE_TABLES:
        assert tuple(small_tables[table].columns) == REQUIRED_COLUMNS[table]


def test_small_tables_are_non_empty(small_tables: dict[str, pd.DataFrame]) -> None:
    assert all(not frame.empty for frame in small_tables.values())


def test_primary_keys_are_unique_and_non_null(
    small_tables: dict[str, pd.DataFrame],
) -> None:
    for table, key in PRIMARY_KEYS.items():
        values = small_tables[table][key]
        assert values.notna().all(), table
        assert values.is_unique, table


def test_foreign_keys_are_valid(small_tables: dict[str, pd.DataFrame]) -> None:
    for child_table, key_map in FOREIGN_KEYS.items():
        for child_key, (parent_table, parent_key) in key_map.items():
            assert set(small_tables[child_table][child_key]).issubset(
                set(small_tables[parent_table][parent_key])
            )

    events = small_tables["usage_events"].merge(
        small_tables["users"][["user_id", "account_id"]],
        on="user_id",
        suffixes=("_event", "_user"),
    )
    assert (events["account_id_event"] == events["account_id_user"]).all()


def test_dates_are_in_range_and_ordered(small_tables: dict[str, pd.DataFrame]) -> None:
    accounts = small_tables["accounts"].copy()
    accounts["created_date"] = pd.to_datetime(accounts["created_date"])
    assert accounts["created_date"].between(DEFAULT_START, DEFAULT_END).all()

    users = small_tables["users"].merge(
        accounts[["account_id", "created_date"]],
        on="account_id",
        suffixes=("_user", "_account"),
    )
    users["created_date_user"] = pd.to_datetime(users["created_date_user"])
    assert (users["created_date_user"] >= users["created_date_account"]).all()
    assert (users["created_date_user"] <= DEFAULT_END).all()

    events = (
        small_tables["usage_events"]
        .merge(users[["user_id", "created_date_user"]], on="user_id")
        .merge(accounts[["account_id", "created_date"]], on="account_id")
    )
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"])
    assert (events["event_timestamp"].dt.normalize() >= DEFAULT_START).all()
    assert (events["event_timestamp"].dt.normalize() <= DEFAULT_END).all()
    assert (events["event_timestamp"] >= events["created_date_user"]).all()
    assert (events["event_timestamp"] >= events["created_date"]).all()

    subscriptions = small_tables["subscriptions"].merge(
        accounts[["account_id", "created_date"]], on="account_id"
    )
    subscriptions["start_date"] = pd.to_datetime(subscriptions["start_date"])
    subscriptions["end_date"] = pd.to_datetime(subscriptions["end_date"])
    assert (subscriptions["start_date"] >= subscriptions["created_date"]).all()
    ended = subscriptions["end_date"].notna()
    assert (subscriptions.loc[ended, "end_date"] >= subscriptions.loc[ended, "start_date"]).all()

    invoices = small_tables["invoices"].copy()
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    invoices["due_date"] = pd.to_datetime(invoices["due_date"])
    invoices["paid_date"] = pd.to_datetime(invoices["paid_date"])
    assert (invoices["due_date"] >= invoices["invoice_date"]).all()
    paid = invoices["paid_date"].notna()
    assert (invoices.loc[paid, "paid_date"] >= invoices.loc[paid, "invoice_date"]).all()
    assert invoices.loc[~paid, "status"].isin({"open", "failed", "void"}).all()

    tickets = small_tables["support_tickets"].copy()
    tickets["created_at"] = pd.to_datetime(tickets["created_at"])
    tickets["resolved_at"] = pd.to_datetime(tickets["resolved_at"])
    resolved = tickets["resolved_at"].notna()
    assert (tickets.loc[resolved, "resolved_at"] >= tickets.loc[resolved, "created_at"]).all()

    touchpoints = small_tables["crm_touchpoints"].merge(
        accounts[["account_id", "created_date"]], on="account_id"
    )
    touchpoints["touchpoint_date"] = pd.to_datetime(touchpoints["touchpoint_date"])
    assert (touchpoints["touchpoint_date"] >= touchpoints["created_date"]).all()
    assert (touchpoints["touchpoint_date"] <= DEFAULT_END).all()

    renewals = small_tables["renewals"].merge(
        accounts[["account_id", "created_date"]], on="account_id"
    )
    renewals["renewal_date"] = pd.to_datetime(renewals["renewal_date"])
    assert renewals["renewal_date"].between(DEFAULT_START, DEFAULT_END).all()
    assert (renewals["renewal_date"] >= renewals["created_date"]).all()


def test_numeric_values_are_bounded(small_tables: dict[str, pd.DataFrame]) -> None:
    assert (small_tables["usage_events"]["event_value"] >= 0).all()
    assert (small_tables["subscriptions"]["mrr"] >= 0).all()
    assert (small_tables["invoices"]["amount"] >= 0).all()
    assert (small_tables["renewals"]["previous_mrr"] >= 0).all()
    assert (small_tables["renewals"]["new_mrr"] >= 0).all()

    scores = small_tables["support_tickets"]["csat_score"].dropna()
    assert scores.between(1, 5).all()


def test_allowed_values_are_used(small_tables: dict[str, pd.DataFrame]) -> None:
    checks = {
        ("accounts", "industry"): "industry",
        ("accounts", "region"): "region",
        ("accounts", "segment"): "segment",
        ("accounts", "company_size_band"): "company_size_band",
        ("accounts", "acquisition_channel"): "acquisition_channel",
        ("accounts", "initial_plan"): "plan",
        ("accounts", "synthetic_archetype"): "synthetic_archetype",
        ("users", "role_type"): "role_type",
        ("usage_events", "event_type"): "event_type",
        ("subscriptions", "plan"): "plan",
        ("subscriptions", "billing_period"): "billing_period",
        ("subscriptions", "status"): "subscription_status",
        ("invoices", "status"): "invoice_status",
        ("support_tickets", "priority"): "ticket_priority",
        ("support_tickets", "category"): "ticket_category",
        ("support_tickets", "status"): "ticket_status",
        ("crm_touchpoints", "team"): "touchpoint_team",
        ("crm_touchpoints", "touchpoint_type"): "touchpoint_type",
        ("crm_touchpoints", "outcome"): "touchpoint_outcome",
        ("renewals", "outcome"): "renewal_outcome",
    }

    for (table, column), allowed_key in checks.items():
        assert set(small_tables[table][column].dropna()).issubset(ALLOWED_VALUES[allowed_key])


def test_default_generation_has_plausible_rates_and_archetype_coverage() -> None:
    default_tables = generate_synthetic_source_data()
    renewals = default_tables["renewals"]
    churn_rate = renewals["outcome"].eq("churned").mean()
    expansion_rate = renewals["outcome"].eq("renewed_expanded").mean()

    assert 0.05 <= churn_rate <= 0.35
    assert 0.05 <= expansion_rate <= 0.35
    assert set(default_tables["accounts"]["synthetic_archetype"]) == set(
        ALLOWED_VALUES["synthetic_archetype"]
    )


def test_generator_does_not_write_local_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    generate_synthetic_source_data(seed=789, n_accounts=10)

    assert list(tmp_path.iterdir()) == []
