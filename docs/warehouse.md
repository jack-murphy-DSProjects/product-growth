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

Package 6 may add local evaluation summary mart tables:

- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

Optional Package 6 detail tables, if implementation justifies them, are:

- `mart.model_topk_evaluation`
- `mart.model_segment_evaluation`
- `mart.model_calibration_summary`
- `mart.model_utility_sensitivity`

Later local operating layers add:

- Package 8: `mart.account_month_scores`
- Package 9: `mart.score_observability_summary`,
  `mart.score_distribution_by_month`, `mart.score_distribution_by_segment`
- Package 10: `mart.account_month_gtm_policy`

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

Package 6 evaluation table contract:

- Built from the Package 5 fixed holdout, local Package 5 MLflow candidate
  runs, and `mart.account_month_baselines`.
- Contains evaluation summaries and champion selection evidence only.
- Does not modify `mart.account_month`.
- Does not create production scoring outputs, account health bands,
  recommended GTM actions, model registry metadata, monitoring reports,
  dashboards, APIs, or cloud outputs.
- Baseline rows are evaluated as ranking benchmarks, not calibrated
  probabilities.
- Generated DuckDB tables remain local and must not be committed.

Package 7 promotion audit contract:

- Built from the Package 6 champion-selection manifest and referenced local
  Package 5 MLflow source run metadata.
- Contains local promotion audit metadata only.
- Does not modify `mart.account_month`, `mart.account_month_baselines`, Package
  5 source runs, or Package 6 evaluation outputs.
- Does not create production scoring outputs, account health bands,
  recommended GTM actions, monitoring reports, dashboards, APIs, cloud outputs,
  or real customer data.
- Baseline-retained, no-ML-champion, and insufficient-evidence outcomes may be
  recorded as skipped or failed promotion attempts, but they must not create
  registered MLflow model versions.

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

Package 6 may create:

- `metadata.model_evaluation_audit`

Package 7 may create:

- `metadata.model_promotion_audit`

Package 8 may create:

- `metadata.batch_scoring_audit`

Package 9 may create:

- `metadata.score_observability_audit`

Package 10 may create:

- `metadata.gtm_policy_audit`

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

The model evaluation audit table records minimal local metadata about
evaluation runs.

Expected fields may include:

- `evaluation_id`
- `evaluated_at_utc`
- `evaluation_version`
- `warehouse_path`
- `experiment_name`
- `train_end_month`
- `target_count`
- `candidate_count`
- `status`

This table is local evaluation audit metadata only. It is not an MLflow
registry, model promotion log, deployment record, monitoring report, or
production scoring audit.

The model promotion audit table records minimal local metadata about Package 7
promotion attempts.

Expected fields may include:

- `promotion_id`
- `promoted_at_utc`
- `promotion_version`
- `target_key`
- `target_label`
- `registered_model_name`
- `model_version`
- `alias`
- `source_mlflow_run_id`
- `source_model_artifact_uri`
- `package6_manifest_path`
- `package6_evaluation_version`
- `package6_selection_status`
- `promotion_status`
- `failure_reason`

This table is local promotion audit metadata only. It is not an MLflow
replacement, production scoring table, deployment record, monitoring report,
health-band table, recommended-action table, or orchestration state store.

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
