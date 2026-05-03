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
- No real data is used.

---

## Package 2: DuckDB warehouse and data contracts

Goal:
Load generated data into DuckDB and validate table contracts.

Tasks:

- Create SQL table definitions.
- Implement DuckDB loader.
- Implement schema validation.
- Document table grains.
- Add contract tests.

Acceptance criteria:

- DuckDB database builds locally.
- Required columns are validated.
- Invalid schema fails loudly.
- Local database files are gitignored.
- Data contract docs are updated.

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
