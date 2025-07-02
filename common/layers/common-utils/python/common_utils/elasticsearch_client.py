"""Lightweight wrapper around the ``elasticsearch`` client."""

from __future__ import annotations

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

import os
from typing import Any, Iterable, List, Optional

from common_utils import configure_logger

logger = configure_logger(__name__)

try:  # pragma: no cover - optional dependency
    from elasticsearch import Elasticsearch
except Exception:  # pragma: no cover - allow import without elasticsearch
    Elasticsearch = None  # type: ignore


class ElasticsearchClient:
    """Minimal Elasticsearch helper for Lambda functions."""

    def __init__(self, url: Optional[str] = None, index_prefix: Optional[str] = None) -> None:
        """Create a client using ``url`` and ``index_prefix``.

        If not provided, the parameters default to the ``ELASTICSEARCH_URL`` and
        ``ELASTICSEARCH_INDEX_PREFIX`` environment variables respectively.
        """

        self.url = url or os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        self.index_prefix = index_prefix or os.environ.get("ELASTICSEARCH_INDEX_PREFIX", "docs")

        if Elasticsearch is None:  # pragma: no cover - imported module missing
            raise ImportError("elasticsearch package is required to use ElasticsearchClient")

        self.client = Elasticsearch(self.url)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def _index(self, name: Optional[str] = None) -> str:
        """Return the full index name for ``name`` using the prefix."""

        return f"{self.index_prefix}-{name}" if name else self.index_prefix

    def insert(self, documents: Iterable[dict], index: Optional[str] = None) -> int:
        """Insert ``documents`` into ``index`` and return the number stored."""

        idx = self._index(index)
        count = 0
        for doc in documents:
            doc_id = doc.get("id")
            body = {k: v for k, v in doc.items() if k != "id"}
            self.client.index(index=idx, id=doc_id, document=body)
            count += 1
        return count

    def delete(self, ids: Iterable[str], index: Optional[str] = None) -> int:
        """Remove documents with ``ids`` from ``index`` and return the count."""

        idx = self._index(index)
        count = 0
        for doc_id in ids:
            self.client.delete(index=idx, id=doc_id, ignore=[404])
            count += 1
        return count

    def update(self, documents: Iterable[dict], index: Optional[str] = None) -> int:
        """Replace documents by ID in ``index`` with ``documents``."""

        idx = self._index(index)
        count = 0
        for doc in documents:
            doc_id = doc.get("id")
            body = {k: v for k, v in doc.items() if k != "id"}
            self.client.index(index=idx, id=doc_id, document=body)
            count += 1
        return count

    def create_index(self, index: Optional[str] = None) -> None:
        """Create ``index`` if it does not already exist."""

        idx = self._index(index)
        self.client.indices.create(index=idx, ignore=400)

    def drop_index(self, index: Optional[str] = None) -> None:
        """Delete ``index`` ignoring missing errors."""

        idx = self._index(index)
        self.client.indices.delete(index=idx, ignore=[400, 404])

    def search(self, embedding: List[float], top_k: int = 5, index: Optional[str] = None) -> List[dict]:
        """Return ``top_k`` nearest vectors to ``embedding`` from ``index``."""

        idx = self._index(index)
        if embedding is None:
            return []
        query = {
            "knn": {
                "field": "embedding",
                "query_vector": embedding,
                "k": top_k,
                "num_candidates": top_k,
            }
        }
        res = self.client.search(index=idx, query=query, size=top_k)
        hits = res.get("hits", {}).get("hits", [])
        return [
            {"id": h.get("_id"), "score": h.get("_score"), "metadata": h.get("_source", {}).get("metadata")}
            for h in hits
        ]

    def hybrid_search(self, embedding: List[float], keywords: Iterable[str] | None = None, top_k: int = 5, index: Optional[str] = None) -> List[dict]:
        """Search ``index`` using vector similarity and optional ``keywords``."""

        idx = self._index(index)
        if embedding is None:
            return []
        knn = {
            "field": "embedding",
            "query_vector": embedding,
            "k": top_k,
            "num_candidates": top_k,
        }
        query: dict[str, Any] = {"bool": {"must": {"knn": knn}}}
        if keywords:
            query["bool"].setdefault("filter", []).append({"match": {"text": " ".join(keywords)}})
        res = self.client.search(index=idx, query=query, size=top_k)
        hits = res.get("hits", {}).get("hits", [])
        return [
            {"id": h.get("_id"), "score": h.get("_score"), "metadata": h.get("_source", {}).get("metadata")}
            for h in hits
        ]
