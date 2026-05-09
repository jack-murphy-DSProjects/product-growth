# Decisions

## Package -1

- The repository name is `product-growth`.
- The Python package path is `src/account_health` because the implementation
  domain is account health inside the broader product-growth project.
- The repo is local-first and public-safe by default.
- Private agent instructions live in ignored local files; public templates use
  the `.example` suffix.
- Generated artefacts are ignored and must not be committed.

## Package 1

- Synthetic SaaS source tables are generated before DuckDB so the public-safe
  data boundary can be tested first with plain DataFrames and CSVs.
- The generator returns pandas DataFrames and the CLI owns all local CSV
  writing.
- `synthetic_archetype` is retained as generator metadata for audit/debugging
  only and is not an approved modelling feature.
- Package 1 uses only `pandas` and `numpy` as runtime dependencies.

## Package 2 decisions

### Decision: DuckDB warehouse path

Package 2 writes the local analytical warehouse to:

- `data/warehouse/account_health.duckdb`

This path is ignored by git.

DuckDB database files and write-ahead log files are generated local artefacts
and are also ignored by git:

- `*.duckdb`
- `*.duckdb.wal`

The DuckDB database is a generated local artefact and must never be committed.

### Decision: DuckDB runtime dependency

Package 2 adds `duckdb` as a runtime dependency because the local analytical
warehouse is a DuckDB database.

DuckDB remains local-only in this project. Package 2 does not add a cloud
warehouse, hosted database, API, orchestration framework, or production
deployment.

### Decision: Raw and metadata schemas

Package 2 uses DuckDB schemas to separate source persistence from load metadata:

- `raw.*`
- `metadata.*`

Package 2 creates raw/source tables only.

Feature tables, labels, model outputs, health bands, recommendations, monitoring tables, and RevOps outputs belong to later packages.

### Decision: Loader accepts explicit paths

The warehouse loader must accept explicit `source_dir` and `database_path` arguments.

Default CLI paths may be:

- `source_dir`: `data/generated/`
- `database_path`: `data/warehouse/account_health.duckdb`

The core Python API must not depend on hardcoded project-local paths.

### Decision: Loading does not generate data

Package 2 does not generate synthetic data.

It loads existing Package 1 CSV outputs.

If required CSVs are missing, the loader must fail clearly rather than generating data implicitly.

### Decision: Overwrite by default

Package 2 uses deterministic overwrite/rebuild loading by default.

Incremental loading, append semantics, late-arriving records, warehouse migrations, and orchestration state are out of scope for the MVP.

### Decision: Minimal load audit is allowed

Package 2 may create a minimal `metadata.load_audit` table containing load metadata such as:

- load ID
- timestamp
- source directory
- database path
- table name
- row count
- status

The audit table must remain simple.

It must not become an orchestration framework or job-control system.

### Decision: Package-gated autonomous execution

Package 2 agents may work autonomously unit by unit only when the current unit
gate is documented and passes.

The durable execution contract lives in:

- `docs/agentic_execution.md`
- `.agent/current_execution_context.md.example`
- `.agent/package_gate.md.example`
- `.agent/agent_runbook.md.example`

Live `.agent/*.md` files are local-only controls and must not be committed.

Agents may continue to the next Package 2 unit only after the current unit gate
passes.

Agents must stop before Package 3 unless the human reviewer explicitly starts
Package 3.

## Package 3 decisions

### Decision: Account-month grain

Package 3 creates `mart.account_month` at one active subscribed account x one
calendar observation month.

The primary grain is:

- `account_id`
- `observation_month`

`observation_month` is the first day of the month. `observation_month_end` is
the last day of that month.

### Decision: Renewal labels

Package 3 uses `raw.renewals` as the canonical source for both labels:

- `churn_90d`
- `expansion_90d`

Both labels use the approved 90-day future horizon after
`observation_month_end`. Ineligible labels are stored as `NULL`, not `0`.

### Decision: MVP feature set

Package 3 implements a small, explicit feature set across static account,
current subscription, usage, support, billing, and CRM source families.

All feature inputs must be known on or before `observation_month_end`.

`raw.accounts.synthetic_archetype` remains generator metadata and is excluded
from `mart.account_month`.

### Decision: Local feature build audit

Package 3 creates `metadata.feature_build_audit` during local account-month
builds.

The audit table records build counts and source coverage for inspectability.
It is not an orchestration framework, monitoring system, model registry, or
production metadata store.

## Package 4 decisions

### Decision: Rule baselines are benchmark artefacts, not policy

Package 4 creates deterministic rule baselines in a separate table:

- `mart.account_month_baselines`

The source table is:

- `mart.account_month`

The baselines are heuristic benchmark scores for later ML models to beat. They
are not calibrated probabilities, final account health bands, recommended GTM
actions, champion decisions, monitoring reports, or production policy outputs.

Rationale:

