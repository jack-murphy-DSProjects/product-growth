PYTHON ?= python3
WAREHOUSE_PATH ?= data/warehouse/account_health.duckdb
TRAIN_END_MONTH ?=
MLFLOW_TRACKING_URI ?=
MLFLOW_REGISTRY_URI ?=
EXPERIMENT_NAME ?= account-health-candidate-training
RANDOM_STATE ?= 42
EVALUATION_OUTPUT_DIR ?= data/outputs/model_evaluation
CHAMPION_MANIFEST_PATH ?= data/outputs/model_evaluation/champion_selection_manifest.json
PROMOTION_MANIFEST_PATH ?= data/outputs/model_registry/promotion_manifest.json
PROMOTION_TARGETS ?=
SCORING_MONTH ?=
BATCH_SCORING_LATEST ?=
BATCH_SCORING_EXPORT_DIR ?=
SCORE_OBSERVABILITY_EXPORT_DIR ?=
GTM_POLICY_EXPORT_DIR ?=

.PHONY: setup test public-safety-check generate-synthetic-data load-warehouse build-account-month build-rule-baselines train-candidate-models evaluate-candidate-models promote-model-registry score-account-month monitor-account-scores monitor-account-scores-latest build-gtm-policy build-gtm-policy-latest clean-generated verify

setup:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

public-safety-check:
	$(PYTHON) scripts/check_public_repo_safety.py

generate-synthetic-data:
	$(PYTHON) scripts/generate_synthetic_data.py

load-warehouse:
	$(PYTHON) scripts/load_warehouse.py

build-account-month:
	$(PYTHON) scripts/build_account_month.py --database-path "$(WAREHOUSE_PATH)"

build-rule-baselines:
	$(PYTHON) scripts/build_rule_baselines.py --database-path "$(WAREHOUSE_PATH)"

train-candidate-models:
	$(PYTHON) scripts/train_candidate_models.py --warehouse-path "$(WAREHOUSE_PATH)" --experiment-name "$(EXPERIMENT_NAME)" --random-state "$(RANDOM_STATE)" $(if $(TRAIN_END_MONTH),--train-end-month "$(TRAIN_END_MONTH)",) $(if $(MLFLOW_TRACKING_URI),--mlflow-tracking-uri "$(MLFLOW_TRACKING_URI)",)

evaluate-candidate-models:
	$(PYTHON) scripts/evaluate_candidate_models.py --warehouse-path "$(WAREHOUSE_PATH)" --experiment-name "$(EXPERIMENT_NAME)" --output-dir "$(EVALUATION_OUTPUT_DIR)" $(if $(TRAIN_END_MONTH),--train-end-month "$(TRAIN_END_MONTH)",) $(if $(MLFLOW_TRACKING_URI),--mlflow-tracking-uri "$(MLFLOW_TRACKING_URI)",)

promote-model-registry:
	$(PYTHON) scripts/promote_model_registry.py --warehouse-path "$(WAREHOUSE_PATH)" --champion-manifest-path "$(CHAMPION_MANIFEST_PATH)" --promotion-manifest-path "$(PROMOTION_MANIFEST_PATH)" $(if $(MLFLOW_TRACKING_URI),--mlflow-tracking-uri "$(MLFLOW_TRACKING_URI)",) $(if $(MLFLOW_REGISTRY_URI),--mlflow-registry-uri "$(MLFLOW_REGISTRY_URI)",) $(foreach target,$(PROMOTION_TARGETS),--target "$(target)")

score-account-month:
	$(PYTHON) scripts/score_account_month.py --warehouse-path "$(WAREHOUSE_PATH)" --promotion-manifest-path "$(PROMOTION_MANIFEST_PATH)" $(if $(SCORING_MONTH),--scoring-month "$(SCORING_MONTH)",) $(if $(BATCH_SCORING_LATEST),--latest,) $(if $(MLFLOW_TRACKING_URI),--mlflow-tracking-uri "$(MLFLOW_TRACKING_URI)",) $(if $(MLFLOW_REGISTRY_URI),--mlflow-registry-uri "$(MLFLOW_REGISTRY_URI)",) $(if $(BATCH_SCORING_EXPORT_DIR),--export-dir "$(BATCH_SCORING_EXPORT_DIR)",)

monitor-account-scores:
	$(PYTHON) scripts/monitor_account_scores.py --warehouse-path "$(WAREHOUSE_PATH)" $(if $(SCORING_MONTH),--scoring-month "$(SCORING_MONTH)",) $(if $(SCORE_OBSERVABILITY_EXPORT_DIR),--export-dir "$(SCORE_OBSERVABILITY_EXPORT_DIR)",)

monitor-account-scores-latest:
	$(PYTHON) scripts/monitor_account_scores.py --warehouse-path "$(WAREHOUSE_PATH)" $(if $(SCORING_MONTH),--scoring-month "$(SCORING_MONTH)",) --latest $(if $(SCORE_OBSERVABILITY_EXPORT_DIR),--export-dir "$(SCORE_OBSERVABILITY_EXPORT_DIR)",)

build-gtm-policy:
	$(PYTHON) scripts/build_gtm_policy.py --warehouse-path "$(WAREHOUSE_PATH)" $(if $(SCORING_MONTH),--scoring-month "$(SCORING_MONTH)",) $(if $(GTM_POLICY_EXPORT_DIR),--export-dir "$(GTM_POLICY_EXPORT_DIR)",)

build-gtm-policy-latest:
	$(PYTHON) scripts/build_gtm_policy.py --warehouse-path "$(WAREHOUSE_PATH)" $(if $(SCORING_MONTH),--scoring-month "$(SCORING_MONTH)",) --latest $(if $(GTM_POLICY_EXPORT_DIR),--export-dir "$(GTM_POLICY_EXPORT_DIR)",)

clean-generated:
	rm -rf data/generated

verify: public-safety-check test
