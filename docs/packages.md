# Implementation Packages

## Package -1: Agent harness and repo safety

Goal:
Create the execution harness, security boundaries and package discipline before implementation begins.

Tasks:

- Create public `AGENTS.md`.
- Create private `AGENTS.override.md.example`.
- Create `.gitignore`.
- Create `.env.example`.
- Create `docs/project_contract.md`.
- Create `docs/context.md`.
- Create `docs/security.md`.
- Create `docs/runbook.md`.
- Create `docs/packages.md`.
- Create `docs/decisions.md`.
- Create `docs/out_of_scope.md`.
- Create strategy docs for training, evaluation, monitoring, deployment and RevOps usage.
- Create `.agent/current_execution_context.md.example`.
- Create `.agent/package_gate.md.example`.
- Create `.agent/agent_runbook.md.example`.
- Create public repo safety check script.
- Create safety check test.

Acceptance criteria:

- Public/private documentation boundary is defined.
- Generated artefacts are ignored.
- Secrets are not required.
- Stop conditions are documented.
- Package plan is visible to future agents.
- Grill-before-build protocol exists.
- TDD feedback loop is documented.
- Public repo safety check exists.
- No modelling code is added.

---

## Package 0: Repo skeleton and public narrative

Goal:
Create the project structure and public README narrative.

Status:
Complete.

Tasks:

- Create Python package structure.
- Keep Makefile commands limited to checks that actually work.
- Improve `README.md`.
- Create `docs/problem_framing.md`.
- Create `docs/architecture.md`.
- Create `docs/tradeoffs.md`.
- Create `docs/data_contract.md` placeholders.
- Create `docs/feature_contract.md` placeholder.
- Create `docs/model_card.md` template.
- Add basic package smoke test.

Acceptance criteria:

- `make test` runs.
- `make verify` passes.
- README explains the project clearly.
- Architecture is documented before implementation.
- No synthetic data generation yet.
- No model training yet.
- No generated output, local database, MLflow run, notebook, dashboard, API, or
  cloud deployment is added.

---

## Package 1: Synthetic SaaS data generator

Status:
Complete.

Goal:
Generate deterministic synthetic B2B SaaS source tables.

Tasks:

- Define synthetic account archetypes.
- Generate accounts.
- Generate users.
- Generate usage events.
- Generate subscriptions.
- Generate invoices.
- Generate support tickets.
- Generate CRM touchpoints.
- Generate renewals.
- Add seed-based reproducibility.
- Add validation checks for generated data.

Acceptance criteria:

- Data generation is deterministic.
- Primary keys are unique.
- Foreign keys are valid.
- Dates are valid.
- Churn and expansion rates are plausible.
- Source values are synthetic and public-safe.
- Generated CSVs remain ignored local files.
- DuckDB, account-month features, labels, models, scores, dashboards,
  notebooks, APIs, Vercel, and cloud deployment remain out of scope.

---

## Package 2 — DuckDB warehouse and source contract validation

**Status:** Complete

### Goal

Load generated synthetic SaaS source CSVs into a local DuckDB analytical warehouse and validate the source-table contracts before any modelling, feature engineering, labels, scoring, or RevOps outputs are built.

Package 2 establishes the raw/source persistence layer for the project.

### Scope

Package 2 creates a local DuckDB database at:

- `data/warehouse/account_health.duckdb`

The database contains raw source tables:

- `raw.accounts`
- `raw.users`
- `raw.usage_events`
- `raw.subscriptions`
- `raw.invoices`
- `raw.support_tickets`
- `raw.crm_touchpoints`
- `raw.renewals`

It may also contain minimal load metadata:

- `metadata.load_audit`

The loader reads existing generated CSVs from:

- `data/generated/`

Generation and loading are separate package responsibilities.

The Package 2 loader must fail clearly if required CSVs are missing.

### Required capabilities

Package 2 must:

- Load all Package 1 source CSVs into DuckDB.
- Use explicit `source_dir` and `database_path` arguments.
- Default to overwrite/rebuild behaviour rather than append/incremental loading.
- Create raw/source tables only.
- Validate required source files are present.
- Validate required source columns are present.
- Validate primary-key uniqueness.
- Validate foreign-key integrity.
- Validate basic date validity and date-ordering rules.
- Validate basic non-empty table expectations.
- Add tests using temporary generated data and temporary DuckDB files.
- Keep generated CSVs and DuckDB databases out of git.
- Update documentation to reflect the warehouse contract.

### Out of scope

Package 2 must not:

