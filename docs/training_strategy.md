# Training Strategy

Package 5 implements local candidate-model training for synthetic account-month
data. The durable implementation contract now lives in `docs/model_training.md`.

Training in this repository remains package-scoped, local-first, reproducible,
and based only on synthetic data generated within the repo. It must not use real
company or customer data.
