"""Embedding layer: SentenceTransformers or OpenAI (config-based)."""

from embeddings.embedding_service import get_embedding_service

__all__ = ["get_embedding_service"]
