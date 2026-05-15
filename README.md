# product-growth

`product-growth` is a public, local-first portfolio project for a production
style SaaS account health system. The intended system converts synthetic B2B
SaaS account, usage, billing, support, renewal, and CRM activity into churn
risk scores, expansion propensity scores, account health bands, recommended GTM
actions, model metrics, local score observability summaries, and RevOps-facing
output tables.

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
contracts, baselines, evaluation, observability, and deterministic policy
rules.

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
- Model, baseline, calibration, segment, fixed-holdout, and temporal robustness
  metrics.
- Local batch scoring observability summaries for scored synthetic
  populations.
- RevOps-readable account score and recommendation tables.

## GTM Operating System

The operating thesis is that model outputs should become part of a commercial
workflow, not sit in isolation. The project separates:

- Source data contracts and account-month feature construction.
- Independent churn and expansion modeling.
- Credible rule baselines before ML.
- Layered evaluation using capacity, fixed holdouts, holdout-month robustness,
  economic utility, calibration, and segment robustness.
- Champion selection based on operating metrics, not ROC AUC alone.
- Deterministic policy rules that map scores into health bands and GTM actions.
- Batch outputs and score observability summaries that RevOps could review.

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
  -> score observability summaries
  -> deterministic policy layer
  -> RevOps-facing output tables
```

Implementation uses the Python package `src/account_health`. Package 2 adds the
local DuckDB raw/source warehouse. Package 3 adds the point-in-time
`mart.account_month` table with renewal-based labels and MVP feature families.
Package 4 adds deterministic rule baselines. Package 5 introduces candidate
model training with scikit-learn and local MLflow tracking. Package 6 adds
local layered evaluation and target-specific champion selection. Package 7
defines local MLflow registry promotion for eligible Package 6-selected ML
champions.

## Evaluation Philosophy

The project will use fixed time splits and holdout-month robustness checks
instead of random splits. Full rolling retraining backtests are outside the
Package 6 MVP unless actual rolling retraining is implemented later. Churn and
expansion will be modeled independently with global models, then evaluated
across segments. Evaluation will emphasize GTM operating questions:

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
- Package 4: commercial rule baseline benchmark artefacts. Complete.
- Package 5: candidate model training with MLflow. Complete.
- Package 6: layered evaluation and champion selection. Complete.
- Package 7: local MLflow registry and model promotion. Complete.
- Package 8: local batch scoring deployment. Complete.
- Package 9: local batch scoring observability.
- Package 10: deterministic GTM policy outputs, public examples, and polish.

## Current Status

Package -1, Package 0, Package 1, Package 2, Package 3, Package 4, Package 5,
Package 6, Package 7, and Package 8 are complete.
Package 1 adds deterministic synthetic source-table generation and a local
CSV-writing CLI. Package 2 adds a local DuckDB raw/source warehouse loader,
minimal load audit, and source-table contract validation. Package 3 adds
`mart.account_month`, renewal-based `churn_90d` and `expansion_90d` labels,
point-in-time MVP features, leakage tests, and local feature build audit.
Package 4 adds `mart.account_month_baselines`, deterministic churn and
expansion rule baseline scores, component columns, rank and decile helpers, a
local rebuild command, and minimal baseline build audit. Package 5 adds
candidate churn and expansion model training with logistic regression and
random forest pipelines, fixed temporal splits, simple validation metrics, and
local MLflow run logging. Package 6 adds fixed-holdout evaluation, top-K
operating metrics, baseline comparison, ML-only calibration checks, segment and
holdout-month robustness slices, illustrative utility sensitivity, local
evaluation tables, and a generated champion selection manifest. Package 7 adds
local MLflow registry promotion for eligible Package 6-selected ML champions,
target-specific registered model names, the `champion` alias, model-version
lineage tags, a local promotion manifest, and minimal promotion audit metadata.
Package 8 adds raw local account-month batch scoring from promoted champions,
score output tables, append-only scoring audit metadata, and optional ignored
local raw exports. There is currently no health-band policy, GTM action layer,
dashboards, notebooks, cloud deployment, or committed generated output.

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

Build the ignored local rule baseline benchmark table with:

```bash
make build-rule-baselines
```

The build creates or replaces `mart.account_month_baselines` from
`mart.account_month` and appends a local audit row to
`metadata.baseline_build_audit`.

Train ignored local candidate model runs with:

```bash
make train-candidate-models
```

The training workflow reads `mart.account_month`, trains churn and expansion
candidate models, and logs local MLflow runs and model artefacts under ignored
tracking/artifact paths. It does not require Package 4 baselines and does not
write scoring output tables.

Evaluate ignored local Package 5 candidate runs against Package 4 rule
baselines with:

```bash
make evaluate-candidate-models
```

The evaluation workflow reads existing local MLflow runs and model artefacts,
scores only the fixed Package 5 holdout, writes ignored local files under
`data/outputs/model_evaluation/`, and creates local evaluation summary tables
in DuckDB. It does not retrain missing candidates, use the MLflow registry,
promote models, deploy models, create production scoring outputs, create health
bands, or recommend GTM actions.

Package 7 uses the Package 6 champion-selection manifest to promote eligible
ML champions into the local MLflow registry. The registry contract is documented
in `docs/model_registry.md`. Package 7 uses target-specific registered model
names and a `champion` alias for future Package 8 local batch scoring
consumption; it does not score accounts, deploy models, create health bands, or
recommend GTM actions.

Promote eligible local champions with:

```bash
make promote-model-registry
```

The promotion workflow reads the ignored Package 6 manifest, validates the
referenced Package 5 MLflow run and model artefact, writes local MLflow
registry metadata, writes
`data/outputs/model_registry/promotion_manifest.json`, and appends
`metadata.model_promotion_audit` in the local DuckDB warehouse. These are local
artefacts and must not be committed.

## Local Checks

```bash
make setup
make public-safety-check
make test
make verify
```
