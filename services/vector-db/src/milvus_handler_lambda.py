"""Milvus vector database operations handler."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List

from common_utils import configure_logger, MilvusClient, VectorItem
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

DEFAULT_TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))

client = MilvusClient()


def _insert(event: Dict[str, Any]) -> Dict[str, Any]:
    embeddings: List[List[float]] = event.get("embeddings", [])
    metadatas: List[Any] = event.get("metadatas", [])
    ids = event.get("ids") or []
    file_guid = event.get("file_guid")
    file_name = event.get("file_name")

    items: List[VectorItem] = []
    for idx, embedding in enumerate(embeddings):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        if metadata is None:
            metadata = {}
        if file_guid and "file_guid" not in metadata:
            metadata["file_guid"] = file_guid
        if file_name and "file_name" not in metadata:
            metadata["file_name"] = file_name
        item_id = ids[idx] if idx < len(ids) else None
        items.append(VectorItem(embedding=embedding, metadata=metadata, id=item_id))

    try:
        inserted = client.insert(items, upsert=False)
    except Exception:  # pragma: no cover - runtime safety
        logger.exception("Failed to insert vectors into Milvus")
        return {"inserted": 0}
    return {"inserted": inserted}


def _delete(event: Dict[str, Any]) -> Dict[str, Any]:
    ids: Iterable[int] = event.get("ids", [])
    try:
        deleted = client.delete(ids)
    except Exception:
        logger.exception("Failed to delete from Milvus")
        return {"deleted": 0}
    return {"deleted": deleted}


def _update(event: Dict[str, Any]) -> Dict[str, Any]:
    embeddings: List[List[float]] = event.get("embeddings", [])
    metadatas: List[Any] = event.get("metadatas", [])
    ids: Iterable[int] = event.get("ids", [])

    items: List[VectorItem] = []
    for idx, embedding in enumerate(embeddings):
        metadata = metadatas[idx] if idx < len(metadatas) else None
        item_id = ids[idx] if idx < len(ids) else None
        items.append(VectorItem(embedding=embedding, metadata=metadata, id=item_id))

    try:
        updated = client.update(items)
    except Exception:
        logger.exception("Failed to update vectors in Milvus")
        return {"updated": 0}
    return {"updated": updated}


def _create(event: Dict[str, Any]) -> Dict[str, Any]:
    dimension = int(event.get("dimension", 768))
    try:
        client.create_collection(dimension=dimension)
    except Exception as exc:
        logger.exception("Failed to create Milvus collection")
        return {"error": str(exc)}
    return {"created": True}


def _drop(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client.drop_collection()
    except Exception as exc:
        logger.exception("Failed to drop Milvus collection")
        return {"error": str(exc)}
    return {"dropped": True}


def _search(event: Dict[str, Any]) -> Dict[str, Any]:
    embedding: List[float] | None = event.get("embedding")
    if embedding is None:
        return {"matches": []}

    top_k = int(event.get("top_k", DEFAULT_TOP_K))
    collection = event.get("collection_name")
    client_obj = client if collection is None else MilvusClient(collection_name=collection)

    try:
        results = client_obj.search(embedding, top_k=top_k)
    except Exception:
        logger.exception("Milvus search failed")
        return {"matches": []}

    matches = [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in results]
    department = event.get("department")
    team = event.get("team")
    user = event.get("user")
    entities: List[str] | None = event.get("entities")
    file_guid = event.get("file_guid")
    file_name = event.get("file_name")
    if department or team or user or entities or file_guid or file_name:
        filtered = []
        for m in matches:
            md = m.get("metadata", {}) or {}
            if department and md.get("department") != department:
                continue
            if team and md.get("team") != team:
                continue
            if user and md.get("user") != user:
                continue
            if entities:
                chunk_ents = md.get("entities", []) or []
                if not any(e in chunk_ents for e in entities):
                    continue
            if file_guid and md.get("file_guid") != file_guid:
                continue
            if file_name and md.get("file_name") != file_name:
                continue
            filtered.append(m)
        matches = filtered
    return {"matches": matches}


def _hybrid_search(event: Dict[str, Any]) -> Dict[str, Any]:
    embedding = event.get("embedding")
    keywords: List[str] = event.get("keywords", [])
    top_k = int(event.get("top_k", DEFAULT_TOP_K))
    try:
        from pymilvus import Collection, connections

        connections.connect(alias="default", host=client.host, port=client.port)
        collection = Collection(client.collection_name)
        res = collection.search(
            [embedding],
            "embedding",
            {"metric_type": "L2"},
            limit=top_k,
            output_fields=["metadata"],
        )
        matches = [
            {"id": r.id, "score": r.distance, "metadata": r.entity.get("metadata")}
            for r in res[0]
        ]
        if keywords:
            filtered = []
            for m in matches:
                text = str(m.get("metadata", {}).get("text", "")).lower()
                if any(k.lower() in text for k in keywords):
                    filtered.append(m)
            matches = filtered
        return {"matches": matches[:top_k]}
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Milvus hybrid search failed")
        return {"error": str(exc), "matches": []}


_HANDLERS = {
    "insert": _insert,
    "delete": _delete,
    "update": _update,
    "create": _create,
    "drop": _drop,
    "search": _search,
    "hybrid-search": _hybrid_search,
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    op = (event.get("operation") or event.get("action") or "search").lower()
    handler = _HANDLERS.get(op)
    if not handler:
        return {"error": "unsupported operation"}
    return handler(event)
