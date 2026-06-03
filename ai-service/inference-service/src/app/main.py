from contextlib import asynccontextmanager
from fastapi import FastAPI
from google.cloud import bigquery
from sentence_transformers import SentenceTransformer
from src.app.core.set_logger import configure_logging
import torch
from src.app.core.config import get_settings
from src.app.infra.embed.embedder import Embedder
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.infra.bigquery.client import BigQueryClient

settings = get_settings()
configure_logging(settings)  # Must be called at the module level to set up logging for all tasks and flows

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ==========================================
    # 1. STARTUP CODE (Runs before server boots)
    # ==========================================

    # --- PyTorch & Sentence Transformer Setup ---
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(
        settings.embedding_model_name,
        trust_remote_code=True,
        device=device,
    )

    app.state.embedder = Embedder(model)
    # --- BigQuery Client Setup ---
    # This automatically picks up credentials via GOOGLE_APPLICATION_CREDENTIALS env var
    bigquery_google_client = bigquery.Client()
    app.state.bigquery_google_client = bigquery_google_client
    app.state.bq_client = BigQueryClient(bigquery_google_client)
    app.state.query_planner = RuleBasedQueryPlanner()
    print("🚀 Startup complete: Embedder and BigQuery initialized.")

    yield  # ----------------------------------------------------
    # Server is running and handling incoming requests right here
    # ----------------------------------------------------

    # ==========================================
    # 2. SHUTDOWN CODE (Runs when server stops)
    # ==========================================
    print("🛑 Shutting down: Closing connections.")

    # Explicitly close the BigQuery HTTP session to prevent connection leaks
    app.state.bigquery_google_client.close()

    if device == "mps":
        torch.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()


# Pass the lifespan context manager directly into your FastAPI initialization
app = FastAPI(lifespan=lifespan)
# Routes use the type alias — no manual Depends() at the call site
from src.app.modules.trial_search.router import router as search_router
app.include_router(search_router)
@app.get("/")
def read_root():
    return {"status": "FastAPI is running with Poetry Script!"}
