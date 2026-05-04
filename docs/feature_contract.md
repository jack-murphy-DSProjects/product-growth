# Feature Contract

## Status

Package 3 implements the account-month modelling contract defined in Package
3A.

The implemented output table is:

- `mart.account_month`

The local build command is:

```bash
make build-account-month
```

## Output Table

Package 3 creates:

- `mart.account_month`

The table is the analytical modelling table for churn risk and expansion
propensity.

## Modeling Grain

Primary grain:

- `account_id`
- `observation_month`

One row represents one active subscribed account x one calendar observation
month.

`observation_month` must be the first day of the calendar month.

`observation_month_end` must be the last day of that calendar month.

The row means:

> What was known about this account as of `observation_month_end`.

No Package 3 unit may change this row grain without human review.

## Feature Cutoff

Features may use only source records known on or before
`observation_month_end`.

General rule:

```text
feature source date <= observation_month_end
```

Labels may use future windows, but those future windows must be excluded from
all feature inputs.

## Label Horizon

Package 3 labels use a 90-day future horizon.

General rule:

```text
event_date > observation_month_end
event_date <= observation_month_end + 90 days
```

No Package 3 unit may change the horizon without human review.

## Eligible Population

Account-month rows should represent active subscribed accounts as of
`observation_month_end`.

Eligibility rules:

- Accounts already churned before or on `observation_month_end` are not
  eligible for account-month rows.
- Observation months must have a complete 90-day future label horizon available.
- Minimum account age is 30 days for the MVP.
- Churn labels apply to eligible active subscribed account-month rows.
- Expansion labels apply only to retained active accounts.
- If an account churns inside the 90-day horizon, then `churn_90d = 1`,
  `expansion_90d = NULL`, and `is_expansion_label_eligible = false`.

Expected label eligibility fields:

- `is_churn_label_eligible`
- `is_expansion_label_eligible`

## Labels

### `churn_90d`

Canonical source:

- `raw.renewals`

Positive label when all of the following are true:

```text
renewals.renewal_date > observation_month_end
renewals.renewal_date <= observation_month_end + 90 days
renewals.outcome = 'churned'
```

Churn is renewal-based churn. It is not same-month subscription status and not
usage inactivity.

### `expansion_90d`

Canonical source:

- `raw.renewals`

Positive label when all of the following are true:

```text
renewals.renewal_date > observation_month_end
renewals.renewal_date <= observation_month_end + 90 days
renewals.outcome = 'renewed_expanded'
renewals.new_mrr > renewals.previous_mrr
```

Expansion is renewal-based paid MRR expansion. It is not seat expansion, usage
growth, CRM opportunity creation, plan movement, or generic upsell intent.

## Null Label Policy

Expected label fields:

- `churn_90d`
- `expansion_90d`

Ineligible label rows must use `NULL` labels, not `0`.

Eligible label rows must have binary labels.

For retained active accounts with no expansion event in the 90-day horizon,
`expansion_90d` should be `0` only when
`is_expansion_label_eligible = true`.

For churn-in-horizon rows:

- `churn_90d = 1`
- `is_expansion_label_eligible = false`
- `expansion_90d = NULL`

## Source Table Roles

Package 3 source roles are:

- `raw.renewals` is canonical for `churn_90d` and `expansion_90d`.
- `raw.subscriptions` is a current and historical subscription-state feature
  source.
- `raw.invoices` is a billing feature source, not the canonical expansion label
  source.
- `raw.crm_touchpoints` is a GTM activity feature source, not label truth.
- `raw.support_tickets` is a support feature source.
- `raw.usage_events` is a product usage feature source.
- `raw.users` may support user, admin, and adoption feature families.
- `raw.accounts` may support account lifecycle and segment feature families.
- `raw.accounts.synthetic_archetype` is generator/debug metadata and must be
  excluded from modelling features.

## Expected Feature Families

- Account lifecycle: age, tenure, onboarding stage, renewal proximity, and
  lifecycle status.
- Segment attributes: company size, industry, region, plan tier, sales motion,
  and customer tier.
- Usage and engagement: active users, event volume, product breadth, frequency,
  recency, stickiness, and usage trends.
- Adoption: activated users, feature adoption, seat utilization, admin activity,
  and multi-stakeholder coverage.
- Billing and subscription: ARR, plan changes, seat changes, invoice status,
  payment delay, discounts, and contract state.
- Support: ticket volume, severity mix, unresolved issues, resolution time, and
  escalation patterns.
- CRM activity: sales touches, CS touches, executive engagement, renewal
  preparation, campaign interactions, and contact coverage.
- Historical outcomes: prior churn, contraction, expansion, or renewal outcomes
  when they are known before the snapshot month.

## Leakage Doctrine

Forbidden as Package 3 features:

