# Model Registry And Promotion Contract

## Status

Package 7 owns the local MLflow registry and model-promotion workflow for the
SaaS account health project.

Package 7 consumes Package 6 champion-selection evidence and existing Package 5
local MLflow model artefacts. It records eligible ML champions in the local
MLflow model registry for future Package 8 batch scoring.

Package 7 does not select champions. Package 6 selects champions.

## Purpose

Package 7 answers:

- Which Package 6 selected champions are eligible for promotion?
- How does an eligible ML champion become a local MLflow registered model
  version?
- Which registered model name and alias should Package 8 use later?
- What Package 5 and Package 6 evidence is carried onto the registered model
  version?
- What local manifest and audit trail record the promotion decision?

The goal is model lifecycle state, not deployment.

## Boundary

Package 7 may:

- Read the Package 6 champion-selection manifest.
- Read existing Package 5 local MLflow runs and model artefacts.
- Validate that a requested target has an eligible ML champion selected by
  Package 6.
- Validate that the source Package 5 model artefact can be loaded locally.
- Register eligible churn and expansion ML champions into separate local MLflow
  registered models.
- Assign aliases, especially `champion`, to promoted model versions.
- Write MLflow tags and metadata linking the registered version to Package 5
  source runs and Package 6 evidence.
- Write a local ignored promotion manifest for Package 8.
- Write a minimal local promotion audit trail.

Package 7 must not:

- Retrain models.
- Re-evaluate models.
- Override Package 6 champion selection.
- Promote Package 4 baselines as MLflow models.
- Scan MLflow and independently choose champions when the Package 6 manifest is
  missing.
- Score accounts.
- Create production scoring outputs.
- Create final account scores.
- Create account health bands.
- Create recommended GTM actions.
- Create monitoring dashboards.
- Add hosted APIs.
- Add cloud infrastructure.
- Use real customer data.
- Train segment-specific models.
- Mutate `mart.account_month`.
- Mutate Package 5 source runs or model artefacts.
- Mutate Package 6 evaluation outputs.

## Target And Naming Policy

Package 7 supports the existing account health targets only:

| Package 7 target key | Package 6 target label | Registered model name |
| --- | --- | --- |
| `churn` | `churn_90d` | `account_health_churn_model` |
| `expansion` | `expansion_90d` | `account_health_expansion_model` |

Churn and expansion are registered separately. Package 7 must not create one
combined multi-output registered model.

Package 7 must not create registered models for rule baselines, account health
bands, GTM actions, monitoring outputs, or scoring tables.

## Registry Stance

Package 7 uses local MLflow tracking and registry only.

It must reject inherited or explicit remote tracking or registry URIs unless a
later durable documentation change and human approval explicitly allow them.
The MVP must not require Databricks, Unity Catalog, hosted MLflow, cloud object
storage, or any other remote registry backend.

Package 7 uses MLflow aliases and tags. It must not use deprecated model
registry stages as the primary lifecycle mechanism.

Forbidden MVP stage names include:

- `Staging`
- `Production`
- `Archived`

## Alias Policy

The primary alias is:

- `champion`

The `champion` alias means:

> Selected by Package 6 and promoted by Package 7 for future local batch
> scoring consumption.

It does not mean:

- online production deployment
- hosted API serving
- cloud deployment
- business approval
- account health band generation
- GTM action generation
- monitoring approval

Package 8 may later load the `champion` alias for local batch scoring. Package
7 must not implement that scoring behavior.

## Required Inputs

Package 7's primary champion evidence input is the generated Package 6 manifest:

- `data/outputs/model_evaluation/champion_selection_manifest.json`

The manifest is a generated local artefact and must not be committed.

Package 7 may cross-check local DuckDB evaluation tables when they exist, but it
must not reconstruct or replace the Package 6 manifest from those tables. If the
manifest is missing, malformed, or ambiguous, Package 7 must fail clearly.

For each requested target, Package 7 requires Package 6 evidence that includes:

- `target`
- `selection_status`
- `selected_champion_model_family`
- `mlflow_run_id`
- `model_artifact_uri`
- `primary_metric`
- `key_topk_metrics`
- `comparison_versus_baseline`
- `calibration_caveats`
- `segment_caveats`
- `temporal_caveats`
- `utility_caveats`
- `synthetic_data_caveat`
- `created_at_utc`
- `evaluation_version`

