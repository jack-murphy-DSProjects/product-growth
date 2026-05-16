from __future__ import annotations

import argparse
import sys

from account_health.gtm_policy import (
    DEFAULT_GTM_POLICY_EXPORT_DIR,
    GTMPolicyError,
    run_gtm_policy,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Package 10 deterministic local GTM policy outputs."
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scoring-month", default=None)
    selector.add_argument("--latest", action="store_true")
    parser.add_argument(
        "--export-dir",
        default=None,
        help=(
            "Optional GTM policy CSV export directory. Repo-local exports must "
            f"stay under {DEFAULT_GTM_POLICY_EXPORT_DIR}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_gtm_policy(
            database_path=args.warehouse_path,
            scoring_month=args.scoring_month,
            latest=args.latest,
            export_dir=args.export_dir,
        )
    except GTMPolicyError as error:
        print(f"Package 10 GTM policy failed: {error}", file=sys.stderr)
        return 1

    print(f"run_id: {result.run_id}")
    print(f"policy_version: {result.policy_version}")
    print(f"selector: {result.selector}")
    print(f"scoring_month: {result.scoring_month.date().isoformat()}")
    print(f"input_score_row_count: {result.input_score_row_count}")
    print(f"output_policy_row_count: {result.output_policy_row_count}")
    print(f"status: {result.status}")
    print(f"observability_status: {result.observability_status}")
    for name, path in result.output_paths.items():
        print(f"output_{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
