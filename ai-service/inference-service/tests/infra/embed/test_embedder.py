import numpy as np
import pytest

from src.app.infra.embed.embedder import Embedder


class FakeModel:
    """Records what embed_query passes to encode(), returns a fixed vector."""

    def __init__(self):
        self.encoded_text = None
        self.encode_kwargs = None

    def encode(self, text, **kwargs):
        self.encoded_text = text
        self.encode_kwargs = kwargs
        return np.array([0.1, 0.2, 0.3])


def test_applies_nomic_search_query_prefix_and_strips_whitespace():
    model = FakeModel()
    result = Embedder(model).embed_query("  melanoma trials  ")

    # nomic models require the "search_query:" prefix; input is stripped first.
    assert model.encoded_text == "search_query: melanoma trials"
    assert result == pytest.approx([0.1, 0.2, 0.3])


def test_requests_normalized_numpy_embeddings():
    model = FakeModel()
    Embedder(model).embed_query("query")

    assert model.encode_kwargs.get("normalize_embeddings") is True
    assert model.encode_kwargs.get("convert_to_numpy") is True
