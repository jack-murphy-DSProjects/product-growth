from __future__ import annotations

import argparse

from account_health.baselines import build_account_month_baselines
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic Package 4 rule baselines from "
            "mart.account_month."
        )
    )
    parser.add_argument("--database-path", default=str(DEFAULT_DATABASE_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_account_month_baselines(database_path=args.database_path)

    print(f"build_id: {result.build_id}")
    print(f"database_path: {result.database_path}")
    print(f"source_table: {result.source_table}")
    print(f"output_table: {result.output_table}")
    print(f"audit_table: {result.audit_table}")
    print(f"baseline_version: {result.baseline_version}")
    print(f"row_count: {result.row_count}")
    print(f"account_count: {result.account_count}")
    print(f"min_observation_month: {result.min_observation_month}")
    print(f"max_observation_month: {result.max_observation_month}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
