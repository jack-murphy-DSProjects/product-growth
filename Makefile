PYTHON ?= python3

.PHONY: setup test public-safety-check verify

setup:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

public-safety-check:
	$(PYTHON) scripts/check_public_repo_safety.py

verify: public-safety-check test
