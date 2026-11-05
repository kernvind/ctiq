from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sentence_transformers import SentenceTransformer

from src.app.api.security import verify_internal_token

from src.app.core.config import get_settings
from src.app.core.set_logger import configure_logging
from src.app.infra.embed.embedder import Embedder
from src.app.infra.postgres.session import create_engine, create_session_factory
from src.app.infra.observability.middleware import ObservabilityMiddleware
from src.app.modules.trial_search.planning.planner_factory import build_query_planner

settings = get_settings()
configure_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    device = (
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    model = SentenceTransformer(
        settings.embedding_model_name,
        trust_remote_code=True,
        device=device,
    )
    app.state.embedder = Embedder(model)
    # Warm the model: the FIRST encode lazily initializes the forward pass (1-3s on
    # CPU/MPS, more with nomic's trust_remote_code). Pay that cost here at startup so the
    # first real search/match request isn't the one that eats it.
    app.state.embedder.embed_query("warmup")

    engine = create_engine(settings.pg_database_url)
    app.state.db_engine = engine
    app.state.db_sessionmaker = create_session_factory(engine)
    app.state.query_planner = build_query_planner(settings)

    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    await engine.dispose()

    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)
app.add_middleware(ObservabilityMiddleware)

from src.app.modules.trial_search.router import router as search_router
from src.app.modules.eligibility_match.router import router as match_router
# All API routes require the internal token; `/` (health) stays open for probes.
app.include_router(search_router, dependencies=[Depends(verify_internal_token)])
app.include_router(match_router, dependencies=[Depends(verify_internal_token)])


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint. Unauthenticated by design: it carries no user data, and in
    docker-compose this service publishes no host port, so only containers on the internal
    network (Prometheus) can reach it. Do not expose it through the public reverse proxy."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
