# Decisions

## Package -1

- The repository name is `product-growth`.
- The Python package path is `src/account_health` because the implementation
  domain is account health inside the broader product-growth project.
- The repo is local-first and public-safe by default.
- Private agent instructions live in ignored local files; public templates use
  the `.example` suffix.
- Generated artefacts are ignored and must not be committed.

## Package 1

- Synthetic SaaS source tables are generated before DuckDB so the public-safe
  data boundary can be tested first with plain DataFrames and CSVs.
- The generator returns pandas DataFrames and the CLI owns all local CSV
  writing.
- `synthetic_archetype` is retained as generator metadata for audit/debugging
  only and is not an approved modelling feature.
- Package 1 uses only `pandas` and `numpy` as runtime dependencies.

## Package 2 decisions

### Decision: DuckDB warehouse path

Package 2 writes the local analytical warehouse to:

- `data/warehouse/account_health.duckdb`

This path is ignored by git.

DuckDB database files and write-ahead log files are generated local artefacts
and are also ignored by git:

- `*.duckdb`
- `*.duckdb.wal`

The DuckDB database is a generated local artefact and must never be committed.

### Decision: DuckDB runtime dependency

Package 2 adds `duckdb` as a runtime dependency because the local analytical
warehouse is a DuckDB database.

DuckDB remains local-only in this project. Package 2 does not add a cloud
warehouse, hosted database, API, orchestration framework, or production
deployment.

### Decision: Raw and metadata schemas

Package 2 uses DuckDB schemas to separate source persistence from load metadata:

- `raw.*`
- `metadata.*`

Package 2 creates raw/source tables only.

Feature tables, labels, model outputs, health bands, recommendations, monitoring tables, and RevOps outputs belong to later packages.

### Decision: Loader accepts explicit paths

The warehouse loader must accept explicit `source_dir` and `database_path` arguments.

Default CLI paths may be:

- `source_dir`: `data/generated/`
- `database_path`: `data/warehouse/account_health.duckdb`

The core Python API must not depend on hardcoded project-local paths.

### Decision: Loading does not generate data

Package 2 does not generate synthetic data.

It loads existing Package 1 CSV outputs.

If required CSVs are missing, the loader must fail clearly rather than generating data implicitly.

### Decision: Overwrite by default

Package 2 uses deterministic overwrite/rebuild loading by default.

Incremental loading, append semantics, late-arriving records, warehouse migrations, and orchestration state are out of scope for the MVP.

### Decision: Minimal load audit is allowed

Package 2 may create a minimal `metadata.load_audit` table containing load metadata such as:

- load ID
- timestamp
- source directory
- database path
- table name
- row count
- status

The audit table must remain simple.

It must not become an orchestration framework or job-control system.

### Decision: Package-gated autonomous execution

Package 2 agents may work autonomously unit by unit only when the current unit
gate is documented and passes.

The durable execution contract lives in:

- `docs/agentic_execution.md`
- `.agent/current_execution_context.md.example`
- `.agent/package_gate.md.example`
- `.agent/agent_runbook.md.example`

Live `.agent/*.md` files are local-only controls and must not be committed.

Agents may continue to the next Package 2 unit only after the current unit gate
passes.

Agents must stop before Package 3 unless the human reviewer explicitly starts
Package 3.

## Package 3 decisions

### Decision: Account-month grain

Package 3 creates `mart.account_month` at one active subscribed account x one
calendar observation month.

The primary grain is:

- `account_id`
- `observation_month`

`observation_month` is the first day of the month. `observation_month_end` is
the last day of that month.

### Decision: Renewal labels

Package 3 uses `raw.renewals` as the canonical source for both labels:

- `churn_90d`
- `expansion_90d`

Both labels use the approved 90-day future horizon after
`observation_month_end`. Ineligible labels are stored as `NULL`, not `0`.

### Decision: MVP feature set

