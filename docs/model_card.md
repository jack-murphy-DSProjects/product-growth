# Model Card

## Status

This is the portfolio-level model card for the local synthetic-data workflow in
`product-growth`. It documents the durable model contract implemented across
Packages 5 through 9. Run-specific metrics, manifests, and model artefacts are
generated locally and intentionally remain out of git.

## Intended Use

The project trains separate churn-risk and expansion-propensity models to support
local GTM prioritization, account-health review, and RevOps-facing batch outputs
inside a synthetic portfolio workflow. Their scores are inputs to later review
layers; they are not direct instructions to contact or suppress a customer.

## Not Intended For

These models are not intended for:

- automated customer-impacting decisions without human review
- production deployment or live commercial operations
- credit, employment, eligibility, or other high-stakes decisions
- use on real customer or company data inside this public project
- claims of validated retention uplift, expansion revenue, or commercial ROI

## Data

All model inputs come from deterministic synthetic B2B SaaS source tables
generated inside the repo: accounts, users, usage events, subscriptions,
invoices, support tickets, CRM touchpoints, and renewals. Modeling rows are
assembled at one account-month snapshot grain in `mart.account_month`.

The workflow uses only generated local data. No real customer, company, invoice,
support, CRM, or usage data belongs in the repository.

## Targets

The system models two independent 90-day renewal outcomes:

- `churn_90d`
- `expansion_90d`

Labels are derived from future renewal windows after each snapshot month. Label
eligibility is explicit, and rows without a valid label for the requested target
are excluded from target-specific training data rather than coerced to zero.

## Features

Approved model features summarize point-in-time account lifecycle, usage,
support, billing, CRM, and segment context available as of the snapshot month.
The modeling dataset uses an explicit allowlist plus forbidden-name checks to
exclude target-like, future-looking, score-derived, and generator-only fields.

Leakage controls are exercised in both implementation and tests:

- point-in-time feature construction in `mart.account_month`
- future-window labels separated from current-state features
- explicit rejection of forbidden modeling feature names
- dedicated tests covering future renewals and future source records

## Models

The implemented candidate families are:

- logistic regression
- random forest

Both use scikit-learn pipelines with deterministic preprocessing, explicit
feature metadata, logged split metadata, and local MLflow tracking. Champion
promotion is target-specific: an ML candidate is promoted only when the Package
6 selection contract says it sufficiently beats the rule baseline. Otherwise,
the honest outcome can be baseline retention or no ML champion promotion.

## Evaluation

Evaluation uses a fixed temporal holdout rather than a random split. Candidate ML
models are compared against deterministic commercial rule baselines using:

- standard classifier metrics for ML candidates
- top-K capacity metrics for GTM operating relevance
- holdout-month robustness slices inside the fixed holdout
- segment robustness checks
- illustrative utility sensitivity
- baseline-versus-ML champion selection evidence

Holdout-month slices are not described as rolling backtests because the repo does
not implement rolling retraining.

## Calibration

Calibration checks are part of ML evaluation through Brier score, log loss, and
calibration-bin summaries. Package 9 later inspects raw score distributions for
completed local scoring runs. The repo does not claim that synthetic local
calibration proves production calibration quality.

## Segment Checks

Evaluation inspects supported synthetic segments such as segment, region,
current plan, company-size band, and industry, with caveats for sparse or
one-class slices. The workflow uses global models with segment evaluation rather
than segment-specific models.

## Governance And Human Review

The repo keeps prediction and policy separate by design:

- feature allowlists and temporal splits constrain model training inputs
- rule baselines provide a required benchmark before ML promotion
- local MLflow manifests and audit tables record promotion evidence
- raw scores stay separate from deterministic `gtm_policy_v1` outputs
- recommended actions remain review outputs, not validated autonomous actions

Human review is required before any hypothetical GTM use. The deterministic
policy layer is illustrative, inspectable, and intentionally separate from model
training.

## Monitoring

The repository implements local score observability rather than production
monitoring. Package 9 checks scored-population structure, score validity, score
distribution summaries, safe segment slices, and observed model lineage for
completed local batch runs.

## Limitations

The main limitations are deliberate:

- synthetic data cannot validate real customer behavior or business impact
- the workflow is local and batch-oriented, not a hosted production system
- there are no live integrations, online serving paths, or automated actions
- the fixed deterministic policy layer is illustrative rather than learned or
  commercially validated
- local observability summaries are not proof of live drift detection,
  automated governance, or future concept-drift resilience
