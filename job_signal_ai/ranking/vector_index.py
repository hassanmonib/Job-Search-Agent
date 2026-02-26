"""FAISS index for job embeddings: index_id -> job_id mapping, cosine similarity via normalized vectors."""

from typing import List, Optional, Tuple

import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_l2(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize rows so that dot product equals cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms > 0, norms, 1.0)
    return vectors.astype(np.float32) / norms


class JobVectorIndex:
    """
    FAISS IndexFlatIP over L2-normalized vectors (cosine similarity).
    Maps index position to job_id (e.g. source_url or a stable id).
    """

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension
        self._index = None
        self._id_list: List[str] = []
        self._built = False

    def _get_faiss_index(self):
        if self._index is None:
            try:
                import faiss
            except ImportError:
                raise ImportError("faiss-cpu not installed; pip install faiss-cpu")
            self._index = faiss.IndexFlatIP(self._dimension)
            logger.info("Created FAISS IndexFlatIP dimension=%s", self._dimension)
        return self._index

    def add_embeddings(
        self,
        vectors: List[List[float]],
        job_ids: List[str],
    ) -> None:
        """
        Add embeddings and their job_id mapping.
        vectors: list of embedding vectors (same dimension).
        job_ids: one id per vector (e.g. job source_url or index).
        """
        if not vectors or not job_ids or len(vectors) != len(job_ids):
            raise ValueError("vectors and job_ids must be same length and non-empty")
        arr = np.array(vectors, dtype=np.float32)
        arr = _normalize_l2(arr)
        index = self._get_faiss_index()
        index.add(arr)
        self._id_list.extend(job_ids)
        self._built = True
        logger.info("Added %s embeddings; total %s", len(job_ids), len(self._id_list))

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Search by query vector (will be L2-normalized).
        Returns list of (job_id, similarity_score) sorted descending by score.
        """
        if not self._id_list or not self._built:
            return []
        q = np.array([query_vector], dtype=np.float32)
        q = _normalize_l2(q)
        index = self._get_faiss_index()
        k = min(top_k, index.ntotal)
        if k <= 0:
            return []
        scores, indices = index.search(q, k)
        out: List[Tuple[str, float]] = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self._id_list):
                out.append((self._id_list[idx], float(scores[0][i])))
        return out

    def clear(self) -> None:
        """Clear all vectors and rebuild empty index."""
        try:
            import faiss
        except ImportError:
            return
        self._index = faiss.IndexFlatIP(self._dimension)
        self._id_list = []
        self._built = False
        logger.info("Cleared FAISS index")

    def size(self) -> int:
        return len(self._id_list)
