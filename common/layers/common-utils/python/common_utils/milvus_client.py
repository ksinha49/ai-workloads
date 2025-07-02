"""Simple wrapper around pymilvus Collection for Lambda usage."""

from __future__ import annotations

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from pymilvus import Collection, connections
except Exception:  # pragma: no cover - allow import without pymilvus
    Collection = None  # type: ignore
    connections = None  # type: ignore


@dataclass
class VectorItem:
    """Embedding with optional ID and metadata."""

    embedding: List[float]
    metadata: Any
    id: Optional[int] = None


@dataclass
class SearchResult:
    """Result item returned from ``search``."""

    id: int
    score: float
    metadata: Any


@dataclass
class GetResult:
    """Record returned from ``get``."""

    id: int
    embedding: List[float]
    metadata: Any


class MilvusClient:
    """Minimal Milvus helper for Lambda functions."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None,
        *,
        index_params: Optional[dict] = None,
        search_params: Optional[dict] = None,
        metric_type: Optional[str] = None,
    ) -> None:
        """Connect to Milvus and prepare a collection.

        Parameters fall back to environment variables when ``None`` is provided:

        - ``host`` (``MILVUS_HOST``, default ``"localhost"``)
        - ``port`` (``MILVUS_PORT``, default ``19530``)
        - ``collection_name`` (``MILVUS_COLLECTION``, default ``"docs"``)
        - ``index_params`` from ``MILVUS_INDEX_PARAMS`` (JSON)
        - ``search_params`` from ``MILVUS_SEARCH_PARAMS`` (JSON)
        - ``metric_type`` from ``MILVUS_METRIC_TYPE`` or ``index_params``
        """

        self.host = host or os.environ.get("MILVUS_HOST", "localhost")
        self.port = int(port or os.environ.get("MILVUS_PORT", "19530"))
        self.collection_name = collection_name or os.environ.get(
            "MILVUS_COLLECTION", "docs"
        )

        if Collection is None or connections is None:  # pragma: no cover
            raise ImportError("pymilvus is required to use MilvusClient")

        # Optional tuning parameters read from env if not provided
        if index_params is None:
            params = os.environ.get("MILVUS_INDEX_PARAMS")
            if params:
                try:
                    index_params = json.loads(params)
                except json.JSONDecodeError:
                    index_params = None
        self.index_params = index_params

        if metric_type is None:
            metric_type = os.environ.get("MILVUS_METRIC_TYPE")
        self.metric_type = metric_type or (index_params or {}).get("metric_type", "L2")

        if search_params is None:
            params = os.environ.get("MILVUS_SEARCH_PARAMS")
            if params:
                try:
                    search_params = json.loads(params)
                except json.JSONDecodeError:
                    search_params = None
        self.search_params = search_params or {"metric_type": self.metric_type}

        connections.connect(alias="default", host=self.host, port=self.port)
        self.collection = Collection(self.collection_name)
        if self.index_params:
            try:
                self.collection.create_index(
                    "embedding", self.index_params, index_name="embedding_idx"
                )
            except Exception:
                # index may already exist
                pass

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def insert(self, items: Iterable[VectorItem], upsert: bool = False) -> int:
        """Insert items and return the number inserted."""

        embeddings: List[List[float]] = []
        metadatas: List[Any] = []
        ids: List[int] = []
        for item in items:
            embeddings.append(item.embedding)
            metadatas.append(item.metadata)
            if item.id is not None:
                ids.append(int(item.id))

        if upsert and ids:
            self.collection.delete(f"id in {ids}")

        if ids:
            entities = [ids, embeddings, metadatas]
        else:
            entities = [embeddings, metadatas]
        self.collection.insert(entities)
        return len(embeddings)

    def search(self, embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """Return closest matches to *embedding*."""

        if embedding is None:
            return []
        res = self.collection.search(
            [embedding],
            "embedding",
            self.search_params,
            limit=top_k,
            output_fields=["metadata"],
        )
        results: List[SearchResult] = []
        for r in res[0]:
            md = None
            if hasattr(r, "entity") and r.entity is not None:
                md = r.entity.get("metadata")
            results.append(SearchResult(id=r.id, score=r.distance, metadata=md))
        return results

    def get(self, ids: Iterable[int]) -> List[GetResult]:
        """Fetch records by ``ids``."""

        id_list = list(ids)
        if not id_list:
            return []
        expr = f"id in {id_list}"
        res = self.collection.query(expr, output_fields=["id", "embedding", "metadata"])
        return [
            GetResult(
                id=rec.get("id"),
                embedding=rec.get("embedding"),
                metadata=rec.get("metadata"),
            )
            for rec in res
        ]

    def delete(self, ids: Iterable[int]) -> int:
        """Delete records with matching ``ids`` and return count."""

        id_list = [int(i) for i in ids]
        if not id_list:
            return 0
        res = self.collection.delete(f"id in {id_list}")
        count = getattr(res, "delete_count", None)
        return count if count is not None else len(id_list)

    def update(self, items: Iterable[VectorItem]) -> int:
        """Replace existing records with ``items``."""

        return self.insert(items, upsert=True)

    def create_collection(self, dimension: int = 768) -> None:
        """Create the collection if it does not exist."""

        from pymilvus import FieldSchema, CollectionSchema, DataType

        id_field = FieldSchema(
            name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
        )
        vec_field = FieldSchema(
            name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension
        )
        meta_field = FieldSchema(name="metadata", dtype=DataType.JSON)
        schema = CollectionSchema([id_field, vec_field, meta_field])
        self.collection = Collection(self.collection_name, schema)
        if self.index_params:
            try:  # pragma: no cover - ignore index exists errors
                self.collection.create_index(
                    "embedding", self.index_params, index_name="embedding_idx"
                )
            except Exception:
                pass

    def drop_collection(self) -> None:
        """Drop the current collection."""

        self.collection.drop()

