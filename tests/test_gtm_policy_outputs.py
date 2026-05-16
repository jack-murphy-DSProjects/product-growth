from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.gtm_policy import (
    GTMPolicyError,
    GTM_POLICY_OUTPUT_TABLE,
    build_gtm_policy_output_frame,
    load_gtm_policy_context,
    load_gtm_policy_inputs,
    write_gtm_policy_output_table,
)
from test_gtm_policy_loading import (
    create_gtm_policy_score_table,
    gtm_policy_score_frame,
)


def gtm_policy_context_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-01-01"),
                "current_plan": "starter",
                "company_size_band": "1_50",
                "region": "europe",
                "industry": "software",
                "current_mrr": 100.0,
                "churn_90d": 0,
                "expansion_90d": 1,
                "synthetic_archetype": "expansion_ready",
            },
            {
                "account_id": "acct_one",
                "observation_month": pd.Timestamp("2024-02-01"),
                "current_plan": "starter",
                "company_size_band": "1_50",
                "region": "europe",
                "industry": "software",
                "current_mrr": 125.0,
                "churn_90d": 0,
                "expansion_90d": 1,
                "synthetic_archetype": "expansion_ready",
            },
            {
                "account_id": "acct_two",
                "observation_month": pd.Timestamp("2024-02-01"),
                "current_plan": "business",
                "company_size_band": "51_200",
                "region": "north_america",
                "industry": "retail",
                "current_mrr": 900.0,
                "churn_90d": 1,
                "expansion_90d": None,
                "synthetic_archetype": "support_frustrated",
            },
        ]
    )


def create_gtm_policy_tables(
    database_path: Path,
    *,
    score_frame: pd.DataFrame | None = None,
    context_frame: pd.DataFrame | None = None,
) -> None:
    create_gtm_policy_score_table(database_path, score_frame=score_frame)
    context_frame = (
        gtm_policy_context_frame() if context_frame is None else context_frame
    )
    with duckdb.connect(str(database_path)) as connection:
        connection.register("context_frame", context_frame)
        try:
            connection.execute(
                """
                CREATE OR REPLACE TABLE mart.account_month AS
                SELECT * FROM context_frame
                """
            )
        finally:
            connection.unregister("context_frame")


def test_build_gtm_policy_output_frame_preserves_safe_context_and_lineage(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    inputs = load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")
    context = load_gtm_policy_context(
        database_path,
        scoring_month=inputs.scoring_month,
    )

    output = build_gtm_policy_output_frame(
        inputs.score_frame,
        context,
        scoring_month=inputs.scoring_month,
        created_at_utc="2024-03-02T00:00:00+00:00",
    )

    assert output.columns.tolist() == [
        "account_id",
        "scoring_month",
        "churn_score",
        "expansion_score",
        "health_band",
        "lifecycle_motion",
        "recommended_action",
        "action_priority",
        "action_reason_code",
        "policy_version",
        "created_at_utc",
        "scoring_run_id",
        "churn_registered_model_name",
        "churn_model_version",
        "expansion_registered_model_name",
        "expansion_model_version",
        "scored_at_utc",
        "scoring_version",
        "current_plan",
        "company_size_band",
        "region",
        "industry",
        "current_mrr",
    ]
    assert output["account_id"].tolist() == ["acct_one", "acct_two"]
    assert output["scoring_month"].tolist() == [
        pd.Timestamp("2024-02-01").date(),
        pd.Timestamp("2024-02-01").date(),
    ]
    assert output["churn_score"].tolist() == [0.20, 0.40]
    assert output["expansion_score"].tolist() == [0.70, 0.60]
    assert output["scoring_run_id"].tolist() == ["run_feb", "run_feb"]
    assert output["churn_model_version"].tolist() == ["1", "1"]
    assert output["expansion_model_version"].tolist() == ["2", "2"]
    assert output["current_plan"].tolist() == ["starter", "business"]
    assert output["current_mrr"].tolist() == [125.0, 900.0]
    assert "churn_90d" not in output.columns
    assert "expansion_90d" not in output.columns
    assert "synthetic_archetype" not in output.columns
    assert "observation_month" not in output.columns


def test_load_gtm_policy_context_excludes_labels_and_generator_only_fields(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)

    context = load_gtm_policy_context(
        database_path,
        scoring_month="2024-02-01",
    )

    assert context.columns.tolist() == [
        "account_id",
        "observation_month",
        "current_plan",
        "company_size_band",
        "region",
        "industry",
        "current_mrr",
    ]


def test_build_gtm_policy_output_frame_rejects_row_multiplying_context_join(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    duplicate_context = pd.concat(
        [gtm_policy_context_frame(), gtm_policy_context_frame().iloc[[1]]],
        ignore_index=True,
    )
    create_gtm_policy_tables(database_path, context_frame=duplicate_context)
    inputs = load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")

    with pytest.raises(GTMPolicyError, match="duplicate account/month"):
        load_gtm_policy_context(database_path, scoring_month=inputs.scoring_month)


def test_write_gtm_policy_output_table_writes_one_row_per_account_month(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_gtm_policy_tables(database_path)
    inputs = load_gtm_policy_inputs(database_path, scoring_month="2024-02-01")
    context = load_gtm_policy_context(
        database_path,
        scoring_month=inputs.scoring_month,
    )
    output = build_gtm_policy_output_frame(
        inputs.score_frame,
        context,
        scoring_month=inputs.scoring_month,
        created_at_utc="2024-03-02T00:00:00+00:00",
    )

    write_gtm_policy_output_table(
        database_path,
        policy_frame=output,
        scoring_month=inputs.scoring_month,
    )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT account_id, scoring_month, action_reason_code
            FROM mart.account_month_gtm_policy
            ORDER BY account_id
            """
        ).fetchall()
        columns = {
            row[0]
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'mart'
                  AND table_name = 'account_month_gtm_policy'
                """
            ).fetchall()
        }

    assert rows == [
        (
            "acct_one",
            pd.Timestamp("2024-02-01").date(),
            "LOW_CHURN_HIGH_EXPANSION",
        ),
        (
            "acct_two",
            pd.Timestamp("2024-02-01").date(),
            "MEDIUM_CHURN_RISK_REVIEW",
        ),
    ]
    assert GTM_POLICY_OUTPUT_TABLE == "mart.account_month_gtm_policy"
    assert "churn_90d" not in columns
    assert "expansion_90d" not in columns
    assert "synthetic_archetype" not in columns
