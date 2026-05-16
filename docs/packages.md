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
Complete.

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

Package 9 owns batch scoring observability.

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

Status:
Complete.

Goal:
Evaluate Package 5 candidate ML models and Package 4 rule baselines through
commercial operating metrics, then select one champion for churn and one
champion for expansion when the evidence supports it.

Package 6 source inputs:

- `mart.account_month`
- `mart.account_month_baselines`
- local Package 5 MLflow candidate runs and model artefacts
- Package 5 feature and split metadata

Package 6 must preserve the Package 3 account-month grain, Package 3 label
semantics, Package 4 baseline-as-ranking-benchmark semantics, and Package 5
local candidate training semantics.

Package 6 must not add MLflow registry use, model registration, model
promotion, deployment, production scoring outputs, account health bands,
recommended GTM actions, monitoring dashboards, hosted APIs, cloud
infrastructure, real customer data, segment-specific models, full rolling
retraining backtests, default candidate retraining, mutation of
`mart.account_month`, or baselines as ML features.

Package 6 uses Package 5 fixed holdout evaluation plus holdout-month temporal
robustness slices within the fixed holdout. It must not claim or implement a
full rolling retraining backtest in the MVP.

Tasks:

- Create the durable Package 6 evaluation contract.
- Load existing local MLflow candidate runs and fail clearly if required runs
  or artefacts are missing.
- Score Package 5 fixed holdout rows for each target and candidate.
- Implement top-K capacity evaluation.
- Implement Package 5 fixed holdout evaluation.
- Implement holdout-month temporal robustness slices within the fixed holdout.
- Implement baseline versus ML comparison.
- Implement economic utility sensitivity.
- Implement calibration checks.
- Implement segment robustness checks.
- Implement champion selection report.
- Keep full rolling retraining backtests out of the Package 6 MVP unless actual
  rolling retraining is explicitly implemented and approved.
- Write local generated evaluation artefacts under
  `data/outputs/model_evaluation/`.
- Create minimal local evaluation summary tables if implemented:
  `metadata.model_evaluation_audit`, `mart.model_evaluation_summary`, and
  `mart.model_champion_selection`.

Acceptance criteria:

- `docs/model_evaluation.md` defines the Package 6 contract.
- Package 6 consumes existing local Package 5 MLflow runs and does not silently
  retrain candidates.
- Missing expected MLflow runs, feature metadata, split metadata, or model
  artefacts fail clearly.
- Top-K / capacity evaluation is implemented.
- Percent K values include top 5%, top 10%, and top 20%.
- Count K values include top 25, top 50, and top 100 only when enough rows
  exist.
- Fixed holdout evaluation using Package 5 split semantics is implemented.
- Holdout-month temporal robustness slices are implemented within the fixed
  holdout.
- Package 6 does not claim or implement a full rolling retraining backtest in
  the MVP.
- Economic utility sensitivity is implemented.
- Baseline versus ML comparison is implemented.
- Baselines are evaluated as ranking scores, not calibrated probabilities.
- Baselines are not included in log loss, Brier score, or calibration bins.
- Segment robustness covers segment, region, plan tier, company size band, and
  industry where present.
- One-class segments and sparse holdout months produce caveats instead of
  misleading metrics.
- Champion is not selected by ROC AUC alone.
- Candidate selection primarily uses GTM operating metrics such as precision,
  lift, and capture at top 10%.
- It is possible to retain the baseline or declare insufficient evidence if no
  ML candidate sufficiently beats the rule baseline.
- Evaluation outputs are saved as ignored local artefacts.
- Training, warehouse, data contract, runbook, decisions, and evaluation docs
  are updated.
- No Package 7 registry/promotion, Package 8 raw scoring, later policy work,
  Package 9 score observability, dashboards, APIs, cloud services, real data, or
  generated artefacts are committed.

### Package 6 units

#### Package 6A - Docs-first evaluation contract

Define the durable Package 6 evaluation contract. Do not implement evaluation
code.

Exit gate:

