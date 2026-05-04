from __future__ import annotations

import argparse

from account_health.warehouse import (
    DEFAULT_DATABASE_PATH,
    DEFAULT_SOURCE_DIR,
    load_source_csvs_to_warehouse,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load generated synthetic SaaS source CSVs into DuckDB."
    )
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--database-path", default=str(DEFAULT_DATABASE_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = load_source_csvs_to_warehouse(
        source_dir=args.source_dir,
        database_path=args.database_path,
    )

    print(f"load_id: {result.load_id}")
    print(f"database_path: {result.database_path}")
    for table_name, row_count in result.table_row_counts.items():
        print(f"raw.{table_name}: {row_count} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
