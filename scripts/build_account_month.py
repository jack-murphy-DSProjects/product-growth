from __future__ import annotations

import argparse

from account_health.features import build_account_month
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build mart.account_month from an existing raw DuckDB warehouse."
    )
    parser.add_argument("--database-path", default=str(DEFAULT_DATABASE_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_account_month(database_path=args.database_path)

    print(f"build_id: {result.build_id}")
    print(f"database_path: {result.database_path}")
    print(f"output_table: {result.output_table}")
    print(f"row_count: {result.row_count}")
    print(f"account_count: {result.account_count}")
    print(f"min_observation_month: {result.min_observation_month}")
    print(f"max_observation_month: {result.max_observation_month}")
    print(f"churn_eligible_count: {result.churn_eligible_count}")
    print(f"churn_positive_count: {result.churn_positive_count}")
    print(f"expansion_eligible_count: {result.expansion_eligible_count}")
    print(f"expansion_positive_count: {result.expansion_positive_count}")
    print(f"source_max_date: {result.source_max_date}")
    print(f"audit_table: {result.audit_table}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
