# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Update documents in an Elasticsearch index."""

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
    """Triggered to update existing Elasticsearch documents.

    1. Updates the documents supplied in ``documents`` using the client.

    Returns the number of documents updated.
    """

    documents: Iterable[dict] = event.get("documents", [])
    try:
        updated = client.update(documents)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to update documents in Elasticsearch")
        return {"error": str(exc)}
    return {"updated": updated}
