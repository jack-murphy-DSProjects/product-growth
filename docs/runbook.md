# Runbook

## Package Workflow

1. Confirm the active package and scope.
2. Grill the request before building.
3. Write or update focused tests for behavior changes.
4. Make the smallest scoped patch.
5. Run the narrowest relevant check.
6. Run `make verify`.
7. Summarize files changed, commands run, and remaining risks.

## Package -1 Checks

```bash
make setup
make public-safety-check
make test
make verify
```

## Stop Conditions

- Future package work is requested without approval.
- Real data or secrets are needed.
- Generated artefacts would need to be committed.
- Public safety checks fail outside the current scope.
