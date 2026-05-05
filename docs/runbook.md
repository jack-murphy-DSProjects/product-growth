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
