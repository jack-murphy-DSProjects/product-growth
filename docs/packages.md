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
Complete.

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
- Build MVP account lifecycle and segment features.
- Build MVP current subscription features.
- Build MVP usage trailing-window features.
- Build MVP billing trailing-window features.
- Build MVP support trailing-window features.
- Build MVP CRM touchpoint trailing-window features.
- Add leakage tests.
- Add a local CLI, Make target, and minimal feature build audit.

Acceptance criteria:

- Output table is `mart.account_month`.
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
- A local CLI and Make target can rebuild `mart.account_month`.
- `metadata.feature_build_audit` records local build metadata.
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

Status:
Complete.

Goal:
Create boring, deterministic, interpretable commercial rule baselines from
`mart.account_month` for future ML models to beat.

Package 4 creates benchmark artefacts. It does not create final policy outputs.

### Scope

Package 4 may create:

- `mart.account_month_baselines`
- optional minimal `metadata.baseline_build_audit`

Package 4 source table:

- `mart.account_month`

Package 4 must preserve:

- `mart.account_month` semantics.
- Account-month grain.
- Package 3 label semantics.
- Public-repo safety.
- Synthetic-data-only boundary.

Package 4 must not:

- Train ML models.
- Add MLflow.
- Add model registry logic.
- Perform champion selection.
- Create final account health bands.
- Create recommended GTM actions.
- Create monitoring reports.
- Add dashboards.
- Add APIs.
- Add cloud, Vercel, dbt, orchestration, or real SaaS integrations.
- Add dependencies.
- Use labels as scoring inputs.
- Use `accounts.synthetic_archetype` or `synthetic_archetype` as a scoring
  input.
- Mutate `mart.account_month`.
- Commit generated, local-only, private, or environment-specific files.

### Acceptance criteria

- Output table is `mart.account_month_baselines`.
- One output row exists per `mart.account_month` row.
- Primary grain is `account_id`, `observation_month`.
- `observation_month_end` is carried through for auditability.
- Baseline scores are deterministic and bounded.
- Baseline scores are heuristic benchmark scores, not calibrated
  probabilities.
- Churn and expansion component columns exist for auditability.
- Labels are not used in score calculation.
- `synthetic_archetype` is not used in score calculation.
- Baseline ranks and deciles are prioritisation helpers, not final GTM policy.
- Minimal audit metadata is local and public-safe.
- Documentation records baseline assumptions and exclusions.
- `make verify`, `git diff --check`, and public repo safety checks pass.
- No Package 5+ work appears.
- No generated CSVs, DuckDB files, MLflow runs, cache folders, live `.agent`
  files, private files, dashboards, APIs, cloud deployments, final scoring
  outputs, or model artefacts are tracked.

### Package 4 units

#### Package 4A - Docs, contract, and harness prep

Prepare durable docs and local harness context for Package 4. Do not implement
baseline scoring.

Exit gate:

- `docs/packages.md` defines Package 4 scope, exclusions, and 4A-4F units.
- `docs/feature_contract.md` defines the baseline source table, output table,
  grain, forbidden scoring inputs, auditability expectations, and rank/decile
  semantics.
- `docs/data_contract.md` prepares the `mart.account_month_baselines` and
  `metadata.baseline_build_audit` contracts.
- `docs/warehouse.md` documents `mart.account_month_baselines` as an additive
  mart table built from `mart.account_month`.
- `docs/decisions.md` records the baseline-as-benchmark decision.
- `docs/agentic_execution.md` explains live harness refresh requirements and
  stale active-package stop conditions.
- Committed `.agent/*.example` templates are aligned for the next active
  package and include stale-package pre-run checks.
- Live local `.agent/*.md` files are refreshed for Package 4 but remain
  ignored and untracked.
- No baseline implementation code, scripts, Make targets, generated data,
  DuckDB loads, dependencies, or Package 4 scoring tests are added.
- `make verify`, `git diff --check`, and public repo safety checks pass.

#### Package 4B - Baseline input contract

