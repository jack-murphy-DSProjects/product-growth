# Score Observability Contract

## Status

Package 9 owns local batch scoring observability for the synthetic
`product-growth` workflow.

Package 9 observes the raw score outputs produced by Package 8. It does not
rescore accounts, retrain models, govern models automatically, or convert scores
into GTM policy outputs.

This document is the durable source of truth for Package 9.

## Purpose

Package 9 makes local Package 8 score runs inspectable after they complete. It
should answer:

- Did the selected scored population look structurally valid?
- Were the churn and expansion scores valid probability-like outputs?
- How were those scores distributed overall and across safe descriptive
  segments?
- Which Package 8 scoring lineage was observed?
- How did the selected scored month compare with the nearest earlier scored
  month, when one exists?

The goal is honest local observability for synthetic batch scoring outputs, not
real production drift detection or automated model governance.

## Responsibilities

Package 9 owns:

- Resolving exactly one scored month for observation.
- Reading Package 8 score and audit evidence.
- Checking the selected scored population against the expected
  `mart.account_month` population.
- Validating raw churn and expansion score shape and value bounds.
- Summarizing score distributions for each target.
- Summarizing score distributions across safe descriptive segments already
  present in `mart.account_month`.
- Summarizing the model/version lineage that Package 8 actually used.
- Comparing the selected scored month with the nearest earlier scored month.
- Writing local observability summaries and append-only observability audit
  records.
- Optionally writing ignored local exports for human review.

## Non-Goals

Package 9 must not:

- Create account health bands.
- Create recommended GTM actions.
- Create Sales or Customer Success playbooks.
- Create RevOps action tables.
- Define GTM policy thresholds.
- Create dashboards, APIs, hosted services, or cloud deployment.
- Retrain models, re-evaluate models, select champions, promote models, or
  rescore accounts.
- Perform label-based performance monitoring.
- Require labels, future outcomes, real data, cloud services, or live
  production integrations.
- Treat local synthetic summaries as proof of real-world drift detection,
  production readiness, or automated model governance.

## Package Boundaries

### Boundary With Package 8 Batch Scoring

Package 8 produces raw local scores and score-run audit evidence:

- `mart.account_month_scores`
- `metadata.batch_scoring_audit`

Package 8 owns loading promoted champions and generating score rows. Package 9
must not replace, rerun, reinterpret, or mutate that work.

Package 9 starts only after Package 8 has written score outputs. It observes
what was scored, validates those outputs, and summarizes them. It does not use
live MLflow registry calls as the authority for what should have been scored;
Package 8 owns champion loading, and Package 9 reads the score/audit evidence
that Package 8 recorded.

`docs/batch_scoring.md` remains the source of truth for Package 8 score
semantics.

### Boundary With Package 10 Deterministic GTM Policy Layer

Package 10 owns deterministic GTM policy outputs, including account health
bands, recommended GTM actions, RevOps-facing action outputs, and the minimal
policy-layer examples approved for that package. Broad public polish remains
deferred beyond Package 10.

Package 9 may report diagnostic score distribution information, including
top-decile thresholds and movement warnings, but those diagnostics must never be
presented as action thresholds, health bands, playbook assignments, or GTM
recommendations.

## Inputs

### Required Inputs

- `mart.account_month_scores`
- `metadata.batch_scoring_audit`
- `mart.account_month` for safe descriptive context and expected-population
  checks
- `docs/batch_scoring.md` as the score-semantics contract

### Optional Lineage Context

Package 9 may use either of the following only as additional lineage context
when helpful:

- `metadata.model_promotion_audit`
- `mart.model_champion_selection`

These optional inputs may enrich the lineage summary, but Package 9 must still
be able to reason from Package 8 score/audit evidence when they are absent.

### Inputs Package 9 Must Not Require

- Labels such as `churn_90d` or `expansion_90d`
- Future outcomes
- Retraining
- Rescoring
- Live MLflow registry calls as loading authority
- Real customer or company data
- Cloud services
- Dashboards
- APIs

## Outputs

Likely Package 9 outputs are:

- `metadata.score_observability_audit`
- `mart.score_observability_summary`
- `mart.score_distribution_by_month`
- `mart.score_distribution_by_segment`
- Optional `mart.scoring_lineage_summary` or equivalent normalized lineage
  output
