"""SQLAlchemy async engine + session factory for the trials database.

Replaces the hand-rolled asyncpg pool (old client.py). The SQLAlchemy asyncpg dialect
plus pgvector.sqlalchemy handle vector binding and JSON(B) codecs natively, so there's
no manual register_vector / jsonb codec / per-acquire `SET search_path` juggling.

search_path is set as an asyncpg connection *startup* parameter (server_settings), so it
persists for the connection's lifetime — SQLAlchemy's pool returns connections with a
ROLLBACK, not the asyncpg-pool session reset that previously wiped search_path.
"""
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Trial tables live in `trials`; `extensions` keeps pgvector's operators/type resolvable
# on Supabase, `public` covers anything shared. Unknown schemas in search_path are
# ignored by Postgres, so this is safe across environments.
_SEARCH_PATH = "trials,public,extensions"


def _to_asyncpg_url(url: str) -> str:
    """Normalize any postgres URL scheme to the asyncpg driver SQLAlchemy needs."""
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        _to_asyncpg_url(database_url),
        connect_args={"server_settings": {"search_path": _SEARCH_PATH}},
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False keeps loaded attributes readable when we map ORM objects to
    # pydantic after the unit of work.
    return async_sessionmaker(engine, expire_on_commit=False)
