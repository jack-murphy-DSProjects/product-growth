# product-growth

Public portfolio repo for an end-to-end SaaS account health, churn risk, and
expansion propensity scoring system.

Package -1 establishes the public repository boundary, agent harness, safety
rules, package plan, and initial test harness. It intentionally contains no
modeling code, synthetic data generation, DuckDB logic, MLflow logic, dashboard,
notebooks, cloud services, or generated artefacts.

## Local Checks

```bash
make setup
make public-safety-check
make test
make verify
```
