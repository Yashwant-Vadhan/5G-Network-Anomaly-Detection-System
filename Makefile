# 5G-NADS developer entry points (todo.md T1-011).
# `make help` lists every target.

PYTHON ?= python
RAW_DIR := data/raw
PROCESSED_DIR := data/processed
SAMPLE_DIR := data/sample

# TODO(T7): set to 80 once the Phase 7 unit/integration tests exist. pyproject.toml
# already records 80 as the target via [tool.coverage.report] fail_under.
COV_FAIL_UNDER ?= 0
# pytest exit code 5 means "no tests collected". todo.md T1-004 allows a
# zero-test bootstrap, so it is reported without failing `make test`.
PYTEST_NO_TESTS := 5

.DEFAULT_GOAL := help
.PHONY: help setup lint format test preprocess pipeline dashboard clean-processed

help:
	@echo "5G-NADS targets:"
	@echo "  setup             install pinned dev requirements and the pre-commit hooks"
	@echo "  lint              ruff check ."
	@echo "  format            ruff format ."
	@echo "  test              pytest with coverage over ml/ and agents/"
	@echo "  preprocess        python -m ml.preprocessing --input $(RAW_DIR) --output $(PROCESSED_DIR)"
	@echo "  pipeline          python -m pipelines.run_pipeline --input $(RAW_DIR) --output $(PROCESSED_DIR)"
	@echo "  dashboard         streamlit run dashboard/app.py on 127.0.0.1"
	@echo "  clean-processed   delete generated files in $(PROCESSED_DIR)/ only"

setup:
	@echo "Installing pinned dev requirements (Python 3.12+)"
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt
	@echo "Installing pre-commit hooks"
	$(PYTHON) -m pre_commit install

lint:
	@echo "ruff check ."
	$(PYTHON) -m ruff check .

format:
	@echo "ruff format ."
	$(PYTHON) -m ruff format .

test:
	@echo "pytest --cov=ml --cov=agents (coverage gate $(COV_FAIL_UNDER); target 80)"
	@$(PYTHON) -m pytest --cov=ml --cov=agents --cov-report=term-missing --cov-fail-under=$(COV_FAIL_UNDER); \
	  status=$$?; \
	  if [ $$status -eq $(PYTEST_NO_TESTS) ]; then \
	    echo "No tests collected yet (bootstrap; Phase 7 tests are pending)"; \
	  elif [ $$status -ne 0 ]; then \
	    exit $$status; \
	  fi

preprocess:
	@echo "python -m ml.preprocessing --input $(RAW_DIR) --output $(PROCESSED_DIR)"
	$(PYTHON) -m ml.preprocessing --input $(RAW_DIR) --output $(PROCESSED_DIR)

pipeline:
	@echo "python -m pipelines.run_pipeline --input $(RAW_DIR) --output $(PROCESSED_DIR)"
	$(PYTHON) -m pipelines.run_pipeline --input $(RAW_DIR) --output $(PROCESSED_DIR)

dashboard:
	@echo "streamlit run dashboard/app.py --server.address 127.0.0.1"
	$(PYTHON) -m streamlit run dashboard/app.py --server.address 127.0.0.1

# Guardrail G7: raw data is immutable. This recipe touches $(PROCESSED_DIR) and
# nothing else; the guard below aborts if that path is empty or resolves inside
# the raw tree.
clean-processed:
	@case "$(PROCESSED_DIR)" in ""|$(RAW_DIR)|$(RAW_DIR)/*) echo "refusing to clean '$(PROCESSED_DIR)': never delete raw data"; exit 1;; esac
	@echo "Deleting generated CSV/JSON under $(PROCESSED_DIR)/ (raw data is untouched)"
	rm -f $(PROCESSED_DIR)/*.csv $(PROCESSED_DIR)/*.json