- Build account-month features.
- Create churn labels.
- Create expansion labels.
- Train models.
- Add MLflow logic.
- Score accounts.
- Create health bands.
- Create recommended GTM actions.
- Create monitoring reports.
- Add dashboards.
- Add notebooks.
- Add APIs.
- Add cloud deployment.
- Add Vercel.
- Add real SaaS integrations.
- Use real customer data.
- Add incremental loading.
- Add dbt, orchestration frameworks, or migration tooling.
- Commit generated CSVs, DuckDB files, MLflow artefacts, cache files, or live local agent files.

### Package 2 units

#### Package 2A — Warehouse contract and documentation

Define the Package 2 warehouse contract, paths, schemas, source table list, validation responsibilities, and exclusions.

Exit gate:

- `docs/warehouse.md` exists.
- `docs/agentic_execution.md` defines the autonomous package-gated loop.
- `docs/packages.md` reflects Package 2 scope.
- `docs/decisions.md` records Package 2 decisions.
- `.agent/current_execution_context.md.example` shows Package 2 activation.
- `.agent/package_gate.md.example` captures the Package 2 gate and stops.
- `.agent/agent_runbook.md.example` captures the autonomous unit workflow.
- No implementation beyond documentation and ignore-rule tightening unless strictly necessary.
- `.gitignore` protects `data/warehouse/`, `*.duckdb`, and `*.duckdb.wal`.
- Live local `.agent/*.md` files are not modified or tracked.
- No generated/local files are tracked.
- `make verify` passes.
- `git diff --check` passes.

#### Package 2B — Loader happy path

Implement the minimal warehouse loader and CLI.

Exit gate:

- Existing generated source CSVs can be loaded into temporary DuckDB database.
- All raw tables are created.
- Row counts match source CSV row counts.
- Minimal `metadata.load_audit` exists.
- Happy-path tests pass.
- `make verify` passes.
- `git diff --check` passes.

#### Package 2C — Source presence and schema validation

Add required file and required column validation.

Exit gate:

- Missing required source CSV fails clearly.
- Missing required source column fails clearly.
- Validation errors are structured or otherwise testable.
- Tests cover missing file and schema mismatch.
- `make verify` passes.
- `git diff --check` passes.

#### Package 2D — Relational and date validation

Add source-table integrity validation.

Exit gate:

- Duplicate primary keys fail validation.
- Broken foreign keys fail validation.
- Invalid date ordering fails validation.
- Validation remains limited to raw source contracts.
- No account-month, label, feature, model, scoring, health-band, recommendation, or monitoring logic is introduced.
- `make verify` passes.
- `git diff --check` passes.

#### Package 2E — Closeout and security review

Close the package.

Exit gate:

- `make verify` passes.
- `git diff --check` passes.
- Public repo safety check passes.
- Documentation is aligned.
- `.gitignore` protects generated/local artefacts.
- No generated CSVs, DuckDB files, `.duckdb.wal`, `mlruns`, cache folders, live `.agent` files, or private files are tracked.
- Package 3 has not started.

---

## Package 3: Account-month features and labels

Goal:
Build the point-in-time `mart.account_month` modelling table from raw DuckDB
source tables.

Status:
Package 3A is the docs-first contract and harness alignment unit. Package 3
feature-building implementation has not started beyond Package 3A
documentation.

Package 3 scope sentence:
Package 3 builds the account-month analytical modelling table only; it does not
train models, create baselines, score accounts, add health bands, create GTM
recommendations, or add dashboards, APIs, cloud deployment, MLflow, dbt, real
SaaS integrations, real customer data, or incremental orchestration.

Tasks:

- Define the durable `mart.account_month` contract.
- Define snapshot months.
- Build the account-month spine.
- Build renewal-based `churn_90d` and `expansion_90d` labels.
- Build account lifecycle features.
- Build usage features.
- Build adoption features.
- Build billing features.
- Build support features.
- Build CRM touchpoint features.
- Build renewal proximity features.
- Add leakage tests.

Acceptance criteria:

- Planned output table is `mart.account_month`.
- One row represents one active subscribed account x one calendar observation
  month.
- Primary grain is `account_id`, `observation_month`.
- `observation_month` is the first day of the calendar month.
- `observation_month_end` is the last day of that month.
- Features use only data available on or before `observation_month_end`.
- Labels use future 90-day outcomes after `observation_month_end`.
- `raw.renewals` is the canonical source for `churn_90d` and `expansion_90d`.
- Ineligible labels are `NULL`, not `0`.
- `raw.accounts.synthetic_archetype` is excluded from modelling features.
- No duplicate account-month rows exist.
- Leakage tests pass.
- Data contract docs are updated.
- Generated CSVs, DuckDB files, MLflow runs, cache folders, live `.agent`
  files, and private files remain untracked.

