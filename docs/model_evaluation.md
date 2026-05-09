# Model Evaluation Contract

## Status

Package 6 implements the local layered evaluation and champion-selection
workflow for the SaaS account health project. This document defines the durable
evaluation and champion-selection contract.

Package 6 consumes Package 5 candidate ML models and Package 4 rule baselines.
It does not train new candidates by default, create production scores, register
models, promote models, deploy models, or create GTM policy outputs.

## Purpose

Package 6 evaluates candidate churn and expansion models against rule baselines
and commercial operating metrics, then selects one target-specific champion for:

- `churn_90d`
- `expansion_90d`

The evaluation must answer whether an ML candidate is useful under realistic
GTM capacity constraints, whether it beats the rule baseline in meaningful
ways, whether probability interpretation needs caveats, and whether performance
is robust across important synthetic SaaS segments and holdout months.

It must be possible for Package 6 to conclude that no ML candidate sufficiently
beats the rule baseline for a target.

## Non-goals

Package 6 must not add:

- MLflow registry use.
- Model registration.
- Model promotion.
- Deployment.
- Production scoring outputs.
- Final account scores.
- Account health bands.
- Recommended GTM actions.
- Monitoring dashboards.
- Hosted APIs.
- Cloud infrastructure.
- Real company or customer data.
- Segment-specific models.
- Full rolling retraining backtests.
- Default candidate retraining.
- Mutation of `mart.account_month`.
- Baseline scores, ranks, deciles, or components as ML features.

Package 7 owns registry and promotion. Package 8 owns production-style batch
scoring and policy outputs. Package 9 owns monitoring.

## Inputs

Package 6 reads:

- `mart.account_month`
- `mart.account_month_baselines`
- local Package 5 MLflow candidate runs and model artefacts
- Package 5 feature and split metadata logged with each run

Required Package 5 MLflow artefacts include:

- `features.json`
- `split_config.json`
- model artefact under the run's `model` artifact path

Required Package 5 run dimensions:

- `target`
- `candidate_model`
- `train_end_month`

Expected candidate families:

- `logistic_regression`
- `random_forest`

Expected targets:

- `churn_90d`
- `expansion_90d`

## MLflow Stance

Package 6 consumes existing local Package 5 candidate runs and model artefacts.
It should fail clearly if expected runs, feature metadata, split metadata, or
model artefacts are missing.

Package 6 must not silently retrain candidates to fill missing MLflow runs.
Retraining requires explicit human approval and belongs outside the default
Package 6 MVP evaluation path.

Package 6 must keep MLflow local-only:

- no registry APIs
- no aliases
- no promotion
- no remote tracking requirement
- no hosted MLflow infrastructure
- no deployment

## Evaluation Stance

Package 6 uses the Package 5 fixed temporal holdout. Package 5 defines train
rows as:

```text
observation_month <= train_end_month
```

Package 5 defines holdout rows as:

```text
observation_month > train_end_month
```

Package 6 should evaluate candidate predictions and baselines on that fixed
holdout. It may add holdout-month temporal robustness slices inside the same
fixed holdout.

Do not call holdout-month slices a rolling backtest. A rolling backtest would
require actual rolling retraining across multiple train/test cutoffs, which is
out of scope for the Package 6 MVP.

## Baseline Stance

Package 4 baseline scores are deterministic ranking scores. They are not
calibrated probabilities.

Allowed baseline metrics:

- ROC AUC
- average precision
- top-K precision
- top-K recall
- lift at K
- capture rate at K
- positives captured at K
- accounts selected at K

Forbidden baseline probability metrics in the MVP:

- log loss
- Brier score
- calibration bins
- predicted-versus-observed calibration curves

Baseline scores must not be used as Package 6 ML features.

## Metric Families

### Standard Metrics

Standard metrics support evaluation but must not be the sole champion-selection
rule.

For ML candidates:

- ROC AUC
- average precision
- log loss
- Brier score
- accuracy at a simple 0.5 probability threshold, if reported

For baselines:

- ROC AUC
- average precision

ROC AUC and average precision may be computed for baselines because they use
ranking order, not calibrated probability interpretation. Skip ROC AUC when an
evaluation slice contains only one target class.

### GTM Operating Metrics

GTM operating metrics are the primary evidence for champion selection.

Required top-K percentages:

- top 5%
- top 10%
- top 20%

Optional count K values may be reported only when enough holdout rows exist:

- top 25
- top 50
- top 100

For each target, candidate, and K slice, report:

- `accounts_selected`
- `positives_captured`
- `precision_at_k`
- `recall_at_k`
- `lift_at_k`
- `capture_rate_at_k`
- `base_positive_rate`

Definitions:

- `accounts_selected`: number of rows selected in the K slice.
- `positives_captured`: positive target labels among selected rows.
- `precision_at_k`: positives captured divided by accounts selected.
- `recall_at_k`: positives captured divided by total positives in the
  evaluated rows.
- `lift_at_k`: precision at K divided by the base positive rate.
- `capture_rate_at_k`: same numerator and denominator as recall at K, reported
  for GTM readability.
- `base_positive_rate`: total positives divided by total evaluated rows.

Ties at the K boundary must be deterministic. The default tie-breaker should be
stable and auditable, such as `account_id`, after sorting by descending score.

### Calibration Metrics

Calibration checks apply to ML candidates only.

Report:

- Brier score.
- Log loss.
- Calibration bins.
- Mean predicted rate by bin.
- Observed positive rate by bin.
- Row count by bin.
- Positive count by bin.

Calibration outputs should include caveats when bins are sparse or when
predicted probabilities should be treated mainly as ranking scores.

