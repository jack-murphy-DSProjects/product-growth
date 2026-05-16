"""Package 10 safe-context joins and RevOps-facing policy outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from account_health.gtm_policy.loading import (
    SAFE_CONTEXT_COLUMNS,
    GTMPolicyError,
)
from account_health.gtm_policy.matrix import apply_gtm_policy_v1

GTM_POLICY_OUTPUT_TABLE = "mart.account_month_gtm_policy"

LINEAGE_COLUMNS = (
    "scoring_run_id",
    "churn_registered_model_name",
    "churn_model_version",
    "expansion_registered_model_name",
    "expansion_model_version",
    "scored_at_utc",
    "scoring_version",
)
POLICY_VALUE_COLUMNS = (
    "health_band",
    "lifecycle_motion",
    "recommended_action",
    "action_priority",
    "action_reason_code",
    "policy_version",
)
OUTPUT_COLUMNS = (
    "account_id",
    "scoring_month",
    "churn_score",
    "expansion_score",
    *POLICY_VALUE_COLUMNS,
    "created_at_utc",
    *LINEAGE_COLUMNS,
    *SAFE_CONTEXT_COLUMNS,
)


def build_gtm_policy_output_frame(
    score_frame: pd.DataFrame,
    context_frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
    created_at_utc: str | None = None,
) -> pd.DataFrame:
    """Build one deterministic RevOps-facing policy row per scored account."""

    _validate_non_multiplying_join(score_frame, context_frame)
    policy_frame = apply_gtm_policy_v1(score_frame)
    joined = policy_frame.merge(
        context_frame[["account_id", "observation_month", *SAFE_CONTEXT_COLUMNS]],
        on=["account_id", "observation_month"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not (joined["_merge"] == "both").all():
        raise GTMPolicyError(
            "Package 10 safe context join is missing scored account/month rows"
        )
    missing_lineage_columns = tuple(
        column for column in LINEAGE_COLUMNS if column not in joined.columns
    )
    if missing_lineage_columns:
        raise GTMPolicyError(
            "Package 10 score lineage is missing column(s): "
            + ", ".join(missing_lineage_columns)
        )

    created_at = created_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat()
    joined["scoring_month"] = scoring_month.date()
    joined["created_at_utc"] = created_at
    output = joined.loc[:, OUTPUT_COLUMNS].copy()
    _validate_policy_output_grain(output)
    return output


def write_gtm_policy_output_table(
    database_path: str | Path,
    *,
    policy_frame: pd.DataFrame,
    scoring_month: pd.Timestamp,
) -> None:
    """Write the selected-month Package 10 policy output rows."""

    database_file = Path(database_path)
    with duckdb.connect(str(database_file)) as connection:
        frame_registered = False
        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("CREATE SCHEMA IF NOT EXISTS mart")
            connection.execute(_create_gtm_policy_output_table_sql())
            connection.execute(
                f"DELETE FROM {GTM_POLICY_OUTPUT_TABLE} WHERE scoring_month = ?",
                [scoring_month.date()],
            )
            connection.register("gtm_policy_output_frame", policy_frame)
            frame_registered = True
            connection.execute(
                f"""
                INSERT INTO {GTM_POLICY_OUTPUT_TABLE}
                SELECT {", ".join(OUTPUT_COLUMNS)}
                FROM gtm_policy_output_frame
                """
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            if frame_registered:
                connection.unregister("gtm_policy_output_frame")


def _validate_non_multiplying_join(
    score_frame: pd.DataFrame,
    context_frame: pd.DataFrame,
) -> None:
    score_duplicates = score_frame.duplicated(
        subset=["account_id", "observation_month"]
    )
    context_duplicates = context_frame.duplicated(
        subset=["account_id", "observation_month"]
    )
    if score_duplicates.any() or context_duplicates.any():
        raise GTMPolicyError("Package 10 safe context join would multiply rows")


def _validate_policy_output_grain(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise GTMPolicyError("Package 10 policy output has no rows")
    if frame["account_id"].isna().any():
        raise GTMPolicyError("Package 10 policy output contains null account_id")
    duplicate_mask = frame.duplicated(subset=["account_id", "scoring_month"])
    if duplicate_mask.any():
        raise GTMPolicyError(
            "Package 10 policy output contains duplicate account/month rows"
        )


def _create_gtm_policy_output_table_sql() -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {GTM_POLICY_OUTPUT_TABLE} (
        account_id VARCHAR,
        scoring_month DATE,
        churn_score DOUBLE,
        expansion_score DOUBLE,
        health_band VARCHAR,
        lifecycle_motion VARCHAR,
        recommended_action VARCHAR,
        action_priority VARCHAR,
        action_reason_code VARCHAR,
        policy_version VARCHAR,
        created_at_utc VARCHAR,
        scoring_run_id VARCHAR,
        churn_registered_model_name VARCHAR,
        churn_model_version VARCHAR,
        expansion_registered_model_name VARCHAR,
        expansion_model_version VARCHAR,
        scored_at_utc VARCHAR,
        scoring_version VARCHAR,
        current_plan VARCHAR,
        company_size_band VARCHAR,
        region VARCHAR,
        industry VARCHAR,
        current_mrr DOUBLE
    )
    """
