# Warehouse

Package 2 introduces the local analytical warehouse for the `product-growth` project.

The warehouse is a local DuckDB database created from generated synthetic SaaS source CSVs.

The warehouse is not a production deployment, not a cloud service, and not a real customer-data store. It is a reproducible local persistence layer for the public portfolio project.

## Default paths

Generated source CSVs are expected at:

- `data/generated/`

The local DuckDB database is written to:

- `data/warehouse/account_health.duckdb`

Both generated data and DuckDB files are local artefacts and must not be committed.

## Warehouse schemas

Package 2 uses two DuckDB schemas:

- `raw`
- `metadata`

The `raw` schema contains source-faithful tables loaded from Package 1 generated CSVs.

The `metadata` schema contains minimal load metadata.

## Planned mart roadmap

Package 3 will eventually introduce a `mart` schema with:

- `mart.account_month`

Package 3A documents the planned mart contract only. It does not create the
`mart` schema or `mart.account_month` table.

Planned `mart.account_month` contract:

- One row per active subscribed account x calendar observation month.
- Primary grain: `account_id`, `observation_month`.
- `observation_month` is the first day of the month.
- `observation_month_end` is the last day of the month.
- Features represent what was known on or before `observation_month_end`.
- Labels use a future 90-day horizon after `observation_month_end`.
- `churn_90d` and `expansion_90d` are renewal-based labels from
  `raw.renewals`.

## Raw source tables

Package 2 loads the following source tables:

- `raw.accounts`
- `raw.users`
- `raw.usage_events`
- `raw.subscriptions`
- `raw.invoices`
- `raw.support_tickets`
- `raw.crm_touchpoints`
- `raw.renewals`

These tables preserve the Package 1 source-table contract.

They are not account-month features, model inputs, scored outputs, or RevOps marts.

## Metadata tables

Package 2 may create:

- `metadata.load_audit`

The load audit table records minimal information about each source table load.

Expected fields may include:

- `load_id`
- `loaded_at_utc`
- `source_dir`
- `database_path`
- `table_name`
- `row_count`
- `status`

This table exists to make local batch runs inspectable.

It is not an orchestration framework.

## Loader behaviour

The Package 2 loader:

- Accepts explicit `source_dir` and `database_path` arguments.
- Reads existing generated CSVs.
- Fails clearly if required CSVs are missing.
- Creates or replaces raw source tables.
- Defaults to deterministic overwrite/rebuild behaviour.
- Validates source table contracts.
- Records minimal load metadata.

The loader must not generate synthetic data.

Synthetic data generation belongs to Package 1.

The default local command is:

```bash
make load-warehouse
```

## Validation responsibilities

Package 2 validates source-level integrity only.

Package 2 validation includes:

- Required source files exist.
- Required columns exist.
- Required tables are non-empty.
- Primary keys are unique.
- Foreign keys resolve to parent source tables.
- Dates and timestamps parse.
- Basic date ordering is valid.

Package 2 validation does not include:

- Account-month feature completeness.
- Churn label construction.
- Expansion label construction.
- Leakage checks for modelling windows.
- Model training.
- Model evaluation.
- Champion selection.
- Scoring.
- Health bands.
- Recommended GTM actions.
- Monitoring reports.

Those responsibilities belong to later packages.

## Out-of-scope behaviours

Package 2 must not introduce:

- Real customer data.
- SaaS integrations.
- Cloud deployment.
- Vercel.
- Hosted APIs.
- Dashboards.
- Notebooks.
- MLflow logic.
- dbt.
- Orchestration frameworks.
- Incremental loading.
- Production migration tooling.
- Account-month marts.
- Feature engineering.
- Labels.
- Model outputs.

## Security and public repo safety

The following must never be committed:

- `data/generated/`
- `data/warehouse/`
- `data/processed/`
- `data/outputs/`
- `*.duckdb`
- `*.duckdb.wal`
- `mlruns/`
- `artifacts/models/`
- `artifacts/tmp/`
- `.env`
- `AGENTS.override.md`
- `.agent/current_execution_context.md`
- `.agent/package_gate.md`
- `.agent/agent_runbook.md`

Only `.example` agent files should be committed.
