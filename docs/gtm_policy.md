# GTM Policy Contract

## Status

Package 10 owns the deterministic GTM policy layer for the synthetic
`product-growth` workflow.

This document is the durable source of truth for Package 10. Package 10 is a
policy-output package, not a model-development package and not the final
portfolio-polish package.

## Purpose

Package 10 converts Package 8 raw score outputs into inspectable, deterministic
account-month GTM operating outputs that a RevOps or Customer Success reviewer
could reason about locally.

It should answer:

- Given separate churn-risk and expansion-propensity scores for one scored
  account-month, which deterministic GTM policy outcome applies?
- Which health band, lifecycle motion, recommended action, action priority, and
  reason code follow from that policy?
- How can a later reviewer reconstruct which version of the policy ran and what
  it produced?

Package 10 uses deliberately simple, fixed, illustrative policy rules. The v1
thresholds are not learned from real outcomes, are not commercially validated,
and are not claims about optimal intervention design.

## Package Boundary

Package 10 starts after raw Package 8 scores exist.

Package 10 may:

- Consume Package 8 raw score rows from `mart.account_month_scores`.
- Optionally inspect Package 9 observability evidence as quality/safety context.
- Join safe descriptive account context that already exists in approved upstream
  synthetic contracts.
- Apply the locked deterministic v1 GTM policy matrix in this document.
- Write RevOps-facing policy outputs and append-only policy audit metadata.
- Optionally write a small ignored local export under `data/outputs/gtm_policy/`.
- Add only the light documentation needed to explain the Package 10 operating
  layer.

Package 10 must preserve:

- Separate raw score dimensions for churn risk and expansion propensity.
- Package 8 score semantics and Package 9 observability semantics.
- The synthetic-data-only and public-repo-safety boundaries.
- The distinction between prediction and policy.

Package 10 must not mutate Package 8 or Package 9 outputs.

## Inputs

### Required Inputs

- `mart.account_month_scores`
- `mart.account_month` only for approved safe descriptive context fields
- A single explicit scoring-month selector:
  - `SCORING_MONTH=YYYY-MM-01`, or
  - an explicit latest-scored-month mode

### Optional Inputs

Package 10 may optionally inspect Package 9 evidence such as:

- `metadata.score_observability_audit`
- `mart.score_observability_summary`

Those inputs may support a recorded gate or warning status, but the v1 policy
matrix itself must remain deterministic from the raw score pair and must not be
retrained, re-estimated, or distribution-fit from observability outputs.

### Inputs Package 10 Must Not Use

- Labels such as `churn_90d` or `expansion_90d`
- Future outcomes
- Package 4 baseline outputs as policy inputs
- `synthetic_archetype`
- Real customer/company data
- Learned or optimized policy rules

## Outputs

### `mart.account_month_gtm_policy`

Preferred grain:

- one row per `account_id` x `scoring_month`

Preferred fields:

- `account_id`
- `scoring_month`
- `churn_score`
- `expansion_score`
- `health_band`
- `lifecycle_motion`
- `recommended_action`
- `action_priority`
- `action_reason_code`
- `policy_version`
- `created_at_utc`
- `scoring_run_id` or equivalent when available from Package 8
- churn and expansion model-lineage fields when available from Package 8
- approved safe descriptive context fields already present upstream, such as:
  - `current_plan`
  - `company_size_band`
  - `region`
  - `industry`
  - `current_mrr`

Safe descriptive context is carried for review convenience only. Package 10 must
not use labels, future outcomes, generator-only fields, or private data as policy
inputs.

### `metadata.gtm_policy_audit`

Preferred fields:

- `run_id`
- `policy_version`
- `scoring_month`
- `started_at_utc`
- `completed_at_utc`
- `input_score_row_count`
- `output_policy_row_count`
- health-band counts
- recommended-action counts
- priority counts
- observability gate/warning status when used
- `status`
- warning/error details

These tables are local generated artefacts. They are not model-training tables,
model-evaluation tables, monitoring dashboards, public business claims, or CRM
execution outputs.

## Non-Goals

Package 10 must not:

