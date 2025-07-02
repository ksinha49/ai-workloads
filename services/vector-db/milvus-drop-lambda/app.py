# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Drop a Milvus collection."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict

from common_utils import MilvusClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = MilvusClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to drop the entire Milvus collection.

    1. Invokes the client's ``drop_collection`` method.

    Returns ``{"dropped": True}`` when the collection has been removed.
    """

    try:
        client.drop_collection()
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to drop Milvus collection")
        return {"error": str(exc)}
    return {"dropped": True}