- Separating baselines preserves the Package 3 account-month semantics.
- Keeping baselines outside `mart.account_month` avoids mutating the modelling
  table and keeps feature/label construction distinct from benchmark scoring.
- Baseline scores remain separate from future ML predictions, which supports
  clear baseline-vs-ML comparison in later evaluation packages.
- Deferring health bands and recommended actions avoids introducing the GTM
  action layer before scores and models have been evaluated.

Package 4 must not use `churn_90d`, `expansion_90d`, or
`synthetic_archetype` as scoring inputs.

### Decision: Local baseline build audit

Package 4 creates `metadata.baseline_build_audit` during local baseline
rebuilds.

The audit table records build ID, UTC build time, source table, output table,
baseline version, row counts, observation-month bounds, and status.

It is local build metadata only. It is not model metadata, MLflow tracking, a
model registry, orchestration state, monitoring output, model evaluation, or
champion-selection evidence.

## Package 5 decisions

### Decision: Independent churn and expansion models

Package 5 trains separate candidate models for `churn_90d` and
`expansion_90d`.

Package 5 does not train a combined multi-output model.

### Decision: Null target labels are excluded

Package 5 excludes rows with `NULL` labels for the relevant target.

`NULL` target labels are not converted to zero.

### Decision: Fixed temporal split

Package 5 uses a fixed train/test split by `observation_month`.

Random train/test splits are not approved.

### Decision: scikit-learn and MLflow dependencies

Package 5 introduces scikit-learn for local candidate model training and
MLflow for local experiment tracking.

Package 5 does not introduce XGBoost, LightGBM, neural networks, cloud
dependencies, serving dependencies, or dashboard dependencies.

### Decision: Baselines are benchmarks only

Package 4 baseline scores, ranks, deciles, and components are benchmark
outputs only.

Package 5 must not use baseline outputs as model features.

### Decision: MLflow logging without registry or promotion

Package 5 logs candidate model runs and artefacts to local MLflow tracking.

Package 5 does not use MLflow registry APIs, register models, promote models,
or deploy models.

### Decision: No champion selection or layered evaluation

Package 5 reports simple validation metrics for candidate runs only.

Champion selection and full layered evaluation belong to Package 6.

## Package 6 decisions

### Decision: Fixed holdout plus holdout-month robustness

Package 6 evaluates candidates on the fixed temporal holdout created by the
Package 5 split semantics.

Package 6 may slice that fixed holdout by `observation_month` to check temporal
robustness.

Package 6 does not implement a full rolling retraining backtest in the MVP. A
rolling backtest would require actual repeated retraining across multiple
cutoffs and must be separately approved.

### Decision: Consume local MLflow runs without silent retraining

Package 6 consumes local Package 5 MLflow candidate runs, feature metadata,
split metadata, and model artefacts.

If required local runs or artefacts are missing, Package 6 should fail clearly.
It must not silently retrain candidates as a fallback.

Package 6 does not use MLflow registry APIs, aliases, promotion, deployment, or
remote tracking requirements.

### Decision: Baselines are ranking benchmarks in evaluation

Package 4 baseline scores may be compared with ML candidates using ranking and
capacity metrics such as ROC AUC, average precision, top-K precision, top-K
recall, lift, and capture rate.

Package 4 baseline scores are not calibrated probabilities. Package 6 must not
use them for log loss, Brier score, or calibration bins in the MVP.

### Decision: Champion selection follows GTM operating metrics

Package 6 selects churn and expansion champions separately.

Primary evidence is top-K GTM operating performance, especially precision,
lift, and capture at top 10%. ROC AUC and average precision are supporting
evidence only.

Package 6 may conclude that no ML candidate sufficiently beats the rule
baseline for a target.

### Decision: Evaluation outputs are local artefacts

Package 6 writes generated evaluation files under:

- `data/outputs/model_evaluation/`

The default generated files are:

- `evaluation_summary.json`
- `champion_selection_manifest.json`
- `evaluation_report.md`

These files are generated local artefacts and must not be committed.

### Decision: Minimal evaluation tables

Package 6 may create a minimal local DuckDB table set:

- `metadata.model_evaluation_audit`
- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

Optional detail tables should be added only when implementation needs them.

These tables are local evaluation summaries. They are not production scoring
outputs, model registry metadata, monitoring outputs, health bands, or
recommended GTM actions.

### Decision: Local evaluation CLI and generated artefacts

Package 6 adds the local command:

- `make evaluate-candidate-models`

The command consumes existing local Package 5 MLflow runs and Package 4
baselines, writes generated evaluation files under
`data/outputs/model_evaluation/`, and writes only the minimal local evaluation
tables.

It does not retrain missing candidates, use the MLflow registry, promote
models, deploy models, create production scoring outputs, create account health
bands, recommend GTM actions, add dashboards, add hosted APIs, or add cloud
infrastructure.
