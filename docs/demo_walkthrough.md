# Demo Walkthrough

## Purpose

This walkthrough is the simplest honest way to review `product-growth` as a
public portfolio project. It demonstrates the end-to-end local path from
synthetic SaaS source data to deterministic RevOps-facing policy outputs without
adding a dashboard, hosted app, production integration, or claim of real
commercial validation.

The project thesis is:

> Commercial ML becomes useful when scores are embedded inside an inspectable
> operating process: source contracts, point-in-time features, credible
> baselines, layered evaluation, controlled promotion, explicit scoring,
> observability, and deterministic GTM policy.

## Prerequisites

- Python environment able to run the repo's `make` targets
- Local filesystem access for generated ignored artefacts
- No external customer data, cloud account, API key, or production service
  required

First-time setup:

```bash
make setup
```

## Simplest Honest Demo Path

Run the workflow in order:

```bash
make generate-synthetic-data
make load-warehouse
make build-account-month
make build-rule-baselines
make train-candidate-models
make evaluate-candidate-models
make promote-model-registry
make score-account-month BATCH_SCORING_LATEST=1
make monitor-account-scores-latest
make build-gtm-policy-latest
```

Why this is the recommended demo path:

- It exercises every completed operating layer once.
- It uses explicit `latest` selectors rather than silently processing all
  historical rows.
- It ends on the real final portfolio output: `mart.account_month_gtm_policy`.
- It keeps generated outputs local and ignored.

The path is honest about its gates. `make promote-model-registry` can proceed
only when Package 6 produced eligible ML champions. If the local evidence says a
baseline should be retained or no ML champion is justified, stop there and
inspect `mart.model_champion_selection` instead of forcing promotion, scoring,
or policy output.

If you want a fixed scoring month instead of the explicit latest mode, replace
the final three commands with:

```bash
make score-account-month SCORING_MONTH=YYYY-MM-01
make monitor-account-scores SCORING_MONTH=YYYY-MM-01
make build-gtm-policy SCORING_MONTH=YYYY-MM-01
```

## Expected Local Artefacts

The demo creates local generated artefacts such as:

- `data/generated/`
- `data/warehouse/account_health.duckdb`
- `mlruns/`
- `data/outputs/model_evaluation/`
- `data/outputs/model_registry/`
- optional local exports under `data/outputs/batch_scoring/`,
  `data/outputs/score_observability/`, or `data/outputs/gtm_policy/` when those
  export flags are used

These are intentionally ignored local files. They should not be committed.

## Package Flow In Plain English

| Package | Reviewer-facing meaning |
| --- | --- |
| 0 | Establishes the public repo skeleton and initial narrative. |
| 1 | Creates synthetic source records that are safe to publish. |
| 2 | Loads those sources into a local DuckDB warehouse and validates them. |
| 3 | Builds point-in-time account-month features and future renewal labels. |
| 4 | Adds deterministic commercial baselines for honest comparison. |
| 5 | Trains separate churn and expansion candidate models. |
| 6 | Evaluates candidates on operating metrics and chooses target-specific champions only when justified. |
| 7 | Promotes eligible ML champions locally with explicit evidence. |
| 8 | Scores one explicit account-month population. |
| 9 | Checks the scored population and summarizes raw score distributions. |
| 10 | Converts separate raw scores into deterministic GTM policy outputs. |
| 11 | Makes the finished repo easier to understand, run, inspect, and close out. |

## Key Tables To Inspect

| Table | Why it matters |
| --- | --- |
| `mart.model_champion_selection` | Shows that champion selection is explicit and target-specific rather than assumed. |
| `mart.account_month_scores` | Shows the raw churn and expansion score layer before GTM policy. |
| `mart.score_observability_summary` | Shows whether the selected scored month is structurally inspectable before actioning. |
| `mart.score_distribution_by_month` | Shows raw score distribution summaries by target and month. |
| `mart.account_month_gtm_policy` | Shows the final RevOps-facing review table. |
| `metadata.batch_scoring_audit` | Shows which scoring run wrote the raw score table. |
| `metadata.gtm_policy_audit` | Shows which deterministic policy run wrote the final table. |

## Safe Example SQL Queries

Run these in any DuckDB client connected to
`data/warehouse/account_health.duckdb`.

### 1. See the selected champions

```sql
SELECT
  target,
  selected_champion_model_family,
  selection_status,
  primary_metric
FROM mart.model_champion_selection
ORDER BY target;
```

This confirms whether each target produced an eligible ML champion or whether
the honest result was to retain a baseline or withhold promotion.

### 2. Inspect the latest raw score population

```sql
SELECT
  observation_month,
  COUNT(*) AS account_count,
  MIN(churn_score) AS min_churn_score,
  MAX(churn_score) AS max_churn_score,
  MIN(expansion_score) AS min_expansion_score,
  MAX(expansion_score) AS max_expansion_score
FROM mart.account_month_scores
GROUP BY observation_month
ORDER BY observation_month DESC;
```

