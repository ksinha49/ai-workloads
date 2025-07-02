# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Delete records from a Milvus collection by ID."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict, Iterable

from common_utils import MilvusClient

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = MilvusClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to remove items from a Milvus collection.

    1. Deletes the vector IDs listed in ``ids`` using the Milvus client.

    Returns a dictionary reporting how many items were deleted.
    """

    ids: Iterable[int] = event.get("ids", [])
    try:
        deleted = client.delete(ids)
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.exception("Failed to delete from Milvus")
        return {"error": str(exc)}
    return {"deleted": deleted}
