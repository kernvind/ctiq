from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer

from src.app.core.config import get_settings
from src.app.core.set_logger import configure_logging
from src.app.infra.embed.embedder import Embedder
from src.app.infra.postgres.client import PostgresClient, create_pool
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

    pool = await create_pool(settings.asyncpg_database_url)
    app.state.pg_client = PostgresClient(pool)
    app.state.query_planner = RuleBasedQueryPlanner()

    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    await pool.close()

    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)

from src.app.modules.trial_search.router import router as search_router
app.include_router(search_router)


@app.get("/")
def read_root():
    return {"status": "ok"}
