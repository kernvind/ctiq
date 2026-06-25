"""Integration tests for TrialSearchRepository against a real pgvector Postgres
(Testcontainers), exercising the SQLAlchemy async ORM end to end.

The schema is created from ctiq-db's ORM metadata (Base.metadata.create_all), so the
test tables are exactly the production tables — a column rename/removal in the trials
domain breaks these tests. Seeding goes through the ORM too, so this also covers the
pgvector bind path (embedding inserts + cosine_distance search).

Docker required. Run with: pytest -m integration
"""
import asyncio
from datetime import date, datetime, timezone

import asyncpg
import pytest
from sqlalchemy import text
from testcontainers.core.container import DockerContainer

from ctiq_db import (
    Base,
    ClinicalTrial,
    TrialArmGroup,
    TrialEmbedding,
    TrialIntervention,
    TrialLocation,
    TrialOfficial,
    TrialOutcome,
)

from src.app.core.config import Settings
from src.app.infra.postgres.session import create_engine, create_session_factory
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository

pytestmark = pytest.mark.integration

EMBED_DIM = 768
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


async def _setup(url: str):
    await _wait_ready(url)
    engine = create_engine(url)
    # Create the pgvector extension + schema, then all tables from the ORM metadata.
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS trials"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add_all(
            [
                ClinicalTrial(
                    nct_id="NCT-A", brief_title="Trial A", overall_status="RECRUITING",
                    phases=["PHASE2"], conditions=["Melanoma"], lead_sponsor_name="Sponsor A",
                    lead_sponsor_class="INDUSTRY", ingestion_date=INGEST_DATE, ingested_at=INGESTED_AT,
                    official_title="Official Trial A", detailed_description="Long description",
                    eligibility_criteria="Inclusion: adults", study_type="INTERVENTIONAL",
                    collaborators=[{"name": "Acme", "class": "INDUSTRY"}],
                    # phone/pmid intentionally stored as JSON ints — real ETL data does this,
                    # and the schema must coerce them to str (see coerce_numbers_to_str).
                    central_contacts=[{"name": "Coord", "role": "CONTACT", "phone": 555, "email": "a@b.co"}],
                    references=[{"citation": "Smith 2020", "type": "BACKGROUND", "pmid": 123}],
                ),
                ClinicalTrial(
                    nct_id="NCT-B", brief_title="Trial B", overall_status="RECRUITING",
                    phases=["PHASE3"], conditions=["Malignant Melanoma"], lead_sponsor_name="Sponsor B",
                    lead_sponsor_class="INDUSTRY", ingestion_date=INGEST_DATE, ingested_at=INGESTED_AT,
                ),
                ClinicalTrial(
                    nct_id="NCT-C", brief_title="Trial C", overall_status="COMPLETED",
                    phases=["PHASE1"], conditions=["Lung Cancer"], lead_sponsor_name="Sponsor C",
                    lead_sponsor_class="OTHER", ingestion_date=INGEST_DATE, ingested_at=INGESTED_AT,
                ),
            ]
        )
        session.add_all(
            [
                TrialEmbedding(nct_id="NCT-A", field_type="summary", chunk_id=0, chunk_text="A summary chunk",
                               source_hash="h1", model_version=MODEL_VERSION, embedding=A_VEC, ingested_at=INGESTED_AT),
                TrialEmbedding(nct_id="NCT-A", field_type="title", chunk_id=0, chunk_text="A title chunk",
                               source_hash="h2", model_version=MODEL_VERSION, embedding=A_VEC, ingested_at=INGESTED_AT),
                TrialEmbedding(nct_id="NCT-B", field_type="summary", chunk_id=0, chunk_text="B summary chunk",
                               source_hash="h3", model_version=MODEL_VERSION, embedding=B_VEC, ingested_at=INGESTED_AT),
                TrialEmbedding(nct_id="NCT-C", field_type="summary", chunk_id=0, chunk_text="C summary chunk",
                               source_hash="h4", model_version=MODEL_VERSION, embedding=C_VEC, ingested_at=INGESTED_AT),
            ]
        )
        session.add_all(
            [
                TrialLocation(nct_id="NCT-A", facility="Site 1", city="New York", state="NY",
                              country="USA", status="RECRUITING", ingestion_date=INGEST_DATE),
                TrialLocation(nct_id="NCT-A", facility="Site 2", city="Los Angeles", state="CA",
                              country="USA", status="COMPLETED", ingestion_date=INGEST_DATE),
            ]
        )
        session.add_all(
            [
                TrialIntervention(nct_id="NCT-A", type="DRUG", name="Compound X",
                                  description="10mg daily", ingestion_date=INGEST_DATE),
                TrialOutcome(nct_id="NCT-A", outcome_type="SECONDARY", measure="PFS",
                             time_frame="12mo", ingestion_date=INGEST_DATE),
                TrialOutcome(nct_id="NCT-A", outcome_type="PRIMARY", measure="Overall survival",
                             time_frame="24mo", ingestion_date=INGEST_DATE),
                TrialArmGroup(nct_id="NCT-A", label="Arm 1", type="EXPERIMENTAL",
                              description="Gets X", ingestion_date=INGEST_DATE),
                TrialOfficial(nct_id="NCT-A", name="Dr Jane", affiliation="Big Hospital",
                              role="PRINCIPAL_INVESTIGATOR", ingestion_date=INGEST_DATE),
            ]
        )
        await session.commit()

    return engine, session_factory


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
    engine = None
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        url = f"postgresql://test:test@{host}:{port}/test"
        engine, session_factory = loop.run_until_complete(_setup(url))
        yield loop, session_factory
    finally:
        if engine is not None:
            loop.run_until_complete(engine.dispose())
        loop.close()
        container.stop()


