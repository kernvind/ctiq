# Build context: repo root (ctiq/)
# docker build -f pipelines/ctiq_etl/Dockerfile -t ctiq-etl .

ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=2.3.4

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 – deps: install PyPI packages from the lockfile
#
# ctiq-db is a local path dep that poetry export omits automatically.
# This layer only busts when pyproject.toml or poetry.lock changes.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS deps

ARG POETRY_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app/pipelines/ctiq_etl

COPY pipelines/ctiq_etl/pyproject.toml \
     pipelines/ctiq_etl/poetry.lock    ./

RUN poetry export -f requirements.txt --without-hashes --without dev -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 – model: bake the ~274 MB embedding model weights
#
# Same model as inference-service (nomic-ai/nomic-embed-text-v1.5).
# Kept as a separate stage so this layer is cached independently —
# only re-runs when PyPI deps change, not when ctiq-db or app source changes.
# ─────────────────────────────────────────────────────────────────────────────
FROM deps AS model

ENV HF_HOME=/app/pipelines/ctiq_etl/.hf-cache

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 – runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG PYTHON_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/pipelines/ctiq_etl:/app/py-packages/ctiq-db/src" \
    HF_HOME="/app/pipelines/ctiq_etl/.hf-cache"

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

WORKDIR /app

# PyPI packages installed in the deps stage
COPY --from=model /usr/local/lib/python${PYTHON_VERSION}/site-packages \
                  /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=model /usr/local/bin /usr/local/bin

# Model weights
COPY --from=model /app/pipelines/ctiq_etl/.hf-cache \
                  /app/pipelines/ctiq_etl/.hf-cache

# ctiq-db source: placed here (downstream of model) so changes don't
# invalidate the model-bake cache.
COPY py-packages/ctiq-db/src /app/py-packages/ctiq-db/src

# Application source
COPY pipelines/ctiq_etl/src /app/pipelines/ctiq_etl/src

RUN chown -R app:app /app
USER app

# ETL runs as a one-shot GKE Job/CronJob — no HEALTHCHECK needed.
# GKE tracks completion via the Job resource, not a probe.
# Pass args at `docker run` or in the GKE Job spec for full-load
# or date-window runs (see pipelines/Makefile for all invocation patterns).
CMD ["python", "-m", "src.flows.clinical_trials_flow"]