Package 3 implements a small, explicit feature set across static account,
current subscription, usage, support, billing, and CRM source families.

All feature inputs must be known on or before `observation_month_end`.

`raw.accounts.synthetic_archetype` remains generator metadata and is excluded
from `mart.account_month`.

### Decision: Local feature build audit

Package 3 creates `metadata.feature_build_audit` during local account-month
builds.

The audit table records build counts and source coverage for inspectability.
It is not an orchestration framework, monitoring system, model registry, or
production metadata store.

## Package 4 decisions

### Decision: Rule baselines are benchmark artefacts, not policy

Package 4 creates deterministic rule baselines in a separate table:

- `mart.account_month_baselines`

The source table is:

- `mart.account_month`

The baselines are heuristic benchmark scores for later ML models to beat. They
are not calibrated probabilities, final account health bands, recommended GTM
actions, champion decisions, monitoring reports, or production policy outputs.

Rationale:

- Separating baselines preserves the Package 3 account-month semantics.
- Keeping baselines outside `mart.account_month` avoids mutating the modelling
  table and keeps feature/label construction distinct from benchmark scoring.
- Baseline scores remain separate from future ML predictions, which supports
  clear baseline-vs-ML comparison in later evaluation packages.
- Deferring health bands and recommended actions avoids introducing the GTM
  action layer before scores and models have been evaluated.

Package 4 must not use `churn_90d`, `expansion_90d`, or
`synthetic_archetype` as scoring inputs.

### Decision: Local baseline build audit

Package 4 creates `metadata.baseline_build_audit` during local baseline
rebuilds.

The audit table records build ID, UTC build time, source table, output table,
baseline version, row counts, observation-month bounds, and status.

It is local build metadata only. It is not model metadata, MLflow tracking, a
model registry, orchestration state, monitoring output, model evaluation, or
champion-selection evidence.

## Package 5 decisions

### Decision: Independent churn and expansion models

Package 5 trains separate candidate models for `churn_90d` and
`expansion_90d`.

Package 5 does not train a combined multi-output model.

### Decision: Null target labels are excluded

Package 5 excludes rows with `NULL` labels for the relevant target.

`NULL` target labels are not converted to zero.

### Decision: Fixed temporal split

Package 5 uses a fixed train/test split by `observation_month`.

Random train/test splits are not approved.

### Decision: scikit-learn and MLflow dependencies

Package 5 introduces scikit-learn for local candidate model training and
MLflow for local experiment tracking.

Package 5 does not introduce XGBoost, LightGBM, neural networks, cloud
dependencies, serving dependencies, or dashboard dependencies.

### Decision: Baselines are benchmarks only

Package 4 baseline scores, ranks, deciles, and components are benchmark
outputs only.

Package 5 must not use baseline outputs as model features.

### Decision: MLflow logging without registry or promotion

Package 5 logs candidate model runs and artefacts to local MLflow tracking.

Package 5 does not use MLflow registry APIs, register models, promote models,
or deploy models.

### Decision: No champion selection or layered evaluation

Package 5 reports simple validation metrics for candidate runs only.

Champion selection and full layered evaluation belong to Package 6.

## Package 6 decisions

### Decision: Fixed holdout plus holdout-month robustness

Package 6 evaluates candidates on the fixed temporal holdout created by the
Package 5 split semantics.

Package 6 may slice that fixed holdout by `observation_month` to check temporal
robustness.

Package 6 does not implement a full rolling retraining backtest in the MVP. A
rolling backtest would require actual repeated retraining across multiple
cutoffs and must be separately approved.

### Decision: Consume local MLflow runs without silent retraining

Package 6 consumes local Package 5 MLflow candidate runs, feature metadata,
split metadata, and model artefacts.

If required local runs or artefacts are missing, Package 6 should fail clearly.
It must not silently retrain candidates as a fallback.

Package 6 does not use MLflow registry APIs, aliases, promotion, deployment, or
remote tracking requirements.

