# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Perform hybrid keyword and vector search against Elasticsearch."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict, Iterable, List

from common_utils import ElasticsearchClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = ElasticsearchClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to search Elasticsearch using vectors and keywords.

    1. Queries the index with the supplied embedding and optional keywords.
    2. Returns the combined relevance results limited to ``top_k``.

    Returns a dictionary containing the ``matches`` list.
    """

    embedding = event.get("embedding")
    if embedding is None:
        return {"matches": []}

    keywords: Iterable[str] = event.get("keywords", [])
    top_k = int(event.get("top_k", 5))
    try:
        results = client.hybrid_search(embedding, keywords=keywords, top_k=top_k)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Elasticsearch hybrid search failed")
        return {"error": str(exc), "matches": []}
    return {"matches": results}
