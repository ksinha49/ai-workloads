# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Search a Milvus collection using an embedding."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger

from typing import Any, Dict, List

from common_utils import MilvusClient
from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))

client = MilvusClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to perform a vector similarity search.

    1. Uses the provided embedding to query Milvus for the top matching
       documents.
    2. Applies optional metadata filtering before returning the results.

    Returns a dictionary of match objects sorted by score.
    """

    embedding: List[float] | None = event.get("embedding")
    if embedding is None:
        return {"matches": []}

    top_k = int(event.get("top_k", TOP_K))
    logger.info("Searching Milvus with top_k=%s", top_k)
    try:
        results = client.search(embedding, top_k=top_k)
    except Exception:
        logger.exception("Milvus search failed")
        return {"matches": []}
    logger.info("Milvus returned %d results", len(results))
    matches = [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in results]

    department = event.get("department")
    team = event.get("team")
    user = event.get("user")
    entities: List[str] | None = event.get("entities")
    if department or team or user or entities:
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
            filtered.append(m)
        matches = filtered
        logger.info("Filtered down to %d matches", len(matches))

    return {"matches": matches}