Define the exact approved input columns from `mart.account_month`, feature
families, null handling, component naming, score bounds, and forbidden inputs
for the baseline builder.

Exit gate:

- The approved Package 4 input list is documented and enforced.
- `churn_90d` and `expansion_90d` are excluded from scoring inputs.
- `synthetic_archetype` is excluded from scoring inputs.
- Identifier, date, audit, label, and generator-only fields are handled
  explicitly.
- No churn or expansion scoring logic is implemented beyond contract plumbing
  needed for the unit.

#### Package 4C - Churn baseline

Implement the deterministic churn rule baseline and its component columns.

Exit gate:

- `baseline_churn_score` is deterministic and bounded.
- Churn component columns exist and explain the score.
- The score uses only approved point-in-time inputs from `mart.account_month`.
- Churn labels are not used in score calculation.
- No expansion score, final health band, GTM action, ML, MLflow, or champion
  logic is introduced.

#### Package 4D - Expansion baseline

Implement the deterministic expansion rule baseline and its component columns.

Exit gate:

- `baseline_expansion_score` is deterministic and bounded.
- Expansion component columns exist and explain the score.
- The score uses only approved point-in-time inputs from `mart.account_month`.
- Expansion labels are not used in score calculation.
- No final health band, GTM action, ML, MLflow, or champion logic is
  introduced.

#### Package 4E - Validation and leakage tests

Add validation coverage for baseline grain, score bounds, determinism,
component presence, forbidden inputs, and output parity with
`mart.account_month`.

Exit gate:

- One output row exists per `mart.account_month` row.
- Output grain is unique on `account_id`, `observation_month`.
- Scores are bounded and deterministic.
- Component columns are present.
- Label columns are not used in scoring logic.
- `synthetic_archetype` is not used.
- No Package 5+ evaluation, ML training, MLflow, champion selection, policy,
  dashboard, API, monitoring, or cloud work is introduced.

#### Package 4F - CLI, audit, and docs closeout

Add the approved local execution surface, minimal audit metadata if useful, and
close Package 4 documentation.

Exit gate:

- Package 4 can rebuild `mart.account_month_baselines` through the approved
  local project command pattern.
- Optional `metadata.baseline_build_audit` remains minimal local audit
  metadata, not orchestration, monitoring, registry, or model metadata.
- Documentation reflects implemented baseline columns, assumptions,
  exclusions, validations, and commands.
- `make verify`, `git diff --check`, and public repo safety checks pass.
- No generated CSVs, DuckDB files, MLflow runs, cache folders, live `.agent`
  files, private files, dashboards, APIs, cloud deployments, final policy
  outputs, model artefacts, or Package 5+ work are tracked.

---

## Package 5: Candidate model training with MLflow

Goal:
Train local, reproducible candidate churn and expansion models from
`mart.account_month` and log candidate runs through MLflow.

Status:
Design contract defined by Package 5A. Package 5 implementation is not
complete.

Package 5 trains candidate models only. It does not select a champion, register
models, promote models, deploy models, batch score accounts, create health
bands, create recommended GTM actions, create dashboards, or create production
scoring output tables.

Package 5 source table:

- `mart.account_month`

Package 5 target models:

- Churn model using `churn_90d`.
- Expansion model using `expansion_90d`.

The two model tasks are independent. Package 5 must not train a combined
multi-output model.

Package 5 must preserve the Package 3 label contract. Rows with `NULL` labels
are excluded for the relevant target and must not be converted to zero.

Package 5 uses a fixed temporal train/test split by `observation_month`.
Random splits are not approved.

Package 5 uses explicit approved feature allowlists from existing
`mart.account_month` columns. It must not infer features by taking every
non-target column. Package 4 baseline outputs are benchmarks only and are not
model features.

Allowed MVP candidate models:

- Logistic regression.
- Random forest.

Allowed MVP modelling dependencies:

- scikit-learn.
- MLflow.

Package 5 must not add XGBoost, LightGBM, neural networks, cloud dependencies,
serving dependencies, dashboards, or hosted services.