This shows the raw prediction layer before health bands or recommended actions
exist.

### 3. Check the latest observability summary

```sql
SELECT
  scoring_month,
  prior_scoring_month,
  expected_account_count,
  scored_account_count,
  population_matches_expected,
  status,
  warning_codes_json
FROM mart.score_observability_summary
ORDER BY scoring_month DESC
LIMIT 5;
```

This answers a basic but important operational question: did the selected scored
population match the expected local account-month population?

### 4. Review score distributions by target

```sql
SELECT
  scoring_month,
  target,
  account_count,
  minimum,
  maximum,
  mean,
  p50,
  p90,
  top_decile_threshold
FROM mart.score_distribution_by_month
ORDER BY scoring_month DESC, target;
```

This helps inspect score shape without calling synthetic local summaries
"production drift detection."

### 5. Inspect the final RevOps-facing policy table

```sql
SELECT
  scoring_month,
  health_band,
  recommended_action,
  action_priority,
  COUNT(*) AS account_count
FROM mart.account_month_gtm_policy
GROUP BY scoring_month, health_band, recommended_action, action_priority
ORDER BY scoring_month DESC, action_priority, health_band, recommended_action;
```

This is the clearest final output for a portfolio reviewer: separate model scores
have been turned into deterministic review categories that a RevOps or CS team
could inspect.

### 6. Pull a concrete review queue

```sql
SELECT
  account_id,
  current_plan,
  current_mrr,
  churn_score,
  expansion_score,
  health_band,
  lifecycle_motion,
  recommended_action,
  action_priority,
  action_reason_code
FROM mart.account_month_gtm_policy
WHERE scoring_month = (
  SELECT MAX(scoring_month)
  FROM mart.account_month_gtm_policy
)
ORDER BY
  CASE action_priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
  churn_score DESC,
  expansion_score DESC,
  account_id
LIMIT 20;
```

This is the clearest demonstration of the GTM-facing layer. The query produces
an inspectable queue
without hiding the original churn and expansion scores or claiming that the
synthetic action is commercially validated.

### 7. Trace the final write path

```sql
SELECT
  scoring_month,
  selector,
  input_score_row_count,
  output_policy_row_count,
  policy_version,
  observability_status,
  status
FROM metadata.gtm_policy_audit
ORDER BY completed_at_utc DESC
LIMIT 5;
```

This shows that the final policy output has its own append-only local audit trail
rather than mutating the raw score layer in place.

## How To Interpret Package 10 Outputs

`gtm_policy_v1` is intentionally simple and deterministic:

- high churn risk dominates expansion actioning
- high churn plus high expansion becomes save-first, not pure upsell
- low churn plus high expansion is the only pure expansion motion
- every valid raw score row maps to exactly one policy row

The policy table is useful because it makes the operating choice explicit. It is
not evidence that the recommended action would improve revenue, retention, or
customer outcomes in a real business. The data, thresholds, and actions are
synthetic portfolio examples.

## Which Outputs Prove The Thesis

The strongest evidence chain is:

1. `mart.model_champion_selection` shows disciplined model choice rather than
   defaulting to ML.
2. `mart.account_month_scores` preserves separate churn and expansion evidence.
3. `mart.score_observability_summary` shows a scored population can be checked
   before use.
4. `mart.account_month_gtm_policy` shows how separate scores become a concrete,
   reviewable GTM queue.
5. The audit tables show that each layer is rerunnable and inspectable locally.

Together, those outputs demonstrate GTM usefulness as an operating design. They
do not demonstrate real commercial truth because the entire project uses
synthetic data.

## Public-Safety And Synthetic-Data Notes

- All records are synthetic.
- No real customer, company, invoice, support, or CRM data belongs in this repo.
- No generated artefact from the demo should be committed.
- Local observability summaries are diagnostic portfolio outputs, not production
  governance or live drift claims.
- Health bands and recommended actions are illustrative policy labels, not real
  customer truth.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| Warehouse or mart table is missing | An upstream command was skipped | Re-run the demo path in order from `make generate-synthetic-data`. |
| `make promote-model-registry` fails | Package 6 did not produce an eligible ML champion, or evidence is missing | Inspect `mart.model_champion_selection`; a baseline-retained outcome is an honest endpoint, not a bug to work around. |
| Scoring or policy command rejects the selector | No explicit month or explicit latest mode was supplied | Use `BATCH_SCORING_LATEST=1`, `make monitor-account-scores-latest`, `make build-gtm-policy-latest`, or an explicit `SCORING_MONTH=YYYY-MM-01`. |
| Expected local files are absent from git status | They are generated artefacts by design | Inspect them locally; do not stage or commit them. |
| You want a UI or production integration | That is intentionally outside the project boundary | Review `README.md`, `docs/project_closeout.md`, and `docs/out_of_scope.md` instead of extending the demo. |
