# Synthetic Data

Package 1 generates deterministic, public-safe B2B SaaS source tables for local
development and testing. The generator creates source-like tables only; it does
not build DuckDB databases, account-month features, labels, scores, models,
dashboards, notebooks, APIs, or cloud deployment artifacts.

## Default Parameters

| Parameter | Default |
| --- | --- |
| `seed` | `42` |
| `n_accounts` | `500` |
| `start_date` | `2023-01-01` |
| `end_date` | `2025-12-31` |
| CLI output directory | `data/generated/` |

## Tables

The generator returns a dictionary of pandas DataFrames keyed by table name:

- `accounts`
- `users`
- `usage_events`
- `subscriptions`
- `invoices`
- `support_tickets`
- `crm_touchpoints`
- `renewals`

Each table contract is documented in `docs/data_contract.md`.

## Python Usage

```python
from account_health.synthetic import generate_synthetic_source_data

tables = generate_synthetic_source_data(seed=42, n_accounts=500)
accounts = tables["accounts"]
```

The Python generator does not write files. It returns DataFrames only.

## CLI Usage

```bash
python3 scripts/generate_synthetic_data.py
```

Optional arguments:

```bash
python3 scripts/generate_synthetic_data.py \
  --output-dir data/generated/ \
  --seed 42 \
  --n-accounts 500 \
  --start-date 2023-01-01 \
  --end-date 2025-12-31
```

The CLI writes one CSV per source table and prints row counts. Generated CSVs
under `data/generated/` are ignored and should stay local.

## Archetypes

Each account receives one `synthetic_archetype`:

- `healthy_growing`
- `steady_retained`
- `low_adoption`
- `support_frustrated`
- `seasonal`
- `expansion_ready`
- `price_sensitive`
- `implementation_risk`

Archetypes are latent generator controls that nudge usage, support, billing,
and renewal patterns with independent noise. They are stored for audit/debugging
only. `synthetic_archetype` is not an approved modelling feature.

## Safety

Account names use neutral values such as `Synthetic Account 000001`. IDs are
stable synthetic identifiers such as `acct_000001`, `user_000001`, and
`evt_000000001`. The generator does not use Faker or external customer/company
sources.

Package 1 may write local CSVs through the CLI, but those files are ignored and
must not be committed.
