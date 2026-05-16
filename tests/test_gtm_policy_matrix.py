from __future__ import annotations

import pandas as pd
import pytest

from account_health.gtm_policy import (
    GTMPolicyError,
    POLICY_VERSION,
    apply_gtm_policy_v1,
)


@pytest.mark.parametrize(
    (
        "churn_score",
        "expansion_score",
        "health_band",
        "lifecycle_motion",
        "recommended_action",
        "action_priority",
        "action_reason_code",
    ),
    [
        (
            0.90,
            0.90,
            "Critical",
            "Retention-led expansion watch",
            "Executive save plan before expansion",
            "P1",
            "HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST",
        ),
        (
            0.90,
            0.50,
            "Critical",
            "Retention",
            "Immediate retention intervention",
            "P1",
            "HIGH_CHURN_RETENTION",
        ),
        (
            0.50,
            0.90,
            "At Risk",
            "Stabilise then expand",
            "Resolve risks before expansion outreach",
            "P2",
            "MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST",
        ),
        (
            0.50,
            0.50,
            "At Risk",
            "Risk monitoring",
            "Customer success risk review",
            "P2",
            "MEDIUM_CHURN_RISK_REVIEW",
        ),
        (
            0.20,
            0.90,
            "Growth Ready",
            "Expansion",
            "Prioritise expansion outreach",
            "P1",
            "LOW_CHURN_HIGH_EXPANSION",
        ),
        (
            0.20,
            0.50,
            "Stable",
            "Nurture",
            "Nurture for future expansion",
            "P3",
            "LOW_CHURN_MEDIUM_EXPANSION_NURTURE",
        ),
        (
            0.20,
            0.20,
            "Stable",
            "Maintain",
            "Monitor in standard cadence",
            "P3",
            "LOW_CHURN_LOW_EXPANSION_MAINTAIN",
        ),
    ],
)
def test_apply_gtm_policy_v1_matches_locked_matrix_rows(
    churn_score: float,
    expansion_score: float,
    health_band: str,
    lifecycle_motion: str,
    recommended_action: str,
    action_priority: str,
    action_reason_code: str,
) -> None:
    result = apply_gtm_policy_v1(
        pd.DataFrame(
            [{"churn_score": churn_score, "expansion_score": expansion_score}]
        )
    )

    assert result.loc[0, "health_band"] == health_band
    assert result.loc[0, "lifecycle_motion"] == lifecycle_motion
    assert result.loc[0, "recommended_action"] == recommended_action
    assert result.loc[0, "action_priority"] == action_priority
    assert result.loc[0, "action_reason_code"] == action_reason_code
    assert result.loc[0, "policy_version"] == POLICY_VERSION


@pytest.mark.parametrize(
    ("churn_score", "expansion_score", "action_reason_code"),
    [
        (0.70, 0.70, "HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST"),
        (0.70, 0.699999, "HIGH_CHURN_RETENTION"),
        (0.40, 0.70, "MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST"),
        (0.40, 0.699999, "MEDIUM_CHURN_RISK_REVIEW"),
        (0.399999, 0.70, "LOW_CHURN_HIGH_EXPANSION"),
        (0.399999, 0.40, "LOW_CHURN_MEDIUM_EXPANSION_NURTURE"),
        (0.399999, 0.399999, "LOW_CHURN_LOW_EXPANSION_MAINTAIN"),
    ],
)
def test_apply_gtm_policy_v1_uses_documented_threshold_boundaries(
    churn_score: float,
    expansion_score: float,
    action_reason_code: str,
) -> None:
    result = apply_gtm_policy_v1(
        pd.DataFrame(
            [{"churn_score": churn_score, "expansion_score": expansion_score}]
        )
    )

    assert result.loc[0, "action_reason_code"] == action_reason_code


def test_apply_gtm_policy_v1_high_churn_high_expansion_is_save_first() -> None:
    result = apply_gtm_policy_v1(
        pd.DataFrame([{"churn_score": 0.95, "expansion_score": 0.95}])
    )

    assert result.loc[0, "lifecycle_motion"] == "Retention-led expansion watch"
    assert (
        result.loc[0, "recommended_action"]
        == "Executive save plan before expansion"
    )
    assert result.loc[0, "recommended_action"] != "Prioritise expansion outreach"


def test_apply_gtm_policy_v1_rejects_invalid_scores_before_assignment() -> None:
    with pytest.raises(GTMPolicyError, match=r"\[0, 1\]"):
        apply_gtm_policy_v1(
            pd.DataFrame([{"churn_score": 1.1, "expansion_score": 0.20}])
        )
