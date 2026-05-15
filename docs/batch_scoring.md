# Batch Scoring Contract

## Status

Package 8 implements a local raw batch scoring workflow for explicit
account-month populations.

Package 8 includes a local CLI and Make target, writes raw DuckDB scoring and
audit tables, and can optionally write ignored local raw scoring exports. It
does not implement a dashboard, API, monitoring report, cloud deployment,
health band, GTM action, recommendation, policy threshold, retraining,
evaluation, champion selection, or model promotion.

## Purpose

Package 8 will run a raw local account-month batch scoring workflow. It will
load the Package 7-promoted MLflow `champion` models, score an explicit
population from `mart.account_month`, write raw churn and expansion model
scores, and record enough local audit metadata for reproducible inspection.

Package 8 is a score production layer only. It is not the account-health
policy layer.

## Responsibilities

Package 8 owns:

- Loading target-specific Package 7 MLflow `champion` model aliases.
- Validating the Package 7 handoff before scoring.
- Reading selected label-free account-month rows from `mart.account_month`.
- Validating the ordered scoring feature set against Package 5 `features.json`.
- Validating forbidden columns against committed feature-contract constants.
- Calling the trained sklearn pipelines to produce raw model scores.
- Writing `mart.account_month_scores` at one row per scored account x scoring
  month.
- Writing append-only `metadata.batch_scoring_audit` records.
- Optionally writing ignored local raw scoring exports.

## Non-Goals

Package 8 must not:

- Train, retrain, evaluate, compare, select, promote, or register models.
- Use Package 5 or Package 6 labelled dataset loaders for scoring population
  reads.
- Filter scoring rows to non-null labels.
- Create health bands, GTM actions, recommendations, playbooks, suppression
  rules, thresholds, monitoring reports, dashboards, APIs, or hosted services.
- Add cloud, cloud-like deployment, orchestration infrastructure, notebooks, or
  real SaaS integrations.
- Require an MLflow model signature, because Package 5 does not create one
  yet.
- Recreate Package 5 preprocessing manually outside the trained sklearn
  pipeline.

## Inputs

Required inputs:

- `mart.account_month` from Package 3.
- Package 7-promoted MLflow registered models:
  - `account_health_churn_model` with alias `champion`
  - `account_health_expansion_model` with alias `champion`
- Package 5 MLflow `features.json` for each promoted source run.
- Package 7 promotion manifest and/or `metadata.model_promotion_audit` as
  cross-check evidence when available locally.
- An explicit scoring population selector:
  - `--scoring-month YYYY-MM-01`, or
  - explicit `--latest` once implemented.

Labels may exist in `mart.account_month`, but they are not required for scoring
and must never be model inputs.

## Outputs

Package 8 outputs:

- `mart.account_month_scores`
- `metadata.batch_scoring_audit`
- Optional ignored local exports under `data/outputs/batch_scoring/`

Package 8 outputs are raw scoring outputs. They are not health-band tables,
recommended-action tables, model evaluation summaries, model registry
metadata, monitoring reports, dashboard extracts, public examples, or hosted
deployment artefacts.

## Scoring Population Semantics

Package 8 scores selected rows from `mart.account_month`.

The scoring reader must be label-free:

- It must not use Package 5 or Package 6 loaders that filter to non-null
  labels.
- It must not require `churn_90d` or `expansion_90d` to exist.
- If labels exist, they may be passed through only as non-feature source
  columns for validation or diagnostics when explicitly approved.
- It must select account-month rows by `observation_month`, not by target-label
  eligibility.

Package 8 must not silently score all history by default. A scoring run must
require an explicit `--scoring-month YYYY-MM-01` or an explicit `--latest`
selector once the command exists.

## Scoring Month Semantics

`observation_month` remains the first day of the account-month observation
period. `--scoring-month YYYY-MM-01` selects exactly rows whose
`observation_month` equals that month.

The explicit `--latest` option resolves to the maximum available
`observation_month` in `mart.account_month` and records the resolved month in
audit metadata. It remains explicit so that a missing CLI argument never
expands into all historical rows.

## Model Loading Design

Package 8 uses Package 7 MLflow registry aliases as the model loading
authority:

- Churn loads `account_health_churn_model` at alias `champion`.
- Expansion loads `account_health_expansion_model` at alias `champion`.

The loaded artifact is the trained sklearn pipeline. The pipeline owns
preprocessing, encoding, imputation, scaling, and model inference. Package 8
must pass the ordered feature frame into the pipeline and must not recreate the
training preprocessing path manually.

## Package 7 Handoff Validation

Before scoring, Package 8 should fail clearly unless each requested target has
a valid promoted champion:

- The expected registered model exists locally.
- The `champion` alias resolves to one model version.
- The resolved model version has Package 7 tags linking it to the Package 5
  source run, Package 5 feature metadata, and Package 6 champion evidence.
- The Package 7 promotion manifest and/or `metadata.model_promotion_audit`
  agrees with the resolved alias when that evidence is available.

MLflow aliases are the loading authority. The Package 7 manifest and audit are
cross-check evidence, not a replacement for loading the promoted `champion`
aliases.

## Feature Contract Validation

Package 8 must use Package 5 MLflow `features.json` as the ordered scoring
feature-list source for each target. The expected keys are:

- `approved_features`
- `numeric_features`
- `categorical_features`

The scoring frame must include every ordered feature from `approved_features`.
The frame passed into the sklearn pipeline must use exactly that ordered
feature list unless a later package explicitly changes the model signature
contract.

Package 8 must also validate feature names against committed forbidden-feature
constants from the modelling feature contract. Forbidden model inputs include:

- labels such as `churn_90d` and `expansion_90d`
- account and row identifiers
- date and timestamp fields
- label eligibility flags
- Package 4 baseline scores, ranks, deciles, components, and audit columns
- `synthetic_archetype` and `accounts.synthetic_archetype`
- target-like, leakage-prone, and future-looking fields

## Leakage Prevention

Package 8 must only pass approved point-in-time features into the trained
pipeline. It must not include anything whose value is known only after
`observation_month_end` for the scored month.

The source table may contain labels and audit fields from prior packages. Their
presence is not a reason to use them. Any feature-list or scoring-frame
validation failure should stop scoring before outputs are written.

## Score Output Schema

`mart.account_month_scores` should contain raw score records at this grain:

- one row per `scoring_run_id` x `account_id` x `observation_month`

Implemented fields:

- `scoring_run_id`
- `account_id`
- `observation_month`
- `churn_score`
- `expansion_score`
- `churn_registered_model_name`
- `churn_model_version`
- `expansion_registered_model_name`
- `expansion_model_version`
- `scored_at_utc`
- `scoring_version`

Scores are raw model scores bounded between 0 and 1. They are not account
health bands, policy thresholds, recommended actions, approved customer-facing
outputs, or monitoring metrics.

## Rank/Decile Stance

Package 8 may include rank or decile fields only as score-layer prioritization
fields for the selected scoring month, such as `churn_score_rank`,
`churn_score_decile`, `expansion_score_rank`, or `expansion_score_decile`.

Ranks and deciles, if included, are not policy outputs. They must not encode
health bands, GTM actions, recommendation labels, suppression rules, capacity
allocation, or business approval.

## Audit Design

`metadata.batch_scoring_audit` should be append-only. A rerun may replace score
rows for the selected scoring month, but it must not mutate previous audit
records.

Audit metadata should be sufficient to answer:

- Which scoring month was selected?
- Was the selector an explicit month or explicit `latest`?
- Which registered model and alias were loaded for each target?
- Which model versions and source MLflow run IDs were used?
- Which Package 5 feature metadata artifact was used?
- How many rows were read and written?
- Did the run succeed or fail, and why?

## Idempotence And Rerun Behaviour

Package 8 should use deterministic replace semantics for score rows:

- For a selected scoring month, reruns replace prior
  `mart.account_month_scores` rows for that month.
- Reruns must not append duplicate score rows for the same
  `account_id` x `observation_month` scoring output.
- Audit records remain append-only, so reruns are inspectable.

The replacement boundary is the selected scoring month, not the full history.

## Local Exports

Package 8 may optionally write ignored local raw scoring exports for human
inspection. Repo-local exports must live under:

- `data/outputs/batch_scoring/`

The CLI supports this through `--export-dir`. Exports must not be committed.

Local exports must not include health bands, GTM recommendations, dashboards,
real customer data, secrets, or environment-specific paths.

## Failure Modes

Package 8 should fail clearly when:

- `mart.account_month` is missing.
- The selected scoring month has no rows.
- The scoring selector is missing or ambiguous.
- A requested MLflow `champion` alias is missing or resolves ambiguously.
- Package 7 handoff evidence conflicts with the loaded alias.
- Required Package 5 `features.json` metadata is missing or malformed.
- Required scoring features are missing from `mart.account_month`.
- Forbidden or leakage-prone fields appear in the model feature list.
- The loaded model cannot produce bounded scores.
- Writing scores or audit metadata fails.

Failure should occur before score rows are written whenever validation fails.

## Review Checklist

Before implementing or closing Package 8 work, verify:

- Package 8 remains raw local batch scoring only.
- No Package 5 or Package 6 labelled dataset loader is used for scoring.
- Scoring requires explicit `--scoring-month YYYY-MM-01` or explicit
  `--latest`.
- Labels may exist in the source table but are never model inputs.
- `features.json` supplies the ordered feature list.
- Committed forbidden-feature constants reject labels, identifiers, date
  fields, eligibility flags, baseline fields, `synthetic_archetype`, and
  future-looking fields.
- The trained sklearn pipeline owns preprocessing.
- No MLflow signature is required for Package 8.
- Score reruns replace rows for the selected scoring month only.
- Audit records remain append-only.
- Health bands, GTM actions, recommendations, monitoring, dashboards, APIs,
  and cloud deployment remain deferred.

## Local Command

The approved Package 8 command is:

```bash
python scripts/score_account_month.py --warehouse-path "data/warehouse/account_health.duckdb" --scoring-month "YYYY-MM-01"
```

The approved Make target is:

```bash
make score-account-month SCORING_MONTH=YYYY-MM-01
```

Use `--latest` or `BATCH_SCORING_LATEST=1` only when the latest available
`observation_month` should be resolved explicitly. Optional raw CSV exports may
be requested with `--export-dir` or `BATCH_SCORING_EXPORT_DIR`.