- `docs/model_evaluation.md` exists and defines purpose, inputs, non-goals,
  MLflow stance, fixed holdout stance, baseline stance, metrics, top-K design,
  calibration, segment robustness, holdout-month robustness, economic utility
  sensitivity, champion selection, local outputs, DuckDB table contracts,
  champion manifest fields, unit plan, and later test expectations.
- `docs/packages.md`, `docs/decisions.md`, `docs/runbook.md`,
  `docs/model_training.md`, `docs/warehouse.md`, and `docs/data_contract.md`
  align with the Package 6 contract.
- Public narrative docs do not claim the Package 6 MVP implements a rolling
  monthly retraining backtest.
- No code, scripts, tests, Make targets, live `.agent/*.md` files, generated
  outputs, MLflow runs, DuckDB files, or model artefacts are modified or
  created.
- `make verify`, `make public-safety-check`, `git diff --check`, and
  `git status --short` are run and reported.

#### Package 6B - Evaluation input and MLflow candidate loading

Implement evaluation input loading only.

Exit gate:

- `mart.account_month` is loaded for evaluation without mutation.
- `mart.account_month_baselines` is loaded for baseline comparison.
- Local Package 5 MLflow runs are discovered for each expected target and
  candidate family.
- Candidate model artefacts, `features.json`, and `split_config.json` are
  loaded and validated.
- Remote MLflow tracking, registry APIs, aliases, promotion, deployment, and
  silent retraining are rejected.

#### Package 6C - Fixed holdout scoring, metrics, and baseline comparison

Score fixed holdout rows and compute candidate-versus-baseline metrics.

Exit gate:

- Evaluation uses Package 5 fixed holdout rows only.
- ML candidates produce bounded probabilities for the relevant target.
- Baselines are joined by `account_id`, `observation_month`.
- ROC AUC and average precision are reported where valid.
- Top-K operating metrics are reported for ML candidates and baselines.
- Baselines are not evaluated with log loss, Brier score, or calibration bins.
- Deterministic tie-breaking is tested.

#### Package 6D - Calibration, segment robustness, and holdout-month robustness

Add layered robustness checks.

Exit gate:

- ML candidate calibration metrics and bins are reported.
- Segment robustness covers approved segment fields where present.
- One-class and low-support slices produce caveats.
- Holdout-month slices are evaluated inside the fixed holdout.
- No rolling retraining backtest is claimed or implemented.

#### Package 6E - Economic utility sensitivity and champion manifest

Add simple utility sensitivity and target-specific champion selection.

Exit gate:

- Utility sensitivity uses illustrative assumptions only and does not claim real
  ROI from synthetic data.
- Churn and expansion champions are selected separately.
- Champion selection primarily uses top 10% operating metrics.
- The manifest supports ML champion, baseline retained, no ML candidate
  sufficiently beats baseline, and insufficient evidence outcomes.
- Registry, promotion, deployment, scoring outputs, health bands, and
  recommended GTM actions remain out of scope.

#### Package 6F - CLI, Make target, tests, docs closeout

Add the approved local Package 6 execution surface and close the package.

Exit gate:

- A local evaluation CLI and Make target exist.
- Focused Package 6 tests cover loading, missing artefacts, remote MLflow
  rejection, metric correctness, caveats, champion selection, and artefact
  safety.
- Documentation reflects implemented commands, outputs, tables, caveats, and
  exclusions.
- `make verify`, `make public-safety-check`, `git diff --check`, and
  `git status --short` pass.
- Generated outputs, DuckDB files, MLflow runs, live `.agent/*.md` files,
  model artefacts, private files, dashboards, APIs, cloud deployments, and
  policy-layer outputs remain untracked.

---

## Package 7: MLflow registry and model promotion

Goal:
Promote eligible Package 6-selected ML champions into the local MLflow model
registry and define the Package 8 consumption contract.

Package 7 records model lifecycle state. It does not select champions,
re-evaluate candidates, retrain models, score accounts, deploy models, create
health bands, create GTM actions, add dashboards, add hosted APIs, or add cloud
infrastructure.

Package 7 consumes:

- `data/outputs/model_evaluation/champion_selection_manifest.json`
- existing local Package 5 MLflow candidate runs and model artefacts

