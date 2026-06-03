from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model: SentenceTransformer):
        self._model = model

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a search query.

        Applies nomic search_query prefix.
        """

        text = text.strip()

        vec = self._model.encode(
            f"search_query: {text}",
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return vec.tolist()