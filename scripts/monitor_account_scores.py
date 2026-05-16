from __future__ import annotations

import argparse
import sys

from account_health.observability import (
    DEFAULT_SCORE_OBSERVABILITY_EXPORT_DIR,
    ScoreObservabilityError,
    run_score_observability,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Package 9 local batch scoring observability."
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scoring-month", default=None)
    selector.add_argument("--latest", action="store_true")
    parser.add_argument(
        "--export-dir",
        default=None,
        help=(
            "Optional observability CSV export directory. Repo-local exports must "
            f"stay under {DEFAULT_SCORE_OBSERVABILITY_EXPORT_DIR}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_score_observability(
            database_path=args.warehouse_path,
            scoring_month=args.scoring_month,
            latest=args.latest,
            export_dir=args.export_dir,
        )
    except ScoreObservabilityError as error:
        print(f"Package 9 score observability failed: {error}", file=sys.stderr)
        return 1

    print(f"observability_run_id: {result.observability_run_id}")
    print(f"observability_version: {result.observability_version}")
    print(f"created_at_utc: {result.created_at_utc}")
    print(f"selector: {result.selector}")
    print(f"scoring_month: {result.scoring_month.date().isoformat()}")
    prior_month = (
        "none"
        if result.prior_scoring_month is None
        else result.prior_scoring_month.date().isoformat()
    )
    print(f"prior_scoring_month: {prior_month}")
    print(f"status: {result.status}")
    print("warning_codes: " + ",".join(result.warning_codes))
    for name, path in result.output_paths.items():
        print(f"output_{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