### Decision: Baselines are ranking benchmarks in evaluation

Package 4 baseline scores may be compared with ML candidates using ranking and
capacity metrics such as ROC AUC, average precision, top-K precision, top-K
recall, lift, and capture rate.

Package 4 baseline scores are not calibrated probabilities. Package 6 must not
use them for log loss, Brier score, or calibration bins in the MVP.

### Decision: Champion selection follows GTM operating metrics

Package 6 selects churn and expansion champions separately.

Primary evidence is top-K GTM operating performance, especially precision,
lift, and capture at top 10%. ROC AUC and average precision are supporting
evidence only.

Package 6 may conclude that no ML candidate sufficiently beats the rule
baseline for a target.

### Decision: Evaluation outputs are local artefacts

Package 6 writes generated evaluation files under:

- `data/outputs/model_evaluation/`

The default generated files are:

- `evaluation_summary.json`
- `champion_selection_manifest.json`
- `evaluation_report.md`

These files are generated local artefacts and must not be committed.

### Decision: Minimal evaluation tables

Package 6 may create a minimal local DuckDB table set:

- `metadata.model_evaluation_audit`
- `mart.model_evaluation_summary`
- `mart.model_champion_selection`

Optional detail tables should be added only when implementation needs them.

These tables are local evaluation summaries. They are not production scoring
outputs, model registry metadata, monitoring outputs, health bands, or
recommended GTM actions.

### Decision: Local evaluation CLI and generated artefacts

Package 6 adds the local command:

- `make evaluate-candidate-models`

The command consumes existing local Package 5 MLflow runs and Package 4
baselines, writes generated evaluation files under
`data/outputs/model_evaluation/`, and writes only the minimal local evaluation
tables.

It does not retrain missing candidates, use the MLflow registry, promote
models, deploy models, create production scoring outputs, create account health
bands, recommend GTM actions, add dashboards, add hosted APIs, or add cloud
infrastructure.

## Package 7 decisions

### Decision: Registry promotion follows Package 6 selection

Package 7 promotes only eligible ML champions selected by Package 6.

Package 7 does not re-evaluate candidates, override champion selection, or scan
MLflow to independently choose a champion when the Package 6 manifest is
missing.

Baseline-retained, no-ML-champion, and insufficient-evidence outcomes are valid
Package 6 outcomes, but they are not eligible MLflow model promotions.

### Decision: Local MLflow registry only

Package 7 uses local MLflow tracking and registry.

Remote MLflow tracking, hosted registry infrastructure, Databricks, Unity
Catalog, cloud object storage, hosted APIs, and production serving are out of
scope for the Package 7 MVP.

### Decision: Aliases and tags instead of registry stages

Package 7 uses MLflow aliases and tags for lifecycle metadata.

The primary alias is:

- `champion`

The `champion` alias means selected by Package 6 and promoted by Package 7 for
future local batch scoring consumption. It does not mean online deployment,
cloud deployment, hosted serving, business approval, health-band generation,
GTM action generation, or monitoring approval.

Deprecated registry stages such as `Staging`, `Production`, and `Archived` are
not the Package 7 MVP lifecycle mechanism.

### Decision: Separate registered models per target

Package 7 registers churn and expansion separately:

- `account_health_churn_model`
- `account_health_expansion_model`

Package 7 does not create a combined multi-output registered model and does not
create registered models for baselines, health bands, GTM actions, monitoring
outputs, or scoring tables.

### Decision: Promotion manifest and audit remain local artefacts

Package 7 writes a generated local promotion manifest under:

- `data/outputs/model_registry/promotion_manifest.json`

Package 7 may also create:

- `metadata.model_promotion_audit`

Both are local promotion artefacts for inspectability and future Package 8
consumption. They are not committed outputs, deployment records, production
scoring tables, monitoring reports, health-band tables, or recommended-action
tables.

## Package 8 decisions

### Decision: Package 8 is raw local batch scoring only

