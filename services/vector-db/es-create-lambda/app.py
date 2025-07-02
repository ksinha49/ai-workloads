# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Create an Elasticsearch index if it does not exist."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict

from common_utils import ElasticsearchClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = ElasticsearchClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to provision an Elasticsearch index if absent.

    1. Calls the Elasticsearch client to create the index.

    Returns ``{"created": True}`` when the operation succeeds.
    """

    try:
        client.create_index()
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to create Elasticsearch index")
        return {"error": str(exc)}
    return {"created": True}
