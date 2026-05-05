from __future__ import annotations

import argparse

from account_health.modeling import (
    DEFAULT_EXPERIMENT_NAME,
    train_candidate_models,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train Package 5 candidate churn and expansion models from "
            "mart.account_month and log local MLflow runs."
        )
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    parser.add_argument("--train-end-month", default=None)
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME)
    parser.add_argument("--mlflow-tracking-uri", default=None)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = train_candidate_models(
        database_path=args.warehouse_path,
        train_end_month=args.train_end_month,
        experiment_name=args.experiment_name,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        random_state=args.random_state,
    )

    print(f"experiment_name: {result.experiment_name}")
    print(f"mlflow_tracking_uri: {result.mlflow_tracking_uri or 'mlflow_default'}")
    print(f"run_count: {len(result.runs)}")
    for run in result.runs:
        print(
            "run: "
            f"target={run.target} "
            f"candidate_model={run.candidate_model} "
            f"run_id={run.run_id} "
            f"train_rows={run.train_row_count} "
            f"test_rows={run.test_row_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