Package 7 must fail clearly if the Package 6 manifest is missing, malformed,
ambiguous, retains the baseline, reports insufficient evidence, or selects no
ML champion for a requested target. Package 7 must not scan MLflow and
independently choose a champion if the manifest is missing.

Expected registered model names:

- `account_health_churn_model`
- `account_health_expansion_model`

The primary alias is `champion`. The alias means selected by Package 6 and
promoted by Package 7 for future local batch scoring consumption. It does not
mean online serving, cloud deployment, hosted API deployment, business approval,
health-band generation, GTM action generation, or monitoring approval.

Package 7 uses MLflow aliases and tags, not deprecated registry stages.

Tasks:

- Create the durable registry and promotion contract in
  `docs/model_registry.md`.
- Validate target-specific Package 6 champion-selection evidence.
- Validate referenced Package 5 source runs and model artefacts.
- Register eligible churn and expansion ML champions separately.
- Assign the `champion` alias to promoted model versions.
- Store MLflow tags linking model versions to Package 5 source runs, Package 5
  feature/split metadata, and Package 6 champion-selection evidence.
- Write a local ignored Package 7 promotion manifest for Package 8.
- Write minimal local promotion audit metadata.
- Add the local `make promote-model-registry` command.

Acceptance criteria:

- `docs/model_registry.md` defines the Package 7 semantic contract.
- Only Package 6-selected eligible ML champions can be promoted.
- Rule baselines are never registered as MLflow models.
- Churn and expansion are registered under separate model names.
- The `champion` alias points to the promoted local model version.
- Registry metadata links the model version to source run, model artefact,
  feature metadata, split metadata, training period, and Package 6 evidence.
- The local promotion manifest is generated under an ignored output path.
- `make promote-model-registry` runs the local promotion workflow.
- Package 5 source runs and Package 6 evaluation outputs are not mutated.
- Package 7 creates no production scoring outputs, account health bands,
  recommended GTM actions, dashboards, hosted APIs, or cloud infrastructure.

---

## Package 8: Batch scoring deployment

Goal:
Create a raw local account-month batch scoring job.

Tasks:

- Load Package 7-promoted MLflow champion models for churn and expansion.
- Read selected `observation_month` rows from `mart.account_month`.
- Require an explicit scoring population such as
  `--scoring-month YYYY-MM-01` or explicit `--latest`.
- Validate scoring schema and feature contract before inference.
- Generate raw churn and expansion model scores only.
- Write raw score rows to a local scoring table.
- Write append-only scoring audit metadata.
- Optionally write ignored local raw scoring exports.

Acceptance criteria:

- Scoring never defaults to all history silently.
- Every selected account-month row receives raw model scores when both
  required champions and features are valid.
- Scores are bounded between 0 and 1.
- Output grain is one row per scored account x scoring month.
- Labels, identifiers, date fields, eligibility flags, baseline columns,
  `synthetic_archetype`, and future-looking fields are never model inputs.
- Package 8 uses the trained sklearn pipeline for preprocessing and does not
  recreate Package 5 preprocessing manually.
- Reruns replace score rows for the selected scoring month and append audit
  metadata.
- Local raw scoring exports, if produced, are ignored generated artefacts.
- Scoring runs are reproducible from the selected month, promoted champions,
  recorded feature metadata, and audit metadata.

Package 8 explicitly does not monitor, evaluate, promote, retrain, or deploy a
hosted service. Package 9 later observes Package 8 score outputs only. Health
bands, GTM actions, recommendations, RevOps action tables, policy thresholds,
dashboards, APIs, and cloud or cloud-like deployment are deferred to Package
10 or later explicitly approved work.

Approved local command:

```bash
make score-account-month SCORING_MONTH=YYYY-MM-01
```

The command may use `BATCH_SCORING_LATEST=1` only as an explicit latest-month
selector and may write optional ignored raw exports under
`data/outputs/batch_scoring/`.

---

## Package 9: Batch scoring observability

Goal:
Generate local observability artefacts for Package 8 batch score outputs.

Tasks:

- Resolve exactly one scored month from an explicit month or explicit latest
  selector.