def _run_repo(fixture, method: str, *args, **kwargs):
    """Open a fresh session, build a repository, and run one of its coroutines."""
    loop, session_factory = fixture

    async def _go():
        async with session_factory() as session:
            repository = TrialSearchRepository(
                session=session, settings=Settings(vector_search_oversample_factor=3)
            )
            return await getattr(repository, method)(*args, **kwargs)

    return loop.run_until_complete(_go())


def test_returns_nearest_trials_ordered_by_distance(repo):
    rows = _run_repo(repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10)

    assert [r.nct_id for r in rows] == ["NCT-A", "NCT-B", "NCT-C"]
    distances = [r.best_distance for r in rows]
    assert distances == sorted(distances)
    assert rows[0].best_chunk.field_type == "summary"


def test_phase_filter_restricts_to_matching_trials(repo):
    rows = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        phase_filter=("PHASE3",),
    )
    assert [r.nct_id for r in rows] == ["NCT-B"]


def test_status_filter_restricts_to_matching_trials(repo):
    rows = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        statuses=("RECRUITING",),
    )
    # NCT-C is COMPLETED, so it's excluded; A then B by distance.
    assert [r.nct_id for r in rows] == ["NCT-A", "NCT-B"]

    completed = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        statuses=("COMPLETED",),
    )
    assert [r.nct_id for r in completed] == ["NCT-C"]


def test_sponsor_filter_is_fuzzy_and_case_insensitive(repo):
    # Exact-ish term narrows to one sponsor.
    one = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        sponsor="Sponsor B",
    )
    assert [r.nct_id for r in one] == ["NCT-B"]

    # Lower-case substring matches every "Sponsor ..." (ILIKE).
    many = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        sponsor="sponsor",
    )
    assert {r.nct_id for r in many} == {"NCT-A", "NCT-B", "NCT-C"}


def test_condition_filter_matches_family_substring(repo):
    # "melanoma" matches both "Melanoma" and "Malignant Melanoma", not "Lung Cancer".
    rows = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        conditions=("melanoma",),
    )
    assert {r.nct_id for r in rows} == {"NCT-A", "NCT-B"}


def test_condition_filter_ors_multiple_terms(repo):
    rows = _run_repo(
        repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10,
        conditions=("melanoma", "lung cancer"),
    )
    assert {r.nct_id for r in rows} == {"NCT-A", "NCT-B", "NCT-C"}


def test_field_filter_restricts_to_field_type(repo):
    rows = _run_repo(repo, "vector_search", embedding=QUERY, fields=[Field.TITLE], top_k=10)

    assert [r.nct_id for r in rows] == ["NCT-A"]
    assert rows[0].best_chunk.field_type == "title"


def test_aggregates_locations(repo):
    rows = _run_repo(repo, "vector_search", embedding=QUERY, fields=[Field.SUMMARY], top_k=10)

    a = next(r for r in rows if r.nct_id == "NCT-A")
    assert a.total_sites == 2
    assert a.recruiting_sites == 1
    assert len(a.sample_facilities) == 2


def test_get_trial_unknown_id_returns_none(repo):
    assert _run_repo(repo, "get_trial", "NCT-DOES-NOT-EXIST") is None


def test_get_trial_assembles_full_record(repo):
    detail = _run_repo(repo, "get_trial", "NCT-A")

    assert detail is not None
    assert detail.nct_id == "NCT-A"
    assert detail.official_title == "Official Trial A"
    assert detail.eligibility_criteria == "Inclusion: adults"

    # JSONB columns decode + validate (incl. the "class" -> sponsor_class alias).
    assert detail.collaborators[0].sponsor_class == "INDUSTRY"
    assert detail.central_contacts[0].email == "a@b.co"
    # JSON ints coerced to str (real ETL stores these numerically).
    assert detail.central_contacts[0].phone == "555"
    assert detail.references[0].pmid == "123"

    # Child collections load via selectinload.
    assert {loc.facility for loc in detail.locations} == {"Site 1", "Site 2"}
    assert detail.interventions[0].name == "Compound X"
    assert detail.arm_groups[0].label == "Arm 1"
    assert detail.officials[0].name == "Dr Jane"

    # Outcomes are ordered PRIMARY before SECONDARY in the repository.
    assert [o.outcome_type for o in detail.outcomes] == ["PRIMARY", "SECONDARY"]
