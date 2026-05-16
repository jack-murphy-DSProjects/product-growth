"""Package 9 observed scoring-lineage summaries from Package 8 evidence."""

from __future__ import annotations

import pandas as pd

from account_health.observability.loading import ScoreObservabilityError

TARGET_LINEAGE_COLUMNS = {
    "churn": {
        "score_model_name": "churn_registered_model_name",
        "score_model_version": "churn_model_version",
        "audit_model_name": "churn_registered_model_name",
        "audit_model_version": "churn_model_version",
        "source_run_id": "churn_source_mlflow_run_id",
        "feature_metadata_artifact": "churn_feature_metadata_artifact",
    },
    "expansion": {
        "score_model_name": "expansion_registered_model_name",
        "score_model_version": "expansion_model_version",
        "audit_model_name": "expansion_registered_model_name",
        "audit_model_version": "expansion_model_version",
        "source_run_id": "expansion_source_mlflow_run_id",
        "feature_metadata_artifact": "expansion_feature_metadata_artifact",
    },
}


def summarize_scoring_lineage(
    score_frame: pd.DataFrame,
    batch_audit_frame: pd.DataFrame,
    *,
    scoring_month: pd.Timestamp,
) -> pd.DataFrame:
    """Summarize observed Package 8 lineage for the selected score rows."""

    scoring_run_id = _single_required_value(
        score_frame,
        "scoring_run_id",
        description="score rows must contain one scoring_run_id",
    )
    scored_at_utc = _single_required_value(
        score_frame,
        "scored_at_utc",
        description="score rows must contain one scored_at_utc",
    )
    scoring_version = _single_required_value(
        score_frame,
        "scoring_version",
        description="score rows must contain one scoring_version",
    )
    matching_audit = batch_audit_frame[
        batch_audit_frame["scoring_run_id"] == scoring_run_id
    ]
    if len(matching_audit) != 1:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage is inconsistent: selected "
            "score rows must have exactly one matching batch scoring audit row"
        )
    audit_row = matching_audit.iloc[0]
    _validate_common_lineage(
        audit_row,
        scoring_month=scoring_month,
        scoring_run_id=scoring_run_id,
        scored_at_utc=scored_at_utc,
        scoring_version=scoring_version,
        score_row_count=len(score_frame),
    )

    rows: list[dict[str, object]] = []
    for target, columns in TARGET_LINEAGE_COLUMNS.items():
        score_model_name = _single_required_value(
            score_frame,
            columns["score_model_name"],
            description=f"{target} score rows must contain one model name",
        )
        score_model_version = _single_required_value(
            score_frame,
            columns["score_model_version"],
            description=f"{target} score rows must contain one model version",
        )
        audit_model_name = audit_row[columns["audit_model_name"]]
        audit_model_version = audit_row[columns["audit_model_version"]]
        if (
            score_model_name != audit_model_name
            or str(score_model_version) != str(audit_model_version)
        ):
            raise ScoreObservabilityError(
                f"Package 9 required {target} lineage mismatch between score rows "
                "and Package 8 audit evidence"
            )
        rows.append(
            {
                "scoring_month": scoring_month.date(),
                "scoring_run_id": scoring_run_id,
                "target": target,
                "registered_model_name": score_model_name,
                "model_version": str(score_model_version),
                "source_mlflow_run_id": audit_row[columns["source_run_id"]],
                "feature_metadata_artifact": audit_row[
                    columns["feature_metadata_artifact"]
                ],
                "scored_at_utc": scored_at_utc,
                "scoring_version": scoring_version,
                "scoring_status": audit_row["status"],
            }
        )
    return pd.DataFrame(rows)


def _validate_common_lineage(
    audit_row: pd.Series,
    *,
    scoring_month: pd.Timestamp,
    scoring_run_id: object,
    scored_at_utc: object,
    scoring_version: object,
    score_row_count: int,
) -> None:
    if audit_row["status"] != "success":
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage audit row is not successful"
        )
    if pd.Timestamp(audit_row["scoring_month"]).normalize() != scoring_month:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage audit month does not match "
            "selected score rows"
        )
    if audit_row["scoring_run_id"] != scoring_run_id:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage run id does not match "
            "selected score rows"
        )
    if audit_row["scored_at_utc"] != scored_at_utc:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage scored_at timestamp does not "
            "match selected score rows"
        )
    if audit_row["scoring_version"] != scoring_version:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage scoring version does not match "
            "selected score rows"
        )
    if int(audit_row["row_count_written"]) != score_row_count:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage row count does not match "
            "selected score rows"
        )


def _single_required_value(
    frame: pd.DataFrame,
    column: str,
    *,
    description: str,
) -> object:
    values = frame[column].dropna().unique()
    if len(values) != 1:
        raise ScoreObservabilityError(
            "Package 9 required Package 8 lineage is inconsistent: " + description
        )
    return values[0]
