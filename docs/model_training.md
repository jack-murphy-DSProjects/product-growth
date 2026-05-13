# Model Training Contract

## Status

Package 5 implements local candidate model training with scikit-learn and
local MLflow tracking.

Package 5 creates training code, a local CLI, and a Make target. MLflow runs
and model artefacts are generated local artefacts and must not be committed.
Package 5 does not create scoring outputs or new warehouse tables.

## Purpose

Package 5 introduces local, reproducible, auditable candidate model training
for account churn risk and expansion propensity.

Package 5 trains candidate models from the existing account-month mart and logs
candidate runs to local MLflow tracking.

Package 5 is an intermediate training package. It does not choose production
models or create final account scores.

## Source Table

Package 5 reads from:

- `mart.account_month`

Package 5 must not read raw source tables.

Package 5 must not mutate `mart.account_month`.

## Modelling Grain

The modelling grain is the Package 3 account-month grain:

- `account_id`
- `observation_month`

One modelling row represents one active subscribed account x one calendar
observation month.

`observation_month_end` may be carried for audit and validation, but it is not
a model feature.

## Target Models

Package 5 trains two independent model tasks:

- Churn model using `churn_90d`.
- Expansion model using `expansion_90d`.

The churn and expansion models are independent. Package 5 must not train a
combined multi-output model.

## Label Eligibility

Package 5 respects the Package 3 label contract.

Rows with `NULL` labels are excluded for the relevant target:

- Churn training excludes rows where `churn_90d IS NULL`.
- Expansion training excludes rows where `expansion_90d IS NULL`.

`NULL` labels must not be converted to zero.

Eligible target labels must be binary.

## Temporal Split

Package 5 uses a fixed temporal train/test split by `observation_month`.

Train rows:

```text
observation_month <= train_end_month
```

Test rows:

```text
observation_month > train_end_month
```

The split must be deterministic and must not be random.

The default `train_end_month` may be derived as the maximum eligible
`observation_month` for the target minus 3 months.

The CLI allows an explicit override:

```bash
scripts/train_candidate_models.py --train-end-month YYYY-MM-01
```

Package 5B or later implementation must reject empty train or test splits.

## Approved Feature Policy

Package 5 uses explicit approved feature allowlists.

Approved feature names must come from existing `mart.account_month` columns.

Codex must not invent feature names.

Package 5 must not infer features by selecting every non-target column.

Broad approved feature groups are limited to the Package 3 point-in-time
feature families already present in `mart.account_month`:

- Static account features.
- Current subscription features.
- Usage trailing-window features.
- Support trailing-window features.
- Billing trailing-window features.
- CRM trailing-window features.

Package 4 baseline outputs are benchmarks only. They are not model features.

Approved categorical features:

- `industry`
- `region`
- `segment`
- `company_size_band`
- `acquisition_channel`
- `current_plan`
- `current_billing_period`

Approved numeric features:

- `account_age_days`
- `current_mrr`
- `subscription_age_days`
- `usage_event_count_30d`
- `usage_event_count_90d`
- `usage_event_count_180d`
- `active_user_count_30d`
- `active_user_count_90d`
- `active_user_count_180d`
- `usage_event_value_sum_90d`
- `support_ticket_count_30d`
- `support_ticket_count_90d`
- `support_ticket_count_180d`
- `high_priority_ticket_count_90d`
- `open_ticket_count`
- `avg_resolution_hours_known`
- `days_since_last_ticket`
- `invoice_count_90d`
- `invoice_count_180d`
- `invoice_amount_sum_90d`
- `invoice_amount_sum_180d`
- `unpaid_invoice_count_90d`
- `failed_invoice_count_90d`
- `overdue_invoice_count`
- `avg_payment_delay_days_known`
- `days_since_last_invoice`
- `crm_touchpoint_count_30d`
- `crm_touchpoint_count_90d`
- `crm_touchpoint_count_180d`
- `sales_touchpoint_count_90d`
- `cs_touchpoint_count_90d`
- `days_since_last_crm_touchpoint`

