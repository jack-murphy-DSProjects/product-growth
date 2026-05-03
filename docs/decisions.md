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
