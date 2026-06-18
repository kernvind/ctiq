import json

import asyncpg
from pgvector.asyncpg import register_vector


# Trial tables live in the `trials` schema. Unqualified table names in the repository's
# raw SQL resolve there; `extensions` (where Supabase installs pgvector) keeps operators
# like `<=>` resolvable, and `public` covers anything shared.
_SEARCH_PATH = "SET search_path TO trials, public, extensions"


async def _setup_conn(conn: asyncpg.Connection) -> None:
    # Runs on EVERY pool acquire. asyncpg resets a connection's session state
    # (including search_path) when it is released back to the pool, so setting it only
    # in `init` is wiped after the first use — set it here so it's always in effect.
    await conn.execute(_SEARCH_PATH)


async def _init_conn(conn: asyncpg.Connection) -> None:
    # Runs once when a connection is created: search_path (so register_vector can resolve
    # the `vector` type) plus the codecs (client-side, survive resets).
    await conn.execute(_SEARCH_PATH)
    await register_vector(conn)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        database_url, init=_init_conn, setup=_setup_conn
    )


class PostgresClient:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)
