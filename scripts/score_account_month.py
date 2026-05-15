from __future__ import annotations

import argparse
import sys

from account_health.registry import DEFAULT_PROMOTION_MANIFEST_PATH
from account_health.scoring import (
    DEFAULT_BATCH_SCORING_EXPORT_DIR,
    BatchScoringError,
    run_batch_scoring,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Package 8 raw local account-month batch scoring."
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scoring-month", default=None)
    selector.add_argument("--latest", action="store_true")
    parser.add_argument(
        "--promotion-manifest-path",
        default=str(DEFAULT_PROMOTION_MANIFEST_PATH),
    )
    parser.add_argument("--mlflow-tracking-uri", default=None)
    parser.add_argument("--mlflow-registry-uri", default=None)
    parser.add_argument(
        "--export-dir",
        default=None,
        help=(
            "Optional raw CSV export directory. Repo-local exports must stay "
            f"under {DEFAULT_BATCH_SCORING_EXPORT_DIR}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_batch_scoring(
            database_path=args.warehouse_path,
            scoring_month=args.scoring_month,
            latest=args.latest,
            promotion_manifest_path=args.promotion_manifest_path,
            mlflow_tracking_uri=args.mlflow_tracking_uri,
            mlflow_registry_uri=args.mlflow_registry_uri,
            export_dir=args.export_dir,
        )
    except BatchScoringError as error:
        print(f"Package 8 batch scoring failed: {error}", file=sys.stderr)
        return 1

    print(f"scoring_run_id: {result.scoring_run_id}")
    print(f"scoring_version: {result.scoring_version}")
    print(f"scored_at_utc: {result.scored_at_utc}")
    print(f"selector: {result.selector}")
    print(f"scoring_month: {result.scoring_month.date().isoformat()}")
    print(f"row_count_read: {result.row_count_read}")
    print(f"row_count_written: {result.row_count_written}")
    for name, path in result.output_paths.items():
        print(f"output_{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
