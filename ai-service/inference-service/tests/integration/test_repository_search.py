"""Integration tests for TrialSearchRepository against a real pgvector Postgres
(Testcontainers). Verifies the actual SQL: vector_search (nearest-neighbour ordering,
phase pre-filter, field-type filtering, location aggregation) and get_trial.

The schema is created from ctiq-db's ORM metadata (not hand-written DDL), so a column
rename/removal in the trials domain breaks these tests — that's the drift guard that
lets the repository keep using raw asyncpg SQL safely. Requires the `local` poetry
group (ctiq-db); see Makefile `test-integration-py`.

Docker required. Run with: pytest -m integration
"""
import asyncio
from datetime import date, datetime, timezone

import asyncpg
import pytest
from testcontainers.core.container import DockerContainer

# NOTE: ctiq_db (the trials ORM, optional `local` poetry group) and sqlalchemy are
# imported lazily inside _create_trials_schema — NOT at module top. pytest imports this
# module during collection even for the unit run (`-m 'not integration'`), and the unit
# job intentionally doesn't install the trials ORM. Keep these imports lazy.

from src.app.core.config import Settings
from src.app.infra.postgres.client import PostgresClient, create_pool
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository

pytestmark = pytest.mark.integration

EMBED_DIM = 768

# NOT NULL bookkeeping columns shared by the real ORM tables; the seeds must supply them.
INGEST_DATE = date(2024, 1, 1)
INGESTED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)
MODEL_VERSION = "test-model-v1"


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

async def _wait_ready(url: str, attempts: int = 40) -> None:
    for _ in range(attempts):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError("postgres did not become ready in time")


async def _create_trials_schema(conn: asyncpg.Connection) -> None:
    """Create the trials schema from ctiq-db's ORM metadata so the test tables are
    exactly the production tables. Compiles each model's CREATE TABLE for Postgres and
    runs it over asyncpg (no SQLAlchemy engine / sync driver needed)."""
    from ctiq_db import Base
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    await conn.execute("CREATE SCHEMA IF NOT EXISTS trials")
    # Install pgvector into `public`: create_pool's register_vector resolves the type as
    # `public.vector`. The unqualified `vector(768)` column type still resolves via the
    # search_path below (public is on it).
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")
    await conn.execute("SET search_path TO trials, public")
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        await conn.execute(ddl)