- Optional ignored local exports under
  `data/outputs/score_observability/`

Suggested output roles:

- `metadata.score_observability_audit`: append-only run evidence, status, and
  warnings.
- `mart.score_observability_summary`: selected-month summary, expected-vs-scored
  population results, prior-month linkage, and overall status.
- `mart.score_distribution_by_month`: one scored-month x target distribution
  summary.
- `mart.score_distribution_by_segment`: one scored-month x target x segment
  slice summary.
- `mart.scoring_lineage_summary` or equivalent: normalized observed lineage by
  scored month and target when implementation benefits from a separate table.

These are local generated observability artefacts. They are not scoring tables,
health-band tables, recommended-action tables, model evaluation outputs, model
registry state, or public examples.

## Scoring Month Resolution

Each Package 9 run must require exactly one selector:

- an explicit scoring month, or
- an explicit latest selector.

Resolution rules:

- An explicit scoring month must be a month-start date in `YYYY-MM-01` form.
- `latest` means the latest scored month present in
  `mart.account_month_scores`.
- Missing selectors and ambiguous selectors are invalid.
- The selected month must contain score rows.
- The prior comparison month, when needed, is the nearest earlier scored month
  present in `mart.account_month_scores`, not necessarily the previous calendar
  month.

## Expected Population Checks

Package 9 should resolve the expected population from `mart.account_month` for
the selected scoring month and compare it with the scored population in
`mart.account_month_scores`.

The check should establish:

- the expected account count for the selected month
- the scored account count for the selected month
- whether scored `account_id` values match the expected population
- whether the selected scored month preserves one row per account/month score
  grain

Expected-population validation is structural only. It must not depend on labels
or future outcomes.

If the expected population cannot be resolved safely, Package 9 must fail rather
than silently observing an unknown population.

## Score Validity Checks

For both churn and expansion scores, Package 9 must fail on:

- missing required input tables
- no score rows for the selected month
- duplicate account/month score rows
- null `account_id`
- invalid scoring month values
- null score values
- non-numeric score values
- scores outside `[0, 1]`
- unresolved expected population
- inconsistent required score lineage

Required lineage is inconsistent when the selected score rows and Package 8
audit evidence do not agree on the target-specific scoring lineage needed to
explain what was scored.

## Score Distribution Summaries

Package 9 should summarize churn and expansion separately.

Required distribution fields for each target:

- account count
- minimum
- maximum
- mean
- standard deviation
- `p01`
- `p05`
- `p10`
- `p25`
- `p50`
- `p75`
- `p90`
- `p95`
- `p99`
- top-decile threshold
- top-decile share

Top-decile fields are diagnostic distribution information only. They are not
GTM policy thresholds and must not imply account health bands or recommended
actions.

## Segment-Level Summaries

Segment summaries may use only safe descriptive columns already available in
`mart.account_month`.

Likely current examples include:

- `current_plan`
- `company_size_band`
- `region`
- `industry`
- `segment`

Package 9 must not introduce labels, future outcomes, segment-specific models,
or segment-specific GTM policies. If optional safe segment columns are missing,
the run may continue with a warning. Small segments should be flagged so readers
do not over-interpret unstable summaries.

## Model And Version Lineage Summaries

Package 9 should summarize the model/version lineage observed in Package 8 score
rows and Package 8 scoring audit evidence, including the target-specific model
names, model versions, score run identifiers, and any recorded source lineage
needed to explain the run.

Rules:

- Package 8 score/audit evidence is the primary observed lineage source.
- Live MLflow registry state is not the Package 9 authority.
- Optional Package 7 or Package 6 lineage context may be joined only for extra
  explanation.
- Missing optional lineage context may warn when Package 8 score/audit evidence
  is still sufficient.
- Contradictory required lineage is a failure.

## Current-Versus-Prior Scored Month Comparison Semantics

When an earlier scored month exists, Package 9 compares the selected month with
the nearest earlier scored month.

The comparison may include:

- scored account counts
- expected-versus-scored population results
- distribution metric deltas for churn and expansion
- segment distribution deltas where comparable segment slices exist
- observed lineage changes between scored months

This is an aggregate scored-output comparison. It is not label-based
performance monitoring and it must not assume that the prior month is the
previous calendar month.

