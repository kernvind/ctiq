import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository


def _repo(pg=None) -> TrialSearchRepository:
    # The input guards run before pg/settings are touched, so None is fine here.
    return TrialSearchRepository(pg=pg, settings=None)


def test_empty_embedding_raises_value_error():
    with pytest.raises(ValueError):
        asyncio.run(
            _repo().vector_search(embedding=[], fields=[Field.SUMMARY], top_k=10)
        )


def test_empty_fields_raises_value_error():
    with pytest.raises(ValueError):
        asyncio.run(_repo().vector_search(embedding=[0.1], fields=[], top_k=10))


def test_get_trial_returns_none_when_no_row():
    pg = MagicMock()
    pg.fetch = AsyncMock(return_value=[])

    result = asyncio.run(_repo(pg).get_trial("NCT01234567"))

    assert result is None
    pg.fetch.assert_called_once()


def test_get_trial_maps_row_to_trial_detail():
    # asyncpg Records behave like dicts via dict(row); a plain dict stands in here.
    row = {
        "nct_id": "NCT01234567",
        "brief_title": "A study of X",
        "overall_status": "RECRUITING",
        "phases": ["PHASE3"],
        "conditions": ["Melanoma"],
        "collaborators": [{"name": "Acme", "class": "INDUSTRY"}],
        "locations": [{"facility": "Site A", "city": "Boston", "status": "RECRUITING"}],
        "interventions": [{"type": "DRUG", "name": "X"}],
        "outcomes": [{"outcome_type": "PRIMARY", "measure": "OS"}],
        "arm_groups": [{"label": "Arm 1", "type": "EXPERIMENTAL"}],
        "officials": [{"name": "Dr Y", "role": "PRINCIPAL_INVESTIGATOR"}],
    }
    pg = MagicMock()
    pg.fetch = AsyncMock(return_value=[row])

    detail = asyncio.run(_repo(pg).get_trial("NCT01234567"))

    assert detail is not None
    assert detail.nct_id == "NCT01234567"
    assert detail.phases == ["PHASE3"]
    assert detail.collaborators[0].sponsor_class == "INDUSTRY"  # alias "class" -> sponsor_class
    assert detail.locations[0].facility == "Site A"
    assert detail.outcomes[0].outcome_type == "PRIMARY"
    assert detail.officials[0].name == "Dr Y"
