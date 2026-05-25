# product-growth

`product-growth` is a public, local-first portfolio project that shows how
commercial machine learning becomes part of a go-to-market (GTM) operating
process, not just a set of model scores. Using synthetic B2B SaaS data only, the
repo builds a reproducible batch workflow from source contracts through
churn-risk and expansion-propensity modeling, local batch scoring, score
observability, and a deterministic Revenue Operations (RevOps)-facing policy
table.

`product-growth` is the public repo name; the Python package and implemented
workflow use `account_health` because the example is centered on account health,
churn risk, and expansion propensity.

In one sentence: this project demonstrates how a Data Scientist can turn account-level predictions into inspectable,
auditable operating outputs for Sales, Customer Success, Growth, and RevOps
without pretending that synthetic data proves real commercial impact.

The commercial problem is ordinary but important: when GTM capacity is limited,
teams need a defensible way to decide which accounts need retention attention,
which are expansion-ready, and which outputs need review before anyone acts on
them.

**Stack:** Commercial Data Science · Growth Data Science · GTM /
Revenue Data Science · Decision Science | Python · DuckDB · scikit-learn ·
MLflow | batch scoring · observability · auditability · testing ·
reproducibility

## The First 60 Seconds

This repo is meant to answer four questions quickly:

1. **What does it do?** It converts synthetic SaaS source data into point-in-time
   account-month features, independent churn and expansion models, scored local
   populations, observability summaries, and deterministic GTM policy outputs.
2. **Why does that matter?** A score alone is not a GTM workflow. The repo
   shows the extra layers needed before GTM teams can review scarce-capacity
   retention and expansion queues responsibly: contracts, baselines, evaluation,
   promotion evidence, score checks, and policy rules.
3. **What should I run?** Use the end-to-end local demo path below, or follow the
   fuller walkthrough in `docs/demo_walkthrough.md`.
4. **What should I inspect?** Start with `mart.account_month_gtm_policy`, then
   trace backward through raw scores, observability summaries, champion
   selection, and audit tables.

## Review This Repo In 5 Minutes

| If you are... | Start here | Then inspect |
| --- | --- | --- |
| a technical reviewer | `## For Technical Reviewers` below | `docs/feature_contract.md`, `docs/model_evaluation.md`, and the linked tests |
| a Commercial / Growth Data Science hiring manager | this README + `docs/problem_framing.md` | `docs/model_card.md` and `docs/demo_walkthrough.md` |
| a recruiter or talent sourcer | the opening summary + role-fit strip above | `## What This Demonstrates` and `docs/reference_demo_result.md` |
| a RevOps, GTM, or commercial leader | the final-output example below | `docs/revops_playbook.md` and `docs/gtm_policy.md` |
| an AI-assisted learner | `docs/README.md` | `docs/architecture.md` and `docs/demo_walkthrough.md` |

## Final Output Example

The final table keeps raw scores visible, then adds deterministic policy fields
for human review. These are two real synthetic rows from the successful local
reference run for `2025-10-01`; they are examples of the workflow, not evidence
of real commercial impact.

| `account_id` | `churn_score` | `expansion_score` | `health_band` | `lifecycle_motion` | `recommended_action` | `action_priority` | `action_reason_code` |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| `acct_000046` | `0.34` | `0.44` | `Stable` | `Nurture` | `Nurture for future expansion` | `P3` | `LOW_CHURN_MEDIUM_EXPANSION_NURTURE` |
| `acct_000024` | `0.30` | `0.27` | `Stable` | `Maintain` | `Monitor in standard cadence` | `P3` | `LOW_CHURN_LOW_EXPANSION_MAINTAIN` |

**Illustrative policy edge case, not a reference-run row:** if an account had a
`0.82` churn score and a `0.88` expansion score, the locked policy would produce
this deterministic save-first outcome:

| `churn_score` | `expansion_score` | `health_band` | `lifecycle_motion` | `recommended_action` | `action_priority` | `action_reason_code` |
| ---: | ---: | --- | --- | --- | --- | --- |
| `0.82` | `0.88` | `Critical` | `Retention-led expansion watch` | `Executive save plan before expansion` | `P1` | `HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST` |

The locked policy handles that conflict explicitly: high churn risk plus high
expansion propensity becomes a save-first motion, not a pure expansion motion.
The example is illustrative, but the policy principle is real inside
`gtm_policy_v1`.

In a real GTM process, thresholds would be set against available capacity and
intervention cost; ownership, suppression, and escalation rules would be agreed
before actioning. This table would support human review and prioritisation rather
than replace account judgement, and any impact claim would need real outcomes or
controlled tests rather than synthetic scores.

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
  -> RevOps-facing review table
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

For one hand-written reference outcome from a successful local demo run, see
`docs/reference_demo_result.md`.

Recent MLflow releases may emit filesystem-backend deprecation warnings during
local runs. That warning is expected for this local portfolio demo; the repo is
not presenting its local MLflow storage choice as production deployment
guidance.

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

## For Technical Reviewers

| Reviewer question | Evidence to inspect |
| --- | --- |
| Are features point-in-time and leakage-aware? | `src/account_health/features/account_month.py`, `tests/test_account_month_builder.py`, `docs/feature_contract.md` |
| Are modeling features explicitly governed? | `src/account_health/modeling/dataset.py`, `tests/test_modeling_dataset.py` |
| Is evaluation temporally separated rather than randomly split? | `src/account_health/modeling/split.py`, `tests/test_modeling_split.py` |
| Does ML have to beat a credible baseline before promotion? | `src/account_health/evaluation/selection.py`, `tests/test_model_evaluation_selection.py`, `docs/model_evaluation.md` |
| Are scoring reruns and audit writes explicit? | `src/account_health/scoring/orchestration.py`, `tests/test_batch_scoring_outputs.py` |
| Is score observability implemented rather than just described? | `src/account_health/observability/orchestration.py`, `tests/test_score_observability_loading.py`, `tests/test_score_observability_outputs.py`, `docs/score_observability.md` |
| Is the GTM layer deterministic and separate from model training? | `src/account_health/gtm_policy/matrix.py`, `tests/test_gtm_policy_matrix.py`, `docs/gtm_policy.md` |
| Are public-repo safety rules enforced? | `scripts/check_public_repo_safety.py`, `tests/test_public_repo_safety.py` |

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

It is also intentionally not a Kaggle-style leaderboard project and not a fake
SaaS product.

Run before committing:

```bash
make public-safety-check
```

## Project Status

Packages 0 through 11 are complete. Package 10 provides the final deterministic
GTM policy layer, and Package 11 completed the docs-only public polish and
closeout pass without reopening modeling, scoring, observability, or GTM-policy
implementation.

Useful closing docs:

- `docs/README.md` — short docs index by visitor intent
- `docs/demo_walkthrough.md` — runnable local reviewer path and inspection SQL
- `docs/reference_demo_result.md` — hand-written reference outcome from one successful local demo run
- `docs/revops_playbook.md` — short RevOps / GTM review guide for the final table
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
