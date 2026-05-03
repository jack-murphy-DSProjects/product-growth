# Design Tradeoffs

## Local Batch Versus Hosted API

Decision: build a reproducible local batch scoring system, not a hosted API.

SaaS GTM scoring usually runs on a cadence: daily, weekly, or monthly account
refreshes that feed RevOps tables and operating reviews. A local batch design is
enough to demonstrate data contracts, feature freshness, scoring reproducibility,
evaluation, and monitoring without adding cloud infrastructure or operational
surface area that is outside the portfolio goal.

## DuckDB Versus Cloud Warehouse

Decision: use DuckDB in later packages as the local analytical warehouse.

DuckDB supports SQL-first analytical workflows without requiring cloud accounts,
credentials, or managed infrastructure. This keeps the project public-safe and
easy to reproduce. A production company could map the same table contracts to a
cloud warehouse later, but that is not part of this repo.

## Synthetic Data Only

Decision: generate and use synthetic SaaS data only.

The project needs to be public, inspectable, and shareable. Synthetic source
tables let the repository demonstrate account, usage, billing, support, renewal,
and CRM-style workflows without exposing private records or relying on external
systems. Synthetic data also makes deterministic tests and examples possible.

## Account-Month Grain

Decision: model at one row per account per snapshot month.

The account-month grain matches GTM operating cadences and supports temporal
evaluation. It also makes leakage control explicit: features describe what was
known as of the snapshot month, while labels describe later churn or expansion
outcomes.

## Separate Churn And Expansion Models

Decision: train independent churn risk and expansion propensity models.

Churn and expansion are different commercial events. Treating them independently
allows each target to have its own labels, metrics, calibration checks,
thresholds, and operating policy. The policy layer can then combine the scores
into health bands and recommended actions.

## Global Models With Segment Evaluation

Decision: start with global models and evaluate robustness by segment.

Segment-specific models can be useful but require enough data, clear ownership,
and separate monitoring. For this project, global models keep the workflow
simple while segment evaluation checks whether performance is acceptable across
customer size, lifecycle stage, industry, region, plan, or other synthetic
segments.

## Operating Metrics Over ROC AUC Alone

Decision: champion selection should depend on operating metrics, not ROC AUC
alone.

ROC AUC can summarize ranking quality, but GTM teams need capacity-aware
decisions. The project will emphasize top-K capture, monthly backtests,
baseline-versus-ML lift, economic utility sensitivity, calibration, and segment
robustness. A model that looks strong by AUC but fails these checks should not
be promoted.

## Deterministic Policy Layer For Health Bands And Actions

Decision: health bands and recommended actions are deterministic outputs.

Training separate targets for health bands or actions would blur the boundary
between prediction and policy. Keeping the policy layer deterministic makes the
recommendation logic inspectable, adjustable, and accountable to GTM capacity
and business rules.
