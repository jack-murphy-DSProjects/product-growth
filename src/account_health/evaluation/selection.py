"""Illustrative utility sensitivity and champion selection for Package 6."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import pandas as pd

from account_health.evaluation.metrics import (
    BASELINE_CANDIDATE_TYPE,
    FIXED_HOLDOUT_SLICE_VALUE,
    ML_CANDIDATE_TYPE,
    OVERALL_SLICE_TYPE,
    MetricRecord,
    select_top_k_rows,
)
from account_health.evaluation.robustness import CaveatRecord

PRIMARY_CHAMPION_METRIC = "precision_at_top_10_pct"
CHAMPION_TOP_K_PERCENTAGE = 0.10
MIN_RELATIVE_PRECISION_GAIN = 0.05
MIN_ABSOLUTE_PRECISION_GAIN = 0.01
SYNTHETIC_DATA_CAVEAT = (
    "Synthetic data supports workflow evaluation only; it does not support "
    "real ROI, customer, or production performance claims."
)
UTILITY_CAVEAT = (
    "Illustrative utility sensitivity uses synthetic data and assumption grids; "
    "it is not a real ROI estimate."
)

UTILITY_SCENARIOS: dict[str, tuple[dict[str, float | str], ...]] = {
    "churn_90d": (
        {
            "scenario": "conservative",
            "value_per_positive": 5000.0,
            "intervention_success_rate": 0.05,
            "cost_per_account": 150.0,
        },
        {
            "scenario": "base",
            "value_per_positive": 10000.0,
            "intervention_success_rate": 0.10,
            "cost_per_account": 150.0,
        },
        {
            "scenario": "optimistic",
            "value_per_positive": 15000.0,
            "intervention_success_rate": 0.15,
            "cost_per_account": 150.0,
        },
    ),
    "expansion_90d": (
        {
            "scenario": "conservative",
            "value_per_positive": 3000.0,
            "intervention_success_rate": 0.05,
            "cost_per_account": 100.0,
        },
        {
            "scenario": "base",
            "value_per_positive": 7500.0,
            "intervention_success_rate": 0.10,
            "cost_per_account": 100.0,
        },
        {
            "scenario": "optimistic",
            "value_per_positive": 12000.0,
            "intervention_success_rate": 0.15,
            "cost_per_account": 100.0,
        },
    ),
}


@dataclass(frozen=True)
class ChampionRecord:
    """One target-specific Package 6 champion manifest row."""

    target: str
    selected_champion_model_family: str
    mlflow_run_id: str | None
    model_artifact_uri: str | None
    selection_status: str
    primary_metric: str
    key_topk_metrics: dict[str, float | None]
    comparison_versus_baseline: dict[str, float | str | None]
    calibration_caveats: tuple[str, ...]
    segment_caveats: tuple[str, ...]
    temporal_caveats: tuple[str, ...]
    utility_caveats: tuple[str, ...]
    synthetic_data_caveat: str
    created_at_utc: str
    evaluation_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "selected_champion_model_family": self.selected_champion_model_family,
            "mlflow_run_id": self.mlflow_run_id,
            "model_artifact_uri": self.model_artifact_uri,
            "selection_status": self.selection_status,
            "primary_metric": self.primary_metric,
            "key_topk_metrics": self.key_topk_metrics,
            "comparison_versus_baseline": self.comparison_versus_baseline,
            "calibration_caveats": list(self.calibration_caveats),
            "segment_caveats": list(self.segment_caveats),
            "temporal_caveats": list(self.temporal_caveats),
            "utility_caveats": list(self.utility_caveats),
            "synthetic_data_caveat": self.synthetic_data_caveat,
            "created_at_utc": self.created_at_utc,
            "evaluation_version": self.evaluation_version,
        }


def compute_utility_sensitivity(
    score_frame: pd.DataFrame,
    *,
    top_k_percentage: float = CHAMPION_TOP_K_PERCENTAGE,
) -> tuple[tuple[MetricRecord, ...], tuple[CaveatRecord, ...]]:
    """Compute simple illustrative utility sensitivity at top 10%."""

    records: list[MetricRecord] = []
    caveats: list[CaveatRecord] = []
    for _, group in _score_groups(score_frame):
        target = str(group["target"].iloc[0])
        scenarios = UTILITY_SCENARIOS.get(target, ())
        if not scenarios:
            continue
        k_count = max(1, int(ceil(len(group) * top_k_percentage)))
        selected = select_top_k_rows(group, k_count=k_count)
        positives_captured = int(selected["label"].astype(int).sum())
        accounts_selected = int(len(selected))
        row_count = int(len(group))
        positive_count = int(group["label"].astype(int).sum())
        base_rate = positive_count / row_count if row_count else None
        for scenario in scenarios:
            gross_value = (
                positives_captured
                * float(scenario["value_per_positive"])
                * float(scenario["intervention_success_rate"])
            )
            intervention_cost = accounts_selected * float(scenario["cost_per_account"])
            net_utility = gross_value - intervention_cost
            records.append(
                _metric_record(
                    group,
                    metric_name="illustrative_net_utility",
                    metric_value=float(net_utility),
                    slice_type="utility_scenario",
                    slice_value=str(scenario["scenario"]),
                    row_count=row_count,
                    positive_count=positive_count,
                    base_positive_rate=base_rate,
                    k_value=float(top_k_percentage),
                    k_type="percent",
                )
            )
        caveats.append(
            _caveat(
                group,
                slice_type="utility_scenario",
                slice_value="all",
                caveat="illustrative_utility_not_real_roi",
            )
        )
    return tuple(records), tuple(caveats)


def select_champions(
    metric_records: Iterable[MetricRecord],
    caveats: Iterable[CaveatRecord] = (),
    *,
    created_at_utc: str,
    evaluation_version: str,
) -> tuple[ChampionRecord, ...]:
    """Select target-specific champions using top 10% operating metrics."""

    topk_metrics = _top10_metric_map(metric_records)
    targets = sorted({key[0] for key in topk_metrics})
    caveats_by_target = _caveats_by_target(caveats)
    champions: list[ChampionRecord] = []
    for target in targets:
        target_groups = {
            key: metrics for key, metrics in topk_metrics.items() if key[0] == target
        }
        baseline_key = next(
            (
                key
                for key in target_groups
                if key[2] == BASELINE_CANDIDATE_TYPE
            ),
            None,
        )
        ml_groups = {
            key: metrics for key, metrics in target_groups.items() if key[2] == ML_CANDIDATE_TYPE
        }
        if baseline_key is None or not ml_groups:
            champions.append(
                _champion_record(
                    target=target,
                    selected_key=None,
                    selected_metrics={},
                    baseline_metrics={},
                    best_ml_metrics={},
                    selection_status="insufficient_evidence",
                    caveats_by_target=caveats_by_target,
                    created_at_utc=created_at_utc,
                    evaluation_version=evaluation_version,
                )
            )
            continue

        baseline_metrics = target_groups[baseline_key]
        best_ml_key, best_ml_metrics = _best_ml_group(ml_groups)
        if _sufficiently_beats_baseline(best_ml_metrics, baseline_metrics):
            champions.append(
                _champion_record(
                    target=target,
                    selected_key=best_ml_key,
                    selected_metrics=best_ml_metrics,
                    baseline_metrics=baseline_metrics,
                    best_ml_metrics=best_ml_metrics,
                    selection_status="ml_champion_selected",
                    caveats_by_target=caveats_by_target,
                    created_at_utc=created_at_utc,
                    evaluation_version=evaluation_version,
                )
            )
        elif _metric_value(baseline_metrics, "precision_at_k") >= _metric_value(
            best_ml_metrics,
            "precision_at_k",
        ):
            champions.append(
                _champion_record(
                    target=target,
                    selected_key=baseline_key,
                    selected_metrics=baseline_metrics,
                    baseline_metrics=baseline_metrics,
                    best_ml_metrics=best_ml_metrics,
                    selection_status="baseline_retained",
                    caveats_by_target=caveats_by_target,
                    created_at_utc=created_at_utc,
                    evaluation_version=evaluation_version,
                )
            )
        else:
            champions.append(
                _champion_record(
                    target=target,
                    selected_key=None,
                    selected_metrics=best_ml_metrics,
                    baseline_metrics=baseline_metrics,
                    best_ml_metrics=best_ml_metrics,
                    selection_status="no_ml_candidate_sufficiently_beats_baseline",
                    caveats_by_target=caveats_by_target,
                    created_at_utc=created_at_utc,
                    evaluation_version=evaluation_version,
                )
            )
    return tuple(champions)


def _top10_metric_map(
    metric_records: Iterable[MetricRecord],
) -> dict[tuple[str, str, str, str | None, str | None], dict[str, float | None]]:
    topk_metrics: dict[
        tuple[str, str, str, str | None, str | None],
        dict[str, float | None],
    ] = {}
    for record in metric_records:
        if (
            record.slice_type != OVERALL_SLICE_TYPE
            or record.slice_value != FIXED_HOLDOUT_SLICE_VALUE
            or record.k_type != "percent"
            or record.k_value is None
            or abs(float(record.k_value) - CHAMPION_TOP_K_PERCENTAGE) > 1e-9
        ):
            continue
        key = (
            record.target,
            record.model_family,
            record.candidate_type,
            record.mlflow_run_id,
            record.model_artifact_uri,
        )
        topk_metrics.setdefault(key, {})[record.metric_name] = record.metric_value
    return topk_metrics


def _best_ml_group(
    ml_groups: dict[
        tuple[str, str, str, str | None, str | None],
        dict[str, float | None],
    ],
) -> tuple[tuple[str, str, str, str | None, str | None], dict[str, float | None]]:
    return max(
        ml_groups.items(),
        key=lambda item: (
            _metric_value(item[1], "precision_at_k"),
            _metric_value(item[1], "lift_at_k"),
            _metric_value(item[1], "capture_rate_at_k"),
            item[0][1],
        ),
    )


def _sufficiently_beats_baseline(
    ml_metrics: dict[str, float | None],
    baseline_metrics: dict[str, float | None],
) -> bool:
    ml_precision = _metric_value(ml_metrics, "precision_at_k")
    baseline_precision = _metric_value(baseline_metrics, "precision_at_k")
    precision_gain = ml_precision - baseline_precision
    required_gain = max(
        MIN_ABSOLUTE_PRECISION_GAIN,
        baseline_precision * MIN_RELATIVE_PRECISION_GAIN,
    )
    return (
        precision_gain >= required_gain
        and _metric_value(ml_metrics, "lift_at_k")
        > _metric_value(baseline_metrics, "lift_at_k")
        and _metric_value(ml_metrics, "capture_rate_at_k")
        >= _metric_value(baseline_metrics, "capture_rate_at_k")
    )


def _champion_record(
    *,
    target: str,
    selected_key: tuple[str, str, str, str | None, str | None] | None,
    selected_metrics: dict[str, float | None],
    baseline_metrics: dict[str, float | None],
    best_ml_metrics: dict[str, float | None],
    selection_status: str,
    caveats_by_target: dict[str, dict[str, tuple[str, ...]]],
    created_at_utc: str,
    evaluation_version: str,
) -> ChampionRecord:
    if selected_key is None:
        model_family = "not_applicable"
        mlflow_run_id = None
        model_artifact_uri = None
    else:
        _, model_family, candidate_type, mlflow_run_id, model_artifact_uri = selected_key
        if candidate_type == BASELINE_CANDIDATE_TYPE:
            mlflow_run_id = None
            model_artifact_uri = None
    target_caveats = caveats_by_target.get(target, {})
    calibration_caveats = target_caveats.get("calibration", ())
    if selection_status in {
        "baseline_retained",
        "no_ml_candidate_sufficiently_beats_baseline",
    }:
        calibration_caveats = (
            *calibration_caveats,
            "baseline_scores_are_ranking_scores_not_calibrated_probabilities",
        )

    return ChampionRecord(
        target=target,
        selected_champion_model_family=model_family,
        mlflow_run_id=mlflow_run_id,
        model_artifact_uri=model_artifact_uri,
        selection_status=selection_status,
        primary_metric=PRIMARY_CHAMPION_METRIC,
        key_topk_metrics=_key_topk_metrics(selected_metrics),
        comparison_versus_baseline=_comparison(best_ml_metrics, baseline_metrics),
        calibration_caveats=tuple(sorted(set(calibration_caveats))),
        segment_caveats=target_caveats.get("segment", ()),
        temporal_caveats=target_caveats.get("temporal", ()),
        utility_caveats=tuple(sorted(set((*target_caveats.get("utility", ()), UTILITY_CAVEAT)))),
        synthetic_data_caveat=SYNTHETIC_DATA_CAVEAT,
        created_at_utc=created_at_utc,
        evaluation_version=evaluation_version,
    )


def _key_topk_metrics(metrics: dict[str, float | None]) -> dict[str, float | None]:
    return {
        "accounts_selected": metrics.get("accounts_selected"),
        "positives_captured": metrics.get("positives_captured"),
        "precision_at_k": metrics.get("precision_at_k"),
        "recall_at_k": metrics.get("recall_at_k"),
        "lift_at_k": metrics.get("lift_at_k"),
        "capture_rate_at_k": metrics.get("capture_rate_at_k"),
        "base_positive_rate": metrics.get("base_positive_rate"),
    }


def _comparison(
    best_ml_metrics: dict[str, float | None],
    baseline_metrics: dict[str, float | None],
) -> dict[str, float | str | None]:
    comparison = {
        "best_ml_precision_at_k": best_ml_metrics.get("precision_at_k"),
        "baseline_precision_at_k": baseline_metrics.get("precision_at_k"),
        "precision_delta": _delta(best_ml_metrics, baseline_metrics, "precision_at_k"),
        "best_ml_lift_at_k": best_ml_metrics.get("lift_at_k"),
        "baseline_lift_at_k": baseline_metrics.get("lift_at_k"),
        "lift_delta": _delta(best_ml_metrics, baseline_metrics, "lift_at_k"),
        "best_ml_capture_rate_at_k": best_ml_metrics.get("capture_rate_at_k"),
        "baseline_capture_rate_at_k": baseline_metrics.get("capture_rate_at_k"),
        "capture_rate_delta": _delta(
            best_ml_metrics,
            baseline_metrics,
            "capture_rate_at_k",
        ),
    }
    return comparison


def _delta(
    first: dict[str, float | None],
    second: dict[str, float | None],
    metric_name: str,
) -> float | None:
    first_value = first.get(metric_name)
    second_value = second.get(metric_name)
    if first_value is None or second_value is None:
        return None
    return float(first_value - second_value)


def _metric_value(metrics: dict[str, float | None], metric_name: str) -> float:
    value = metrics.get(metric_name)
    if value is None:
        return float("-inf")
    return float(value)


def _caveats_by_target(
    caveats: Iterable[CaveatRecord],
) -> dict[str, dict[str, tuple[str, ...]]]:
    values: dict[str, dict[str, set[str]]] = {}
    for caveat in caveats:
        category = _caveat_category(caveat.slice_type)
        values.setdefault(caveat.target, {}).setdefault(category, set()).add(
            f"{caveat.slice_value}: {caveat.caveat}"
        )
    return {
        target: {
            category: tuple(sorted(category_values))
            for category, category_values in categories.items()
        }
        for target, categories in values.items()
    }


def _caveat_category(slice_type: str) -> str:
    if slice_type == "calibration_bin":
        return "calibration"
    if slice_type == "segment":
        return "segment"
    if slice_type == "holdout_month":
        return "temporal"
    if slice_type == "utility_scenario":
        return "utility"
    return "other"


def _score_groups(score_frame: pd.DataFrame):
    group_columns = [
        "target",
        "model_family",
        "candidate_type",
        "mlflow_run_id",
        "model_artifact_uri",
        "score_source",
    ]
    return score_frame.groupby(group_columns, dropna=False, sort=False)


def _metric_record(
    group: pd.DataFrame,
    *,
    metric_name: str,
    metric_value: float,
    slice_type: str,
    slice_value: str,
    row_count: int,
    positive_count: int,
    base_positive_rate: float | None,
    k_value: float | int | None = None,
    k_type: str | None = None,
) -> MetricRecord:
    return MetricRecord(
        target=str(group["target"].iloc[0]),
        model_family=str(group["model_family"].iloc[0]),
        candidate_type=str(group["candidate_type"].iloc[0]),
        mlflow_run_id=_optional_value(group["mlflow_run_id"].iloc[0]),
        model_artifact_uri=_optional_value(group["model_artifact_uri"].iloc[0]),
        score_source=str(group["score_source"].iloc[0]),
        metric_name=metric_name,
        metric_value=metric_value,
        slice_type=slice_type,
        slice_value=slice_value,
        row_count=row_count,
        positive_count=positive_count,
        base_positive_rate=base_positive_rate,
        k_value=k_value,
        k_type=k_type,
    )


def _caveat(
    group: pd.DataFrame,
    *,
    slice_type: str,
    slice_value: str,
    caveat: str,
) -> CaveatRecord:
    return CaveatRecord(
        target=str(group["target"].iloc[0]),
        model_family=str(group["model_family"].iloc[0]),
        candidate_type=str(group["candidate_type"].iloc[0]),
        slice_type=slice_type,
        slice_value=slice_value,
        caveat=caveat,
    )


def _optional_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    return str(value)
