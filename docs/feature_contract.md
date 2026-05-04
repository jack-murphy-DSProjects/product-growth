# Feature Contract

## Status

Package 3 implements the account-month modelling contract defined in Package
3A. Package 4 implements deterministic rule baseline benchmark artefacts from
`mart.account_month`.

The implemented output tables are:

- `mart.account_month`
- `mart.account_month_baselines`

The local build commands are:

```bash
make build-account-month
make build-rule-baselines
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

## Package 4 Baseline Contract

Package 4 creates deterministic, interpretable rule baselines as benchmark
artefacts for later ML packages.

Package 4 source table:

- `mart.account_month`

Package 4 output table:

- `mart.account_month_baselines`

Primary grain is the same account-month grain as `mart.account_month`:

- `account_id`
- `observation_month`

`observation_month_end` should be carried through to the output table for
auditability.

Baseline scores are heuristic benchmark scores. They are not calibrated
probabilities, production risk scores, final health bands, or GTM actions.

Required baseline score fields:

- `baseline_churn_score`
- `baseline_expansion_score`

Forbidden scoring inputs:

- `churn_90d`
- `expansion_90d`
- `accounts.synthetic_archetype`
- `synthetic_archetype`
- any generator-only field, latent control, or future outcome field

Package 4 may carry labels through only for validation or later evaluation
contracts when explicitly documented. Labels must not influence score
calculation.

Component columns should exist for auditability. Components should make the
rule score explainable at row level and should be named so churn and expansion
components are clearly separated.

Expected prioritisation helper fields:

- `baseline_churn_rank`
- `baseline_expansion_rank`
- `baseline_churn_decile`
- `baseline_expansion_decile`

Ranks and deciles are prioritisation helpers for later comparison. They are not
capacity decisions, account health policy, recommended GTM actions, or champion
selection outputs.

Package 4E validates that these helper fields remain bounded helpers on the
baseline output table and do not introduce policy-layer outputs.

Package 4 must not mutate `mart.account_month`. Baselines must be built as a
separate additive table.

The local Package 4 build command is:

```bash
make build-rule-baselines
```

The command creates or replaces `mart.account_month_baselines` and appends one
minimal local audit row to `metadata.baseline_build_audit`.

### Package 4B Approved Baseline Inputs

Package 4B approves only point-in-time feature columns already present in
`mart.account_month` as baseline scoring inputs.

Carry-through identifiers and dates:

- `account_id`
- `observation_month`
- `observation_month_end`

Approved scoring input columns:

- Account and segment: `account_age_days`, `industry`, `region`, `segment`,
  `company_size_band`, `acquisition_channel`
- Subscription: `current_plan`, `current_mrr`, `current_billing_period`,
  `subscription_age_days`
- Usage: `usage_event_count_30d`, `usage_event_count_90d`,
  `usage_event_count_180d`, `active_user_count_30d`,
  `active_user_count_90d`, `active_user_count_180d`,
  `usage_event_value_sum_90d`
- Support: `support_ticket_count_30d`, `support_ticket_count_90d`,
  `support_ticket_count_180d`, `high_priority_ticket_count_90d`,
  `open_ticket_count`, `avg_resolution_hours_known`,
  `days_since_last_ticket`
- Billing: `invoice_count_90d`, `invoice_count_180d`,
  `invoice_amount_sum_90d`, `invoice_amount_sum_180d`,
  `unpaid_invoice_count_90d`, `failed_invoice_count_90d`,
  `overdue_invoice_count`, `avg_payment_delay_days_known`,
  `days_since_last_invoice`
- CRM: `crm_touchpoint_count_30d`, `crm_touchpoint_count_90d`,
  `crm_touchpoint_count_180d`, `sales_touchpoint_count_90d`,
  `cs_touchpoint_count_90d`, `days_since_last_crm_touchpoint`

Explicitly excluded from scoring:

- Identifiers and dates: `account_id`, `observation_month`,
  `observation_month_end`, `account_created_date`
- Label and eligibility fields: `is_churn_label_eligible`,
  `is_expansion_label_eligible`, `churn_90d`, `expansion_90d`
- Generator-only fields: `accounts.synthetic_archetype`,
  `synthetic_archetype`
- Baseline audit fields: `baseline_version`, `baseline_created_at_utc`

Null handling for baseline components:

- Count and sum inputs keep the Package 3 `0` defaults when no known records
  exist.
- Recency fields that are `NULL` mean no known historical event and must be
  handled explicitly by any component using that field.
- Known average fields that are `NULL` mean no qualifying known value and must
  be handled explicitly by any component using that field.
- Categorical nulls should score neutrally unless a later Package 4 unit
  documents a deterministic component rule.

Component naming:

- Churn component columns use the `baseline_churn_component_*` prefix.
- Expansion component columns use the `baseline_expansion_component_*` prefix.
- Component values are bounded numeric contributions or explicitly documented
  helper values.

Score bounds:

- `baseline_churn_score` must be bounded between `0` and `100`.
- `baseline_expansion_score` must be bounded between `0` and `100`.

### Package 4C Churn Baseline

The deterministic churn baseline is a commercial risk heuristic. It is not a
calibrated probability.

Churn score field:

- `baseline_churn_score`

Churn component columns:

- `baseline_churn_component_usage_risk`
- `baseline_churn_component_support_risk`
- `baseline_churn_component_billing_risk`
- `baseline_churn_component_relationship_risk`
- `baseline_churn_component_subscription_risk`

The churn score is the bounded sum of the churn component columns. Components
use approved Package 4B inputs only. The churn label fields
`is_churn_label_eligible`, `is_expansion_label_eligible`, `churn_90d`, and
`expansion_90d` must not be referenced by the churn score calculation.

Churn component assumptions:

- Low recent usage, low active-user coverage, and declining recent activity
  increase churn benchmark risk.
- High-priority support load, unresolved support work, and long known
  resolution times increase churn benchmark risk.
- Failed, unpaid, overdue, or slow-paid invoices increase churn benchmark risk.
- Missing or stale CRM/customer-success engagement increases churn benchmark
  risk.
- Lower-commitment subscription context, such as starter plans, monthly
  billing, young subscriptions, and very low MRR, increases churn benchmark
  risk.

### Package 4D Expansion Baseline

The deterministic expansion baseline is a commercial readiness heuristic. It is
not a calibrated probability, a sales-qualified lead rule, or a recommended GTM
action.

Expansion score field:

- `baseline_expansion_score`

Expansion component columns:

- `baseline_expansion_component_usage_strength`
- `baseline_expansion_component_commercial_fit`
- `baseline_expansion_component_gtm_engagement`
- `baseline_expansion_component_low_friction`
- `baseline_expansion_component_maturity`

The expansion score is the bounded sum of the expansion component columns.
Components use approved Package 4B inputs only. The label fields
`is_churn_label_eligible`, `is_expansion_label_eligible`, `churn_90d`, and
`expansion_90d` must not be referenced by the expansion score calculation.

Expansion component assumptions:

- Strong product usage, active-user depth, usage value, and current-period
  usage strength increase expansion benchmark readiness.
- Commercial fit is higher when the account has plan headroom, meaningful MRR,
  larger segment or company-size context, and annual billing.
- Recent sales, customer-success, and CRM engagement increase expansion
  benchmark readiness.
- Low billing friction and low unresolved support burden increase expansion
  benchmark readiness.
- Mature accounts and subscriptions with remaining plan headroom increase
  expansion benchmark readiness.

### Package 4F Baseline Audit

Package 4 creates:

- `metadata.baseline_build_audit`

This table records one row per local baseline rebuild with build ID, UTC build
time, source table, output table, baseline version, row counts, observation
month bounds, and status.

The audit table is local build metadata only. It is not model metadata,
MLflow, a registry, orchestration state, monitoring output, model evaluation,
or champion-selection evidence.

## Package 5 Modelling Feature Policy

Package 5 trains candidate churn and expansion models from `mart.account_month`
using explicit approved feature allowlists.

Approved feature names must come from existing `mart.account_month` columns.
Codex must not invent feature names.

Package 5 must not infer modelling features by selecting every non-target
column.

Broad approved feature groups are limited to existing Package 3 point-in-time
feature families:

- Static account features.
- Current subscription features.
- Usage trailing-window features.
- Support trailing-window features.
- Billing trailing-window features.
- CRM trailing-window features.

Labels are not features.

Eligibility flags are not features.

Identifiers and observation dates are not features:

- `account_id`
- `observation_month`
- `observation_month_end`

`synthetic_archetype` is never a modelling feature.

Package 4 baseline scores, ranks, deciles, and components are benchmark
outputs only. They are not Package 5 model features.

Forbidden exact fields:

- `account_id`
- `observation_month`
- `observation_month_end`
- `churn_90d`
- `expansion_90d`
- any eligibility flags
- `synthetic_archetype`
- `baseline_*`

Forbidden feature name terms:

- `renewal`
- `outcome`
- `future`
- `label`
- `target`
- `score`
- `rank`
- `decile`

The forbidden term policy applies to any column containing the term.

## Later Contract Requirements

Later packages should define:

- Exact Package 5 model feature allowlists selected from existing
  `mart.account_month` columns.
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
