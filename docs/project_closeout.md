# Project Closeout

## Purpose

Package 11 is the final public-facing closeout pass for `product-growth`. It is
meant to make the finished repo easier to understand, run, inspect, and review
as a portfolio asset after the operating system itself already exists.

Package 11 is intentionally docs-only. It should not become a quiet new product
build.

## What Package 11 Owns

Package 11 owns:

- the final README landing-page narrative
- the runnable public demo walkthrough
- package-flow explanation for portfolio reviewers
- output-inspection guidance for the final local tables
- clear public-safety and synthetic-data framing
- final repo closeout guidance and checklist
- optional refreshes to committed `.agent/*.example` templates so they no longer
  describe Package 10 as the active package

Package 11 does **not** own new modeling, scoring, monitoring, policy, UI,
integration, or deployment behavior.

## Final Commercial Narrative

The repo should present one honest story:

- commercial ML becomes useful when predictions are embedded inside an operating
  process
- that process needs data contracts, point-in-time features, baselines,
  evaluation, promotion evidence, explicit scoring, observability, and policy
- deterministic GTM outputs make the workflow legible to RevOps, Sales, CS, and
  Growth partners
- synthetic data can demonstrate the design of that system, but it cannot prove
  real retention uplift, expansion revenue, or commercial validation

That is a strong portfolio claim without turning synthetic outputs into fake
business evidence.

## Why Both Public Docs Exist

Package 11 should keep two closing docs because they solve different problems:

- `docs/demo_walkthrough.md` is for a reviewer who wants to run and inspect the
  system.
- `docs/project_closeout.md` is for the maintainer who wants to know what the
  repo now claims, what remains out of scope, and what must be checked before
  calling the public project finished.

Combining them would either make the demo path too abstract or make the closeout
checklist too operationally noisy.

## Final Closeout Checklist

Before declaring the public repo ready:

1. Confirm Packages 0-10 remain complete and Package 11 adds documentation only.
2. Confirm the README explains the project thesis, workflow, demo path, final
   outputs, demonstrated skills, and explicit non-goals in the first review
   pass.
3. Confirm `docs/demo_walkthrough.md` runs through the local workflow, final
   tables, safe SQL inspection, troubleshooting, and synthetic-data honesty.
4. Confirm `docs/packages.md`, `docs/runbook.md`, and `docs/decisions.md` agree
   that Package 11 is public polish and closeout rather than new product scope.
5. Confirm Package 10's locked `gtm_policy_v1` matrix remains unchanged.
6. Confirm no generated or local-only artefacts are staged or tracked.
7. Run `make public-safety-check`, `git diff --check`, and the relevant repo
   verification commands before committing.
8. Confirm there are no claims of real commercial validation, production drift
   detection, automated governance, or customer-impacting actioning.

## Generated And Local Artefacts That Must Stay Uncommitted

Do not commit:

- `data/generated/`
- `data/warehouse/`
- `data/processed/`
- `data/outputs/`
- `mlruns/`
- `artifacts/models/`
- `artifacts/tmp/`
- `*.duckdb`
- `*.duckdb.wal`
- `.env`
- `AGENTS.override.md`
- live `.agent/current_execution_context.md`
- live `.agent/package_gate.md`
- live `.agent/agent_runbook.md`
- interpreter caches and local test caches

Only safe committed templates such as `.env.example` and `.agent/*.example`
belong in the public repo.

## Explicitly Still Out Of Scope

Package 11 must not add:

- model training, retraining, re-evaluation, champion selection, promotion, or
  rescoring
- new observability logic
- changes to `gtm_policy_v1`
- new health-band or action-policy logic
- dashboards, Streamlit, frontend work, screenshots pretending to be a real UI,
  hosted APIs, or cloud deployment
- CRM integration, campaign execution, or automated playbooks
- real customer data
- generated artefacts committed to git
- claims of validated business impact from synthetic outputs

## Stop Conditions Before Package 11 Closeout

Stop rather than continue if:

- Package 10 is not committed
- any requested change would alter the locked Package 10 policy contract without
  a new explicit decision
- the work drifts into new code or product behavior rather than documentation
- the demo requires committing generated outputs or local artefacts
- a public-facing claim overstates what synthetic data can prove
- required safety checks fail for reasons outside the narrow docs-only scope

## End State

The intended end state is a repo that a reviewer can understand quickly, run
locally, inspect honestly, and evaluate as a production-style portfolio system
without mistaking it for a hosted product or a real commercial deployment.
