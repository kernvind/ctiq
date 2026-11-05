from sentence_transformers import SentenceTransformer

from src.app.infra.observability.metrics import EMBEDDING_LATENCY


class Embedder:
    def __init__(self, model: SentenceTransformer):
        self._model = model

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a search query.

        Applies nomic search_query prefix.
        """

        text = text.strip()

        with EMBEDDING_LATENCY.time():
            vec = self._model.encode(
                f"search_query: {text}",
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

        return vec.tolist()