- Train, retrain, re-evaluate, select, promote, or rescore models.
- Mutate Package 8 raw scores or Package 9 observability outputs.
- Use labels or future outcomes.
- Learn, optimize, or auto-tune the policy.
- Add dashboards, APIs, cloud deployment, CRM integration, campaign execution,
  email automation, playbook engines, reinforcement learning, or optimization
  engines.
- Claim that synthetic-data actions are commercially validated.
- Perform final README polish, screenshots, broad portfolio storytelling,
  dashboard-like examples, or repository closeout work.

## Locked v1 Policy Contract

### Policy Version

The initial locked policy version is:

- `policy_version = "gtm_policy_v1"`

Any change to the matrix, thresholds, taxonomy, or boundary semantics requires
an explicit decision/update before implementation changes.

### Score Buckets

Churn-risk buckets:

| Bucket | Rule |
| --- | --- |
| `high_churn_risk` | `churn_score >= 0.70` |
| `medium_churn_risk` | `churn_score >= 0.40 and churn_score < 0.70` |
| `low_churn_risk` | `churn_score < 0.40` |

Expansion-propensity buckets:

| Bucket | Rule |
| --- | --- |
| `high_expansion_propensity` | `expansion_score >= 0.70` |
| `medium_expansion_propensity` | `expansion_score >= 0.40 and expansion_score < 0.70` |
| `low_expansion_propensity` | `expansion_score < 0.40` |

These cutoffs are fixed illustrative thresholds for the synthetic portfolio
project. They are not learned thresholds, policy optimizations, or commercial
recommendations validated on real outcomes.

### Exact Health Band Names

The only allowed v1 `health_band` values are:

- `Critical`
- `At Risk`
- `Stable`
- `Growth Ready`

Health bands are deterministic policy outputs, not trained targets.

### Exact Lifecycle Motion Values

The only allowed v1 `lifecycle_motion` values are:

- `Retention-led expansion watch`
- `Retention`
- `Stabilise then expand`
- `Risk monitoring`
- `Expansion`
- `Nurture`
- `Maintain`

### Exact Recommended Action Names

The only allowed v1 `recommended_action` values are:

- `Executive save plan before expansion`
- `Immediate retention intervention`
- `Resolve risks before expansion outreach`
- `Customer success risk review`
- `Prioritise expansion outreach`
- `Nurture for future expansion`
- `Monitor in standard cadence`

Recommended actions are deterministic policy outputs, not trained targets.

### Exact Action Priority Values

The only allowed v1 `action_priority` values are:

- `P1`
- `P2`
- `P3`

Priority semantics:

- `P1`: highest review urgency inside the illustrative policy layer
- `P2`: meaningful follow-up required, but below the save-first or strongest
  growth-ready cases
- `P3`: standard cadence or nurture motion

Priority values are local policy labels for the synthetic workflow. They are not
capacity commitments, SLAs, or validated commercial service levels.

### Exact Action Reason Code Taxonomy

The only allowed v1 `action_reason_code` values are:

- `HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST`
- `HIGH_CHURN_RETENTION`
- `MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST`
- `MEDIUM_CHURN_RISK_REVIEW`
- `LOW_CHURN_HIGH_EXPANSION`
- `LOW_CHURN_MEDIUM_EXPANSION_NURTURE`
- `LOW_CHURN_LOW_EXPANSION_MAINTAIN`

### Deterministic v1 Matrix

