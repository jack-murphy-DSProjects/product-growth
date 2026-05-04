# Data Contract

## Status

Package 1 defines deterministic synthetic source-table contracts as CSV and
DataFrame contracts.

Package 2 persists those source tables into the local DuckDB `raw` schema and
validates source-level contracts. Account-month feature contracts, labels,
scores, and model outputs are reserved for later packages.

## Safety Statement

All generated records are synthetic and created locally. The repository must not
commit production records, credentials, generated datasets, local databases,
model artefacts, MLflow runs, notebooks, dashboards, reports, or temporary
outputs.

## Source Tables

| Table | Grain | Primary key |
| --- | --- | --- |
| `accounts` | One row per synthetic account | `account_id` |
| `users` | One row per synthetic user | `user_id` |
| `usage_events` | One row per synthetic product event | `event_id` |
| `subscriptions` | One row per subscription period or plan state | `subscription_id` |
| `invoices` | One row per invoice | `invoice_id` |
| `support_tickets` | One row per support ticket | `ticket_id` |
| `crm_touchpoints` | One row per CRM interaction | `touchpoint_id` |
| `renewals` | One row per renewal event or opportunity | `renewal_id` |

## Required Columns

### accounts

Required columns:
`account_id`, `account_name`, `created_date`, `industry`, `region`, `segment`,
`company_size_band`, `acquisition_channel`, `initial_plan`,
`synthetic_archetype`.

Rules:

- `account_id` is unique and non-null.
- `account_name` uses neutral generated names such as
  `Synthetic Account 000001`.
- `created_date` is inside the requested generation window.
- `synthetic_archetype` is generator metadata for audit/debugging and is not an
  approved modelling feature.

### users

Required columns:
`user_id`, `account_id`, `created_date`, `role_type`, `is_admin`.

Rules:

- `user_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `created_date` is on or after the account `created_date` and on or before
  the generation end date.
- Each default account has at least one user, with an admin user where
  practical.

### usage_events

Required columns:
`event_id`, `account_id`, `user_id`, `event_timestamp`, `event_type`,
`event_value`.

Rules:

- `event_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `user_id` references `users.user_id` and belongs to the same account.
- `event_timestamp` is inside the requested generation window and on or after
  both account and user creation dates.
- `event_value` is non-negative.

### subscriptions

Required columns:
`subscription_id`, `account_id`, `plan`, `start_date`, `end_date`, `mrr`,
`billing_period`, `status`.

Rules:

- `subscription_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `start_date` is on or after the account `created_date`.
- `end_date`, when present, is on or after `start_date`.
- `mrr` is non-negative.

### invoices

Required columns:
`invoice_id`, `account_id`, `invoice_date`, `due_date`, `paid_date`, `amount`,
`status`.

Rules:

- `invoice_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `due_date` is on or after `invoice_date`.
- `paid_date`, when present, is on or after `invoice_date`.
- `paid_date` is null for `open`, `failed`, and `void` invoices.
- `amount` is non-negative.

### support_tickets

Required columns:
`ticket_id`, `account_id`, `created_at`, `resolved_at`, `priority`,
`category`, `status`, `csat_score`.

Rules:

- `ticket_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `resolved_at`, when present, is on or after `created_at`.
- `csat_score`, when present, is between 1 and 5.

### crm_touchpoints

Required columns:
`touchpoint_id`, `account_id`, `touchpoint_date`, `team`, `touchpoint_type`,
`outcome`.

Rules:

- `touchpoint_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `touchpoint_date` is on or after the account `created_date` and on or before
  the generation end date.

### renewals

Required columns:
`renewal_id`, `account_id`, `renewal_date`, `outcome`, `previous_mrr`,
`new_mrr`.

Rules:

- `renewal_id` is unique and non-null.
- `account_id` references `accounts.account_id`.
- `renewal_date` is inside the requested generation window and on or after the
  account `created_date`.
- `previous_mrr` and `new_mrr` are non-negative.
- For `churned` renewals, `new_mrr` is `0`.
- Default churn and expansion rates are expected to be plausible, with each
  between 5% and 35% for the default generator run.

## Allowed Values

| Field | Allowed values |
| --- | --- |
| `industry` | `software`, `financial_services`, `healthcare`, `education`, `retail`, `manufacturing`, `professional_services`, `media` |
| `region` | `north_america`, `europe`, `asia_pacific`, `latin_america` |
| `segment` | `smb`, `mid_market`, `enterprise` |
| `company_size_band` | `1_50`, `51_200`, `201_1000`, `1001_5000`, `5001_plus` |
| `acquisition_channel` | `inbound`, `partner`, `outbound`, `product_led`, `event` |
| `plan` / `initial_plan` | `starter`, `growth`, `business`, `enterprise` |
| `synthetic_archetype` | `healthy_growing`, `steady_retained`, `low_adoption`, `support_frustrated`, `seasonal`, `expansion_ready`, `price_sensitive`, `implementation_risk` |
| `role_type` | `admin`, `manager`, `contributor`, `viewer`, `analyst`, `developer` |
| `event_type` | `login`, `dashboard_view`, `report_export`, `workflow_run`, `integration_sync`, `api_call`, `seat_invited` |
| `billing_period` | `monthly`, `annual` |
| `subscription.status` | `active`, `ended`, `cancelled` |
| `invoice.status` | `paid`, `open`, `failed`, `void` |
| `support_tickets.priority` | `low`, `medium`, `high`, `urgent` |
| `support_tickets.category` | `billing`, `bug`, `how_to`, `integration`, `performance`, `implementation` |
| `support_tickets.status` | `open`, `resolved`, `closed` |
| `crm_touchpoints.team` | `sales`, `customer_success`, `support`, `growth` |
| `crm_touchpoints.touchpoint_type` | `onboarding`, `business_review`, `renewal_check_in`, `expansion_discussion`, `risk_review`, `training` |
| `crm_touchpoints.outcome` | `completed`, `no_show`, `follow_up_needed`, `opportunity_created`, `risk_identified`, `resolved` |
| `renewals.outcome` | `renewed_flat`, `renewed_expanded`, `renewed_contracted`, `churned` |

## Foreign Keys

| Child table | Child key | Parent table | Parent key |
| --- | --- | --- | --- |
| `users` | `account_id` | `accounts` | `account_id` |
| `usage_events` | `account_id` | `accounts` | `account_id` |
| `usage_events` | `user_id` | `users` | `user_id` |
| `subscriptions` | `account_id` | `accounts` | `account_id` |
| `invoices` | `account_id` | `accounts` | `account_id` |
| `support_tickets` | `account_id` | `accounts` | `account_id` |
| `crm_touchpoints` | `account_id` | `accounts` | `account_id` |
| `renewals` | `account_id` | `accounts` | `account_id` |

## Out Of Scope Until Later Packages

- Account-month features.
- Churn or expansion labels.
- Model training, scores, health bands, or GTM recommendations.
- Dashboards, notebooks, APIs, Vercel, cloud deployment, and MLflow runs.
