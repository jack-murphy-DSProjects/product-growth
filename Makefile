PYTHON ?= python3
WAREHOUSE_PATH ?= data/warehouse/account_health.duckdb

.PHONY: setup test public-safety-check generate-synthetic-data load-warehouse build-account-month build-rule-baselines clean-generated verify

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

clean-generated:
	rm -rf data/generated

verify: public-safety-check test
