# Security

This repository is public. Assume every committed file can be read by anyone.

## Never Commit

- `.env` or machine-specific environment files.
- `AGENTS.override.md`.
- Secrets, tokens, passwords, private keys, credentials, or API keys.
- Real company, customer, user, invoice, support, CRM, subscription, or product
  usage data.
- Generated datasets, local databases, model artefacts, MLflow runs, notebooks,
  reports, or temporary outputs.
- Private production paths, hostnames, bucket names, or internal system names.

## Safe Public Templates

- `.env.example`
- `AGENTS.override.md.example`
- `.agent/*.example`

## Required Check

Run `make public-safety-check` before committing. If it fails, fix the public
repo boundary before continuing.

## Stop Conditions

Stop work if a request requires real data, secrets, private infrastructure, or
implementation from a package that has not been approved.
