# Feature Contract

## Status

This is an initial Package 0 placeholder. The final feature list, data types,
transformation logic, and validation tests will be added after synthetic source
data and DuckDB contracts exist.

## Modeling Grain

Features will be built at the account-month grain: one row per account per
snapshot month. Each feature must represent information available as of that
snapshot month.

## Expected Feature Families

- Account lifecycle: age, tenure, onboarding stage, renewal proximity, and
  lifecycle status.
- Segment attributes: company size, industry, region, plan tier, sales motion,
  and customer tier.
- Usage and engagement: active users, event volume, product breadth, frequency,
  recency, stickiness, and usage trends.
- Adoption: activated users, feature adoption, seat utilization, admin activity,
  and multi-stakeholder coverage.
- Billing and subscription: ARR, plan changes, seat changes, invoice status,
  payment delay, discounts, and contract state.
- Support: ticket volume, severity mix, unresolved issues, resolution time, and
  escalation patterns.
- CRM activity: sales touches, CS touches, executive engagement, renewal
  preparation, campaign interactions, and contact coverage.
- Historical outcomes: prior churn, contraction, expansion, or renewal outcomes
  when they are known before the snapshot month.

## Point-In-Time Safety

Feature generation must prevent leakage. No feature may use events, outcomes,
or derived values that occur after the snapshot date. Labels may use future
windows, but those label windows must be excluded from feature inputs.

## Deterministic Transformations

Feature transformations should be deterministic for a given synthetic dataset
and snapshot configuration. Aggregations, windows, thresholds, categorical
mappings, and default values should be documented and tested.

## Null Handling

Null handling must be explicit. Later packages should document whether missing
values mean not applicable, no observed activity, unknown source value, or
synthetic generation gap. Any imputation used for modeling should be recorded in
the feature contract.

## Segment Evaluation Readiness

The feature table should include stable segment fields needed for robustness
checks. These fields should support evaluation by account size, lifecycle stage,
plan tier, region, industry, sales motion, and other synthetic GTM segments.

## Future Contract Requirements

Later packages should define:

- Feature names, types, and descriptions.
- Source tables used for each feature.
- Snapshot cutoffs and aggregation windows.
- Null semantics and imputation behavior.
- Leakage tests.
- Contract tests for duplicate account-month rows.
- Segment columns required for evaluation and reporting.
