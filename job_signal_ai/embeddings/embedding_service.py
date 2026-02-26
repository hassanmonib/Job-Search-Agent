"""Embedding service: embed_text and batch_embed via SentenceTransformers or OpenAI."""

from abc import ABC, abstractmethod
from typing import List

from config import (
    EMBEDDING_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
    SENTENCE_TRANSFORMERS_MODEL,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text. Returns a vector of floats."""
        ...

    @abstractmethod
    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts. Returns list of vectors."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        ...


class SentenceTransformersEmbeddingService(EmbeddingService):
    """Local embeddings via SentenceTransformers (e.g. all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = SENTENCE_TRANSFORMERS_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info("Loaded SentenceTransformer model: %s", self._model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed; pip install sentence-transformers"
                )
        return self._model

    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        if not (text or "").strip():
            return self._get_model().encode(" ", convert_to_numpy=True).tolist()
        vec = self._get_model().encode(text.strip(), convert_to_numpy=True)
        return vec.tolist()

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        cleaned = [t.strip() if t else " " for t in texts]
        matrix = self._get_model().encode(cleaned, convert_to_numpy=True)
        return matrix.tolist()


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embeddings API (e.g. text-embedding-3-small)."""

    def __init__(
        self,
        api_key: str = OPENAI_API_KEY,
        model: str = OPENAI_EMBEDDING_MODEL,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension: int | None = None

    def _get_client(self):
        from openai import OpenAI
        return OpenAI(api_key=self._api_key)

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # Small embedding to get dimension once
            vec = self.embed_text(".")
            self._dimension = len(vec)
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        client = self._get_client()
        t = (text or "").strip() or " "
        resp = client.embeddings.create(model=self._model, input=[t])
        return resp.data[0].embedding

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        cleaned = [t.strip() if t else " " for t in texts]
        client = self._get_client()
        resp = client.embeddings.create(model=self._model, input=cleaned)
        by_idx = {d.index: d.embedding for d in resp.data}
        return [by_idx[i] for i in range(len(cleaned))]


def get_embedding_service(provider: str | None = None) -> EmbeddingService:
    """
    Return the configured embedding service (dependency injection).
    provider: override config; None uses EMBEDDING_PROVIDER.
    """
    p = (provider or EMBEDDING_PROVIDER).strip().lower()
    if p == "openai":
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set; falling back to sentence_transformers")
            return SentenceTransformersEmbeddingService()
        return OpenAIEmbeddingService()
    return SentenceTransformersEmbeddingService()
