# Reference Demo Result

## Purpose

This hand-written note records one successful local reference run of the
deterministic demo path described in `README.md` and
`docs/demo_walkthrough.md`. It gives external reviewers a concrete outcome to
anchor on without committing generated data, local databases, MLflow artefacts,
or exported outputs.

## Reference Outcome

For the successful local demo run:

- latest explicit scoring month resolved to `2025-10-01`
- `mart.account_month_scores` contained `429` rows
- `mart.account_month_gtm_policy` contained `429` rows

The matching row counts show that the selected local scored population flowed
through raw scoring into the deterministic GTM policy layer for that reference
run.

## Champion Selection And Promotion

The same local reference state recorded these target-specific champion outcomes:

| Target | Selected champion | Selection status | Primary metric |
| --- | --- | --- | --- |
| `churn_90d` | `random_forest` | `ml_champion_selected` | `precision_at_top_10_pct` |
| `expansion_90d` | `random_forest` | `ml_champion_selected` | `precision_at_top_10_pct` |

The local promotion audit then recorded:

| Target key | Registered model | Model version | Alias | Promotion status |
| --- | --- | --- | --- | --- |
| `churn` | `account_health_churn_model` | `1` | `champion` | `promoted` |
| `expansion` | `account_health_expansion_model` | `1` | `champion` | `promoted` |

These are local synthetic-demo outcomes, not claims that the selected models are
commercially validated for real use.

## Final Policy Distribution

For the reference scoring month `2025-10-01`, the final deterministic policy
table contained:

| `health_band` | `recommended_action` | `action_priority` | Accounts |
| --- | --- | --- | ---: |
| `Stable` | `Monitor in standard cadence` | `P3` | `427` |
| `Stable` | `Nurture for future expansion` | `P3` | `2` |

That distribution is intentionally reported as observed, not made more dramatic
for presentation. In this reference month, the valid synthetic scored
population flowed end to end, but the locked policy assigned only `Stable`
outcomes.

## Representative Output Rows

| `account_id` | `churn_score` | `expansion_score` | `health_band` | `lifecycle_motion` | `recommended_action` | `action_reason_code` |
| --- | ---: | ---: | --- | --- | --- | --- |
| `acct_000046` | `0.34` | `0.44` | `Stable` | `Nurture` | `Nurture for future expansion` | `LOW_CHURN_MEDIUM_EXPANSION_NURTURE` |
| `acct_000024` | `0.30` | `0.27` | `Stable` | `Maintain` | `Monitor in standard cadence` | `LOW_CHURN_LOW_EXPANSION_MAINTAIN` |

## How To Interpret This

This is a reproducibility aid for the public portfolio repo, not a committed
generated artefact and not a benchmark claim. It demonstrates that the intended
local synthetic workflow can complete end to end and preserve row-count parity
between the raw score table and the final policy table for the selected scoring
month.

## Caveats

- The entire workflow uses synthetic data only.
- The reference run is local-only and does not represent hosted deployment.
- The outputs do not prove real retention uplift, expansion revenue, or customer
  validation.
- The deterministic GTM policy outputs are illustrative review categories, not
  commercially validated actions.