## Forbidden Feature Policy

Package 5 must reject leakage-prone or forbidden features.

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

## Candidate Models

Package 5 MVP candidate models are:

- Logistic regression.
- Random forest.

Package 5 uses scikit-learn only.

Package 5 must not add XGBoost, LightGBM, neural networks, hosted model
services, serving dependencies, or cloud dependencies in the MVP.

## Preprocessing Policy

Package 5 preprocessing must be explicit and reproducible.

Expected preprocessing:

- Numeric imputation.
- Categorical imputation.
- One-hot encoding for categorical features.
- Unknown-category handling for categorical features.
- Scaling where appropriate, such as for logistic regression.

Preprocessing must be part of the model pipeline or otherwise logged so a
candidate run can be reproduced locally.

## MLflow Logging Contract

Package 5 uses local MLflow tracking.

Experiment name:

- `account-health-candidate-training`

Package 5 logs one MLflow run per target and candidate model.

Expected run dimensions:

- target: `churn_90d` or `expansion_90d`
- candidate model: logistic regression or random forest

Each run must log:

- Parameters.
- Row counts.
- Positive rates.
- Split config.
- Feature lists.
- Simple validation metrics.
- Model artefact.

Split config should include at minimum:

- `train_end_month`
- train row count
- test row count
- train observation-month range
- test observation-month range

Feature list logging should include:

- approved feature names used
- numeric feature names
- categorical feature names

Package 5 must not use MLflow registry APIs.

Package 5 must not promote models.

Package 7 may later register a Package 5 model artefact only when Package 6 has
selected that ML candidate as the target champion and Package 7 validation has
confirmed the source run and artefact are present and loadable. Package 7 must
not mutate Package 5 source runs or model artefacts during promotion.

## Simple Metrics

Package 5 reports simple validation metrics only.

Required metrics:

- ROC AUC.
- Average precision.
- Log loss.
- Brier score.
- Accuracy.

Additional metric:

- Precision at top 10%.

Package 5 does not select a champion model.

Package 5 does not perform full layered Package 6 evaluation.

Package 5 logs the local candidate runs, feature metadata, split metadata, and
model artefacts that Package 6 later consumes for fixed holdout evaluation.
Package 6 should fail clearly when required runs or artefacts are missing
rather than silently retraining candidates.

## CLI

Package 5 adds:

- `scripts/train_candidate_models.py`
- `make train-candidate-models`

CLI arguments:

- `--warehouse-path`
- `--train-end-month`
- `--experiment-name`
- `--mlflow-tracking-uri`
- `--random-state`

Default Make usage:

```bash
make train-candidate-models
```

The local prerequisite flow remains:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
```

Package 5 training does not require `make build-rule-baselines`.

## Package Boundaries And Non-goals

Package 5 trains candidate models only.

Package 5 must not:

- Select a champion model.
- Register models in the MLflow registry.
- Promote models.
- Deploy models.
- Batch score accounts.
- Create final account scores.
- Create account health bands.
- Create recommended GTM actions.
- Perform fixed holdout layered Package 6 evaluation.
- Perform holdout-month robustness checks.
- Perform full rolling retraining backtests.
- Perform economic utility sensitivity.
- Perform segment robustness checks.
- Use Package 4 baseline scores as model features.
- Mutate `mart.account_month`.
- Read raw source tables.
- Create production scoring output tables.
- Add dashboards, notebooks, APIs, hosted services, or cloud dependencies.
- Use real company or customer data.

Package 6 owns layered evaluation and champion selection.

Package 7 owns MLflow registry and promotion.

Package 8 owns batch scoring deployment.

Package 9 owns monitoring.

## Expected Implementation Units

Package 5 implementation remains split into these units:

- Package 5A - docs and dependency contract.
- Package 5B - dataset and feature guards.
- Package 5C - temporal split.
- Package 5D - candidates and metrics.
- Package 5E - MLflow orchestration.
- Package 5F - CLI, Make target, and docs closeout.
