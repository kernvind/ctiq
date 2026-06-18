from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI
from sentence_transformers import SentenceTransformer

from src.app.api.security import verify_internal_token

from src.app.core.config import get_settings
from src.app.core.set_logger import configure_logging
from src.app.infra.embed.embedder import Embedder
from src.app.infra.postgres.session import create_engine, create_session_factory
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner

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

    engine = create_engine(settings.pg_database_url)
    app.state.db_engine = engine
    app.state.db_sessionmaker = create_session_factory(engine)
    app.state.query_planner = RuleBasedQueryPlanner()

    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    await engine.dispose()

    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)

from src.app.modules.trial_search.router import router as search_router
# All search routes require the internal token; `/` (health) stays open for probes.
app.include_router(search_router, dependencies=[Depends(verify_internal_token)])


@app.get("/")
def read_root():
    return {"status": "ok"}
