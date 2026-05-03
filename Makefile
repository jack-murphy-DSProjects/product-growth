PYTHON ?= python3

.PHONY: setup test public-safety-check generate-synthetic-data clean-generated verify

setup:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

public-safety-check:
	$(PYTHON) scripts/check_public_repo_safety.py

generate-synthetic-data:
	$(PYTHON) scripts/generate_synthetic_data.py

clean-generated:
	rm -rf data/generated

verify: public-safety-check test
