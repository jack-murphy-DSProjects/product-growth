# product-growth

`product-growth` is a public, local-first portfolio project that shows how
commercial machine learning becomes part of a GTM operating process, not just a
set of model scores. Using synthetic B2B SaaS data only, the repo builds a
reproducible batch workflow from source contracts through churn-risk and
expansion-propensity modeling, local batch scoring, score observability, and a
deterministic RevOps-facing policy table.

In one sentence: this project demonstrates how a Commercial Data Scientist or
Growth Data Scientist can turn account-level predictions into inspectable,
auditable operating outputs for Sales, Customer Success, Growth, and RevOps
without pretending that synthetic data proves real commercial impact.

The commercial problem is ordinary but important: when GTM capacity is limited,
teams need a defensible way to decide which accounts need retention attention,
which are expansion-ready, and which outputs need review before anyone acts on
them.

## The First 60 Seconds

This repo is meant to answer four questions quickly:

1. **What does it do?** It converts synthetic SaaS source data into point-in-time
   account-month features, independent churn and expansion models, scored local
   populations, observability summaries, and deterministic GTM recommendations.
2. **Why does that matter?** A score alone is not an operating system. The repo
   shows the extra layers needed before GTM teams can review scarce-capacity
   retention and expansion queues responsibly: contracts, baselines, evaluation,
   promotion evidence, score checks, and policy rules.
3. **What should I run?** Use the end-to-end local demo path below, or follow the
   fuller walkthrough in `docs/demo_walkthrough.md`.
4. **What should I inspect?** Start with `mart.account_month_gtm_policy`, then
   trace backward through raw scores, observability summaries, champion
   selection, and audit tables.

## What The System Does

The workflow is intentionally local and batch-oriented:

```text
synthetic SaaS sources
  -> DuckDB warehouse
  -> account-month features and labels
  -> commercial rule baselines
  -> candidate churn and expansion models
  -> layered evaluation and champion selection
  -> local MLflow registry promotion
  -> raw batch scores
  -> score observability summaries
  -> deterministic GTM policy layer
  -> RevOps-facing account recommendations
```

The final RevOps-facing output is `mart.account_month_gtm_policy`. It keeps the
raw churn and expansion scores separate, then maps them through the fixed
illustrative `gtm_policy_v1` contract into:

- `health_band`
- `lifecycle_motion`
- `recommended_action`
- `action_priority`
- `action_reason_code`

Those are deterministic policy outputs for a synthetic workflow. They are not
trained targets, customer truth, or validated real-world commercial actions.

## Local Demo Path

First-time setup:

```bash
make setup
```

Then run the intended end-to-end local workflow:

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

The `latest` commands are still explicit selectors; they do not silently score
or action all history. If you want a fixed review month instead, use
`SCORING_MONTH=YYYY-MM-01` on the scoring, monitoring, and policy commands.

For a guided version of the same path, including inspection SQL and common local
failure modes, see `docs/demo_walkthrough.md`.

## What To Inspect

| Layer | Main local table | What it shows |
| --- | --- | --- |
| Features | `mart.account_month` | Point-in-time account-month modeling rows. |
| Baselines | `mart.account_month_baselines` | Auditable commercial benchmark scores. |
| Evaluation | `mart.model_champion_selection` | Why a target-specific champion was or was not selected. |
| Raw scoring | `mart.account_month_scores` | Churn and expansion scores for one explicit local scoring month. |
| Observability | `mart.score_observability_summary` | Whether the scored population and raw scores look structurally valid. |
| Final policy | `mart.account_month_gtm_policy` | The RevOps-facing policy view built from separate raw scores. |

If you only inspect one output, inspect `mart.account_month_gtm_policy`. If you
want to understand whether that table deserves trust, inspect the audit and
handoff tables behind it as well:

- `metadata.model_promotion_audit`
- `metadata.batch_scoring_audit`
- `metadata.score_observability_audit`
- `metadata.gtm_policy_audit`

## What Each Package Contributes

| Package | Contribution to the operating system |
| --- | --- |
| 0 | Repo skeleton and public narrative. |
| 1 | Deterministic synthetic SaaS source data. |
| 2 | DuckDB warehouse and source contract validation. |
| 3 | Point-in-time account-month features and renewal-based labels. |
| 4 | Rule baselines as credible commercial benchmarks. |
| 5 | Candidate churn and expansion model training with local MLflow runs. |
| 6 | Layered evaluation and target-specific champion selection. |
| 7 | Local MLflow registry promotion evidence for eligible champions. |
| 8 | Raw local batch scoring for explicit account-month populations. |
| 9 | Local score observability summaries before GTM use. |
| 10 | Deterministic `gtm_policy_v1` outputs for RevOps review. |
| 11 | Final public walkthrough, repo clarity, and closeout only. |

## What This Demonstrates

The project is designed to show practical portfolio skills across the full
commercial-ML lifecycle:

- source contracts and public-safe synthetic data design
- DuckDB-based local warehousing
- point-in-time feature engineering and leakage discipline
- baseline-versus-ML evaluation rather than metric theater
- local MLflow tracking, promotion evidence, and registry handoff
- explicit batch scoring, audit trails, and rerun semantics
- score observability without overclaiming production monitoring
- deterministic policy design that turns scores into GTM review queues
- repo hygiene, package discipline, and reproducible local workflows

## Public Safety And Honest Limits

This repository is public-safe by design:

- synthetic data only
- no production customer records, secrets, or private paths
- no generated CSVs, DuckDB files, MLflow runs, local outputs, or live agent
  controls committed
- no claims of real commercial validation from synthetic outcomes

This repo intentionally does **not** add dashboards, apps, hosted APIs, cloud
deployment, CRM integration, campaign execution, retraining loops, learned GTM
policy, or screenshots pretending to be a production product. The project stops
at a local, inspectable portfolio system because that is the honest boundary of
what the synthetic workflow can support.

Run before committing:

```bash
make public-safety-check
```

## Project Status

Packages 0 through 10 are complete. Package 10 is committed and provides the
final deterministic GTM policy layer. Package 11 is the final docs-only public
polish and closeout pass; it must not reopen modeling, scoring, observability,
or GTM-policy implementation.

Useful closing docs:

- `docs/demo_walkthrough.md` — runnable local reviewer path and inspection SQL
- `docs/project_closeout.md` — final review checklist and repo-closeout stance
- `docs/packages.md` — package-by-package scope and boundaries
- `docs/runbook.md` — local execution commands
- `docs/gtm_policy.md` — locked Package 10 policy contract

## Local Checks

```bash
make public-safety-check
make test
make verify
```
