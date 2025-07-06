"""Elasticsearch index operations handler."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

from common_utils import configure_logger, ElasticsearchClient

logger = configure_logger(__name__)

client = ElasticsearchClient()


def _insert(event: Dict[str, Any]) -> Dict[str, Any]:
    documents: Iterable[dict] = event.get("documents", [])
    try:
        inserted = client.insert(documents)
    except Exception:
        logger.exception("Failed to insert documents into Elasticsearch")
        return {"inserted": 0}
    return {"inserted": inserted}


def _delete(event: Dict[str, Any]) -> Dict[str, Any]:
    ids: Iterable[str] = event.get("ids", [])
    try:
        deleted = client.delete(ids)
    except Exception:
        logger.exception("Failed to delete from Elasticsearch")
        return {"deleted": 0}
    return {"deleted": deleted}


def _update(event: Dict[str, Any]) -> Dict[str, Any]:
    documents: Iterable[dict] = event.get("documents", [])
    try:
        updated = client.update(documents)
    except Exception:
        logger.exception("Failed to update documents in Elasticsearch")
        return {"updated": 0}
    return {"updated": updated}


def _create_index(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client.create_index()
    except Exception as exc:
        logger.exception("Failed to create Elasticsearch index")
        return {"error": str(exc)}
    return {"created": True}


def _drop_index(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client.drop_index()
    except Exception as exc:
        logger.exception("Failed to drop Elasticsearch index")
        return {"error": str(exc)}
    return {"dropped": True}


def _search(event: Dict[str, Any]) -> Dict[str, Any]:
    embedding: List[float] | None = event.get("embedding")
    if embedding is None:
        return {"matches": []}
    top_k = int(event.get("top_k", 5))
    try:
        results = client.search(embedding, top_k=top_k)
    except Exception as exc:
        logger.exception("Elasticsearch search failed")
        return {"error": str(exc), "matches": []}
    return {"matches": results}


def _hybrid_search(event: Dict[str, Any]) -> Dict[str, Any]:
    embedding = event.get("embedding")
    if embedding is None:
        return {"matches": []}
    keywords: Iterable[str] = event.get("keywords", [])
    top_k = int(event.get("top_k", 5))
    try:
        results = client.hybrid_search(embedding, keywords=keywords, top_k=top_k)
    except Exception as exc:
        logger.exception("Elasticsearch hybrid search failed")
        return {"error": str(exc), "matches": []}
    return {"matches": results}


_HANDLERS = {
    "insert": _insert,
    "delete": _delete,
    "update": _update,
    "create-index": _create_index,
    "drop-index": _drop_index,
    "search": _search,
    "hybrid-search": _hybrid_search,
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    op = (event.get("operation") or event.get("action") or "search").lower()
    handler = _HANDLERS.get(op)
    if not handler:
        return {"error": "unsupported operation"}
    return handler(event)
