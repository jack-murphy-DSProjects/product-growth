PYTHON ?= python3
WAREHOUSE_PATH ?= data/warehouse/account_health.duckdb
TRAIN_END_MONTH ?=
MLFLOW_TRACKING_URI ?=
EXPERIMENT_NAME ?= account-health-candidate-training
RANDOM_STATE ?= 42
EVALUATION_OUTPUT_DIR ?= data/outputs/model_evaluation

.PHONY: setup test public-safety-check generate-synthetic-data load-warehouse build-account-month build-rule-baselines train-candidate-models evaluate-candidate-models clean-generated verify

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

clean-generated:
	rm -rf data/generated

verify: public-safety-check test
