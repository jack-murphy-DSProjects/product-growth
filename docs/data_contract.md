# Data Contract

## Status

This is an initial Package 0 placeholder. It defines intended source tables and
grains only. Final column-level contracts, data types, constraints, validation
rules, and DuckDB schemas will be added in later packages.

## Safety Statement

All data in this project must be synthetic and generated locally. The repository
must not commit production customer records, credentials, generated datasets,
local databases, model artefacts, MLflow runs, notebooks, dashboards, reports,
or temporary outputs.

## Intended Source Tables

| Table | Intended grain | Purpose |
| --- | --- | --- |
| `accounts` | One row per synthetic account | Account identity, segment, lifecycle, firmographic, and ownership attributes. |
| `users` | One row per synthetic user | User membership, role, activation, and account relationship attributes. |
| `usage_events` | One row per synthetic product event | Product activity used to derive adoption, engagement, breadth, depth, and trend features. |
| `subscriptions` | One row per subscription period or plan state | Plan, contract, seat, ARR, term, and lifecycle state inputs. |
| `invoices` | One row per invoice | Billing status, payment timing, amount, collection friction, and revenue signal inputs. |
| `support_tickets` | One row per support ticket | Support volume, severity, resolution, sentiment proxy, and escalation signal inputs. |
| `crm_touchpoints` | One row per CRM interaction | Sales, CS, lifecycle, renewal, and stakeholder coverage activity. |
| `renewals` | One row per renewal event or renewal opportunity | Renewal timing, outcome, churn, contraction, expansion, and renewal motion inputs. |

## Modeling Grain

The modeling table will use one row per account per snapshot month. Source
records may be event-level, period-level, or entity-level, but they must be
aggregated into point-in-time account-month features before modeling.

## Future Contract Requirements

Later packages should define:

- Primary keys and foreign keys.
- Required and nullable columns.
- Data types and allowed values.
- Date semantics and timezone assumptions.
- Synthetic generation rules and deterministic seeds.
- Validation checks for uniqueness, referential integrity, plausible rates, and
  temporal consistency.
- DuckDB table definitions and contract tests.
