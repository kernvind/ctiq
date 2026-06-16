# Build context: repo root (ctiq/)
# docker build -f ai-service/inference-service/Dockerfile -t ctiq-inference .

ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=2.1.3

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 – deps: install PyPI packages from the lockfile
#
# ctiq-db is a local path dep that poetry export omits automatically.
# This layer only busts when pyproject.toml or poetry.lock changes —
# not when ctiq-db source or application source changes.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS deps

ARG POETRY_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app/ai-service/inference-service

COPY ai-service/inference-service/pyproject.toml \
     ai-service/inference-service/poetry.lock    ./

RUN poetry export -f requirements.txt --without-hashes --without dev -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 – model: bake the ~274 MB embedding model weights
#
# Kept as a separate stage so this expensive layer is cached independently.
# Now it only re-runs when PyPI deps change, not when ctiq-db or app source
# changes (both of which are introduced in the runtime stage below).
# ─────────────────────────────────────────────────────────────────────────────
FROM deps AS model

ENV HF_HOME=/app/ai-service/inference-service/.hf-cache

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 – runtime: slim production image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG PYTHON_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # src.app.main importable from the uvicorn command
    # ctiq_db importable via src/ layout (packages = [{include = "ctiq_db", from = "src"}])
    PYTHONPATH="/app/ai-service/inference-service:/app/py-packages/ctiq-db/src" \
    HF_HOME="/app/ai-service/inference-service/.hf-cache"

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

WORKDIR /app

# PyPI packages installed in the deps stage
COPY --from=model /usr/local/lib/python${PYTHON_VERSION}/site-packages \
                  /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=model /usr/local/bin /usr/local/bin

# Model weights
COPY --from=model /app/ai-service/inference-service/.hf-cache \
                  /app/ai-service/inference-service/.hf-cache

# ctiq-db source: placed here (downstream of the model stage) so changes to
# shared models don't invalidate the model-bake cache.
COPY py-packages/ctiq-db/src /app/py-packages/ctiq-db/src

# Application source
COPY ai-service/inference-service/src /app/ai-service/inference-service/src

RUN chown -R app:app /app
USER app

EXPOSE 8000

# /  returns {"status":"ok"} — lightweight liveness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"

# Single worker: horizontal scale via K8s replicas, not OS processes.
# Each replica owns its own asyncpg connection pool.
CMD ["uvicorn", "src.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers"]