### Segment Robustness Metrics

Where the fields are present, evaluate by:

- `segment`
- `region`
- `current_plan`
- `company_size_band`
- `industry`

For each segment slice, report row counts, positive counts, base positive rate,
and top-K operating metrics where support is sufficient.

Use minimum-support caveats. Do not compute ROC AUC for one-class segments.
Do not hide low-support or one-class slices; report them with caveats.

Package 6 does not train segment-specific models.

### Holdout-month Temporal Metrics

Within the fixed holdout, evaluate each `observation_month` slice.

Report:

- holdout month
- row count
- positive count
- base positive rate
- top-K operating metrics where support is sufficient
- ROC AUC and average precision only when both classes are present

Sparse or one-class holdout months should produce caveats, not misleading
metrics.

### Economic Utility Sensitivity

Package 6 may apply a simple illustrative assumption grid for commercial
utility.

Example assumptions may vary:

- value of a retained churn-risk account
- probability that an intervention saves an at-risk account
- cost per retention intervention
- value of a won expansion opportunity
- probability that outreach converts an expansion-ready account
- cost per expansion motion

Utility sensitivity must be labelled as illustrative. Synthetic data cannot
support real ROI claims.

For each target, model, and scenario at the same top-K slice, the MVP utility
formula is:

```text
illustrative_net_utility =
    positives_captured * value_per_positive * intervention_success_rate
    - accounts_selected * cost_per_account
```

The same assumption grid and formula must be applied to ML candidates and rule
baselines. These assumptions are sensitivity inputs only, not real ROI claims.

## Champion Selection

Champion selection is separate for churn and expansion.

Primary selection evidence should use GTM operating metrics, especially:

- precision at top 10%
- lift at top 10%
- capture rate at top 10%
- positives captured at top 10%

ROC AUC and average precision are supporting evidence. They must not be the
sole decision rule.

The selected champion may be:

- an ML candidate
- the rule baseline
- no ML champion, if ML does not sufficiently beat the baseline

Champion selection must preserve target-specific caveats for calibration,
segment robustness, holdout-month robustness, economic utility, and synthetic
data limitations.

## Local Outputs

Package 6 generated file artefacts should be written under the ignored path:

- `data/outputs/model_evaluation/evaluation_summary.json`
- `data/outputs/model_evaluation/champion_selection_manifest.json`
- `data/outputs/model_evaluation/evaluation_report.md`

Optional local CSV summaries may also be written under:

- `data/outputs/model_evaluation/`

Generated evaluation files must not be committed.

## Local Execution

The approved local evaluation command is:

```bash
make evaluate-candidate-models
```

The command expects the Package 6 prerequisite flow to have already produced
the local warehouse, rule baselines, and Package 5 MLflow candidate runs:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
make build-rule-baselines
make train-candidate-models
make evaluate-candidate-models
```

The CLI is:

```bash
scripts/evaluate_candidate_models.py
```

It accepts explicit local paths for the warehouse, MLflow tracking URI,
experiment name, train-end month, and generated output directory. It must fail
clearly if the expected local Package 5 candidate runs or model artefacts are
missing. It must not retrain candidates as a fallback.

## DuckDB Output Tables

Package 6 should use a minimal, boring MVP table set:

- `metadata.model_evaluation_audit`
- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

Optional detail tables should be added only if implementation needs them:

- `mart.model_topk_evaluation`
- `mart.model_segment_evaluation`
- `mart.model_calibration_summary`
- `mart.model_utility_sensitivity`

These tables are local evaluation outputs in the ignored DuckDB warehouse. They
are not production scoring tables, registry metadata, monitoring tables, health
band outputs, or GTM action tables.

## Champion Manifest

The champion selection manifest should include one record per target.

Required fields per target:

- `target`
- `selected_champion_model_family`
- `mlflow_run_id`
- `model_artifact_uri`
- `selection_status`
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

`selection_status` should support values such as:

- `ml_champion_selected`
- `baseline_retained`
- `no_ml_candidate_sufficiently_beats_baseline`
- `insufficient_evidence`

If the selected champion is not an ML candidate, `mlflow_run_id` and
`model_artifact_uri` should be null or explicitly marked not applicable.

## Package 6 Implementation Units

Package 6 remains split into:

1. Package 6A - docs-first evaluation contract
2. Package 6B - evaluation input and MLflow candidate loading
3. Package 6C - fixed holdout scoring, metrics, and baseline comparison
4. Package 6D - calibration, segment robustness, and holdout-month robustness
5. Package 6E - economic utility sensitivity and champion manifest
6. Package 6F - CLI, Make target, tests, docs closeout

## Expected Tests For Later Units

Later Package 6 implementation should test:

- missing `mart.account_month` fails clearly
- missing `mart.account_month_baselines` fails clearly
- missing MLflow experiment, runs, feature metadata, split metadata, or model
  artefacts fail clearly
- remote MLflow tracking is rejected
- target-specific null labels are excluded consistently with Package 5
- invalid labels fail clearly
- invalid probabilities fail clearly
- baseline scores are treated as ranking scores
- baselines are excluded from log loss, Brier score, and calibration bins
- top-K percentage metrics are correct
- top-K count metrics are skipped or caveated when there are too few rows
- deterministic tie-breaking is stable
- one-class segments do not compute ROC AUC
- low-support segments produce caveats
- sparse holdout months produce caveats
- champion selection uses operating metrics and can retain the baseline
- no MLflow registry, promotion, alias, or deployment behavior is used
- no production scoring, health bands, or recommended GTM actions are created
- generated evaluation artefacts remain ignored and untracked
