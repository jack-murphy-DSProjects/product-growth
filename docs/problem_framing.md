# Problem Framing

## SaaS GTM Problem

B2B SaaS teams make repeated decisions about a large account base with limited
commercial capacity. Customer Success cannot deeply inspect every account each
week. Sales cannot pursue every expansion signal. Growth teams need to know
which product behaviors indicate durable adoption. RevOps needs consistent,
auditable tables that translate data science outputs into operating queues.

The project frames account health as a GTM decision problem: identify which
accounts are likely to churn, which are ready to expand, and which action should
be recommended given both scores and business policy.

## Why Churn And Expansion Scoring Matter

Churn risk and expansion propensity are economically different but tightly
related GTM workflows.

Churn scoring supports retention motions such as executive outreach, CS
intervention, renewal preparation, support escalation, or product adoption
coaching. Expansion scoring supports account prioritization for upsell,
cross-sell, sales-assist, lifecycle campaigns, and product-led growth motions.

Both workflows compete for GTM capacity. A useful system must help teams rank
accounts, understand tradeoffs, and decide what to do next.

## Scores Must Map To Actions

Raw probabilities are not enough for GTM teams. A high churn score might mean
renewal risk, support pain, low usage, billing friction, or poor stakeholder
coverage. A high expansion score might call for a sales motion, a lifecycle
campaign, or no action if churn risk is also high.

This project therefore separates model scores from the deterministic policy
layer. Models estimate churn risk and expansion propensity. Policy rules convert
those scores, thresholds, segments, and capacity assumptions into account health
bands and recommended GTM actions.

## Target Users

- Sales uses expansion propensity to prioritize commercial outreach.
- Customer Success uses churn risk and health bands to plan retention work.
- Growth uses usage and adoption signals to understand scalable activation and
  expansion paths.
- RevOps uses output tables, thresholds, and monitoring to operate the process
  reliably.

## Decisions Supported

- Which accounts should receive proactive CS attention this month?
- Which accounts should be included in a renewal save queue?
- Which accounts are expansion-ready enough for Sales follow-up?
- Which accounts should be routed to growth nurture instead of a human motion?
- How should weekly or monthly GTM capacity be allocated across segments?
- Which recommendations should be monitored, suppressed, or reviewed by humans?

## Modeling Grain

The modeling grain is one row per account per snapshot month. This account-month
grain matches how SaaS GTM teams usually inspect book health, plan renewal work,
review pipeline, and manage monthly operating cadences.

Features must be point-in-time as of the snapshot month. Future outcomes are
reserved for labels, such as churn or expansion over a later observation window.

## Why Separate Churn And Expansion Models

Churn and expansion are not opposites. An account can be high risk and high
potential at the same time, especially near renewal or during a complex rollout.
Combining them into a single target would hide important GTM tradeoffs.

The project will use independent churn and expansion models, then combine their
outputs in the policy layer. This allows evaluation, calibration, thresholds,
and recommended actions to reflect each commercial objective separately.

## Success Beyond AUC

Generic classifier metrics are useful but incomplete. Success means the system
helps GTM teams make better operating decisions.

The project will evaluate whether candidate models beat credible rule baselines,
perform well under top-K capacity constraints, remain stable across holdout
months inside the fixed holdout, calibrate well enough for thresholding, behave
robustly across segments, and create positive economic utility under plausible
business assumptions. Full rolling retraining backtests require actual rolling
retraining and are outside the Package 6 MVP.