### Package 3 locked contract

Package 3 units must preserve:

- Account-month grain: one active subscribed account x one calendar observation
  month.
- Label horizon: 90 days after `observation_month_end`.
- Churn definition: renewal-based churn from `raw.renewals`.
- Expansion definition: renewal-based paid MRR expansion from `raw.renewals`.
- Expansion population: retained active accounts only.
- Label null policy: ineligible labels are `NULL`, not `0`.
- Feature leakage policy: future source records and generator-only fields are
  excluded from features.

### Package 3 units

#### Package 3A - Docs, contract, and harness update

Update durable docs and committed `.agent/*.example` templates so Package 3B
onward can be implemented without relying on prompt memory.

Exit gate:

- `docs/feature_contract.md` defines `mart.account_month`, row grain,
  observation month semantics, feature cutoff, label horizon, eligibility
  rules, labels, null-label policy, source roles, leakage rules, Package 3
  exclusions, and expected validation categories.
- `docs/data_contract.md` includes Package 3-facing source-role clarifications.
- `docs/warehouse.md` documents planned `mart.account_month` without implying
  it exists.
- `docs/packages.md` lists Package 3 slices and confirms implementation has not
  started beyond docs in Package 3A.
- `docs/agentic_execution.md` defines Package 3 autonomous execution rules.
- Committed `.agent/*.example` templates point to Package 3 and the 3A-3F unit
  structure.
- Live local `.agent/*.md` files are not modified or tracked.
- No code, scripts, Make targets, generated data, DuckDB loads, dependencies,
  or Package 3 feature-building tests are added.
- `make verify` passes.
- `git diff --check` passes.
- Public repo safety check passes.

#### Package 3B - Account-month spine

Implement the `mart.account_month` spine only.

Exit gate:

- `mart.account_month` exists.
- The table has one row per eligible `account_id`, `observation_month`.
- `observation_month` and `observation_month_end` have correct calendar
  semantics.
- Rows represent active subscribed accounts as of `observation_month_end`.
- Accounts churned before or on `observation_month_end` are excluded.
- Observation months have complete 90-day future label horizon available.
- Minimum account age is 30 days for the MVP.
- No labels, features, models, baselines, scores, dashboards, MLflow logic, or
  out-of-scope outputs are added.

#### Package 3C - Labels

Add renewal-based label eligibility and label columns only.

Exit gate:

- `is_churn_label_eligible`, `is_expansion_label_eligible`, `churn_90d`, and
  `expansion_90d` exist.
- `churn_90d` is positive only for `raw.renewals.outcome = 'churned'` inside
  the 90-day future horizon.
- `expansion_90d` is positive only for `raw.renewals.outcome =
  'renewed_expanded'` inside the 90-day future horizon where `new_mrr >
  previous_mrr`.
- Ineligible labels are `NULL`, not `0`.
- If an account churns inside the horizon, `churn_90d = 1`,
  `is_expansion_label_eligible = false`, and `expansion_90d = NULL`.
- No feature families, models, baselines, scores, dashboards, MLflow logic, or
  out-of-scope outputs are added.

#### Package 3D - Features

Add point-in-time feature families from approved source tables.

Exit gate:

- Features use only records known on or before `observation_month_end`.
- Source roles from `docs/feature_contract.md` are preserved.
- `raw.accounts.synthetic_archetype` is not exposed as a modelling feature.
- Feature null semantics are documented.
- No label definitions, row grain, horizon, models, baselines, scores,
  dashboards, MLflow logic, or out-of-scope outputs are changed.

#### Package 3E - Leakage hardening

Add explicit leakage checks and harden edge cases.

Exit gate:

- Leakage tests cover future renewals, subscriptions, invoices, support,
  CRM touchpoints, usage, and generator-only fields.
- Support resolution-time features exclude resolutions after
  `observation_month_end`.
- Ineligible label null policy is tested.
- Account-month uniqueness and cutoff checks pass.
- No Package 3 scope expansion is introduced.

#### Package 3F - CLI, audit, docs closeout

Add the approved Package 3 execution surface and close documentation.

Exit gate:

- Package 3 can rebuild `mart.account_month` through the approved local CLI or
  existing project command pattern.
- Any audit metadata remains local and public-safe.
- Documentation reflects the implemented table, features, labels, validations,
  and exclusions.
