from __future__ import annotations

import argparse

from account_health.evaluation import (
    DEFAULT_EVALUATION_OUTPUT_DIR,
    run_model_evaluation,
)
from account_health.modeling import DEFAULT_EXPERIMENT_NAME
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Package 5 candidate models and Package 4 baselines on "
            "the fixed Package 5 holdout."
        )
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME)
    parser.add_argument("--mlflow-tracking-uri", default=None)
    parser.add_argument("--train-end-month", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_EVALUATION_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_model_evaluation(
        database_path=args.warehouse_path,
        experiment_name=args.experiment_name,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        train_end_month=args.train_end_month,
        output_dir=args.output_dir,
    )

    print(f"evaluation_id: {result.evaluation_id}")
    print(f"experiment_name: {result.experiment_name}")
    print(f"train_end_month: {result.train_end_month.date().isoformat()}")
    print(f"metric_count: {len(result.metric_records)}")
    print(f"champion_count: {len(result.champions)}")
    for champion in result.champions:
        print(
            "champion: "
            f"target={champion.target} "
            f"status={champion.selection_status} "
            f"model_family={champion.selected_champion_model_family}"
        )
    for name, path in result.output_paths.items():
        print(f"output_{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