async def _setup(url: str):
    await _wait_ready(url)

    # Build the schema on a raw connection: the `vector` type must exist before
    # create_pool's register_vector runs.
    raw = await asyncpg.connect(url)
    await _create_trials_schema(raw)
    await raw.close()

    pool = await create_pool(url)
    async with pool.acquire() as conn:
        # ingestion_date / ingested_at are NOT NULL on the real tables.
        await conn.executemany(
            "INSERT INTO trials.clinical_trials "
            "(nct_id, brief_title, overall_status, phases, conditions, lead_sponsor_name, "
            " lead_sponsor_class, ingestion_date, ingested_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            [
                ("NCT-A", "Trial A", "RECRUITING", ["PHASE2"], [], "Sponsor A", "INDUSTRY", INGEST_DATE, INGESTED_AT),
                ("NCT-B", "Trial B", "RECRUITING", ["PHASE3"], [], "Sponsor B", "INDUSTRY", INGEST_DATE, INGESTED_AT),
                ("NCT-C", "Trial C", "RECRUITING", ["PHASE1"], [], "Sponsor C", "OTHER", INGEST_DATE, INGESTED_AT),
            ],
        )
        # trial_embeddings PK is (nct_id, field_type, chunk_id); source_hash, model_version,
        # ingested_at are NOT NULL.
        await conn.executemany(
            "INSERT INTO trials.trial_embeddings "
            "(nct_id, field_type, chunk_id, chunk_text, source_hash, model_version, embedding, ingested_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            [
                ("NCT-A", "summary", 0, "A summary chunk", "h1", MODEL_VERSION, A_VEC, INGESTED_AT),
                ("NCT-A", "title", 0, "A title chunk", "h2", MODEL_VERSION, A_VEC, INGESTED_AT),
                ("NCT-B", "summary", 0, "B summary chunk", "h3", MODEL_VERSION, B_VEC, INGESTED_AT),
                ("NCT-C", "summary", 0, "C summary chunk", "h4", MODEL_VERSION, C_VEC, INGESTED_AT),
            ],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_locations "
            "(nct_id, facility, city, state, country, status, ingestion_date) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            [
                ("NCT-A", "Site 1", "New York", "NY", "USA", "RECRUITING", INGEST_DATE),
                ("NCT-A", "Site 2", "Los Angeles", "CA", "USA", "COMPLETED", INGEST_DATE),
            ],
        )

        # Extra detail data for NCT-A so get_trial has a rich record to assemble.
        await conn.execute(
            """UPDATE trials.clinical_trials SET
                 official_title = 'Official Trial A',
                 detailed_description = 'Long description',
                 eligibility_criteria = 'Inclusion: adults',
                 study_type = 'INTERVENTIONAL',
                 collaborators = $2::jsonb,
                 central_contacts = $3::jsonb,
                 "references" = $4::jsonb
               WHERE nct_id = $1""",
            "NCT-A",
            # Pass Python objects (not JSON strings): the pool's jsonb codec encodes via
            # json.dumps, so a string here would be double-encoded.
            [{"name": "Acme", "class": "INDUSTRY"}],
            [{"name": "Coord", "role": "CONTACT", "phone": "555", "email": "a@b.co"}],
            [{"citation": "Smith 2020", "type": "BACKGROUND", "pmid": "123"}],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_interventions (nct_id, type, name, description, ingestion_date) VALUES ($1,$2,$3,$4,$5)",
            [("NCT-A", "DRUG", "Compound X", "10mg daily", INGEST_DATE)],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_outcomes (nct_id, outcome_type, measure, description, time_frame, ingestion_date) VALUES ($1,$2,$3,$4,$5,$6)",
            [
                ("NCT-A", "SECONDARY", "PFS", None, "12mo", INGEST_DATE),
                ("NCT-A", "PRIMARY", "Overall survival", None, "24mo", INGEST_DATE),
            ],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_arm_groups (nct_id, label, type, description, ingestion_date) VALUES ($1,$2,$3,$4,$5)",
            [("NCT-A", "Arm 1", "EXPERIMENTAL", "Gets X", INGEST_DATE)],
        )
        await conn.executemany(
            "INSERT INTO trials.trial_officials (nct_id, name, affiliation, role, ingestion_date) VALUES ($1,$2,$3,$4,$5)",
            [("NCT-A", "Dr Jane", "Big Hospital", "PRINCIPAL_INVESTIGATOR", INGEST_DATE)],
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


def test_get_trial_unknown_id_returns_none(repo):
    _, repository = repo
    assert _run(repo, repository.get_trial("NCT-DOES-NOT-EXIST")) is None


def test_get_trial_assembles_full_record(repo):
    _, repository = repo
    detail = _run(repo, repository.get_trial("NCT-A"))

    assert detail is not None
    assert detail.nct_id == "NCT-A"
    assert detail.official_title == "Official Trial A"
    assert detail.eligibility_criteria == "Inclusion: adults"

    # JSONB columns decode + validate (incl. the "class" -> sponsor_class alias and the
    # quoted "references" reserved word).
    assert detail.collaborators[0].sponsor_class == "INDUSTRY"
    assert detail.central_contacts[0].email == "a@b.co"
    assert detail.references[0].pmid == "123"

    # Child collections aggregate via the JSONB subqueries.
    assert {loc.facility for loc in detail.locations} == {"Site 1", "Site 2"}
    assert detail.interventions[0].name == "Compound X"
    assert detail.arm_groups[0].label == "Arm 1"
    assert detail.officials[0].name == "Dr Jane"

    # Outcomes are ordered PRIMARY before SECONDARY by the query.
    assert [o.outcome_type for o in detail.outcomes] == ["PRIMARY", "SECONDARY"]