| Churn rule | Expansion rule | `health_band` | `lifecycle_motion` | `recommended_action` | `action_priority` | `action_reason_code` |
| --- | --- | --- | --- | --- | --- | --- |
| `churn_score >= 0.70` | `expansion_score >= 0.70` | `Critical` | `Retention-led expansion watch` | `Executive save plan before expansion` | `P1` | `HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST` |
| `churn_score >= 0.70` | `expansion_score < 0.70` | `Critical` | `Retention` | `Immediate retention intervention` | `P1` | `HIGH_CHURN_RETENTION` |
| `churn_score >= 0.40 and churn_score < 0.70` | `expansion_score >= 0.70` | `At Risk` | `Stabilise then expand` | `Resolve risks before expansion outreach` | `P2` | `MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST` |
| `churn_score >= 0.40 and churn_score < 0.70` | `expansion_score < 0.70` | `At Risk` | `Risk monitoring` | `Customer success risk review` | `P2` | `MEDIUM_CHURN_RISK_REVIEW` |
| `churn_score < 0.40` | `expansion_score >= 0.70` | `Growth Ready` | `Expansion` | `Prioritise expansion outreach` | `P1` | `LOW_CHURN_HIGH_EXPANSION` |
| `churn_score < 0.40` | `expansion_score >= 0.40 and expansion_score < 0.70` | `Stable` | `Nurture` | `Nurture for future expansion` | `P3` | `LOW_CHURN_MEDIUM_EXPANSION_NURTURE` |
| `churn_score < 0.40` | `expansion_score < 0.40` | `Stable` | `Maintain` | `Monitor in standard cadence` | `P3` | `LOW_CHURN_LOW_EXPANSION_MAINTAIN` |

The seven rows above are exhaustive and mutually exclusive for valid v1 score
pairs.

## Conflict Handling

Churn risk dominates expansion actioning in v1.

Rules:

- If `churn_score >= 0.70`, the account cannot receive a pure expansion action,
  even when `expansion_score >= 0.70`.
- High churn plus high expansion becomes a save-first motion:
  - `Retention-led expansion watch`
  - `Executive save plan before expansion`
- Medium churn plus high expansion becomes a stabilise-first motion rather than
  direct upsell.
- Low churn plus high expansion is the only pure v1 expansion motion.
- High churn plus low/medium expansion remains a retention motion.
- Low churn plus low expansion remains a monitor/maintain motion.

Package 10 may combine raw score dimensions through this deterministic policy,
but it must preserve both original raw scores in the output table.

## Boundary And Validation Behaviour

Boundary rules:

- Use `>=` when entering the higher risk or higher propensity bucket.
- `0.70` belongs to the higher bucket.
- `0.40` belongs to the medium bucket.

Validation rules:

- `churn_score` and `expansion_score` must be finite, non-null numeric values
  in `[0, 1]`.
- Invalid scores fail validation before any policy row is assigned.
- Each valid account-month score row must map to exactly one v1 policy row.
- Duplicate or ambiguous source score rows must fail before policy assignment.
- Missing scoring-month selectors or ambiguous month selectors must fail.

`scoring_month` must be explicit or explicitly resolved through latest-scored
month mode. Package 10 must not silently infer a month or process all history by
default.

## Observability Relationship

Package 9 remains diagnostic observability over Package 8 raw scores.

Package 10 may optionally read Package 9 outputs as a quality/safety input, for
example to record whether a relevant observability run succeeded cleanly or with
warnings. If used:

- the gate or warning result must be recorded in `metadata.gtm_policy_audit`
- Package 10 must not reinterpret observability diagnostics as policy
  thresholds
- Package 10 must not claim real production readiness or automated governance
- the v1 matrix itself must not change because score distributions moved

Observability evidence can inform review readiness; it does not replace the
deterministic policy contract.

## Audit And Idempotence

Rerun semantics:

- Rerunning one `scoring_month` replaces `mart.account_month_gtm_policy` rows
  for that month.
- `metadata.gtm_policy_audit` is append-only.
- Failed runs should append audit evidence where safe and must not replace
  policy rows.
- Reruns must preserve one current policy row per `account_id` x
  `scoring_month`.
- Package 10 must not mutate `mart.account_month_scores` or Package 9 outputs.

Audit should make it possible to answer:

- Which month was processed?
- Which explicit selector or latest selector was used?
- Which `policy_version` ran?
- How many raw score rows were read and how many policy rows were written?
- Which counts were produced by health band, recommended action, and priority?
- Whether optional observability evidence was checked, warned, or not used?
- Whether the run succeeded, succeeded with warnings, or failed?

## Local CLI And Make Contract

Local CLI:

```bash
python scripts/build_gtm_policy.py --scoring-month "YYYY-MM-01"
python scripts/build_gtm_policy.py --latest
```

Make targets:

```bash
make build-gtm-policy SCORING_MONTH=YYYY-MM-01
make build-gtm-policy-latest
```

