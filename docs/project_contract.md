# Project Contract

## Name

The public project name is `product-growth`.

The Python import package is `account_health` under `src/account_health`. This
is acceptable because the repository describes the broader product-growth
portfolio project while the package contains account-health implementation code.

## Public Goal

Build a public, local-first portfolio project that demonstrates how a SaaS team
could score account health, churn risk, and expansion propensity.

## Package -1 Boundary

Package -1 is limited to:

- Agent harness.
- Public/private documentation boundary.
- Project contract.
- Context vocabulary.
- Package plan.
- Runbook.
- Security rules.
- Public repo safety check.
- Initial test harness.

Package -1 must not include modelling code, data generation, DuckDB logic,
MLflow logic, dashboards, notebooks, cloud services, or generated artefacts.

## Public Data Contract

No real company, customer, user, invoice, support ticket, CRM, subscription, or
product usage data may be committed. Future data must be synthetic and generated
locally.

## Required Local Checks

- `make setup`
- `make public-safety-check`
- `make test`
- `make verify`
