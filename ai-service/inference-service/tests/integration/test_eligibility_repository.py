"""Integration tests for EligibilityMatchRepository against a real Postgres
(Testcontainers), exercising get_criteria / get_criteria_bulk through the SQLAlchemy async
ORM — including the predicate JSONB round-trip.

Schema is created from ctiq-db's ORM metadata, so these tables are exactly production's.
Docker required. Run with: pytest -m integration
"""
import asyncio
from datetime import date, datetime, timezone

import asyncpg
import pytest
from sqlalchemy import text
from testcontainers.core.container import DockerContainer

from ctiq_db import Base, ClinicalTrial, TrialEligibilityCriterion

from src.app.modules.eligibility_match.repository import EligibilityMatchRepository
from src.app.infra.postgres.session import create_engine, create_session_factory

pytestmark = pytest.mark.integration

INGEST_DATE = date(2024, 1, 1)
INGESTED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)

# Predicate stored on a biomarker criterion — we assert this round-trips as a dict.
PD_L1_PREDICATE = {"marker": "PD-L1", "op": ">=", "value": 1, "unit": "%TC", "relation": "required"}


def _crit(nct_id, order, criterion_type, text_, category, predicate=None):
    return TrialEligibilityCriterion(
        nct_id=nct_id, criterion_type=criterion_type, text=text_, category=category,
        predicate=predicate, is_actionable=True, source_bullet_index=0,
        display_order=order, ingestion_date=INGEST_DATE,
    )


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
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS trials"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        # Parent trials (criteria FK to clinical_trials.nct_id).
        session.add_all([
            ClinicalTrial(nct_id="NCT-A", ingestion_date=INGEST_DATE, ingested_at=INGESTED_AT),
            ClinicalTrial(nct_id="NCT-B", ingestion_date=INGEST_DATE, ingested_at=INGESTED_AT),
        ])
        session.add_all([
            # NCT-A: out-of-order display_order to prove ordering on read.
            _crit("NCT-A", 1, "inclusion", "ECOG <= 1", "performance_status",
                  {"scale": "ECOG", "min": 0, "max": 1}),
            _crit("NCT-A", 0, "inclusion", "PD-L1 >= 1%", "biomarker", PD_L1_PREDICATE),
            _crit("NCT-A", 2, "exclusion", "active autoimmune disease", "comorbidity", None),
            _crit("NCT-B", 0, "inclusion", "Stage IV", "disease_stage", {"stage": ["IV"]}),
        ])
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


def _run(fixture, method, *args):
    loop, session_factory = fixture

    async def _go():
        async with session_factory() as session:
            return await getattr(EligibilityMatchRepository(session), method)(*args)

    return loop.run_until_complete(_go())


def test_get_criteria_returns_rows_in_display_order(repo):
    rows = _run(repo, "get_criteria", "NCT-A")
    assert len(rows) == 3
    # Ordered by display_order (0=biomarker, 1=performance_status, 2=comorbidity), even
    # though display_order itself isn't in the returned dict (the matcher doesn't need it).
    assert [r["category"] for r in rows] == ["biomarker", "performance_status", "comorbidity"]
    assert set(rows[0]) == {"criterion_type", "category", "text", "predicate", "is_actionable"}


def test_get_criteria_predicate_roundtrips_as_dict(repo):
    rows = _run(repo, "get_criteria", "NCT-A")
    assert rows[0]["predicate"] == PD_L1_PREDICATE  # JSONB -> dict, unchanged
    assert rows[2]["predicate"] is None             # prose criterion has no predicate


def test_get_criteria_unknown_trial_is_empty(repo):
    assert _run(repo, "get_criteria", "NCT-MISSING") == []


def test_get_criteria_bulk_groups_by_nct(repo):
    grouped = _run(repo, "get_criteria_bulk", ["NCT-A", "NCT-B", "NCT-MISSING"])
    assert set(grouped) == {"NCT-A", "NCT-B"}  # missing nct simply absent
    assert len(grouped["NCT-A"]) == 3
    assert len(grouped["NCT-B"]) == 1


def test_get_criteria_bulk_empty_input(repo):
    assert _run(repo, "get_criteria_bulk", []) == {}
