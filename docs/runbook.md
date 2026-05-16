# Runbook

## Package Workflow

1. Confirm the active package and scope.
2. Grill the request before building.
3. Write or update focused tests for behavior changes.
4. Make the smallest scoped patch.
5. Run the narrowest relevant check.
6. Run `make verify`.
7. Summarize files changed, commands run, and remaining risks.

For bounded autonomous runs, use `docs/agentic_execution.md` together with the
`.agent/*.example` templates. Live `.agent/*.md` files are local-only controls
and must not be committed.

## Package -1 Checks

```bash
make setup
make public-safety-check
make test
make verify
```

## Stop Conditions

- Future package work is requested without approval.
- Real data or secrets are needed.
- Generated artefacts would need to be committed.
- Public safety checks fail outside the current scope.

## Package 5 runbook - Candidate model training

Package 5 trains local candidate churn and expansion models from
`mart.account_month` and logs candidate runs through local MLflow tracking.

Package 5 does not select, register, promote, deploy, score, monitor, create
health bands, create recommended GTM actions, or perform full layered
evaluation.

Prerequisite local flow:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
```

Package 5 training must not require Package 4 baselines. Baseline outputs are
benchmarks for later comparison, not training prerequisites and not model
features.

The Package 5 training command is:

```bash
make train-candidate-models
```

MLflow writes generated local tracking artefacts under:

- `mlruns/`

Model-training scratch or model artefact paths such as `artifacts/models/` and
`artifacts/tmp/` are generated local artefacts.

These paths must not be committed.

Before closing a Package 5 unit, run:

- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

Confirm no generated data, DuckDB files, MLflow runs, model artefacts, caches,
private files, or live `.agent/*.md` files are tracked.

## Package 6 runbook - Layered evaluation and champion selection

Package 6 evaluates local Package 5 candidate ML runs and Package 4 rule
baselines, then selects separate churn and expansion champions when justified.

Package 6 does not register, promote, deploy, batch score, create account
health bands, create recommended GTM actions, add dashboards, add hosted APIs,
add cloud infrastructure, use real data, mutate `mart.account_month`, retrain
candidates by default, or use baselines as ML features.

Package 6 uses the Package 5 fixed holdout plus holdout-month temporal
robustness slices. Do not call this a rolling backtest unless actual rolling
retraining is implemented and approved.

Prerequisite local flow for Package 6 implementation units:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
make build-rule-baselines
make train-candidate-models
make evaluate-candidate-models
```

Package 6A is docs-first only. It must not add evaluation code, scripts, tests,
Make targets, generated outputs, MLflow runs, DuckDB files, or model artefacts.

The Package 6 evaluation command is:

```bash
make evaluate-candidate-models
```

It writes ignored local artefacts under `data/outputs/model_evaluation/` and
local DuckDB evaluation tables only:

- `metadata.model_evaluation_audit`
- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

These are evaluation summaries, not production scoring outputs, registry
metadata, health bands, recommended GTM actions, dashboards, hosted APIs, or
monitoring reports.

Before each Package 6 unit:

- Restate the active Package 6 unit.
- Restate the relevant gate from `docs/model_evaluation.md`.
- Run `git status --short`.
- Confirm no live `.agent/*.md` file will be modified or committed.
- Identify intended files to change.
- Identify tests to add or update when behavior changes.
- Identify stop-condition risk.

Before closing a Package 6 unit, run:

- focused tests for implementation units
- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

Confirm no generated evaluation files, DuckDB files, MLflow runs, model
artefacts, caches, private files, or live `.agent/*.md` files are staged or
tracked.

## Package 7 runbook - MLflow registry and model promotion

Package 7 promotes eligible Package 6-selected ML champions into the local
MLflow model registry. Package 7 records lifecycle state; Package 6 selects the
champions and Package 8 later owns batch scoring.

Package 7 does not retrain, re-evaluate, override Package 6 champion selection,
promote baselines as MLflow models, score accounts, create production scoring
outputs, create account health bands, recommend GTM actions, add dashboards,
add hosted APIs, add cloud infrastructure, use real data, mutate
`mart.account_month`, mutate Package 5 source runs, or mutate Package 6
evaluation outputs.

Prerequisite local flow for Package 7 implementation units:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
make build-rule-baselines
make train-candidate-models
make evaluate-candidate-models
```

Package 7A is docs-first only. It must not add registry code, scripts, tests,
Make targets, generated outputs, MLflow registry entries, MLflow runs, DuckDB
files, promotion manifests, model artefacts, scoring outputs, health bands, GTM
actions, dashboards, hosted APIs, or cloud infrastructure.

The Package 7 source of truth is:

- `docs/model_registry.md`

Package 7 uses local MLflow aliases and tags, not deprecated registry stages.
The main alias is `champion`. The expected registered model names are:

- `account_health_churn_model`
- `account_health_expansion_model`

The generated Package 7 promotion manifest should live under:

- `data/outputs/model_registry/promotion_manifest.json`

The Package 7 promotion command is:

```bash
make promote-model-registry
```

It consumes the Package 6 champion-selection manifest and existing local
Package 5 MLflow model artefacts. It writes local MLflow registry aliases/tags,
the ignored promotion manifest, and `metadata.model_promotion_audit`; it does
not score accounts, deploy models, create health bands, recommend GTM actions,
add dashboards, add hosted APIs, or add cloud infrastructure.

Before each Package 7 unit:

- Restate the active Package 7 unit.
- Restate the relevant gate from `docs/model_registry.md`.
- Run `git status --short`.
- Confirm no live `.agent/*.md` file will be modified or committed.
- Identify intended files to change.
- Identify tests to add or update when behavior changes.
- Identify stop-condition risk.

Before closing a Package 7 unit, run:

- focused tests for implementation units
- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

For docs-only Package 7A, document any skipped implementation tests explicitly.
Confirm no generated promotion files, DuckDB files, MLflow runs, model
artefacts, caches, private files, or live `.agent/*.md` files are staged or
tracked.

## Package 8 runbook - Raw local batch scoring

Package 8 scores explicit account-month populations from `mart.account_month`
with Package 7-promoted MLflow `champion` models.

Package 8 is raw local batch scoring only. It must not train, retrain,
evaluate, promote, monitor, deploy a hosted service, create health bands,
recommend GTM actions, add dashboards, add APIs, add cloud infrastructure, use
real data, or mutate Package 5/6/7 source evidence.

Preconditions for Package 8 scoring:

- Package 3 has built `mart.account_month`.
- Package 5 has logged trained sklearn pipelines and `features.json`.
- Package 6 has selected eligible ML champions.
- Package 7 has promoted churn and expansion champions to local MLflow
  registered model aliases named `champion`.
- The scoring month is explicit as `YYYY-MM-01`, or an explicit `latest`
  selector is requested.

The approved local command is:

```bash
python scripts/score_account_month.py --warehouse-path "data/warehouse/account_health.duckdb" --scoring-month "YYYY-MM-01"
```

The approved Make target is:

```bash
make score-account-month SCORING_MONTH=YYYY-MM-01
```

Use `--latest` or `BATCH_SCORING_LATEST=1` only as an explicit latest-month
selector. Optional repo-local raw CSV exports must stay under:

- `data/outputs/batch_scoring/`

Package 8 output paths and tables remain local generated artefacts:

- `mart.account_month_scores`
- `metadata.batch_scoring_audit`
- optional ignored exports under `data/outputs/batch_scoring/`

Before each Package 8 implementation unit:

- Restate that Package 8 is raw local batch scoring only.
- Confirm no Package 5 or Package 6 labelled loader will be reused for scoring.
- Confirm scoring will require explicit `--scoring-month YYYY-MM-01` or
  explicit `--latest`.
- Identify intended files to change and tests to add or update.
- Identify stop-condition risk.

Before closing a Package 8 implementation unit, run:

- focused tests for implemented scoring behaviour
- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

For docs-only Package 8A, document skipped implementation tests explicitly.
Confirm no generated scoring files, DuckDB files, MLflow runs, model artefacts,
caches, private files, or live `.agent/*.md` files are staged or tracked.

## Package 9 runbook - Batch scoring observability

Package 9 runs after Package 8 scoring and observes the raw local score outputs
that Package 8 already wrote.

Package 9 is batch scoring observability only. It validates selected scored
populations, score values, distribution summaries, safe segment summaries, and
observed scoring lineage for synthetic local outputs. It does not rescore
accounts, require labels, retrain, re-evaluate, select champions, promote
models, create account health bands, recommend GTM actions, create RevOps
action tables, define GTM policy thresholds, add dashboards, add APIs, add
cloud deployment, or use real data.

The Package 9 source of truth is:

- `docs/score_observability.md`

The approved local Package 9 commands are:

```bash
make monitor-account-scores SCORING_MONTH=YYYY-MM-01
make monitor-account-scores-latest
```

Optional repo-local observability exports must stay under:

- `data/outputs/score_observability/`

Package 9 local outputs remain generated local artefacts such as:

- `metadata.score_observability_audit`
- `mart.score_observability_summary`
- `mart.score_distribution_by_month`
- `mart.score_distribution_by_segment`
- optional ignored exports under `data/outputs/score_observability/`

Before each Package 9 implementation unit:

- Restate that Package 9 is batch scoring observability only.
- Confirm Package 8 already owns score generation and scoring audit evidence.
- Confirm no labels, future outcomes, live MLflow registry authority, or
  policy-layer outputs are being introduced.
- Identify intended files to change and tests to add or update.
- Identify stop-condition risk.

Before closing a Package 9 implementation unit, run:

- focused tests for implemented observability behaviour
- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

For docs-only Package 9 work, document skipped implementation tests explicitly.
Confirm no generated observability outputs, DuckDB files, MLflow runs, model
artefacts, caches, private files, or live `.agent/*.md` files are staged or
tracked.

## Package 10 runbook - Deterministic GTM policy layer

Package 10 consumes Package 8 raw scores and creates deterministic GTM policy
outputs for the synthetic local workflow.

Package 10 is not broad final repo polish. Final README polish, screenshots,
portfolio storytelling, dashboard-like examples, and final closeout belong to
Package 11 or a later explicit polish pass.

The Package 10 source of truth is:

- `docs/gtm_policy.md`

Package 10 uses the locked illustrative policy version:

- `policy_version = "gtm_policy_v1"`

Package 10 must preserve separate churn and expansion raw scores, apply the
exact documented v1 matrix, and keep high churn risk dominant over expansion
actioning.

Preconditions for later Package 10 implementation units:

- Package 8 has written `mart.account_month_scores`.
- The selected scoring month is explicit as `YYYY-MM-01`, or explicit
  latest-scored-month mode is requested.
- Package 9 observability evidence may be consulted only as optional
  quality/safety context if the implementation chooses to use it.

Likely Package 10 commands are:

```bash
python scripts/build_gtm_policy.py --scoring-month "YYYY-MM-01"
python scripts/build_gtm_policy.py --latest
```

Likely Make targets are:

```bash
make build-gtm-policy SCORING_MONTH=YYYY-MM-01
make build-gtm-policy-latest
```

Package 10 local outputs may include:

- `mart.account_month_gtm_policy`
- `metadata.gtm_policy_audit`
- optional ignored exports under `data/outputs/gtm_policy/`

Package 10 must not train, retrain, re-evaluate, promote, rescore, mutate
Package 8/9 outputs, use labels or future outcomes, learn policy thresholds,
add dashboards, add APIs, add cloud infrastructure, integrate with CRM systems,
execute campaigns, or claim commercial validation from synthetic data.

Before each Package 10 implementation unit:

- Restate that `docs/gtm_policy.md` is authoritative.
- Restate the active Package 10 unit.
- Restate the locked `gtm_policy_v1` matrix and the high-churn-dominates rule.
- Run `git status --short`.
- Confirm no live `.agent/*.md` file will be modified or committed.
- Identify intended files to change and tests to add or update.
- Identify stop-condition risk.

Before closing a Package 10 implementation unit, run:

- focused tests for implemented policy behaviour
- `make verify`
- `make public-safety-check`
- `git diff --check`
- `git status --short`

For docs-only Package 10A, do not add code, scripts, tests, Make targets,
DuckDB tables, generated outputs, or exports. Document skipped implementation
tests explicitly. Confirm no generated policy outputs, DuckDB files, MLflow
runs, model artefacts, caches, private files, or live `.agent/*.md` files are
staged or tracked.

## Package 2 runbook — DuckDB warehouse

When working on Package 2, agents must preserve the following boundaries.

### Active package

Package 2 is limited to loading Package 1 generated synthetic source CSVs into a local DuckDB warehouse and validating source-table contracts.

Package 2 proves that source CSVs can be safely persisted and validated in DuckDB.

Package 2 does not make the data model-ready.

Durable Package 2 autonomous execution guidance lives in
`docs/agentic_execution.md`.

### Required stance

Before each implementation unit, restate:

- the active Package 2 unit
- the specific runbook rule that constrains the unit
- the out-of-scope behaviours that must not be introduced

### Allowed changes

Package 2 may change:

- Warehouse loader code under `src/account_health/warehouse/`
- Warehouse CLI script under `scripts/`
- Warehouse tests under `tests/`
- Warehouse documentation under `docs/`
- Makefile commands for real, tested warehouse operations
- `.gitignore` only to strengthen public-repo safety

### Forbidden changes

Package 2 must not add:

- Account-month features
- Churn labels
- Expansion labels
- Model training
- MLflow logic
- Champion selection
- Batch scoring
- Health bands
- Recommended actions
- Monitoring reports
- Dashboards
- Notebooks
- APIs
- Cloud deployment
- Vercel
- Real SaaS integrations
- Real customer data
- Incremental loading
- dbt
- Orchestration frameworks

### Security checks

Before closing each Package 2 unit, run:

- `make verify`
- `git diff --check`
- `git status --short`

Generated or local-only files must not be tracked.

Confirm none of the following are staged or tracked:

- `data/generated/`
- `data/warehouse/`
- `*.duckdb`
- `*.duckdb.wal`
- `mlruns/`
- `.env`
- `AGENTS.override.md`
- `.agent/current_execution_context.md`
- `.agent/package_gate.md`
- `.agent/agent_runbook.md`
- `__pycache__/`
- `.pytest_cache/`
- `*.egg-info/`

Only `.agent/*.example` files may be committed. Live `.agent/*.md` files are
ignored local controls.

### Stop conditions

Stop and request review before:

- Changing the account-month grain.
- Adding or changing modelling labels.
- Adding model training.
- Adding MLflow.
- Adding scoring.
- Adding dashboards.
- Adding cloud deployment.
- Adding Vercel.
- Adding real customer data.
- Weakening public-repo safety.
- Committing generated artefacts.
- Adding unapproved production dependencies.
- Removing tests.
- Expanding beyond raw/source warehouse loading.
