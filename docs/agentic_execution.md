# Agentic Execution

This project supports bounded autonomous agent work.

Agents may continue across small units only when the active package, unit gate,
allowed files, checks, and stop conditions are documented in the repository.
Large pasted prompts should not be the durable source of truth.

## Package-bounded execution

Every agent run must start from the package contract on disk:

- `AGENTS.md`
- `docs/packages.md`
- `docs/runbook.md`
- `.agent/current_execution_context.md.example`
- `.agent/package_gate.md.example`
- `.agent/agent_runbook.md.example`

Live files under `.agent/` are local-only controls. They may guide a local run,
but they must not be committed. Only `.example` templates are public repo
artefacts.

Agents must work only inside the active package and current unit. They must not
start a later package early.

## Unit gates

Each unit must have an exit gate before implementation begins.

A unit gate should define:

- the active package
- the current unit
- allowed files
- disallowed files
- required tests or checks
- security checks
- package-specific stop conditions
- completion criteria

Agents may continue to the next unit only when the current unit gate passes and
the runbook explicitly allows automatic continuation.

For Package 2, agents must not start Package 3 automatically. Package 3 may
start only when the human reviewer explicitly opens a Package 3 unit.

## When agents may continue

Agents may continue without review when all of these are true:

- the current unit gate passes
- `make verify` passes
- `git diff --check` passes
- `git status --short` has been reviewed
- no generated, local-only, private, or cache artefacts are tracked
- no stop condition was encountered
- the next unit is part of the active package
- the next unit scope is already documented

If any condition is unclear, stop and request review.

## When agents must stop

Agents must stop when:

- the current unit gate fails
- required checks fail and the fix is outside the active unit
- generated or local-only artefacts would need to be committed
- real data, secrets, private customer information, or environment-specific
  paths are required
- the requested work changes package scope
- the requested work starts a later package without approval
- the requested work weakens tests or public-repo safety

Package-specific stop conditions in `docs/packages.md`, `docs/runbook.md`, and
`.agent/package_gate.md.example` take precedence over general autonomy.

## Before each unit

Before changing files, agents must:

1. Restate the active package.
2. Restate the active unit.
3. Restate the package scope sentence when one exists.
4. Restate the relevant runbook rule.
5. Run `git status --short`.
6. Inspect relevant docs, tests, and source files.
7. Identify intended files to change.
8. Confirm intended files are within the active package and unit.
9. Identify tests or checks to add or update.
10. Identify stop-condition risk.

## During each unit

During the unit, agents must:

- keep changes narrow
- prefer explicit implementation over broad abstractions
- add or update focused tests when behavior changes
- avoid unrelated refactors
- preserve package boundaries
- avoid unapproved dependencies
- avoid generated local artefacts except in temporary test directories
- avoid modifying ignored live `.agent/*.md` controls

For Package 3B onward, agents must also read `docs/feature_contract.md` before
changing code and restate the relevant Package 3 leakage and eligibility rule
for the active unit.

Package 3 agents must stop before changing:

- the `mart.account_month` row grain
- the 90-day label horizon
- canonical label source tables
- the renewal-based churn definition
- the renewal-based paid MRR expansion definition
- the retained-active expansion population
- the policy that ineligible labels are `NULL`, not `0`

Generated data, DuckDB warehouses, MLflow runs, local live `.agent/*.md` files,
private overrides, cache folders, and generated artefacts must not be committed.

## After each unit

Before summarising, agents must run:

```bash
make verify
git diff --check
git status --short
```

Agents must also confirm no generated, local-only, private, or cache artefacts
are tracked.

At minimum, check for:

- `data/generated/`
- `data/warehouse/`
- `data/processed/`
- `data/outputs/`
- `*.duckdb`
- `*.duckdb.wal`
- `*.db`
- `mlruns/`
- `artifacts/models/`
- `artifacts/tmp/`
- `.env`
- `AGENTS.override.md`
- live `.agent/*.md` files
- `__pycache__/`
- `.pytest_cache/`
- `*.egg-info/`

## Final summary

The final summary for each unit must include:

- files changed
- tests added or updated
- commands run
- security and public-repo checks
- package scope checks
- whether any stop condition was encountered
- what remains incomplete
- risks or review points

If a unit fails its gate, summarise the failed condition and stop.

## Package 2 autonomous loop

Package 2 proves that source CSVs can be safely persisted and validated in
DuckDB; it does not make the data model-ready.

Package 2 units must run in order:

1. Package 2A - Warehouse contract and documentation
2. Package 2B - Loader happy path
3. Package 2C - Source presence and schema validation
4. Package 2D - Relational and date validation
5. Package 2E - Closeout and security review

Agents may continue from one Package 2 unit to the next only when the current
unit gate passes.

Agents must stop before Package 3 unless the human reviewer explicitly starts
Package 3.

## Package 3 autonomous loop

Package 3 builds `mart.account_month`, the point-in-time account-month
analytical modelling table. It does not train models, create baselines, score
accounts, add health bands, create GTM recommendations, add dashboards, add
APIs, deploy to cloud services, add MLflow, add dbt, use real SaaS
integrations, use real customer data, or add incremental orchestration.

Package 3 must remain split by the approved slices:

1. Package 3A - Docs, contract, and harness update
2. Package 3B - Account-month spine
3. Package 3C - Labels
4. Package 3D - Features
5. Package 3E - Leakage hardening
6. Package 3F - CLI, audit, docs closeout

Package 3A is documentation and harness alignment only. It must not create
`mart.account_month`, add scripts, add Make targets, add dependencies, generate
synthetic data, load DuckDB, or implement Package 3 feature-building code.

For Package 3B onward, `docs/feature_contract.md` is the durable Package 3
source of truth. Prompt memory is not sufficient authority for row grain,
eligibility, label definitions, horizon, source roles, null-label policy, or
leakage rules.

Agents may continue from one Package 3 unit to the next only when the current
unit gate passes and the next unit is one of the approved Package 3 slices.