- `raw.accounts.synthetic_archetype`.
- Future `raw.renewals.outcome`, `previous_mrr`, or `new_mrr`.
- Future subscription status, end-state, MRR, or plan values before their
  effective date.
- Future invoices, invoice amounts, payment statuses, paid dates, or failed
  payments.
- Future support tickets or support resolutions.
- Support resolution time where `resolved_at > observation_month_end`.
- Future CRM touchpoints or outcomes.
- Any latent or generator-only controls if they ever surface.

All Package 3B onward units must restate the relevant leakage and eligibility
rules before changing code.

## Package 3 Exclusions

Package 3 must not add:

- Model training.
- MLflow experiments.
- Model registry.
- Champion model selection.
- Rule baselines.
- Health bands.
- Recommended GTM actions.
- Batch scoring.
- Monitoring reports.
- Dashboards.
- APIs.
- Cloud deployment.
- Vercel.
- dbt.
- Real SaaS integrations.
- Real customer data.
- Incremental orchestration.

## Deterministic Transformations

Feature transformations should be deterministic for a given synthetic dataset
and snapshot configuration. Aggregations, windows, thresholds, categorical
mappings, and default values should be documented and tested.

## Null Handling

Null handling must be explicit. Package 3 records whether missing values mean
not applicable, no observed activity, unknown source value, or synthetic
generation gap. Any later imputation used for modeling should be recorded in
the feature contract before model training begins.

## Package 3D MVP Feature Columns

Package 3D implements a deliberately small point-in-time feature set on
`mart.account_month`.

Static account fields:

- `industry`
- `region`
- `segment`
- `company_size_band`
- `acquisition_channel`
- `account_age_days`

Current subscription fields as of `observation_month_end`:

- `current_plan`
- `current_mrr`
- `current_billing_period`
- `subscription_age_days`

Trailing usage fields:

- `usage_event_count_30d`
- `usage_event_count_90d`
- `usage_event_count_180d`
- `active_user_count_30d`
- `active_user_count_90d`
- `active_user_count_180d`
- `usage_event_value_sum_90d`

Support fields:

- `support_ticket_count_30d`
- `support_ticket_count_90d`
- `support_ticket_count_180d`
- `high_priority_ticket_count_90d`
- `open_ticket_count`
- `avg_resolution_hours_known`
- `days_since_last_ticket`

Billing fields:

- `invoice_count_90d`
- `invoice_count_180d`
- `invoice_amount_sum_90d`
- `invoice_amount_sum_180d`
- `unpaid_invoice_count_90d`
- `failed_invoice_count_90d`
- `overdue_invoice_count`
- `avg_payment_delay_days_known`
- `days_since_last_invoice`

CRM fields:

- `crm_touchpoint_count_30d`
- `crm_touchpoint_count_90d`
- `crm_touchpoint_count_180d`
- `sales_touchpoint_count_90d`
- `cs_touchpoint_count_90d`
- `days_since_last_crm_touchpoint`

Null semantics:

- Count and sum features default to `0` when no qualifying records are known by
  `observation_month_end`.
- Recency fields are `NULL` when no qualifying historical record exists.
- Average resolution hours uses only support tickets resolved on or before
  `observation_month_end`; it is `NULL` when no such ticket exists.
- Average payment delay uses only invoices paid on or before
  `observation_month_end`; it is `NULL` when no such invoice exists.
- `synthetic_archetype` remains excluded from `mart.account_month`.

## Segment Evaluation Readiness

The feature table should include stable segment fields needed for robustness
checks. These fields should support evaluation by account size, lifecycle stage,
plan tier, region, industry, sales motion, and other synthetic GTM segments.

## Later Contract Requirements

Later packages should define:

- Model feature lists selected from `mart.account_month`.
- Training-time imputation behavior, if any.
- Segment columns required for evaluation and reporting.
- Any model-specific exclusion list for labels, identifiers, or audit fields.

## Package 3 Validation Categories

Package 3 includes focused validations for:

- `mart.account_month` existence.
- One row per `account_id`, `observation_month`.
- `observation_month` and `observation_month_end` calendar semantics.
- Active subscribed account eligibility as of `observation_month_end`.
- Complete 90-day future label horizon.
- Minimum 30-day account age.
- Churn and expansion label definitions from `raw.renewals`.
- Ineligible labels stored as `NULL`, not `0`.
- Expansion label ineligibility when churn occurs inside the horizon.
- Feature cutoff enforcement by source date.
- Exclusion of `synthetic_archetype` and other generator-only fields.
- Source-role boundaries for renewals, invoices, CRM touchpoints, support,
  usage, subscriptions, users, and accounts.
- Absence of Package 3 out-of-scope outputs such as models, scores, MLflow
  runs, baselines, dashboards, or monitoring reports.