- Validate the selected scored population against the expected
  `mart.account_month` population.
- Validate churn and expansion score shape, nullability, numeric type, and
  `[0, 1]` bounds.
- Summarize score distributions overall and by safe descriptive segment.
- Summarize Package 8 scoring lineage from score/audit evidence.
- Compare the selected scored month with the nearest earlier scored month when
  available.
- Write local observability summaries and append-only audit metadata.
- Optionally write ignored local exports under
  `data/outputs/score_observability/`.
- Document the Package 9 contract in `docs/score_observability.md`.

Acceptance criteria:

- Exactly one scoring-month selector is required.
- `latest` resolves from `mart.account_month_scores`.
- Prior comparison uses the nearest earlier scored month, not necessarily the
  previous calendar month.
- If no prior scored month exists, the run can succeed with a warning and null
  prior-comparison fields.
- Missing required tables, invalid or duplicate score rows, unresolved expected
  populations, out-of-range scores, and inconsistent required lineage fail
  clearly.
- Warning-only conditions are distinguishable from clean success.
- Local outputs remain generated artefacts.
- Package 9 does not require labels, future outcomes, retraining, rescoring,
  live MLflow registry authority, dashboards, APIs, or real data.
- Package 9 remains honest local batch scoring observability for synthetic data,
  not real production drift detection or automated model governance.

---

## Package 10: Deterministic GTM policy layer

Goal:
Create a deterministic GTM policy layer on top of Package 8 raw scores, plus
only the minimal public-safe examples needed to explain that layer.

Package 10 is not the broad final repo-polish package. Final README polish,
screenshots, portfolio storytelling, dashboard-like examples, and final closeout
belong to Package 11 or a later explicit polish pass.

Primary source of truth:

- `docs/gtm_policy.md`

Package 10 consumes:

- `mart.account_month_scores`
- safe descriptive context already present in approved upstream synthetic
  contracts
- optional Package 9 observability evidence as quality/safety context only

Package 10 may create:

- `mart.account_month_gtm_policy`
- `metadata.gtm_policy_audit`
- optional ignored local exports under `data/outputs/gtm_policy/`

Package 10 must preserve:

- separate raw churn-risk and expansion-propensity score columns
- Package 8 scoring outputs without mutation
- Package 9 observability outputs without mutation
- the synthetic-data-only and public-safe project boundary

Tasks:

- Define the locked illustrative `gtm_policy_v1` matrix in
  `docs/gtm_policy.md`.
- Validate raw score inputs before assigning policy outputs.
- Assign deterministic health bands.
- Assign deterministic lifecycle motions.
- Assign deterministic recommended actions.
- Assign deterministic action priorities.
- Assign deterministic action reason codes.
- Handle churn/expansion conflicts explicitly with churn risk dominating
  expansion actioning.
- Join approved safe descriptive account context for RevOps review.
- Create one RevOps-facing account-month policy table.
- Create append-only policy audit metadata.
- Support explicit scoring-month or explicit latest-scored-month semantics.
- Optionally create a small ignored local export under
  `data/outputs/gtm_policy/`.
- Keep README/runbook/package-index updates light and Package-10-specific.

Non-goals:

- No model training, retraining, re-evaluation, champion selection, promotion,
  rescoring, or mutation of Package 8/9 outputs.
- No labels or future outcomes.
- No learned policy.
- No dashboard, API, cloud deployment, CRM integration, campaign execution,
  email automation, playbook engine, reinforcement learning, or optimisation
  engine.
- No claim that synthetic-data actions are commercially validated.
- No broad final repo polish.

Acceptance criteria:

- `docs/gtm_policy.md` defines the Package 10 contract and the exact
  `gtm_policy_v1` matrix.
- Health bands and recommended actions are deterministic policy outputs rather
  than trained targets.
- The exact v1 health bands, thresholds, lifecycle motions, recommended
  actions, priorities, and reason codes are implemented as documented.
- Churn risk and expansion propensity remain separate raw score dimensions.
- High churn risk dominates expansion actioning.
- High churn plus high expansion resolves to save-first behaviour rather than a
  pure upsell action.
