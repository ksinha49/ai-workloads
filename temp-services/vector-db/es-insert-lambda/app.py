# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Insert documents into an Elasticsearch index."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict, Iterable

from common_utils import ElasticsearchClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = ElasticsearchClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to index new documents in Elasticsearch.

    1. Inserts the ``documents`` list into the configured index.

    Returns a count of how many documents were inserted.
    """

    documents: Iterable[dict] = event.get("documents", [])
    try:
        inserted = client.insert(documents)
    except Exception:  # pragma: no cover - runtime safety
        logger.exception("Failed to insert documents into Elasticsearch")
        return {"inserted": 0}
    return {"inserted": inserted}
