import json

import asyncpg
from pgvector.asyncpg import register_vector


async def _init_conn(conn: asyncpg.Connection) -> None:
    await register_vector(conn)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, init=_init_conn)


class PostgresClient:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)