Package 8 will load Package 7-promoted local MLflow champions, score selected
`mart.account_month` rows, write raw churn and expansion model scores, and
record scoring audit metadata.

Package 8 does not monitor, evaluate, compare, select, promote, retrain,
register, or deploy models. It does not add hosted serving, APIs, dashboards,
cloud infrastructure, notebooks, or real SaaS integrations.

### Decision: Health bands and GTM actions are deferred

Package 8 does not create health bands, GTM actions, recommendations,
suppression rules, policy thresholds, capacity rules, or customer-facing
account-health outputs.

Those belong to a later policy or public-polish package after raw scores exist
and their semantics can be reviewed separately.

### Decision: MLflow `champion` aliases are the loading authority

Package 8 uses Package 7 MLflow `champion` aliases as the model loading
authority:

- `account_health_churn_model` at alias `champion`
- `account_health_expansion_model` at alias `champion`

The Package 7 promotion manifest and `metadata.model_promotion_audit` are
cross-check evidence for the handoff. They do not replace loading the promoted
MLflow aliases.

### Decision: Scoring reads `mart.account_month` without labels

Package 8 scoring uses a label-free reader over `mart.account_month`.

It must not reuse Package 5 or Package 6 loaders that filter to non-null target
labels. Labels may exist in the source table, but they are not required for
scoring and are never model inputs.

Package 8 must score selected `observation_month` rows and must require an
explicit `--scoring-month YYYY-MM-01` or explicit `--latest`.
It must not silently score all history by default.

### Decision: Package 5 feature metadata controls scoring feature order

Package 8 uses Package 5 MLflow `features.json` as the ordered feature-list
source for scoring.

Committed feature-contract constants remain the source for forbidden-column
validation. `synthetic_archetype`, labels, identifiers, date fields,
eligibility flags, baseline outputs, target-like fields, and future-looking
fields must never be passed as model features.

No MLflow model signature exists yet, so Package 8 must not require one. The
trained sklearn pipeline owns preprocessing; Package 8 must not recreate
training preprocessing manually.

### Decision: Reruns replace score rows and append audit

Package 8 score output reruns replace `mart.account_month_scores` rows for the
selected scoring month.

The replacement boundary is the selected scoring month, not full history.
`metadata.batch_scoring_audit` remains append-only so rerun history is
inspectable.

### Decision: Ranks and deciles are score-layer fields only

Package 8 may include score ranks or score deciles only as raw scoring-layer
prioritization fields for the selected scoring month.

Ranks and deciles are not health bands, GTM actions, recommendations,
suppression rules, capacity policy, or business approval.

## Package 10 decisions

### Decision: Package 10 is the deterministic GTM policy layer, not the final polish package

Status:
Accepted for Package 10.

Context:

- Packages 8 and 9 now provide raw score production and local score
  observability.
- The repo still needs a deterministic layer that converts scores into
  inspectable GTM operating outputs.
- Earlier roadmap text bundled that policy layer together with broad public
  polish, which would make Package 10 too wide and blur the implementation
  target for later agents.

Decision:

- Package 10 owns deterministic GTM policy outputs only, plus minimal
  public-safe examples when needed to explain those outputs.
- Final README polish, screenshots, portfolio storytelling, dashboard-like
  examples, and final closeout are deferred to Package 11 or a later explicit
  polish pass.
- `docs/gtm_policy.md` is the Package 10 source of truth.

Consequences:

- Later Package 10 implementation work can stay narrow, auditable, and
  testable.
- Reviewers can evaluate the policy layer separately from presentation work.
- Future polish work must not silently alter the Package 10 policy contract.

### Decision: `gtm_policy_v1` is a fixed illustrative matrix

Package 10 starts with:

- `policy_version = "gtm_policy_v1"`

The v1 contract uses fixed illustrative buckets:

- high churn risk: `churn_score >= 0.70`
- medium churn risk: `churn_score >= 0.40 and churn_score < 0.70`
- low churn risk: `churn_score < 0.40`
- high expansion propensity: `expansion_score >= 0.70`
- medium expansion propensity:
  `expansion_score >= 0.40 and expansion_score < 0.70`
- low expansion propensity: `expansion_score < 0.40`

These thresholds are deliberately simple and are not learned from real
outcomes. They are illustrative portfolio-policy constants, not validated
commercial recommendations.

The exact v1 health bands, lifecycle motions, recommended actions, priorities,
reason codes, boundary behaviour, and save-first conflict handling live in
`docs/gtm_policy.md`.

### Decision: Churn risk dominates expansion actioning

Package 10 may combine churn and expansion scores into one deterministic policy
decision, but the raw scores remain separate output columns.

If `churn_score >= 0.70`, the account cannot receive a pure expansion action
even when expansion propensity is high. High churn plus high expansion becomes a
save-first, retention-led expansion watch motion.

This preserves the distinction between model predictions and GTM policy while
making the conflict handling explicit and testable.

### Decision: Policy outputs remain separate from score outputs

Package 10 writes separate local outputs:

- `mart.account_month_gtm_policy`
- `metadata.gtm_policy_audit`

Rerunning one scoring month replaces policy rows for that month only. Audit rows
remain append-only.

Package 10 must not mutate:

- `mart.account_month_scores`
- Package 8 audit evidence
- Package 9 observability outputs

This keeps raw prediction evidence, observability evidence, and policy outputs
auditable as distinct layers.

## Package 11 decisions

### Decision: Package 11 is docs-only public polish and closeout

Status:
Accepted for Package 11.

Context:

- Packages 0 through 10 already provide the finished local operating workflow.
- The remaining gap is reviewer experience: fast orientation, runnable demo
  guidance, final output inspection, public-safety framing, and repo closeout.
- Adding another product layer would blur the portfolio boundary and reopen
  scopes that earlier packages intentionally closed.

Decision:

- Package 11 owns public documentation, walkthroughs, and closeout only.
- Package 11 must not add dashboards, apps, APIs, cloud deployment, CRM
  integration, campaign execution, new model logic, new scoring logic, new
  observability logic, or new GTM policy logic.
- Package 11 may refresh committed `.agent/*.example` templates so public
  workflow examples no longer describe Package 10 as the active package.

Consequences:

- The repo can become easier to review without pretending to become a new
  product.
- Public-facing claims stay aligned with what synthetic data can honestly
  demonstrate.
- Future changes to behavior remain explicit future work rather than hidden
  inside a polish pass.

### Decision: Package 11 keeps separate walkthrough and closeout docs

Status:
Accepted for Package 11.

Decision:

- `docs/demo_walkthrough.md` is the runnable reviewer guide.
- `docs/project_closeout.md` is the maintainer-facing final review and boundary
  checklist.

Consequences:

- Reviewers get a short, practical path to running and inspecting the repo.
- The final public-safety, artefact, and scope decisions stay visible without
  overloading the walkthrough.

### Decision: The simplest public demo path is local, explicit, and end-to-end

Status:
Accepted for Package 11.

Decision:

- The public demo path should run the completed local workflow in package order
  and end on `mart.account_month_gtm_policy` when Package 6 produced eligible
  ML champions for Package 7 promotion.
- If Package 6 honestly retains a baseline or withholds an ML champion, the
  public demo should stop at `mart.model_champion_selection` rather than force
  later promotion, scoring, or policy steps.
- The default reviewer-friendly path may use explicit `latest` selectors for
  scoring, observability, and policy generation; fixed-month examples should
  remain available for reviewers who want exact replay.
- Final GTM usefulness should be shown through inspectable local tables and safe
  SQL queries, not through fake UI screenshots or claims of real commercial
  truth.

Consequences:

- The demo is honest, reproducible, and easy to follow.
- The repo shows operational usefulness without overstating synthetic results.
