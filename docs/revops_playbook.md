# RevOps / GTM Review Guide

## Purpose

This guide explains how to inspect the final operator-facing output in the
synthetic local demo. It is not a deployed RevOps process, a CRM playbook, or a
claim that the policy improves real retention or expansion outcomes.

## What To Inspect

Start with:

- `mart.account_month_gtm_policy`

That table is the final RevOps-facing review table. It keeps the raw model scores
visible and adds deterministic policy fields for one scored month:

- `churn_score`
- `expansion_score`
- `health_band`
- `lifecycle_motion`
- `recommended_action`
- `action_priority`
- `action_reason_code`

## What One Row Means

One row represents one synthetic account for one explicit scored month after the
local workflow has:

1. produced separate churn-risk and expansion-propensity scores,
2. checked the scored population locally, and
3. applied the fixed illustrative `gtm_policy_v1` matrix.

The row is a review output. It is not customer truth, an automated instruction,
or proof that the suggested action would work in a real company.

## What The Policy Layer Does

The policy layer converts two separate score dimensions into a consistent local
review vocabulary. It:

- preserves the original churn and expansion scores,
- assigns one deterministic health band,
- assigns one lifecycle motion and one recommended action,
- records a reason code so a reviewer can reconstruct why the row landed there.

That makes the handoff legible to a GTM operator without pretending that the
policy was learned or commercially validated.

## What It Does Not Decide

The repo does not decide:

- whether a real customer should be contacted,
- which human owns the account,
- how much Sales or CS capacity exists,
- whether a playbook changed retention or expansion,
- whether a CRM workflow, campaign, or escalation should actually run.

Those decisions remain outside this synthetic local portfolio project and would
require real operating context, governance, and outcome evidence.

## How Score Conflicts Are Handled

`gtm_policy_v1` treats churn risk as the dominant safety signal:

- high churn risk plus high expansion propensity becomes a save-first motion,
  not pure upsell,
- medium churn risk plus high expansion propensity becomes stabilise-first,
- only low churn risk plus high expansion propensity becomes a pure expansion
  motion.

That conflict handling is deterministic and inspectable. It is a policy choice,
not a model prediction.

## Questions For A Monthly Review

A GTM operator reviewing the synthetic monthly output would ask:

1. Did the scored population match the expected account-month population?
2. Which actions are concentrated in the current month, and are any counts
   surprising?
3. Which accounts are high churn and high expansion at the same time?
4. Do score distributions or segment summaries look materially different from
   the prior scored month?
5. Which outputs should be reviewed by humans before any hypothetical action?

For the supporting evidence behind those questions, inspect:

- `mart.account_month_scores`
- `mart.score_observability_summary`
- `mart.score_distribution_by_month`
- `metadata.batch_scoring_audit`
- `metadata.gtm_policy_audit`

## Honest Boundary

Everything here is synthetic, local-only, and review-oriented. The repository
demonstrates how a deterministic handoff can be made inspectable; it does not
implement a live GTM operating process.
