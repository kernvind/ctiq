"""Integration tests for TrialSearchRepository.vector_search against a real pgvector
Postgres (Testcontainers). Verifies the actual SQL: nearest-neighbour ordering, the
phase pre-filter, field-type filtering, and location aggregation.

Docker required. Run with: pytest -m integration
"""
import asyncio

import asyncpg
import pytest
from testcontainers.core.container import DockerContainer

from src.app.core.config import Settings
from src.app.infra.postgres.client import PostgresClient, create_pool
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository

pytestmark = pytest.mark.integration

EMBED_DIM = 768


def _vec(*pairs: tuple[int, float]) -> list[float]:
    v = [0.0] * EMBED_DIM
    for index, value in pairs:
        v[index] = value
    return v


# Orthogonal-ish vectors; QUERY is closest to A, then B, then C.
A_VEC = _vec((0, 1.0))
B_VEC = _vec((1, 1.0))
C_VEC = _vec((2, 1.0))
QUERY = _vec((0, 1.0), (1, 0.3))

_DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE SCHEMA IF NOT EXISTS trials",
    """CREATE TABLE trials.clinical_trials (
        nct_id text PRIMARY KEY, brief_title text, brief_summary text,
        overall_status text, phases text[], conditions text[],
        lead_sponsor_name text, lead_sponsor_class text,
        min_age_years double precision, max_age_years double precision,
        sex text, healthy_volunteers boolean)""",
    "CREATE TABLE trials.trial_embeddings (nct_id text, field_type text, chunk_text text, embedding vector(768))",
    "CREATE TABLE trials.trial_locations (nct_id text, facility text, city text, state text, country text, status text)",
]


async def _wait_ready(url: str, attempts: int = 40) -> None:
    for _ in range(attempts):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError("postgres did not become ready in time")


async def _setup(url: str):
    await _wait_ready(url)

    # DDL on a raw connection: the `vector` type must exist before create_pool's
    # register_vector runs.
    raw = await asyncpg.connect(url)
    await raw.execute("SET search_path TO trials, public")
    for stmt in _DDL:
        await raw.execute(stmt)
    await raw.close()

    pool = await create_pool(url)
    async with pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO trials.clinical_trials "
            "(nct_id, brief_title, overall_status, phases, conditions, lead_sponsor_name, lead_sponsor_class) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            [
                ("NCT-A", "Trial A", "RECRUITING", ["PHASE2"], [], "Sponsor A", "INDUSTRY"),
                ("NCT-B", "Trial B", "RECRUITING", ["PHASE3"], [], "Sponsor B", "INDUSTRY"),
                ("NCT-C", "Trial C", "RECRUITING", ["PHASE1"], [], "Sponsor C", "OTHER"),
            ],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_embeddings (nct_id, field_type, chunk_text, embedding) VALUES ($1,$2,$3,$4)",
            [
                ("NCT-A", "summary", "A summary chunk", A_VEC),
                ("NCT-A", "title", "A title chunk", A_VEC),
                ("NCT-B", "summary", "B summary chunk", B_VEC),
                ("NCT-C", "summary", "C summary chunk", C_VEC),
            ],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_locations (nct_id, facility, city, state, country, status) VALUES ($1,$2,$3,$4,$5,$6)",
            [
                ("NCT-A", "Site 1", "New York", "NY", "USA", "RECRUITING"),
                ("NCT-A", "Site 2", "Los Angeles", "CA", "USA", "COMPLETED"),
            ],
        )

    repo = TrialSearchRepository(
        pg=PostgresClient(pool), settings=Settings(vector_search_oversample_factor=3)
    )
    return pool, repo


@pytest.fixture(scope="module")
def repo():
    container = (
        DockerContainer("pgvector/pgvector:pg16")
        .with_env("POSTGRES_USER", "test")
        .with_env("POSTGRES_PASSWORD", "test")
        .with_env("POSTGRES_DB", "test")
        .with_exposed_ports(5432)
    )
    container.start()
    loop = asyncio.new_event_loop()
    pool = None
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        url = f"postgresql://test:test@{host}:{port}/test"
        pool, repository = loop.run_until_complete(_setup(url))
        yield loop, repository
    finally:
        if pool is not None:
            loop.run_until_complete(pool.close())
        loop.close()
        container.stop()


def _run(repo_fixture, coro):
    loop, _ = repo_fixture
    return loop.run_until_complete(coro)


def test_returns_nearest_trials_ordered_by_distance(repo):
    _, repository = repo
    rows = _run(repo, repository.vector_search(embedding=QUERY, fields=[Field.SUMMARY], top_k=10))

    assert [r.nct_id for r in rows] == ["NCT-A", "NCT-B", "NCT-C"]
    distances = [r.best_distance for r in rows]
    assert distances == sorted(distances)
    assert rows[0].best_chunk.field_type == "summary"


def test_phase_filter_restricts_to_matching_trials(repo):
    _, repository = repo
    rows = _run(
        repo,
        repository.vector_search(
            embedding=QUERY, fields=[Field.SUMMARY], top_k=10, phase_filter=("PHASE3",)
        ),
    )
    assert [r.nct_id for r in rows] == ["NCT-B"]


def test_field_filter_restricts_to_field_type(repo):
    _, repository = repo
    rows = _run(repo, repository.vector_search(embedding=QUERY, fields=[Field.TITLE], top_k=10))

    assert [r.nct_id for r in rows] == ["NCT-A"]
    assert rows[0].best_chunk.field_type == "title"


def test_aggregates_locations(repo):
    _, repository = repo
    rows = _run(repo, repository.vector_search(embedding=QUERY, fields=[Field.SUMMARY], top_k=10))

    a = next(r for r in rows if r.nct_id == "NCT-A")
    assert a.total_sites == 2
    assert a.recruiting_sites == 1
    assert len(a.sample_facilities) == 2
