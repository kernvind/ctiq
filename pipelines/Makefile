# ── Python / ETL pipeline ──────────────────────────────────────────────────────
PIPELINES_ETL_DIR := ctiq_etl
POETRY           := poetry

# ctiq-db (the trials ORM) is a local path dep imported at runtime via PYTHONPATH, not
# pip-installed (it's the optional `local` poetry group). Mirror the Docker image's
# PYTHONPATH locally so `python -m src.flows...` can import ctiq_db. Paths are relative to
# $(PIPELINES_ETL_DIR), which the run recipes `cd` into.
RUN_ENV := PYTHONPATH=.:../../py-packages/ctiq-db/src

FROM                ?=
TO                  ?= $(FROM)
# NB: $(if VAR) tests non-EMPTY, not truthiness — so plain $(if) would treat VAR=0 as on.
# filter-out makes 0/false/no (and empty) mean OFF; any other value means ON.
SKIP_EXISTING_CHECK ?=
_SKIP_EXISTING_FLAG  = $(if $(filter-out 0 false no,$(SKIP_EXISTING_CHECK)),--skip-existing-check,)
SKIP_ELIGIBILITY    ?=
_SKIP_ELIGIBILITY_FLAG = $(if $(filter-out 0 false no,$(SKIP_ELIGIBILITY)),--skip-eligibility,)
# inline (concurrent) or batch (OpenAI Batch API). Empty = use the flow default.
ELIGIBILITY_MODE    ?=
_ELIGIBILITY_MODE_FLAG = $(if $(ELIGIBILITY_MODE),--eligibility-mode $(ELIGIBILITY_MODE),)

.PHONY: ctiq-etl-install ctiq-etl-run ctiq-etl-full-load ctiq-etl-skip-embeddings ctiq-etl-test-run ctiq-etl-test-run-skip-embeddings ctiq-etl-eligibility-poll ctiq-etl-deploy ctiq-etl-lint

## Install dependencies via Poetry (creates/updates the managed venv).
ctiq-etl-install:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) install

## Incremental load — appends studies updated since the last BQ watermark.
ctiq-etl-run:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.clinical_trials_flow $(_SKIP_ELIGIBILITY_FLAG) $(_ELIGIBILITY_MODE_FLAG)

## Full load — truncates both staging tables and reloads everything from 2000-01-01.
ctiq-etl-full-load:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.clinical_trials_flow --full-load $(_SKIP_ELIGIBILITY_FLAG) $(_ELIGIBILITY_MODE_FLAG)

## Incremental load, skipping embedding generation.
ctiq-etl-skip-embeddings:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.clinical_trials_flow --skip-embeddings $(_SKIP_ELIGIBILITY_FLAG) $(_ELIGIBILITY_MODE_FLAG)

## Test run for a specific date window. Usage: make ctiq-etl-test-run FROM=2024-01-15 [TO=2024-01-15] [SKIP_EXISTING_CHECK=1] [SKIP_ELIGIBILITY=1] [ELIGIBILITY_MODE=inline|batch]
ctiq-etl-test-run:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.clinical_trials_flow \
		--from-date $(FROM) --to-date $(TO) $(_SKIP_EXISTING_FLAG) $(_SKIP_ELIGIBILITY_FLAG) $(_ELIGIBILITY_MODE_FLAG)

## Test run for a specific date window, skipping embeddings. Usage: make ctiq-etl-test-run FROM=2024-01-15 [TO=2024-01-15]
ctiq-etl-test-run-skip-embeddings:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.clinical_trials_flow \
		--from-date $(FROM) --to-date $(TO) --skip-embeddings

## Poll & ingest async eligibility batch jobs (the companion to ELIGIBILITY_MODE=batch,
## which only submits). Idempotent — run repeatedly (e.g. cron) until all jobs are ingested.
ctiq-etl-eligibility-poll:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m src.flows.eligibility_poll

## Deploy the Prefect flow (daily at 02:00 UTC).
ctiq-etl-deploy:
	cd $(PIPELINES_ETL_DIR) && $(RUN_ENV) $(POETRY) run python -m prefect deploy \
		src/flows/clinical_trials_flow.py:clinical_trials_etl_flow \
		--name clinical-trials-daily \
		--cron "0 2 * * *"

## Run ruff linter over the pipeline source.
ctiq-etl-lint:
	cd $(PIPELINES_ETL_DIR) && $(POETRY) run ruff check .
