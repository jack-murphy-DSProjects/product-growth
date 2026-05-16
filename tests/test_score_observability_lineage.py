from __future__ import annotations

import pandas as pd
import pytest

from account_health.observability import (
    ScoreObservabilityError,
    summarize_scoring_lineage,
)
from test_score_observability_loading import (
    batch_scoring_audit_frame,
    score_observability_frame,
)


def february_score_rows() -> pd.DataFrame:
    frame = score_observability_frame()
    return frame[frame["observation_month"] == pd.Timestamp("2024-02-01")].reset_index(
        drop=True
    )


def february_audit_rows() -> pd.DataFrame:
    frame = batch_scoring_audit_frame()
    return frame[frame["scoring_month"] == pd.Timestamp("2024-02-01")].reset_index(
        drop=True
    )


def test_summarize_scoring_lineage_uses_package_8_score_and_audit_evidence() -> None:
    summary = summarize_scoring_lineage(
        february_score_rows(),
        february_audit_rows(),
        scoring_month=pd.Timestamp("2024-02-01"),
    )

    churn = summary.loc[summary["target"] == "churn"].iloc[0]
    expansion = summary.loc[summary["target"] == "expansion"].iloc[0]

    assert summary["target"].tolist() == ["churn", "expansion"]
    assert churn["scoring_run_id"] == "run_feb"
    assert churn["registered_model_name"] == "account_health_churn_model"
    assert churn["model_version"] == "1"
    assert churn["source_mlflow_run_id"] == "churn_source_run"
    assert expansion["registered_model_name"] == "account_health_expansion_model"
    assert expansion["model_version"] == "2"
    assert expansion["source_mlflow_run_id"] == "expansion_source_run"
    assert set(summary["scoring_status"]) == {"success"}


def test_summarize_scoring_lineage_rejects_inconsistent_current_score_run_ids() -> None:
    score_rows = february_score_rows()
    score_rows.loc[0, "scoring_run_id"] = "different_run"

    with pytest.raises(ScoreObservabilityError, match="one scoring_run_id"):
        summarize_scoring_lineage(
            score_rows,
            february_audit_rows(),
            scoring_month=pd.Timestamp("2024-02-01"),
        )


def test_summarize_scoring_lineage_rejects_audit_score_mismatch() -> None:
    audit_rows = february_audit_rows()
    audit_rows.loc[0, "churn_model_version"] = "999"

    with pytest.raises(ScoreObservabilityError, match="lineage mismatch"):
        summarize_scoring_lineage(
            february_score_rows(),
            audit_rows,
            scoring_month=pd.Timestamp("2024-02-01"),
        )