### One-Month-History Behaviour

If no earlier scored month exists:

- the run should succeed with a warning
- prior-month fields should be null
- current-month validity, distribution, and lineage summaries should still be
  produced

## Warning Versus Failure Semantics

### Hard Failures

Package 9 must fail for:

- missing required input tables
- no score rows for the selected month
- duplicate account/month score rows
- null `account_id`
- invalid scoring month
- null score values
- non-numeric score values
- scores outside `[0, 1]`
- unresolved expected population
- inconsistent required score lineage

### Warnings

Package 9 may succeed with warnings for:

- no prior scored month
- small segment sample size
- missing optional safe segment columns
- large score movement versus the prior scored month
- all scores being nearly identical or having very low variance
- incomplete optional lineage context when Package 8 score/audit evidence is
  still valid

Warnings must be visible in the outputs and distinguishable from clean success.
They are diagnostic review prompts, not automated business decisions.

## Audit Design

`metadata.score_observability_audit` should be append-only.

Audit evidence should be sufficient to answer:

- Which scoring month was selected?
- Was the selector explicit or latest?
- Which prior scored month was used, if any?
- Which required tables were found?
- What expected and scored population counts were observed?
- Which required lineage was observed from Package 8 score/audit evidence?
- Which checks passed, warned, or failed?
- Did the run end in clean success, success with warnings, or failure?
- Were optional local exports requested?

Failed runs should write audit evidence where it is safe to do so, so reviewers
can inspect why the run stopped.

## Idempotence And Rerun Behaviour

Package 9 reruns should be inspectable and deterministic:

- `metadata.score_observability_audit` remains append-only.
- Summary mart tables may be replaced for the selected scoring month on rerun.
- Failed runs should record audit evidence where safe.
- Successful runs with warnings must be distinguishable from clean success.
- Package 9 must not mutate Package 8 score rows in
  `mart.account_month_scores`.
- Package 9 must not mutate Package 8 audit rows in
  `metadata.batch_scoring_audit`.

## Optional Local Exports

Package 9 may optionally write ignored local exports under:

- `data/outputs/score_observability/`

Exports are for local human inspection only. They must remain ignored generated
artefacts and must not contain:

- health bands
- recommended GTM actions
- policy thresholds
- real customer data
- secrets
- dashboards
- public examples unless a later package explicitly approves them

## Local CLI And Make Contract

Package 9 exposes the local CLI:

```bash
python scripts/monitor_account_scores.py --scoring-month "YYYY-MM-01"
python scripts/monitor_account_scores.py --latest
```

Approved Make targets are:

```bash
make monitor-account-scores SCORING_MONTH=YYYY-MM-01
make monitor-account-scores-latest
```

Optional repo-local observability exports must stay under
`data/outputs/score_observability/`.

## Synthetic And Local-Only Limitations

Package 9 observes synthetic local batch outputs only.

It does not prove:

- production drift detection
- automated model governance
- customer-impacting alert readiness
- business-value impact
- live integration correctness

Local score movement can be useful for inspecting the synthetic workflow, but it
must not be described as evidence that a production model is healthy or unsafe.

## Review Checklist

Before implementing or closing Package 9 work, verify:

- Package 9 remains batch scoring observability only.
- Package 8 remains the owner of score generation and score-run audit evidence.
- Package 10 remains the owner of deterministic GTM policy outputs, health
  bands, and recommended actions.
- Exactly one scoring-month selector is required.
- `latest` resolves from `mart.account_month_scores`.
- Prior comparison uses the nearest earlier scored month.
- One-month history succeeds with a warning and null prior fields.
- Expected-population checks use `mart.account_month` without labels.
- Score validity failures are hard failures.
- Score distribution summaries are target-specific and diagnostic only.
- Segment summaries use safe descriptive columns only.
- Package 9 observes lineage from Package 8 evidence rather than live MLflow
  registry state.
- Audit rows remain append-only.
- Reruns do not mutate Package 8 score rows or audit rows.
- Optional exports remain local and ignored.
- No health bands, GTM actions, policy thresholds, dashboards, APIs, cloud
  deployment, retraining, re-evaluation, champion selection, promotion,
  rescoring, or label-based performance monitoring have leaked into Package 9.