Package 5 logs one MLflow run per target and candidate model under the local
experiment `account-health-candidate-training`. Runs should log parameters,
row counts, positive rates, split config, feature lists, simple validation
metrics, and model artefacts. Package 5 must not use MLflow registry APIs.

Package 6 owns layered evaluation and champion selection.

Package 7 owns MLflow registry and promotion.

Package 8 owns batch scoring deployment.

Package 9 owns monitoring.

### Package 5 units

#### Package 5A - Docs and dependency contract

Define the durable model training contract and approved dependencies. Do not
implement model training logic.

Exit gate:

- `docs/model_training.md` defines Package 5 purpose, source table, grain,
  targets, label eligibility, temporal split, feature policy, candidate model
  policy, preprocessing policy, MLflow logging policy, metrics, CLI
  expectations, implementation units, and non-goals.
- `docs/feature_contract.md` defines the Package 5 modelling feature policy.
- `docs/packages.md` makes Package 5 a design-contract package without marking
  implementation complete.
- `docs/decisions.md` records durable Package 5 decisions.
- `docs/runbook.md` records Package 5 prerequisite flow and generated artefact
  guidance.
- `README.md` includes Package 5 in the public architecture narrative.
- `pyproject.toml` includes only approved Package 5 runtime dependencies.
- `.gitignore` protects generated data, DuckDB files, MLflow runs, and local
  model artefacts.
- No model training code, scripts, Make targets, dataset loaders, feature
  guards, split code, candidate model code, MLflow logging code, model
  artefacts, DuckDB outputs, generated data, live `.agent/*.md` files, or
  local-only files are committed.
- `make verify`, `make public-safety-check`, `git diff --check`, and
  `git status --short` are run and reported.

#### Package 5B - Dataset and feature guards

Implement modelling dataset loading and feature validation.

Exit gate:

- Reads `mart.account_month` only.
- Validates required target, grain, and feature columns.
- Validates duplicate grain absence.
- Excludes rows with `NULL` labels for the relevant target.
- Enforces explicit approved feature allowlists.
- Rejects forbidden and leakage-prone features.
- Does not train models or log MLflow runs.

#### Package 5C - Temporal split

Implement the fixed time split by `observation_month`.

Exit gate:

- Train rows satisfy `observation_month <= train_end_month`.
- Test rows satisfy `observation_month > train_end_month`.
- Explicit `train_end_month` is supported.
- Default `train_end_month` may be derived from eligible data.
- Empty train or test splits are rejected.
- Single-class train or test targets are rejected.
- Random splitting is not introduced.

#### Package 5D - Candidates and metrics

Implement scikit-learn candidate pipelines and simple validation metrics.

Exit gate:

- Logistic regression candidate exists.
- Random forest candidate exists.
- Numeric and categorical preprocessing is explicit.
- Metrics include ROC AUC, average precision, log loss, Brier score, and
  accuracy.
- Precision at top 10% may be added.
- No champion selection or full Package 6 evaluation is introduced.

#### Package 5E - MLflow orchestration

Implement local MLflow training orchestration.

Exit gate:

- Experiment name is `account-health-candidate-training`.
- One run is logged per target and candidate model.
- Runs log parameters, row counts, positive rates, split config, feature lists,
  metrics, and model artefacts.
- Registry APIs, model promotion, deployment, and scoring outputs are not
  introduced.

#### Package 5F - CLI, Make target, and docs closeout

Add the approved local execution surface and close Package 5 documentation.

Exit gate:

- `scripts/train_candidate_models.py` exists.
- `make train-candidate-models` runs the local training workflow.
- Documentation reflects implemented commands, dependencies, artefacts, and
  exclusions.
- `mlruns/` and model artefacts remain ignored local generated artefacts.
- `make verify`, `git diff --check`, and public repo safety checks pass.
- No Package 6+ evaluation, champion selection, registry promotion, batch
  scoring, health-band, GTM action, dashboard, cloud, real-data, generated, or
  local-only artefact leakage is introduced.

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
