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

The DuckDB database is a generated local artefact and must never be committed.

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
