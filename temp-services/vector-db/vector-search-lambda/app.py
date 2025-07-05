# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Search a Milvus collection using an embedding."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger

from typing import Any, Dict, List
from pydantic import BaseModel, ValidationError
import json

from common_utils import MilvusClient
from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))

client = MilvusClient()


class VectorSearchEvent(BaseModel):
    embedding: List[float] | None = None
    top_k: int = TOP_K
    collection_name: str | None = None
    department: str | None = None
    team: str | None = None
    user: str | None = None
    entities: List[str] | None = None
    file_guid: str | None = None
    file_name: str | None = None

    class Config:
        extra = "allow"


def _process_event(event: VectorSearchEvent) -> Dict[str, Any]:
    """Perform a vector similarity search.

    1. Uses the provided embedding to query Milvus for the top matching
       documents.
    2. Applies optional metadata filtering before returning the results.

    Returns a dictionary of match objects sorted by score.
    """

    embedding: List[float] | None = event.embedding
    if embedding is None:
        return {"matches": []}

    top_k = int(event.top_k)
    logger.info("Searching Milvus with top_k=%s", top_k)
    collection = event.collection_name
    client_obj = client if collection is None else MilvusClient(collection_name=collection)
    try:
        results = client_obj.search(embedding, top_k=top_k)
    except Exception:
        logger.exception("Milvus search failed")
        return {"matches": []}
    logger.info("Milvus returned %d results", len(results))
    matches = [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in results]

    department = event.department
    team = event.team
    user = event.user
    entities: List[str] | None = event.entities
    file_guid = event.file_guid
    file_name = event.file_name
    if department or team or user or entities or file_guid or file_name:
        logger.info(
            "Filtering %d matches by department=%s team=%s user=%s entities=%s",
            len(matches),
            department,
            team,
            user,
            entities,
        )
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
        logger.info("Filtered down to %d matches", len(matches))

    return {"matches": matches}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point supporting SQS events."""
    if "Records" in event:
        results = []
        for r in event["Records"]:
            try:
                ev = VectorSearchEvent.parse_obj(json.loads(r.get("body", "{}")))
            except ValidationError as exc:
                logger.error("Invalid event: %s", exc)
                results.append({"matches": []})
            else:
                results.append(_process_event(ev))
        return results
    try:
        ev = VectorSearchEvent.parse_obj(event)
    except ValidationError as exc:
        logger.error("Invalid event: %s", exc)
        return {"matches": []}
    return _process_event(ev)