- Score inputs must be finite, numeric, non-null, and inside `[0, 1]` before
  assignment.
- Every valid account-month score row maps to exactly one policy row.
- Rerunning one scoring month replaces `mart.account_month_gtm_policy` rows for
  that month only.
- `metadata.gtm_policy_audit` remains append-only.
- Local exports remain generated ignored artefacts.
- Package 10 does not use labels, future outcomes, learned thresholds,
  dashboards, APIs, cloud services, or commercial-validation claims.

### Package 10 units

#### Package 10A - Docs-first deterministic GTM policy contract

Define the durable Package 10 contract before implementation.

Exit gate:

- `docs/gtm_policy.md` exists and defines Package 10 purpose, boundary,
  inputs, outputs, non-goals, locked `gtm_policy_v1` matrix, exact taxonomy,
  conflict handling, boundary behaviour, observability relationship,
  idempotence, CLI/Make contract, local export semantics, public-safety stance,
  tests, review checklist, and deferred Package 11 items.
- `docs/packages.md`, `docs/runbook.md`, `docs/decisions.md`, and `README.md`
  align with the Package 10 boundary.
- Committed `.agent/*.example` templates are aligned for Package 10 and later
  implementation units.
- No code, scripts, tests, Make targets, DuckDB tables, generated outputs, or
  exports are added.
- Live local `.agent/*.md` files are not modified or tracked.
- `make public-safety-check`, `git diff --check`, and `git status --short` are
  run and reported.

#### Package 10B - Input validation and policy matrix helpers

Implement the Package 10 scoring-month selection, score validation, and locked
matrix helpers only.

Exit gate:

- Requires explicit scoring month or explicit latest-scored-month mode.
- Reads Package 8 raw scores without mutating them.
- Fails on null, non-numeric, non-finite, out-of-range, duplicate, or ambiguous
  score rows before policy assignment.
- Implements the exact `gtm_policy_v1` matrix, strings, and boundary rules from
  `docs/gtm_policy.md`.
- Focused tests pin all seven matrix rows and all threshold boundaries.
- No table writes, exports, dashboards, APIs, cloud services, or final polish
  are added.

#### Package 10C - Policy table build and safe context join

Build the RevOps-facing account-month policy output.

Exit gate:

- `mart.account_month_gtm_policy` is written at one row per `account_id` x
  `scoring_month`.
- Raw churn and expansion scores are preserved.
- Approved safe descriptive context is joined without multiplying rows.
- Labels, future outcomes, and generator-only fields are excluded.
- Every valid source score row maps to exactly one output policy row.
- Focused tests cover conflict handling, row parity, safe joins, and forbidden
  fields.

#### Package 10D - Audit, idempotence, and optional observability context

Add inspectable rerun behaviour and audit evidence.

Exit gate:

- `metadata.gtm_policy_audit` is append-only.
- Rerunning one month replaces policy rows for that month only.
- Health-band, recommended-action, and priority counts are recorded.
- Optional Package 9 observability status, when used, is recorded as
  quality/safety context without changing the deterministic matrix.
- Focused tests cover reruns, counts, and optional observability context.

#### Package 10E - CLI, Make targets, local export, and docs closeout

Add the approved local execution surface and close the package.

Exit gate:

- `scripts/build_gtm_policy.py` exists.
- `make build-gtm-policy SCORING_MONTH=YYYY-MM-01` exists.
- `make build-gtm-policy-latest` exists.
- Optional ignored local exports stay under `data/outputs/gtm_policy/`.
- Documentation reflects implemented commands and outputs without broad final
  repo polish.
- Focused tests plus required broad checks pass.
- No Package 11/final-polish work appears.

---

## Package 11: Final public polish and closeout

Goal:
Improve final public presentation after the deterministic policy layer exists.

Likely scope:

- final README polish
- screenshots or other public-safe visual examples if approved
- portfolio storytelling and closeout
- dashboard-like examples if explicitly approved
- broader public example-output polish
- final repository review

Package 11 must not silently change the Package 10 v1 policy contract. Any
change to the locked policy matrix, thresholds, taxonomy, or boundary semantics
requires an explicit new decision/update first.
