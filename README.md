# product-growth

`product-growth` is a public, local-first portfolio project for a production
style SaaS account health system. The intended system converts synthetic B2B
SaaS account, usage, billing, support, renewal, and CRM activity into churn
risk scores, expansion propensity scores, account health bands, recommended GTM
actions, model metrics, monitoring reports, and RevOps-facing output tables.

The project is designed to show how a Commercial Data Scientist or Growth Data
Scientist would turn model outputs into an operating process for Sales, Customer
Success, Growth, and RevOps. It is not a Kaggle-style modeling exercise and it
is not a hosted product. The core deliverable is a reproducible local batch ML
workflow whose outputs can be inspected, evaluated, and used to drive GTM
prioritization.

## Why It Exists

AI-native B2B SaaS teams need to decide where limited GTM capacity should go:
which accounts deserve save motions, which are ready for expansion, which need
CS intervention, and which recommendations should be suppressed because the
evidence is weak. A score by itself does not answer those questions. This
project treats scoring as one layer inside a broader decision system with
contracts, baselines, evaluation, monitoring, and deterministic policy rules.

## Users Served

- Sales: prioritize expansion conversations and commercial follow-up.
- Customer Success: identify accounts needing proactive retention work.
- Growth: understand adoption patterns that create expansion readiness.
- RevOps: convert scores into reliable tables, segments, thresholds, and action
  queues.
- Data teams: demonstrate reproducible, public-safe ML engineering practices.

## Planned Outputs

- `churn_risk_score`: probability-like score for near-term churn risk.
- `expansion_propensity_score`: probability-like score for near-term expansion.
- `account_health_band`: deterministic policy output such as healthy, watch,
  or at-risk.
- `recommended_gtm_action`: deterministic action recommendation for GTM teams.
- Model, baseline, calibration, segment, and backtest metrics.
- Local monitoring reports for data, feature, prediction, and recommendation
  drift.
- RevOps-readable account score and recommendation tables.

## GTM Operating System

The operating thesis is that model outputs should become part of a commercial
workflow, not sit in isolation. The project separates:

- Source data contracts and account-month feature construction.
- Independent churn and expansion modeling.
- Credible rule baselines before ML.
- Layered evaluation using capacity, monthly backtests, economic utility,
  calibration, and segment robustness.
- Champion selection based on operating metrics, not ROC AUC alone.
- Deterministic policy rules that map scores into health bands and GTM actions.
- Batch outputs and monitoring reports that RevOps could review.

Health bands and recommended actions are policy-layer outputs. They are not
trained as standalone targets.

## Intended Architecture

The target architecture is local and batch oriented:

```text
synthetic SaaS sources
  -> DuckDB analytical warehouse
  -> account-month feature table
  -> churn and expansion labels
  -> rule baselines
  -> candidate ML models
  -> layered evaluation
  -> MLflow champion registry
  -> batch scoring
  -> deterministic policy layer
  -> RevOps-facing output tables
  -> monitoring reports
```

Implementation uses the Python package `src/account_health`. Package 2 adds the
local DuckDB raw/source warehouse. Package 3 adds the point-in-time
`mart.account_month` table with renewal-based labels and MVP feature families.
MLflow remains planned for a later package.

## Evaluation Philosophy

The project will use fixed time splits and rolling monthly backtests instead of
random splits. Churn and expansion will be modeled independently with global
models, then evaluated across segments. Evaluation will emphasize GTM operating
questions:

- Does ML beat credible commercial rule baselines?
- Which accounts should fit within limited weekly CS or Sales capacity?
- How stable are metrics month over month?
- Are scores calibrated enough to support thresholding?
- Do important segments receive robust performance?
- How sensitive is utility to different churn-save and expansion-value
  assumptions?

ROC AUC can be reported, but it will not be the sole champion selection metric.

## Public Repo Safety

This repository is public-safe by design.

- Synthetic data only.
- No production customer records, secrets, private paths, or local credentials.
- No generated datasets, DuckDB files, MLflow runs, model artefacts, notebooks,
  reports, or dashboards committed by default.
- Local-only agent controls use ignored files; committed templates use the
  `.example` suffix.
- Cloud deployment, hosted APIs, Vercel, and production integrations are out of
  scope.

Run `make public-safety-check` before committing.

## Package Roadmap

- Package -1: public repo boundary, agent harness, safety rules, and package
  plan. Complete.
- Package 0: repo skeleton, public narrative, initial docs, and package smoke
  test. Complete.
- Package 1: deterministic synthetic SaaS source data generator. Complete.
- Package 2: DuckDB warehouse and table contracts. Complete.
- Package 3: account-month features and labels. Complete.
- Package 4: commercial rule baseline benchmark artefacts.
- Package 5: candidate model training with MLflow.
- Package 6: layered evaluation and champion selection.
- Package 7: MLflow registry and model promotion.
- Package 8: local batch scoring deployment.
- Package 9: local monitoring and observability reports.
- Package 10: public repo polish and safe examples.

## Current Status

Package -1, Package 0, Package 1, Package 2, and Package 3 are complete.
Package 1 adds deterministic synthetic source-table generation and a local
CSV-writing CLI. Package 2 adds a local DuckDB raw/source warehouse loader,
minimal load audit, and source-table contract validation. Package 3 adds
`mart.account_month`, renewal-based `churn_90d` and `expansion_90d` labels,
point-in-time MVP features, leakage tests, and local feature build audit. There
is currently no baseline scoring implementation, MLflow tracking, model
training, final scoring logic, dashboards, notebooks, cloud deployment, or
committed generated output.

## Synthetic Source Data

Generate ignored local CSVs with:

```bash
make generate-synthetic-data
```

The default run writes `accounts`, `users`, `usage_events`, `subscriptions`,
`invoices`, `support_tickets`, `crm_touchpoints`, and `renewals` CSVs under
`data/generated/`. See `docs/synthetic_data.md` and `docs/data_contract.md` for
Package 1 details.

Load ignored local CSVs into the ignored local DuckDB warehouse with:

```bash
make load-warehouse
```

The default warehouse path is `data/warehouse/account_health.duckdb`. See
`docs/warehouse.md` for the Package 2 warehouse contract.

Build the ignored local account-month modelling table with:

```bash
make build-account-month
```

The build creates or replaces `mart.account_month` and appends a local audit row
to `metadata.feature_build_audit`.

## Local Checks

```bash
make setup
make public-safety-check
make test
make verify
```
