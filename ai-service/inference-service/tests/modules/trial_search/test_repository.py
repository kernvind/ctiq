import asyncio

import pytest

from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository


def _repo() -> TrialSearchRepository:
    # The input guards run before pg/settings are touched, so None is fine here.
    return TrialSearchRepository(pg=None, settings=None)


def test_empty_embedding_raises_value_error():
    with pytest.raises(ValueError):
        asyncio.run(
            _repo().vector_search(embedding=[], fields=[Field.SUMMARY], top_k=10)
        )


def test_empty_fields_raises_value_error():
    with pytest.raises(ValueError):
        asyncio.run(_repo().vector_search(embedding=[0.1], fields=[], top_k=10))
