# Data Contract

## Status

Package 1 defines deterministic synthetic source-table contracts as CSV and
DataFrame contracts.

Package 2 persists those source tables into the local DuckDB `raw` schema and
validates source-level contracts. Package 3 creates `mart.account_month`.
Package 4 prepares deterministic rule baseline contracts from
`mart.account_month`. Package 6 may create local model evaluation summary
tables. Package 7 may create minimal local model-promotion audit metadata.
Package 8 plans raw local batch scoring outputs only.

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

## Package 3 Source-Role Clarification

Package 3 will build `mart.account_month` from the persisted `raw` source
tables. Package 3A documents these roles only; it does not create the mart
table.

Package 3-facing source roles:

- `raw.renewals` is the canonical label source for `churn_90d` and
  `expansion_90d`.
- `raw.subscriptions` supports point-in-time subscription features, but future
  status, end-state, MRR, and plan values must not leak before their effective
  dates.
- `raw.invoices` supports billing features and is not the canonical expansion
  label source.
- `raw.crm_touchpoints` supports GTM touchpoint features and is not label truth.
- `raw.accounts.synthetic_archetype` is generator/debug metadata and is excluded
  from modelling features.

## Package 4 Mart Contract

Package 4 builds rule baseline benchmark artefacts from `mart.account_month`.
It must not change the source `mart.account_month` table.

### `mart.account_month_baselines`

Grain:

- One row per `mart.account_month` row.

Primary grain:

- `account_id`
- `observation_month`

Minimum expected columns:

- `account_id`
- `observation_month`
- `observation_month_end`
- `baseline_churn_score`
- `baseline_expansion_score`
- `baseline_churn_rank`
- `baseline_expansion_rank`
- `baseline_churn_decile`
- `baseline_expansion_decile`
- `baseline_churn_component_usage_risk`
- `baseline_churn_component_support_risk`
- `baseline_churn_component_billing_risk`
- `baseline_churn_component_relationship_risk`
- `baseline_churn_component_subscription_risk`
- `baseline_expansion_component_usage_strength`
- `baseline_expansion_component_commercial_fit`
- `baseline_expansion_component_gtm_engagement`
- `baseline_expansion_component_low_friction`
- `baseline_expansion_component_maturity`
- `baseline_version`
- `baseline_created_at_utc`

Column rules:

- `baseline_churn_score` and `baseline_expansion_score` are deterministic,
  bounded heuristic benchmark scores.
- Scores are not calibrated probabilities and are not final policy outputs.
- Component columns must be sufficient to audit why the deterministic score
  moved for a row.
- Churn component columns should use a clear churn-specific naming convention.
- Expansion component columns should use a clear expansion-specific naming
  convention.
- Ranks and deciles are prioritisation helpers only.
- `churn_90d` and `expansion_90d` must not be scoring inputs.
- `accounts.synthetic_archetype` and `synthetic_archetype` must not be scoring
  inputs.
- The output must preserve one-row-per-account-month parity with
  `mart.account_month`.

Package 4 approved scoring inputs are limited to the documented Package 3
point-in-time feature families already present in `mart.account_month`:

- Account and segment fields.
- Current subscription fields.
- Trailing usage fields.
- Support fields.
- Billing fields.
- CRM touchpoint fields.

Identifier fields, observation dates, label fields, label eligibility fields,
generator-only fields, and baseline audit fields are not approved scoring
inputs. In particular, `churn_90d`, `expansion_90d`, and
`synthetic_archetype` must not influence either baseline score.

### `metadata.baseline_build_audit`

Package 4 creates minimal local audit metadata for baseline builds.

Minimum expected columns if created:

- `build_id`
- `built_at_utc`
- `source_table`
- `output_table`
- `baseline_version`
- `row_count`
- `account_count`
- `min_observation_month`
- `max_observation_month`
- `status`

This table is local audit metadata only. It is not model metadata, an MLflow
replacement, a model registry, an orchestration state store, or a monitoring
report.

## Package 6 Evaluation Contract

Package 6 evaluates Package 5 candidate models and Package 4 rule baselines.
It must not change `mart.account_month` or `mart.account_month_baselines`.

Package 6 may create these minimal local tables:

- `metadata.model_evaluation_audit`
- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

Optional detail tables require implementation justification:

- `mart.model_topk_evaluation`
- `mart.model_segment_evaluation`
- `mart.model_calibration_summary`
- `mart.model_utility_sensitivity`

These tables are local evaluation outputs only. They are not production scoring
outputs, health-band tables, recommended-action tables, model registry tables,
deployment records, monitoring reports, or real customer data.

### `metadata.model_evaluation_audit`

Grain:

- One row per local Package 6 evaluation run.

Minimum expected columns if created:

- `evaluation_id`
- `evaluated_at_utc`
- `evaluation_version`
- `warehouse_path`
- `experiment_name`
- `train_end_month`
- `target_count`
- `candidate_count`
- `status`

### `mart.model_evaluation_summary`

Grain:

- One row per evaluation run x target x candidate or baseline x metric slice.

Minimum expected columns if created:

- `evaluation_id`
- `target`
- `model_family`
- `candidate_type`
- `mlflow_run_id`
- `score_source`
- `metric_name`
- `metric_value`
- `slice_type`
- `slice_value`
- `row_count`
- `positive_count`
- `base_positive_rate`
- `k_value`
- `k_type`
- `evaluation_version`
- `created_at_utc`

