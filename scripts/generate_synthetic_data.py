from __future__ import annotations

import argparse
from pathlib import Path

from account_health.synthetic import generate_synthetic_source_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic SaaS source CSVs."
    )
    parser.add_argument("--output-dir", default="data/generated/")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-accounts", type=int, default=500)
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = generate_synthetic_source_data(
        seed=args.seed,
        n_accounts=args.n_accounts,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    for table_name, frame in tables.items():
        output_path = output_dir / f"{table_name}.csv"
        frame.to_csv(output_path, index=False)
        print(f"{table_name}: {len(frame)} rows -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
