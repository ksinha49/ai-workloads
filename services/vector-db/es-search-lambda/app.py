# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Search an Elasticsearch index using a vector embedding."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict, List

from common_utils import ElasticsearchClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = ElasticsearchClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to perform a vector search against Elasticsearch.

    1. Uses the given embedding to query the index for similar documents.
    2. Limits the response to ``top_k`` results.

    Returns the list of matching documents.
    """

    embedding: List[float] | None = event.get("embedding")
    if embedding is None:
        return {"matches": []}

    top_k = int(event.get("top_k", 5))
    try:
        results = client.search(embedding, top_k=top_k)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Elasticsearch search failed")
        return {"error": str(exc), "matches": []}
    return {"matches": results}
