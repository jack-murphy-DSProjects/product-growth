from __future__ import annotations

import argparse
import sys

from account_health.registry import (
    DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH,
    DEFAULT_PROMOTION_MANIFEST_PATH,
    PACKAGE7_TARGETS,
    ModelRegistryError,
    run_model_registry_promotion,
)
from account_health.warehouse import DEFAULT_DATABASE_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Promote eligible Package 6-selected ML champions into the local "
            "MLflow registry."
        )
    )
    parser.add_argument(
        "--champion-manifest-path",
        default=str(DEFAULT_CHAMPION_SELECTION_MANIFEST_PATH),
    )
    parser.add_argument("--warehouse-path", default=str(DEFAULT_DATABASE_PATH))
    parser.add_argument(
        "--promotion-manifest-path",
        default=str(DEFAULT_PROMOTION_MANIFEST_PATH),
    )
    parser.add_argument("--mlflow-tracking-uri", default=None)
    parser.add_argument("--mlflow-registry-uri", default=None)
    parser.add_argument(
        "--target",
        action="append",
        choices=tuple(PACKAGE7_TARGETS),
        help="Target key to promote. Repeat to promote multiple targets.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = tuple(args.target) if args.target else tuple(PACKAGE7_TARGETS)
    try:
        result = run_model_registry_promotion(
            champion_manifest_path=args.champion_manifest_path,
            targets=targets,
            mlflow_tracking_uri=args.mlflow_tracking_uri,
            mlflow_registry_uri=args.mlflow_registry_uri,
            promotion_manifest_path=args.promotion_manifest_path,
            database_path=args.warehouse_path,
        )
    except ModelRegistryError as error:
        print(f"Package 7 promotion failed: {error}", file=sys.stderr)
        return 1

    print(f"promotion_id: {result.promotion_id}")
    print(f"promotion_version: {result.promotion_version}")
    print(f"promoted_at_utc: {result.promoted_at_utc}")
    print(f"promoted_count: {len(result.promotion_records)}")
    for record in result.promotion_records:
        print(
            "promoted: "
            f"target={record['target_key']} "
            f"registered_model={record['registered_model_name']} "
            f"version={record['model_version']} "
            f"alias={record['alias']}"
        )
    for name, path in result.output_paths.items():
        print(f"output_{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