- `make verify`, `git diff --check`, and public repo safety checks pass.
- No generated CSVs, DuckDB files, MLflow runs, cache folders, live `.agent`
  files, private files, dashboards, APIs, cloud deployments, baselines, scoring
  outputs, or model artefacts are tracked.

---

## Package 4: Rule baselines

Goal:
Create commercial rule baselines before ML.

Tasks:

- Implement churn rule baseline.
- Implement expansion rule baseline.
- Score account-month rows using baseline logic.
- Evaluate baseline using top-K and monthly backtest.
- Document baseline assumptions.

Acceptance criteria:

- Baselines are credible, not strawmen.
- Baselines generate comparable scores or flags.
- Baseline metrics are saved.
- Baseline logic is documented.

---

## Package 5: Candidate model training with MLflow

Goal:
Train candidate churn and expansion models under a reproducible MLflow experiment setup.

Tasks:

- Implement fixed time split.
- Train logistic regression candidate.
- Train scikit-learn gradient boosting candidate.
- Optionally prepare XGBoost interface, but do not add unless explicitly approved.
- Log parameters to MLflow.
- Log metrics to MLflow.
- Log model artefacts to MLflow.
- Log feature list and training metadata.
- Save local metrics JSON.

Acceptance criteria:

- No random split.
- Models use account-month table only.
- Churn and expansion models are independent.
- Runs are logged to MLflow.
- Model signatures or input examples are logged where practical.
- Training is reproducible.

---

## Package 6: Layered evaluation and champion selection

Goal:
Evaluate candidate models through commercial operating metrics and select champions.

Tasks:

- Implement top-K capacity evaluation.
- Implement rolling monthly backtest.
- Implement baseline versus ML comparison.
- Implement economic utility sensitivity.
- Implement calibration checks.
- Implement segment robustness checks.
- Implement champion selection report.

Acceptance criteria:

- Top-K / capacity evaluation is implemented.
- Rolling monthly backtest is implemented.
- Economic utility sensitivity is implemented.
- Baseline versus ML comparison is implemented.
- Champion is not selected by ROC AUC alone.
- Candidate must beat baseline on operating metric.
- Evaluation outputs are saved.
- Training and evaluation strategy docs are updated.

---

## Package 7: MLflow registry and model promotion

Goal:
Register selected champion models and define the deployment contract.

Tasks:

- Register churn champion model.
- Register expansion champion model.
- Assign champion aliases.
- Store threshold config.
- Store feature set metadata.
- Implement model loading by alias.
- Document registry workflow.

Acceptance criteria:

- Scoring can load champion models.
- Registry metadata links model, features, thresholds and training period.
- Promotion criteria are documented.
- No manual hardcoding of local model paths in scoring logic.

---

## Package 8: Batch scoring deployment

Goal:
Create a production-style local batch scoring job.

Tasks:

- Load latest account-month scoring snapshot.
- Load champion models from MLflow.
- Validate scoring schema.
- Generate churn and expansion scores.
- Apply thresholds.
- Generate health bands.
- Generate GTM recommendations.
- Write `account_scores.csv`.
- Write `account_recommendations.csv`.
- Log scoring run metadata.

Acceptance criteria:

- Every eligible account receives scores.
- Scores are bounded between 0 and 1.
- Every account receives one health band.
- Every account receives one recommended action.
- Output tables are GTM-readable.
- Scoring run is reproducible.

---

## Package 9: Monitoring and observability

Goal:
Generate local monitoring artefacts for data, feature, prediction and operating drift.

Tasks:

- Add data quality checks.
- Add feature drift checks.
- Add prediction drift checks.
- Add recommendation volume checks.
- Add capacity breach warnings.
- Optionally add Evidently reports.
- Save `monitoring_report.json`.
- Document monitoring approach.

Acceptance criteria:

- Monitoring can compare current scoring data to training reference.
- Drift warnings are explainable.
- Capacity warnings are included.
- Monitoring outputs are saved locally.
- Docs explain what would be monitored in real production.

---

## Package 10: Public repo polish and examples

Goal:
Make the project GitHub-ready.

Tasks:

- Finalise README.
- Finalise model card.
- Finalise RevOps playbook.
- Finalise deployment doc.
- Finalise security doc.
- Create example outputs under `examples/outputs`.
- Ensure generated local artefacts are ignored.
- Run full test and pipeline suite.
- Review docs for public readability.

Acceptance criteria:

- A reviewer can understand the project in under five minutes.
- A technical reviewer can run the project locally.
- A commercial reviewer can understand the operating process.
- No secrets or local artefacts are committed.
- Full test suite passes.
