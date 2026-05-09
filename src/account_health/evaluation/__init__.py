"""Layered Package 6 model evaluation and champion selection."""

from account_health.evaluation.loading import (
    BASELINE_SCORE_COLUMNS,
    EVALUATION_VERSION,
    SEGMENT_FIELDS,
    EvaluationInputError,
    EvaluationInputs,
    LoadedCandidate,
    load_evaluation_inputs,
    validate_local_mlflow_tracking_uri,
)
from account_health.evaluation.metrics import (
    DEFAULT_TOP_K_COUNTS,
    DEFAULT_TOP_K_PERCENTAGES,
    EvaluationMetricError,
    MetricRecord,
    evaluate_overall_metrics,
    score_fixed_holdout,
    select_top_k_rows,
)
from account_health.evaluation.robustness import (
    DEFAULT_CALIBRATION_BIN_COUNT,
    DEFAULT_MIN_ROBUSTNESS_SUPPORT,
    CaveatRecord,
    compute_calibration_metrics,
    compute_holdout_month_robustness,
    compute_segment_robustness,
)
from account_health.evaluation.selection import (
    ChampionRecord,
    compute_utility_sensitivity,
    select_champions,
)
from account_health.evaluation.orchestration import (
    DEFAULT_EVALUATION_OUTPUT_DIR,
    ModelEvaluationResult,
    run_model_evaluation,
)

__all__ = [
    "BASELINE_SCORE_COLUMNS",
    "CaveatRecord",
    "ChampionRecord",
    "DEFAULT_CALIBRATION_BIN_COUNT",
    "DEFAULT_EVALUATION_OUTPUT_DIR",
    "DEFAULT_MIN_ROBUSTNESS_SUPPORT",
    "DEFAULT_TOP_K_COUNTS",
    "DEFAULT_TOP_K_PERCENTAGES",
    "EVALUATION_VERSION",
    "SEGMENT_FIELDS",
    "EvaluationInputError",
    "EvaluationMetricError",
    "EvaluationInputs",
    "LoadedCandidate",
    "MetricRecord",
    "ModelEvaluationResult",
    "compute_calibration_metrics",
    "compute_holdout_month_robustness",
    "compute_segment_robustness",
    "compute_utility_sensitivity",
    "evaluate_overall_metrics",
    "load_evaluation_inputs",
    "run_model_evaluation",
    "score_fixed_holdout",
    "select_champions",
    "select_top_k_rows",
    "validate_local_mlflow_tracking_uri",
]