Month semantics:

- An explicit scoring month must be in `YYYY-MM-01` month-start form.
- Explicit latest mode should resolve to the latest scored month available in
  `mart.account_month_scores`.
- No CLI or Make target may silently infer the month when neither selector is
  provided.

These commands are implemented by Package 10 and preserve explicit selector
semantics.

## Local Export Semantics

Package 10 may optionally write a small ignored local export under:

- `data/outputs/gtm_policy/`

Exports are generated local artefacts for human inspection only. They must remain
ignored and must not contain:

- real customer data
- labels or future outcomes
- private paths or secrets
- dashboards
- campaign execution outputs
- claims of validated commercial impact

## Public-Safety Stance

Package 10 remains synthetic, local, and illustrative.

- Health bands are policy outputs, not observed truth.
- Recommended actions are policy outputs, not observed truth.
- The fixed thresholds and actions are deliberately simple portfolio examples.
- No output should imply validated commercial recommendations from real data.
- Public examples, if any are added in Package 10, must stay minimal and safe.

## Test Expectations

Later implementation tests must pin the locked v1 contract.

Required focused coverage:

- Each of the seven v1 matrix rows maps to the exact expected:
  - `health_band`
  - `lifecycle_motion`
  - `recommended_action`
  - `action_priority`
  - `action_reason_code`
  - `policy_version`
- Boundary cases are explicit:
  - `churn_score = 0.70`
  - `churn_score = 0.40`
  - `expansion_score = 0.70`
  - `expansion_score = 0.40`
- High churn plus high expansion maps to save-first behaviour rather than pure
  expansion.
- Low churn plus high expansion maps to the pure expansion motion.
- Scores that are null, non-numeric, non-finite, below `0`, or above `1` fail
  before policy assignment.
- Every valid score row maps to exactly one policy row.
- Duplicate source score rows fail rather than creating ambiguous output.
- Reruns replace only the selected month in
  `mart.account_month_gtm_policy`.
- `metadata.gtm_policy_audit` remains append-only.
- Optional observability evidence, when used, is recorded as gate/warning
  context without changing the deterministic matrix.

Suggested matrix boundary fixtures:

| `churn_score` | `expansion_score` | Expected `action_reason_code` |
| --- | --- | --- |
| `0.70` | `0.70` | `HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST` |
| `0.70` | `0.699999` | `HIGH_CHURN_RETENTION` |
| `0.40` | `0.70` | `MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST` |
| `0.40` | `0.699999` | `MEDIUM_CHURN_RISK_REVIEW` |
| `0.399999` | `0.70` | `LOW_CHURN_HIGH_EXPANSION` |
| `0.399999` | `0.40` | `LOW_CHURN_MEDIUM_EXPANSION_NURTURE` |
| `0.399999` | `0.399999` | `LOW_CHURN_LOW_EXPANSION_MAINTAIN` |

## Review Checklist

Before implementing or closing Package 10 work, verify:

- `docs/gtm_policy.md` remains the authoritative Package 10 contract.
- Package 10 still consumes Package 8 raw scores without mutating them.
- Churn risk and expansion propensity remain separate raw score columns.
- `gtm_policy_v1` is the recorded policy version.
- The seven-row matrix, exact strings, and boundary rules have not drifted.
- High churn still dominates expansion actioning.
- Invalid scores fail before assignment.
- Every valid source row maps to exactly one policy row.
- Policy reruns replace only one scoring month and audit remains append-only.
- Optional Package 9 observability context is recorded honestly when used.
- No labels, future outcomes, learned policy, dashboards, APIs, cloud services,
  CRM execution, or commercial-validation claims have leaked into the package.
- Public examples remain minimal and generated local exports remain ignored.

## Deferred Package 11 Or Final-Polish Items

The following are intentionally deferred beyond Package 10:

- final README polish
- screenshots
- broad portfolio storytelling
- dashboard-like examples
- public narrative closeout
- broader example-output polish
- final repository cleanup and presentation pass

Package 11 or a later final-polish pass may improve presentation and examples,
but it should not change the Package 10 v1 policy contract unless a new explicit
decision/update records that change.
