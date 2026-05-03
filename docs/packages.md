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

**Status:** Not started

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
- Create recommended GTT actions.
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
- `docs/packages.md` reflects Package 2 scope.
- `docs/decisions.md` records Package 2 decisions.
- No implementation beyond documentation and ignore-rule tightening unless strictly necessary.
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
Build point-in-time account-month modelling table.

Tasks:

- Define snapshot months.
- Build account lifecycle features.
- Build usage features.
- Build adoption features.
- Build billing features.
- Build support features.
- Build CRM touchpoint features.
- Build renewal proximity features.
- Build `churn_90d` label.
- Build `expansion_90d` label.
- Add leakage tests.

Acceptance criteria:

- One row per account-month.
- Features use only data available as of snapshot month.
- Labels use future 90-day outcomes.
- No duplicate account-month rows.
- Leakage tests pass.
- Data contract docs are updated.

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
