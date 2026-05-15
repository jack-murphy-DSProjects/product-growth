from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pytest

from account_health.scoring import (
    BatchScoringError,
    SCORE_OUTPUT_TABLE,
    BATCH_SCORING_AUDIT_TABLE,
    load_batch_scoring_inputs,
    run_batch_scoring,
    score_batch_inputs,
    write_batch_scoring_tables,
)
from test_batch_scoring_loading import create_promoted_scoring_inputs


class OutOfRangeProbabilityModel:
    classes_ = np.array([0, 1])

    def predict_proba(self, frame):
        return np.array([[0.0, 1.2] for _ in range(len(frame))])


class WrongRowCountModel:
    classes_ = np.array([0, 1])

    def predict_proba(self, frame):
        return np.array([[0.5, 0.5]])


def test_run_batch_scoring_writes_raw_scores_and_audit(tmp_path: Path) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )

    result = run_batch_scoring(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )

    assert result.row_count_read == 2
    assert result.row_count_written == 2
    assert result.output_paths == {
        "score_table": SCORE_OUTPUT_TABLE,
        "audit_table": BATCH_SCORING_AUDIT_TABLE,
    }

    with duckdb.connect(str(database_path), read_only=True) as connection:
        score_rows = connection.execute(
            """
            SELECT
                account_id,
                churn_score,
                expansion_score,
                churn_registered_model_name,
                expansion_registered_model_name,
                scoring_version
            FROM mart.account_month_scores
            ORDER BY account_id
            """
        ).fetchall()
        audit_rows = connection.execute(
            """
            SELECT
                scoring_run_id,
                scoring_month,
                selector,
                row_count_read,
                row_count_written,
                status
            FROM metadata.batch_scoring_audit
            """
        ).fetchall()
        mart_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'mart'
                """
            ).fetchall()
        }

    assert len(score_rows) == 2
    for row in score_rows:
        assert 0.0 <= row[1] <= 1.0
        assert 0.0 <= row[2] <= 1.0
        assert row[3] == "account_health_churn_model"
        assert row[4] == "account_health_expansion_model"
        assert row[5] == "package_8_batch_scoring_v1"
    assert audit_rows == [
        (
            result.scoring_run_id,
            result.scoring_month.date(),
            "scoring_month",
            2,
            2,
            "success",
        )
    ]
    assert "account_health_band" not in mart_tables
    assert "recommended_gtm_actions" not in mart_tables


def test_run_batch_scoring_replaces_month_scores_and_appends_audit(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )

    first = run_batch_scoring(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )
    second = run_batch_scoring(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        score_summary = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT scoring_run_id), MIN(scoring_run_id)
            FROM mart.account_month_scores
            WHERE observation_month = DATE '2024-02-01'
            """
        ).fetchone()
        audit_summary = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT scoring_run_id)
            FROM metadata.batch_scoring_audit
            """
        ).fetchone()

    assert first.scoring_run_id != second.scoring_run_id
    assert score_summary == (2, 1, second.scoring_run_id)
    assert audit_summary == (2, 2)


def test_write_batch_scoring_tables_rolls_back_month_replace_when_audit_fails(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    inputs = load_batch_scoring_inputs(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )
    result = score_batch_inputs(
        inputs,
        scoring_run_id="new_run",
        scored_at_utc="2024-03-01T00:00:00+00:00",
    )

    with duckdb.connect(str(database_path)) as connection:
        connection.execute("CREATE SCHEMA IF NOT EXISTS metadata")
        connection.execute(
            """
            CREATE TABLE mart.account_month_scores (
                scoring_run_id VARCHAR,
                account_id VARCHAR,
                observation_month DATE,
                churn_score DOUBLE,
                expansion_score DOUBLE,
                churn_registered_model_name VARCHAR,
                churn_model_version VARCHAR,
                expansion_registered_model_name VARCHAR,
                expansion_model_version VARCHAR,
                scored_at_utc VARCHAR,
                scoring_version VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO mart.account_month_scores
            VALUES (
                'old_run',
                'acct_old',
                DATE '2024-02-01',
                0.1,
                0.2,
                'account_health_churn_model',
                '1',
                'account_health_expansion_model',
                '1',
                '2024-02-01T00:00:00+00:00',
                'package_8_batch_scoring_v1'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE metadata.batch_scoring_audit (
                scoring_run_id VARCHAR
            )
            """
        )

    with pytest.raises(duckdb.BinderException):
        write_batch_scoring_tables(
            database_path,
            inputs=inputs,
            result=result,
        )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        score_rows = connection.execute(
            """
            SELECT scoring_run_id, account_id
            FROM mart.account_month_scores
            WHERE observation_month = DATE '2024-02-01'
            """
        ).fetchall()

    assert score_rows == [("old_run", "acct_old")]


def test_score_batch_inputs_rejects_invalid_probability_values(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    inputs = load_batch_scoring_inputs(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )
    bad_inputs = replace(
        inputs,
        churn_model=replace(inputs.churn_model, model=OutOfRangeProbabilityModel()),
    )

    with pytest.raises(BatchScoringError, match="bounded between 0 and 1"):
        score_batch_inputs(bad_inputs)


def test_score_batch_inputs_rejects_probability_row_mismatch(
    tmp_path: Path,
) -> None:
    tracking_dir, promotion_manifest_path, database_path = create_promoted_scoring_inputs(
        tmp_path
    )
    inputs = load_batch_scoring_inputs(
        database_path,
        scoring_month="2024-02-01",
        promotion_manifest_path=promotion_manifest_path,
        mlflow_tracking_uri=str(tracking_dir),
        mlflow_registry_uri=str(tracking_dir),
    )
    bad_inputs = replace(
        inputs,
        churn_model=replace(inputs.churn_model, model=WrongRowCountModel()),
    )

    with pytest.raises(BatchScoringError, match="probability shape"):
        score_batch_inputs(bad_inputs)
