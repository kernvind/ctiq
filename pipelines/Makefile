# ── Python / ETL pipeline ──────────────────────────────────────────────────────
PIPELINES_ETL_DIR := ctiq_etl
POETRY           := poetry

FROM ?=
TO   ?= $(FROM)

.PHONY: ctiq-etl-install ctiq-etl-run ctiq-etl-full-load ctiq-etl-skip-embeddings ctiq-etl-test-run ctiq-etl-deploy ctiq-etl-lint

## Install dependencies via Poetry (creates/updates the managed venv).
ctiq-etl-install:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) install

## Incremental load — appends studies updated since the last BQ watermark.
ctiq-etl-run:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run python -m src.flows.clinical_trials_flow

## Full load — truncates both staging tables and reloads everything from 2000-01-01.
ctiq-etl-full-load:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run python -m src.flows.clinical_trials_flow --full-load

## Incremental load, skipping embedding generation.
ctiq-etl-skip-embeddings:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run python -m src.flows.clinical_trials_flow --skip-embeddings

## Test run for a specific date window, skipping embeddings. Usage: make ctiq-etl-test-run FROM=2024-01-15 [TO=2024-01-15]
ctiq-etl-test-run:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run python -m src.flows.clinical_trials_flow \
		--from-date $(FROM) --to-date $(TO) --skip-embeddings

## Deploy the Prefect flow (daily at 02:00 UTC).
ctiq-etl-deploy:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run python -m prefect deploy \
		src/flows/clinical_trials_flow.py:clinical_trials_etl_flow \
		--name clinical-trials-daily \
		--cron "0 2 * * *"

## Run ruff linter over the pipeline source.
ctiq-etl-lint:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run ruff check .
