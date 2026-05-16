from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from account_health.observability import (
    SCORE_DISTRIBUTION_BY_MONTH_TABLE,
    SCORE_DISTRIBUTION_BY_SEGMENT_TABLE,
    SCORE_OBSERVABILITY_AUDIT_TABLE,
    SCORE_OBSERVABILITY_SUMMARY_TABLE,
    SCORING_LINEAGE_SUMMARY_TABLE,
    ScoreObservabilityError,
    run_score_observability,
)
from test_score_observability_loading import (
    create_score_observability_tables,
    score_observability_frame,
)


def test_run_score_observability_writes_summary_tables_and_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    result = run_score_observability(
        database_path,
        scoring_month="2024-02-01",
        small_segment_threshold=1,
    )

    assert result.status == "success"
    assert result.warning_codes == ()
    assert result.output_paths == {
        "summary_table": SCORE_OBSERVABILITY_SUMMARY_TABLE,
        "distribution_by_month_table": SCORE_DISTRIBUTION_BY_MONTH_TABLE,
        "distribution_by_segment_table": SCORE_DISTRIBUTION_BY_SEGMENT_TABLE,
        "lineage_summary_table": SCORING_LINEAGE_SUMMARY_TABLE,
        "audit_table": SCORE_OBSERVABILITY_AUDIT_TABLE,
    }

    with duckdb.connect(str(database_path), read_only=True) as connection:
        summary_rows = connection.execute(
            """
            SELECT scoring_month, status, expected_account_count, scored_account_count
            FROM mart.score_observability_summary
            """
        ).fetchall()
        month_distribution_count = connection.execute(
            "SELECT COUNT(*) FROM mart.score_distribution_by_month"
        ).fetchone()[0]
        segment_distribution_count = connection.execute(
            "SELECT COUNT(*) FROM mart.score_distribution_by_segment"
        ).fetchone()[0]
        lineage_count = connection.execute(
            "SELECT COUNT(*) FROM mart.scoring_lineage_summary"
        ).fetchone()[0]
        audit_rows = connection.execute(
            """
            SELECT status, warning_codes_json, failure_reason
            FROM metadata.score_observability_audit
            """
        ).fetchall()

    assert summary_rows == [
        (pd.Timestamp("2024-02-01").date(), "success", 2, 2)
    ]
    assert month_distribution_count == 2
    assert segment_distribution_count == 20
    assert lineage_count == 2
    assert audit_rows == [("success", "[]", None)]


def test_run_score_observability_replaces_summary_rows_and_appends_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    first = run_score_observability(
        database_path,
        scoring_month="2024-02-01",
        small_segment_threshold=1,
    )
    second = run_score_observability(
        database_path,
        scoring_month="2024-02-01",
        small_segment_threshold=1,
    )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        summary_rows = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT observability_run_id), MIN(observability_run_id)
            FROM mart.score_observability_summary
            WHERE scoring_month = DATE '2024-02-01'
            """
        ).fetchone()
        audit_rows = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT observability_run_id)
            FROM metadata.score_observability_audit
            """
        ).fetchone()

    assert first.observability_run_id != second.observability_run_id
    assert summary_rows == (1, 1, second.observability_run_id)
    assert audit_rows == (2, 2)


def test_run_score_observability_succeeds_with_warning_for_one_month_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    create_score_observability_tables(database_path)

    result = run_score_observability(
        database_path,
        scoring_month="2024-01-01",
        small_segment_threshold=1,
    )

    assert result.status == "success_with_warnings"
    assert "no_prior_scored_month" in result.warning_codes
    assert result.prior_scoring_month is None


def test_run_score_observability_records_failed_audit_when_safe(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "warehouse.duckdb"
    scores = score_observability_frame()
    scores.loc[
        scores["observation_month"] == pd.Timestamp("2024-02-01"),
        "churn_score",
    ] = 1.5
    create_score_observability_tables(database_path, score_frame=scores)

    with pytest.raises(ScoreObservabilityError, match=r"\[0, 1\]"):
        run_score_observability(
            database_path,
            scoring_month="2024-02-01",
            small_segment_threshold=1,
        )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        audit_rows = connection.execute(
            """
            SELECT status, failure_reason
            FROM metadata.score_observability_audit
            """
        ).fetchall()

    assert len(audit_rows) == 1
    assert audit_rows[0][0] == "failed"
    assert "[0, 1]" in audit_rows[0][1]
