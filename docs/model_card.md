# Model Card

## Status

No model has been trained yet. This file is a template for later packages.

## Intended Use

Describe how the churn risk and expansion propensity models are intended to
support GTM prioritization, capacity planning, account health review, and
RevOps-facing batch outputs.

## Not Intended For

Describe excluded uses, including automated customer-impacting decisions without
human review, production deployment, credit or employment decisions, and use on
non-synthetic data inside this public project.

## Data

Document the synthetic source tables, generation period, account-month snapshot
window, training period, validation period, and test or backtest periods.

## Targets

Document the churn and expansion labels, prediction windows, eligibility rules,
positive class definitions, and any exclusions.

## Features

Summarize feature families, point-in-time safeguards, leakage tests, null
handling, categorical treatment, and segment fields used for evaluation.

## Models

Document candidate model classes, training configuration, random seeds, feature
sets, preprocessing steps, and selected champion versions.

## Evaluation

Report baseline-versus-ML comparisons, fixed holdout results, holdout-month
robustness slices, top-K capacity metrics, economic utility sensitivity,
precision and recall at operating thresholds, and any standard classifier
metrics. Do not describe holdout-month slices as a rolling backtest unless
actual rolling retraining is implemented.

## Calibration

Report calibration curves, calibration error, score distribution checks, and any
post-processing used to make thresholds operationally meaningful.

## Segment Checks

Report performance by key synthetic segments such as account size, lifecycle
stage, plan tier, region, industry, sales motion, and customer tier.

## Monitoring

Document planned or observed monitoring for data quality, feature drift,
prediction drift, recommendation volume, capacity breaches, and scoring run
metadata.

## Limitations

Document known limitations, including synthetic data realism, lack of production
integrations, local batch scope, future concept drift, and policy dependence.

## Human Review

Describe how GTM users should review recommendations before action, how
thresholds should be governed, and when a recommendation should be suppressed or
escalated.
