"""Locked deterministic `gtm_policy_v1` matrix for Package 10."""

from __future__ import annotations

import numpy as np
import pandas as pd

from account_health.gtm_policy.loading import (
    GTMPolicyError,
    validate_gtm_policy_score_values,
)

POLICY_VERSION = "gtm_policy_v1"


def apply_gtm_policy_v1(score_frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the exhaustive locked Package 10 v1 policy matrix."""

    frame = validate_gtm_policy_score_values(score_frame)
    churn = frame["churn_score"]
    expansion = frame["expansion_score"]

    conditions = (
        (churn >= 0.70) & (expansion >= 0.70),
        (churn >= 0.70) & (expansion < 0.70),
        (churn >= 0.40) & (churn < 0.70) & (expansion >= 0.70),
        (churn >= 0.40) & (churn < 0.70) & (expansion < 0.70),
        (churn < 0.40) & (expansion >= 0.70),
        (churn < 0.40) & (expansion >= 0.40) & (expansion < 0.70),
        (churn < 0.40) & (expansion < 0.40),
    )
    _validate_exactly_one_match(conditions)

    mapped = frame.copy()
    mapped["health_band"] = np.select(
        conditions,
        (
            "Critical",
            "Critical",
            "At Risk",
            "At Risk",
            "Growth Ready",
            "Stable",
            "Stable",
        ),
    )
    mapped["lifecycle_motion"] = np.select(
        conditions,
        (
            "Retention-led expansion watch",
            "Retention",
            "Stabilise then expand",
            "Risk monitoring",
            "Expansion",
            "Nurture",
            "Maintain",
        ),
    )
    mapped["recommended_action"] = np.select(
        conditions,
        (
            "Executive save plan before expansion",
            "Immediate retention intervention",
            "Resolve risks before expansion outreach",
            "Customer success risk review",
            "Prioritise expansion outreach",
            "Nurture for future expansion",
            "Monitor in standard cadence",
        ),
    )
    mapped["action_priority"] = np.select(
        conditions,
        ("P1", "P1", "P2", "P2", "P1", "P3", "P3"),
    )
    mapped["action_reason_code"] = np.select(
        conditions,
        (
            "HIGH_CHURN_HIGH_EXPANSION_SAVE_FIRST",
            "HIGH_CHURN_RETENTION",
            "MEDIUM_CHURN_HIGH_EXPANSION_STABILISE_FIRST",
            "MEDIUM_CHURN_RISK_REVIEW",
            "LOW_CHURN_HIGH_EXPANSION",
            "LOW_CHURN_MEDIUM_EXPANSION_NURTURE",
            "LOW_CHURN_LOW_EXPANSION_MAINTAIN",
        ),
    )
    mapped["policy_version"] = POLICY_VERSION
    _validate_policy_assignments(mapped)
    return mapped


def _validate_exactly_one_match(conditions: tuple[pd.Series, ...]) -> None:
    match_counts = np.column_stack(
        [condition.to_numpy(dtype=int) for condition in conditions]
    ).sum(axis=1)
    if not np.equal(match_counts, 1).all():
        raise GTMPolicyError(
            "Package 10 valid score rows must map to exactly one gtm_policy_v1 row"
        )


def _validate_policy_assignments(frame: pd.DataFrame) -> None:
    required_policy_columns = (
        "health_band",
        "lifecycle_motion",
        "recommended_action",
        "action_priority",
        "action_reason_code",
        "policy_version",
    )
    if frame.loc[:, required_policy_columns].isna().any().any():
        raise GTMPolicyError("Package 10 policy assignment contains null outputs")
