"""Deterministic synthetic B2B SaaS source data generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil

import numpy as np
import pandas as pd

from account_health.synthetic.schemas import ALLOWED_VALUES, REQUIRED_COLUMNS, SOURCE_TABLES


@dataclass(frozen=True)
class ArchetypeControl:
    usage_multiplier: float
    usage_trend: float
    ticket_multiplier: float
    billing_friction: float
    expansion_multiplier: float
    churn_multiplier: float
    early_activation: float = 1.0
    seasonal: bool = False


ARCHETYPE_CONTROLS: dict[str, ArchetypeControl] = {
    "healthy_growing": ArchetypeControl(1.15, 0.035, 0.80, 0.75, 1.35, 0.60),
    "steady_retained": ArchetypeControl(1.00, 0.005, 0.95, 0.90, 0.95, 0.80),
    "low_adoption": ArchetypeControl(0.45, -0.010, 1.10, 1.00, 0.60, 1.55),
    "support_frustrated": ArchetypeControl(0.85, -0.020, 2.10, 1.35, 0.75, 1.45),
    "seasonal": ArchetypeControl(0.95, 0.000, 1.00, 0.95, 0.95, 0.90, seasonal=True),
    "expansion_ready": ArchetypeControl(1.25, 0.045, 0.85, 0.80, 1.85, 0.55),
    "price_sensitive": ArchetypeControl(0.95, 0.000, 1.05, 1.90, 0.75, 1.30),
    "implementation_risk": ArchetypeControl(0.55, 0.015, 1.80, 1.20, 0.65, 1.50, 0.55),
}

PLAN_ORDER = ("starter", "growth", "business", "enterprise")

PLAN_MRR = {
    "starter": 250,
    "growth": 700,
    "business": 1_800,
    "enterprise": 5_500,
}

SEGMENT_USER_BASE = {
    "smb": 5,
    "mid_market": 18,
    "enterprise": 48,
}

SEGMENT_USAGE_BASE = {
    "smb": 3.5,
    "mid_market": 9.5,
    "enterprise": 21.0,
}

PLAN_MULTIPLIER = {
    "starter": 0.75,
    "growth": 1.00,
    "business": 1.35,
    "enterprise": 1.75,
}


def generate_synthetic_source_data(
    seed: int = 42,
    n_accounts: int = 500,
    start_date: str | date = "2023-01-01",
    end_date: str | date = "2025-12-31",
) -> dict[str, pd.DataFrame]:
    """Generate deterministic synthetic SaaS source tables.

    The generator returns pandas DataFrames only. It does not write files or
    create local databases.
    """

    start_ts, end_ts = _validate_inputs(n_accounts, start_date, end_date)
    rng = np.random.default_rng(seed)

    accounts = _generate_accounts(rng, n_accounts, start_ts, end_ts)
    users = _generate_users(rng, accounts, end_ts)
    subscriptions, renewals = _generate_subscriptions_and_renewals(rng, accounts, end_ts)
    invoices = _generate_invoices(rng, subscriptions, accounts, end_ts)
    usage_events = _generate_usage_events(rng, accounts, users, start_ts, end_ts)
    support_tickets = _generate_support_tickets(rng, accounts, end_ts)
    crm_touchpoints = _generate_crm_touchpoints(rng, accounts, end_ts)

    frames = {
        "accounts": accounts,
        "users": users,
        "usage_events": usage_events,
        "subscriptions": subscriptions,
        "invoices": invoices,
        "support_tickets": support_tickets,
        "crm_touchpoints": crm_touchpoints,
        "renewals": renewals,
    }

    return {table: _ordered_frame(table, frames[table]) for table in SOURCE_TABLES}


def _validate_inputs(
    n_accounts: int,
    start_date: str | date,
    end_date: str | date,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if n_accounts < 1:
        raise ValueError("n_accounts must be at least 1")

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise ValueError("start_date and end_date must be valid dates")
    if end_ts < start_ts:
        raise ValueError("end_date must be on or after start_date")
    return start_ts, end_ts


def _generate_accounts(
    rng: np.random.Generator,
    n_accounts: int,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    total_days = max(0, (end_ts - start_ts).days)
    latest_created_offset = max(0, total_days - 365) if total_days >= 365 else total_days
    created_offsets = rng.integers(0, latest_created_offset + 1, size=n_accounts)
    archetypes = _balanced_values(ALLOWED_VALUES["synthetic_archetype"], n_accounts, rng)

    rows: list[dict[str, object]] = []
    for index in range(n_accounts):
        segment = _choice(rng, ALLOWED_VALUES["segment"], p=(0.55, 0.30, 0.15))
        size_band = _size_band_for_segment(rng, segment)
        plan = _initial_plan_for_segment(rng, segment)
        account_number = index + 1
        rows.append(
            {
                "account_id": f"acct_{account_number:06d}",
                "account_name": f"Synthetic Account {account_number:06d}",
                "created_date": start_ts + pd.Timedelta(days=int(created_offsets[index])),
                "industry": _choice(rng, ALLOWED_VALUES["industry"]),
                "region": _choice(rng, ALLOWED_VALUES["region"], p=(0.52, 0.27, 0.16, 0.05)),
                "segment": segment,
                "company_size_band": size_band,
                "acquisition_channel": _choice(
                    rng,
                    ALLOWED_VALUES["acquisition_channel"],
                    p=(0.38, 0.16, 0.18, 0.22, 0.06),
                ),
                "initial_plan": plan,
                "synthetic_archetype": str(archetypes[index]),
            }
        )

    return pd.DataFrame(rows)


def _generate_users(
    rng: np.random.Generator,
    accounts: pd.DataFrame,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    role_probs = np.array([0.05, 0.14, 0.39, 0.21, 0.11, 0.10])
    rows: list[dict[str, object]] = []
    user_number = 1

    for account in accounts.itertuples(index=False):
        control = ARCHETYPE_CONTROLS[account.synthetic_archetype]
        base_users = SEGMENT_USER_BASE[account.segment] * PLAN_MULTIPLIER[account.initial_plan]
        user_count = max(1, int(rng.poisson(base_users * _user_archetype_multiplier(account.synthetic_archetype))))
        if account.segment == "enterprise":
            user_count = min(user_count + int(rng.integers(8, 35)), 140)
        elif account.segment == "mid_market":
            user_count = min(user_count + int(rng.integers(2, 12)), 70)
        else:
            user_count = min(user_count, 24)

        latest_offset = max(0, min(180, (end_ts - account.created_date).days))
        for user_index in range(user_count):
            is_admin = user_index == 0 or rng.random() < 0.07
            role_type = "admin" if is_admin else _choice(rng, ALLOWED_VALUES["role_type"][1:], p=role_probs[1:] / role_probs[1:].sum())
            activation_window = latest_offset
            if control.early_activation < 0.75:
                activation_window = max(latest_offset, min(270, (end_ts - account.created_date).days))
            created_date = account.created_date + pd.Timedelta(
                days=int(rng.integers(0, activation_window + 1)) if activation_window > 0 else 0
            )
            rows.append(
                {
                    "user_id": f"user_{user_number:06d}",
                    "account_id": account.account_id,
                    "created_date": created_date,
                    "role_type": role_type,
                    "is_admin": bool(is_admin),
                }
            )
            user_number += 1

    return pd.DataFrame(rows)


def _generate_usage_events(
    rng: np.random.Generator,
    accounts: pd.DataFrame,
    users: pd.DataFrame,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    event_number = 1
    users_by_account = {
        account_id: frame.sort_values("created_date")
        for account_id, frame in users.groupby("account_id", sort=False)
    }

    for account in accounts.itertuples(index=False):
        control = ARCHETYPE_CONTROLS[account.synthetic_archetype]
        account_users = users_by_account[account.account_id]
        account_user_ids = account_users["user_id"].to_numpy()
        account_user_created = account_users["created_date"].to_numpy()
        active_start = max(start_ts, account.created_date)
        month_starts = _month_starts(active_start, end_ts)
        base_usage = (
            SEGMENT_USAGE_BASE[account.segment]
            * PLAN_MULTIPLIER[account.initial_plan]
            * control.usage_multiplier
            * float(rng.uniform(0.75, 1.25))
        )

        for month_index, month_start in enumerate(month_starts):
            month_end = min(month_start + pd.offsets.MonthEnd(0), end_ts)
            available_positions = np.flatnonzero(account_user_created <= np.datetime64(month_end))
            if available_positions.size == 0:
                continue

            age_factor = max(0.15, 1.0 + control.usage_trend * month_index)
            early_factor = control.early_activation if month_index < 4 else 1.0
            seasonal_factor = _seasonal_factor(month_start.month, control.seasonal)
            expected_events = base_usage * age_factor * early_factor * seasonal_factor
            event_count = min(int(rng.poisson(max(0.3, expected_events))), 95)

            for _ in range(event_count):
                user_position = int(rng.choice(available_positions))
                user_id = str(account_user_ids[user_position])
                lower = max(month_start, account.created_date, pd.Timestamp(account_user_created[user_position]))
                upper = _end_of_day(month_end)
                if lower > upper:
                    lower = month_start
                event_type = _choice(
                    rng,
                    ALLOWED_VALUES["event_type"],
                    p=(0.34, 0.24, 0.09, 0.13, 0.08, 0.09, 0.03),
                )
                rows.append(
                    {
                        "event_id": f"evt_{event_number:09d}",
                        "account_id": account.account_id,
                        "user_id": user_id,
                        "event_timestamp": _random_timestamp(rng, lower, upper),
                        "event_type": event_type,
                        "event_value": _event_value(rng, event_type),
                    }
                )
                event_number += 1

    return pd.DataFrame(rows)


def _generate_subscriptions_and_renewals(
    rng: np.random.Generator,
    accounts: pd.DataFrame,
    end_ts: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    subscription_rows: list[dict[str, object]] = []
    renewal_rows: list[dict[str, object]] = []
    subscription_number = 1
    renewal_number = 1

    for account in accounts.itertuples(index=False):
        current_plan = account.initial_plan
        current_mrr = _initial_mrr(rng, account.initial_plan, account.segment)
        billing_period = _choice(
            rng,
            ALLOWED_VALUES["billing_period"],
            p=(0.78, 0.22) if account.segment == "smb" else (0.52, 0.48),
        )
        period_start = account.created_date
        renewal_date = account.created_date + pd.DateOffset(months=12)
        churned = False

        while renewal_date <= end_ts:
            outcome = _renewal_outcome(rng, account)
            previous_mrr = current_mrr
            new_mrr = _new_mrr_for_outcome(rng, previous_mrr, outcome)
            status = "cancelled" if outcome == "churned" else "ended"
            subscription_rows.append(
                _subscription_row(
                    subscription_number,
                    account.account_id,
                    current_plan,
                    period_start,
                    renewal_date,
                    previous_mrr,
                    billing_period,
                    status,
                )
            )
            subscription_number += 1
            renewal_rows.append(
                {
                    "renewal_id": f"ren_{renewal_number:07d}",
                    "account_id": account.account_id,
                    "renewal_date": renewal_date,
                    "outcome": outcome,
                    "previous_mrr": round(previous_mrr, 2),
                    "new_mrr": round(new_mrr, 2),
                }
            )
            renewal_number += 1

            if outcome == "churned":
                churned = True
                break

            current_mrr = new_mrr
            current_plan = _plan_after_renewal(rng, current_plan, outcome)
            period_start = renewal_date + pd.Timedelta(days=1)
            renewal_date = period_start + pd.DateOffset(months=12)

        if not churned and period_start <= end_ts:
            subscription_rows.append(
                _subscription_row(
                    subscription_number,
                    account.account_id,
                    current_plan,
                    period_start,
                    pd.NaT,
                    current_mrr,
                    billing_period,
                    "active",
                )
            )
            subscription_number += 1

    return pd.DataFrame(subscription_rows), pd.DataFrame(renewal_rows)


def _generate_invoices(
    rng: np.random.Generator,
    subscriptions: pd.DataFrame,
    accounts: pd.DataFrame,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    account_lookup = accounts.set_index("account_id")
    rows: list[dict[str, object]] = []
    invoice_number = 1

    for subscription in subscriptions.itertuples(index=False):
        account = account_lookup.loc[subscription.account_id]
        control = ARCHETYPE_CONTROLS[account["synthetic_archetype"]]
        invoice_date = subscription.start_date
        period_end = end_ts if pd.isna(subscription.end_date) else min(subscription.end_date, end_ts)
        cadence_months = 1 if subscription.billing_period == "monthly" else 12
        amount = subscription.mrr if subscription.billing_period == "monthly" else subscription.mrr * 12

        while invoice_date <= period_end:
            status = _invoice_status(rng, control.billing_friction, invoice_date, end_ts)
            due_date = invoice_date + pd.Timedelta(days=30)
            paid_date = (
                invoice_date + pd.Timedelta(days=int(rng.integers(1, 21)))
                if status == "paid"
                else pd.NaT
            )
            rows.append(
                {
                    "invoice_id": f"inv_{invoice_number:08d}",
                    "account_id": subscription.account_id,
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "paid_date": paid_date,
                    "amount": round(float(amount), 2),
                    "status": status,
                }
            )
            invoice_number += 1
            invoice_date = invoice_date + pd.DateOffset(months=cadence_months)

    return pd.DataFrame(rows)


def _generate_support_tickets(
    rng: np.random.Generator,
    accounts: pd.DataFrame,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    ticket_number = 1

    for account in accounts.itertuples(index=False):
        control = ARCHETYPE_CONTROLS[account.synthetic_archetype]
        months_active = max(1, ceil((end_ts - account.created_date).days / 30))
        base_rate = {"smb": 0.06, "mid_market": 0.13, "enterprise": 0.25}[account.segment]
        ticket_count = int(rng.poisson(months_active * base_rate * control.ticket_multiplier))
        if account.synthetic_archetype in {"support_frustrated", "implementation_risk"}:
            ticket_count = max(1, ticket_count)

        for _ in range(ticket_count):
            created_at = _random_timestamp(rng, account.created_date, _end_of_day(end_ts))
            priority = _ticket_priority(rng, control.ticket_multiplier)
            resolved = rng.random() < (0.84 if priority in {"low", "medium"} else 0.72)
            status = _choice(rng, ("resolved", "closed")) if resolved else "open"
            resolved_at = (
                min(created_at + pd.Timedelta(hours=int(rng.integers(4, 24 * 21))), _end_of_day(end_ts))
                if resolved
                else pd.NaT
            )
            rows.append(
                {
                    "ticket_id": f"tkt_{ticket_number:08d}",
                    "account_id": account.account_id,
                    "created_at": created_at,
                    "resolved_at": resolved_at,
                    "priority": priority,
                    "category": _ticket_category(rng, account.synthetic_archetype),
                    "status": status,
                    "csat_score": _csat_score(rng, account.synthetic_archetype) if resolved else np.nan,
                }
            )
            ticket_number += 1

    return pd.DataFrame(rows)


def _generate_crm_touchpoints(
    rng: np.random.Generator,
    accounts: pd.DataFrame,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    touchpoint_number = 1

    for account in accounts.itertuples(index=False):
        months_active = max(1, ceil((end_ts - account.created_date).days / 30))
        base_rate = {"smb": 0.07, "mid_market": 0.17, "enterprise": 0.34}[account.segment]
        touchpoint_count = int(rng.poisson(months_active * base_rate))
        if account.segment == "enterprise":
            touchpoint_count = max(2, touchpoint_count)
        elif account.segment == "mid_market":
            touchpoint_count = max(1, touchpoint_count)

        for _ in range(touchpoint_count):
            touchpoint_type = _touchpoint_type(rng, account.synthetic_archetype)
            rows.append(
                {
                    "touchpoint_id": f"crm_{touchpoint_number:08d}",
                    "account_id": account.account_id,
                    "touchpoint_date": _random_date(rng, account.created_date, end_ts),
                    "team": _touchpoint_team(rng, touchpoint_type),
                    "touchpoint_type": touchpoint_type,
                    "outcome": _touchpoint_outcome(rng, touchpoint_type),
                }
            )
            touchpoint_number += 1

    return pd.DataFrame(rows)


def _ordered_frame(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    return frame.reindex(columns=REQUIRED_COLUMNS[table])


def _choice(
    rng: np.random.Generator,
    values: tuple[str, ...],
    p: tuple[float, ...] | np.ndarray | None = None,
) -> str:
    return str(rng.choice(values, p=p))


def _balanced_values(
    values: tuple[str, ...],
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    repeated = np.resize(np.array(values, dtype=object), n)
    rng.shuffle(repeated)
    return repeated


def _size_band_for_segment(rng: np.random.Generator, segment: str) -> str:
    if segment == "enterprise":
        return _choice(rng, ALLOWED_VALUES["company_size_band"], p=(0.00, 0.03, 0.25, 0.43, 0.29))
    if segment == "mid_market":
        return _choice(rng, ALLOWED_VALUES["company_size_band"], p=(0.02, 0.36, 0.49, 0.12, 0.01))
    return _choice(rng, ALLOWED_VALUES["company_size_band"], p=(0.64, 0.30, 0.06, 0.00, 0.00))


def _initial_plan_for_segment(rng: np.random.Generator, segment: str) -> str:
    if segment == "enterprise":
        return _choice(rng, ALLOWED_VALUES["plan"], p=(0.00, 0.07, 0.36, 0.57))
    if segment == "mid_market":
        return _choice(rng, ALLOWED_VALUES["plan"], p=(0.08, 0.42, 0.39, 0.11))
    return _choice(rng, ALLOWED_VALUES["plan"], p=(0.52, 0.36, 0.11, 0.01))


def _user_archetype_multiplier(archetype: str) -> float:
    return {
        "low_adoption": 0.65,
        "implementation_risk": 0.75,
        "expansion_ready": 1.25,
        "healthy_growing": 1.15,
    }.get(archetype, 1.0)


def _month_starts(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DatetimeIndex:
    first_month = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=1)
    return pd.date_range(first_month, end_ts, freq="MS")


def _seasonal_factor(month: int, enabled: bool) -> float:
    if not enabled:
        return 1.0
    if month in {1, 4, 9, 10}:
        return 1.65
    if month in {6, 7, 12}:
        return 0.65
    return 1.0


def _event_value(rng: np.random.Generator, event_type: str) -> int:
    if event_type == "api_call":
        return int(rng.integers(25, 501))
    if event_type == "integration_sync":
        return int(rng.integers(2, 31))
    if event_type == "workflow_run":
        return int(rng.integers(1, 16))
    if event_type == "report_export":
        return int(rng.integers(1, 8))
    return 1


def _initial_mrr(rng: np.random.Generator, plan: str, segment: str) -> float:
    segment_multiplier = {"smb": 0.85, "mid_market": 1.25, "enterprise": 2.00}[segment]
    noise = float(rng.lognormal(mean=0.0, sigma=0.18))
    return round(PLAN_MRR[plan] * segment_multiplier * noise, 2)


def _subscription_row(
    number: int,
    account_id: str,
    plan: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    mrr: float,
    billing_period: str,
    status: str,
) -> dict[str, object]:
    return {
        "subscription_id": f"sub_{number:07d}",
        "account_id": account_id,
        "plan": plan,
        "start_date": start_date,
        "end_date": end_date,
        "mrr": round(mrr, 2),
        "billing_period": billing_period,
        "status": status,
    }


def _renewal_outcome(rng: np.random.Generator, account: object) -> str:
    control = ARCHETYPE_CONTROLS[account.synthetic_archetype]
    segment_expansion = {"smb": 0.85, "mid_market": 1.05, "enterprise": 1.20}[account.segment]
    segment_churn = {"smb": 1.20, "mid_market": 0.90, "enterprise": 0.70}[account.segment]
    churn = min(0.30, 0.085 * control.churn_multiplier * segment_churn * float(rng.uniform(0.75, 1.35)))
    expanded = min(0.32, 0.145 * control.expansion_multiplier * segment_expansion * float(rng.uniform(0.75, 1.25)))
    contracted = min(0.24, 0.105 * control.billing_friction * float(rng.uniform(0.75, 1.25)))
    flat = max(0.10, 1.0 - churn - expanded - contracted)
    probs = np.array([flat, expanded, contracted, churn], dtype=float)
    probs = probs / probs.sum()
    return _choice(rng, ALLOWED_VALUES["renewal_outcome"], p=probs)


def _new_mrr_for_outcome(rng: np.random.Generator, previous_mrr: float, outcome: str) -> float:
    if outcome == "churned":
        return 0.0
    if outcome == "renewed_expanded":
        return previous_mrr * float(rng.uniform(1.12, 1.65))
    if outcome == "renewed_contracted":
        return previous_mrr * float(rng.uniform(0.62, 0.90))
    return previous_mrr * float(rng.uniform(0.97, 1.05))


def _plan_after_renewal(rng: np.random.Generator, current_plan: str, outcome: str) -> str:
    index = PLAN_ORDER.index(current_plan)
    if outcome == "renewed_expanded" and index < len(PLAN_ORDER) - 1 and rng.random() < 0.36:
        return PLAN_ORDER[index + 1]
    if outcome == "renewed_contracted" and index > 0 and rng.random() < 0.22:
        return PLAN_ORDER[index - 1]
    return current_plan


def _invoice_status(
    rng: np.random.Generator,
    billing_friction: float,
    invoice_date: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> str:
    unresolved_recent_invoice = invoice_date + pd.Timedelta(days=30) > end_ts and rng.random() < 0.20
    if unresolved_recent_invoice:
        return "open"

    failed = min(0.13, 0.028 * billing_friction)
    void = min(0.04, 0.008 * billing_friction)
    open_probability = min(0.11, 0.020 * billing_friction)
    paid = max(0.70, 1.0 - failed - void - open_probability)
    probs = np.array([paid, open_probability, failed, void], dtype=float)
    probs = probs / probs.sum()
    return _choice(rng, ALLOWED_VALUES["invoice_status"], p=probs)


def _ticket_priority(rng: np.random.Generator, ticket_multiplier: float) -> str:
    high_weight = min(0.30, 0.09 * ticket_multiplier)
    urgent_weight = min(0.16, 0.025 * ticket_multiplier)
    low_weight = max(0.22, 0.46 - high_weight / 2)
    medium_weight = max(0.25, 1.0 - low_weight - high_weight - urgent_weight)
    probs = np.array([low_weight, medium_weight, high_weight, urgent_weight], dtype=float)
    probs = probs / probs.sum()
    return _choice(rng, ALLOWED_VALUES["ticket_priority"], p=probs)


def _ticket_category(rng: np.random.Generator, archetype: str) -> str:
    if archetype == "price_sensitive":
        return _choice(rng, ALLOWED_VALUES["ticket_category"], p=(0.42, 0.10, 0.15, 0.13, 0.08, 0.12))
    if archetype == "implementation_risk":
        return _choice(rng, ALLOWED_VALUES["ticket_category"], p=(0.08, 0.13, 0.20, 0.24, 0.10, 0.25))
    if archetype == "support_frustrated":
        return _choice(rng, ALLOWED_VALUES["ticket_category"], p=(0.13, 0.28, 0.12, 0.17, 0.20, 0.10))
    return _choice(rng, ALLOWED_VALUES["ticket_category"])


def _csat_score(rng: np.random.Generator, archetype: str) -> int:
    if archetype in {"support_frustrated", "implementation_risk"}:
        probs = (0.14, 0.22, 0.31, 0.23, 0.10)
    elif archetype == "healthy_growing":
        probs = (0.02, 0.06, 0.18, 0.34, 0.40)
    else:
        probs = (0.04, 0.09, 0.25, 0.36, 0.26)
    return int(rng.choice(np.arange(1, 6), p=probs))


def _touchpoint_type(rng: np.random.Generator, archetype: str) -> str:
    if archetype == "expansion_ready":
        return _choice(rng, ALLOWED_VALUES["touchpoint_type"], p=(0.13, 0.21, 0.16, 0.32, 0.06, 0.12))
    if archetype in {"support_frustrated", "low_adoption", "implementation_risk", "price_sensitive"}:
        return _choice(rng, ALLOWED_VALUES["touchpoint_type"], p=(0.23, 0.12, 0.19, 0.06, 0.28, 0.12))
    return _choice(rng, ALLOWED_VALUES["touchpoint_type"], p=(0.20, 0.22, 0.19, 0.15, 0.10, 0.14))


def _touchpoint_team(rng: np.random.Generator, touchpoint_type: str) -> str:
    if touchpoint_type == "expansion_discussion":
        return _choice(rng, ALLOWED_VALUES["touchpoint_team"], p=(0.64, 0.24, 0.02, 0.10))
    if touchpoint_type in {"onboarding", "training", "business_review"}:
        return _choice(rng, ALLOWED_VALUES["touchpoint_team"], p=(0.05, 0.72, 0.12, 0.11))
    if touchpoint_type == "risk_review":
        return _choice(rng, ALLOWED_VALUES["touchpoint_team"], p=(0.10, 0.65, 0.20, 0.05))
    return _choice(rng, ALLOWED_VALUES["touchpoint_team"])


def _touchpoint_outcome(rng: np.random.Generator, touchpoint_type: str) -> str:
    if touchpoint_type == "expansion_discussion":
        return _choice(rng, ALLOWED_VALUES["touchpoint_outcome"], p=(0.36, 0.06, 0.18, 0.30, 0.04, 0.06))
    if touchpoint_type == "risk_review":
        return _choice(rng, ALLOWED_VALUES["touchpoint_outcome"], p=(0.25, 0.07, 0.24, 0.03, 0.28, 0.13))
    return _choice(rng, ALLOWED_VALUES["touchpoint_outcome"], p=(0.55, 0.07, 0.20, 0.05, 0.04, 0.09))


def _random_date(
    rng: np.random.Generator,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.Timestamp:
    days = max(0, (end_ts - start_ts).days)
    return start_ts + pd.Timedelta(days=int(rng.integers(0, days + 1)) if days else 0)


def _random_timestamp(
    rng: np.random.Generator,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.Timestamp:
    seconds = max(0, int((end_ts - start_ts).total_seconds()))
    offset = int(rng.integers(0, seconds + 1)) if seconds else 0
    return start_ts + pd.Timedelta(seconds=offset)


def _end_of_day(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