Package 7 also requires the referenced Package 5 local MLflow source run and
model artefact to exist and load successfully. Expected Package 5 supporting
artefacts include:

- model artefact under the run's `model` artifact path
- `features.json`
- `split_config.json`

## Promotion Eligibility

A requested target is eligible for promotion only when all of these conditions
hold:

- The requested Package 7 target key is `churn` or `expansion`.
- The Package 6 manifest target maps to `churn_90d` or `expansion_90d`.
- Package 6 has exactly one unambiguous champion-selection record for that
  target.
- `selection_status` is `ml_champion_selected`.
- The selected champion is an ML candidate, not a rule baseline.
- `selected_champion_model_family` identifies an approved Package 5 candidate
  family.
- `mlflow_run_id` is present.
- `model_artifact_uri` is present.
- The source Package 5 run can be found in local MLflow tracking.
- The source model artefact can be loaded locally.
- Package 5 feature metadata and split metadata can be read.
- Package 6 evidence is sufficient to explain the selection.

Package 7 must fail clearly for a requested target when:

- Package 6 retained the baseline.
- Package 6 selected no ML champion.
- Package 6 reported insufficient evidence.
- Package 6 evidence is missing, malformed, duplicated, or ambiguous.
- The selected champion type is not ML.
- The source Package 5 run ID is missing or cannot be found.
- The source model URI or artefact path is missing.
- The source model artefact cannot be loaded.
- Local MLflow tracking or registry constraints are ambiguous.

Package 7 must not search across MLflow runs to find a substitute champion.

## MLflow Metadata Policy

Package 7 should write enough metadata for a reviewer to trace a registered
model version back to its training and evaluation evidence without mutating
Package 5 or Package 6 outputs.

Expected registered model or model-version tags include:

- `account_health.package`: `package_7`
- `account_health.target_key`: `churn` or `expansion`
- `account_health.target_label`: `churn_90d` or `expansion_90d`
- `account_health.registered_model_name`
- `account_health.alias`: `champion`
- `account_health.source_mlflow_run_id`
- `account_health.source_model_artifact_uri`
- `account_health.selected_champion_model_family`
- `account_health.package6_selection_status`
- `account_health.package6_evaluation_version`
- `account_health.package6_manifest_path`
- `account_health.package6_created_at_utc`
- `account_health.package7_promotion_version`
- `account_health.promoted_at_utc`
- `account_health.synthetic_data_only`: `true`
- `account_health.consumer`: `package_8_local_batch_scoring`

When available from Package 5 metadata, Package 7 should also record:

- `account_health.train_end_month`
- `account_health.feature_metadata_artifact`
- `account_health.split_config_artifact`

These tags are lineage and consumption metadata. They are not production
deployment metadata, security approvals, or real-business ROI claims.

## Promotion Manifest

Package 7 should write a local ignored manifest for Package 8:

- `data/outputs/model_registry/promotion_manifest.json`

The manifest is generated local state and must not be committed.

When the manifest path is inside this repository, it must stay under the
ignored local output directory:

- `data/outputs/model_registry/`

Temporary paths outside the repository are acceptable for isolated tests.

The manifest should include one record per requested target. Minimum fields:

- `promotion_id`
- `promotion_version`
- `promoted_at_utc`
- `target_key`
- `target_label`
- `registered_model_name`
- `model_version`
- `alias`
- `source_mlflow_run_id`
- `source_model_artifact_uri`
- `selected_champion_model_family`
- `package6_manifest_path`
- `package6_evaluation_version`
- `package6_selection_status`
- `package6_created_at_utc`
- `promotion_status`
- `failure_reason`
- `synthetic_data_only`

For successful promotions:

- `promotion_status` should be `promoted`.
- `model_version` must identify the local MLflow registered model version.
- `alias` should include `champion`.
- `failure_reason` should be null or omitted.

Package 7 MVP promotion is fail-fast for requested targets that are not
eligible ML champions. In that default CLI path, validation failures occur
before registry writes, promotion manifest writes, or audit writes.

For skipped or failed target records:

- `promotion_status` should distinguish clear outcomes such as
  `skipped_baseline_retained`, `skipped_no_ml_champion`,
  `skipped_insufficient_evidence`, `failed_missing_manifest`,
  `failed_ambiguous_evidence`, `failed_missing_source_run`, or
  `failed_unloadable_model`.
- `model_version` and `alias` should be null or omitted when no model was
  promoted.

Package 8 may later consume this manifest. Package 7 must not create Package 8
scoring outputs.

## Audit Design

Package 7 should create a minimal local audit table:

- `metadata.model_promotion_audit`

The audit table is local DuckDB metadata and must not be committed.

Grain:

- One row per promotion attempt x target.

Minimum expected columns:

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

This audit trail is for local inspectability. It is not an orchestration state
store, deployment record, monitoring report, security approval, or business
approval workflow.

## Local Execution Contract

The prerequisite local flow is expected to remain:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
make build-rule-baselines
make train-candidate-models
make evaluate-candidate-models
```

Package 7 promotion runs after Package 6 evaluation. It must not rerun training
or evaluation as an implicit fallback.

The approved local Package 7 promotion command is:

```bash
make promote-model-registry
```

The CLI is:

```bash
scripts/promote_model_registry.py
```

It accepts explicit local paths for the champion-selection manifest, warehouse
database, MLflow tracking URI, MLflow registry URI, generated promotion
manifest, and optional target filters. It must fail clearly if requested
targets are not eligible ML champions. It must not retrain, re-evaluate, score
accounts, deploy models, create health bands, create GTM actions, or add cloud
infrastructure.

Repeated local promotions create a new MLflow model version for each requested
eligible target and move the `champion` alias to the newest promoted version.
The source Package 5 run and Package 6 manifest remain unchanged.

## Generated Artefact Safety

Generated registry, promotion, MLflow, model, DuckDB, scoring, and output
artefacts must remain local and ignored.

Do not commit:

- `data/outputs/model_registry/`
- `data/outputs/model_evaluation/`
- `data/generated/`
- `data/warehouse/`
- `data/processed/`
- `mlruns/`
- `artifacts/models/`
- `artifacts/tmp/`
- `*.duckdb`
- `*.duckdb.wal`
- `.agent/*.md`
- `AGENTS.override.md`
- `.env`

Only safe durable docs and source code should be committed.

## Package 7 Implementation Units

Package 7 remains split into:

1. Package 7A - docs-first model registry and promotion contract.
2. Package 7B - harness refresh for autonomous implementation.
3. Package 7C - promotion manifest loading and validation.
4. Package 7D - local MLflow registry promotion service.
5. Package 7E - promotion manifest and audit outputs.
6. Package 7F - CLI, Make target, tests, docs closeout.

Package 7A was docs-first only and did not add implementation code, scripts,
tests, Make targets, generated outputs, registry writes, MLflow runs, DuckDB
artefacts, model artefacts, scoring outputs, health bands, GTM actions,
dashboards, APIs, or cloud infrastructure.

Package 7F adds the local CLI and Make target for the implemented promotion
workflow.

## Expected Tests For Later Units

Later Package 7 implementation should test:

- missing Package 6 champion-selection manifest fails clearly
- malformed champion-selection manifest fails clearly
- duplicate or ambiguous target evidence fails clearly
- baseline-retained targets are not promoted
- insufficient-evidence targets are not promoted
- no-ML-champion targets are not promoted
- missing `mlflow_run_id` fails clearly
- missing `model_artifact_uri` fails clearly
- missing source Package 5 MLflow run fails clearly
- unloadable source model artefact fails clearly
- remote MLflow tracking or registry URI is rejected
- churn and expansion use separate registered model names
- aliases are used instead of deprecated registry stages
- the `champion` alias points to the promoted version
- required MLflow tags are written
- the local promotion manifest follows the documented schema
- the local promotion audit table follows the documented schema
- Package 5 source runs and Package 6 outputs are not mutated
- no baselines are registered as MLflow models
- no scoring outputs, health bands, GTM actions, dashboards, hosted APIs, or
  cloud infrastructure are created
- generated promotion, registry, MLflow, DuckDB, and model artefacts remain
  ignored and untracked
