# Agent Instructions

This is a public portfolio repository. Treat every committed file as public.

## Package Discipline

- Work only on the active package named by the user or `.agent` examples.
- Do not implement future packages early.
- For Package -1, do not add modelling code, data generation, DuckDB logic,
  MLflow logic, dashboards, notebooks, cloud services, or generated artefacts.
- Prefer the smallest patch that satisfies the current package acceptance
  criteria.

## Grill Before Build

Before implementation, challenge unclear requirements:

- What package is active?
- What files are in scope?
- What outputs are forbidden?
- What tests should fail first?
- What would make the change unsafe for a public repo?

If scope is ambiguous, stop and ask.

## TDD Loop

- Add or update focused tests before implementation when behavior changes.
- Run the narrowest relevant check first.
- Run `make verify` before proposing a package as complete.

## Public Safety

- Never commit `.env`, `AGENTS.override.md`, generated data, local databases,
  model artefacts, notebooks, secrets, or real company/customer data.
- Use `.env.example` and `*.example` files for safe public templates.
- Run `make public-safety-check` before commit.

## Stop Conditions

Stop immediately if any of these occur:

- The task requires real customer, company, user, CRM, invoice, support, or
  production data.
- A secret or private key is present or requested.
- The requested work crosses into a future package.
- A generated artefact would need to be committed.
- Required safety checks fail and the fix is not clearly in scope.