Column rules:

- `candidate_type` should distinguish ML candidates from rule baselines.
- `score_source` should identify whether the row uses ML probabilities or
  baseline ranking scores.
- Baseline rows must not use log loss, Brier score, or calibration-bin metric
  names in the MVP.

### `mart.model_champion_selection`

Grain:

- One row per evaluation run x target.

Minimum expected columns if created:

- `evaluation_id`
- `target`
- `selected_champion_model_family`
- `mlflow_run_id`
- `model_artifact_uri`
- `selection_status`
- `primary_metric`
- `key_topk_metrics`
- `comparison_versus_baseline`
- `calibration_caveats`
- `segment_caveats`
- `temporal_caveats`
- `utility_caveats`
- `synthetic_data_caveat`
- `evaluation_version`
- `created_at_utc`

Column rules:

- `selection_status` must support baseline-retained, insufficient-evidence, and
  no-ML-candidate-sufficiently-beats-baseline outcomes.
- `mlflow_run_id` and `model_artifact_uri` may be null when the selected
  champion is not an ML candidate.
- Champion rows do not create MLflow registry aliases or production scoring
  configuration.

### Optional detail tables

Optional detail tables may break out top-K, segment, calibration, and utility
records if `mart.model_evaluation_summary` becomes too dense.

They must preserve the same Package 6 restrictions:

- local evaluation only
- no production scoring
- no health bands
- no recommended GTM actions
- no registry or promotion metadata
- no real customer data

## Package 7 Registry And Promotion Contract

Package 7 promotes eligible Package 6-selected ML champions into the local
MLflow model registry. It must not change `mart.account_month`,
`mart.account_month_baselines`, Package 5 source MLflow runs, or Package 6
evaluation outputs.

Package 7 may create this minimal local audit table:

- `metadata.model_promotion_audit`

Package 7 also writes a generated local promotion manifest under:

- `data/outputs/model_registry/promotion_manifest.json`

The promotion manifest is a generated local artefact, not a committed data
contract file.

### `metadata.model_promotion_audit`

Grain:

- One row per promotion attempt x target.

Minimum expected columns if created:

- `promotion_id`
- `promoted_at_utc`
- `promotion_version`
- `target_key`
- `target_label`
- `registered_model_name`
- `model_version`
- `alias`
- `source_mlflow_run_id`
- `source_model_artifact_uri`
- `package6_manifest_path`
- `package6_evaluation_version`
- `package6_selection_status`
- `promotion_status`
- `failure_reason`

Column rules:

- `target_key` must be `churn` or `expansion`.
- `target_label` must be `churn_90d` or `expansion_90d`.
- `registered_model_name` must be `account_health_churn_model` or
  `account_health_expansion_model`.
- The main alias is `champion`.
- Baseline-retained, no-ML-champion, and insufficient-evidence outcomes must
  not create registered MLflow model versions.

This table is local promotion audit metadata only. It is not an MLflow
replacement, production scoring table, deployment record, monitoring report,
health-band table, recommended-action table, or real customer data.

## Planned Package 8 Raw Batch Scoring Contract

Package 8 plans raw local scoring outputs from Package 7-promoted MLflow
champion models. This section documents expected grain and purpose only. It
does not imply these tables already exist.

Package 8 planned tables:

- `mart.account_month_scores`
- `metadata.batch_scoring_audit`

Package 8 scoring outputs are raw score outputs only. They are not health-band
tables, recommended-action tables, monitoring reports, dashboards, hosted API
state, cloud deployment records, model evaluation summaries, or model registry
metadata.

### `mart.account_month_scores`

Expected grain:

- One row per scored account x scoring month for a scoring run.

Purpose:

- Store raw churn and expansion model scores for selected
  `mart.account_month` rows.
- Preserve the scored `account_id` and `observation_month` grain.
- Link score rows to the local scoring run and model versions used.

Column rules:

- Scores are raw model outputs bounded between 0 and 1.
- Score rows are not health bands, GTM actions, recommendations, monitoring
  alerts, or approved customer-facing outputs.
- Reruns are expected to replace rows for the selected scoring month, not
  append duplicate rows for the same account-month output.

### `metadata.batch_scoring_audit`

Expected grain:

- Append-only local audit metadata for each Package 8 scoring run, with
  target-specific model evidence recorded either per target or as structured
  run metadata.

Purpose:

- Record the selected scoring month, resolved model aliases and versions,
  source MLflow run evidence, feature metadata evidence, row counts, run
  status, and failure reason when applicable.
- Preserve rerun history even when score rows for a selected month are
  replaced.

Column rules:

- This table is audit metadata only.
- It is not a model registry replacement, orchestration framework, monitoring
  table, dashboard source, health-band table, recommended-action table, or real
  customer data.

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

## Out Of Scope For Package 4

- Model training and ML predictions.
- MLflow, model registry, and champion selection.
- Final account health bands or GTM recommendations.
- Dashboards, notebooks, APIs, Vercel, cloud deployment, monitoring reports,
  and real integrations.
- Mutating `mart.account_month`.
- Using labels, `accounts.synthetic_archetype`, or `synthetic_archetype` as
  baseline scoring inputs.

Package 3 builds account-month features and renewal-based labels from these
public synthetic source contracts. Package 4 builds separate baseline
benchmark artefacts from `mart.account_month`. Neither package changes the
Package 1 raw source schemas.
