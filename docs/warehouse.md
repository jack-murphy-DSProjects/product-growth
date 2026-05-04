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

## Mart schema

Package 3 introduces a `mart` schema with:

- `mart.account_month`

Package 4 adds a separate benchmark mart table:

- `mart.account_month_baselines`

`mart.account_month` contract:

- One row per active subscribed account x calendar observation month.
- Primary grain: `account_id`, `observation_month`.
- `observation_month` is the first day of the month.
- `observation_month_end` is the last day of the month.
- Features represent what was known on or before `observation_month_end`.
- Labels use a future 90-day horizon after `observation_month_end`.
- `churn_90d` and `expansion_90d` are renewal-based labels from
  `raw.renewals`.
- Point-in-time MVP features are built from approved raw source families.
- `raw.accounts.synthetic_archetype` is excluded from modelling features.

`mart.account_month_baselines` contract:

- Built from `mart.account_month`.
- Additive table; Package 4 does not modify `mart.account_month`.
- One output row per `mart.account_month` row.
- Primary grain: `account_id`, `observation_month`.
- Contains deterministic bounded churn and expansion baseline scores.
- Contains component columns so rule scores are auditable.
- Contains ranks and deciles as prioritisation helpers only.
- Does not use `churn_90d`, `expansion_90d`, or `synthetic_archetype` as
  scoring inputs.
- Does not create final account health bands, recommended GTM actions, ML
  predictions, MLflow runs, monitoring reports, dashboards, APIs, or cloud
  outputs.

The default local account-month command is:

```bash
make build-account-month
```

The default local baseline command is:

```bash
make build-rule-baselines
```

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

Package 3 may create:

- `metadata.feature_build_audit`

Package 4 may create:

- `metadata.baseline_build_audit`

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

The feature build audit table records one row per local `mart.account_month`
build.

Expected fields include:

- `build_id`
- `built_at_utc`
- `output_table`
- `row_count`
- `account_count`
- `min_observation_month`
- `max_observation_month`
- `churn_eligible_count`
- `churn_positive_count`
- `expansion_eligible_count`
- `expansion_positive_count`
- `source_max_date`

This table is local audit metadata only. It is not an orchestration state store.

The baseline build audit table records minimal local metadata about
`mart.account_month_baselines` builds.

Expected fields may include:

- `build_id`
- `built_at_utc`
- `source_table`
- `output_table`
- `baseline_version`
- `row_count`
- `account_count`
- `min_observation_month`
- `max_observation_month`
- `status`

This table is local audit metadata only. It is not an orchestration framework,
monitoring system, model registry, MLflow substitute, or production metadata
store.

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

Package 3 owns account-month features, labels, and leakage checks. Package 4
owns separate deterministic rule baseline benchmark artefacts. Later packages
own ML models, final scoring, health bands, actions, and monitoring.

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
