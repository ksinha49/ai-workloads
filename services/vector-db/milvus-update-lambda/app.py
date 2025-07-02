# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Update records in a Milvus collection."""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict, Iterable, List

from common_utils import MilvusClient, VectorItem

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

client = MilvusClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to update vectors in Milvus.

    1. Builds ``VectorItem`` objects from the provided embeddings, metadata and
       IDs.
    2. Calls the client's ``update`` method to overwrite existing vectors.

    Returns the count of vectors updated.
    """

    embeddings: List[List[float]] = event.get("embeddings", [])
    metadatas: List[Any] = event.get("metadatas", [])
    ids: Iterable[int] = event.get("ids", [])

    items: List[VectorItem] = []
    for idx, embedding in enumerate(embeddings):
        metadata = metadatas[idx] if idx < len(metadatas) else None
        item_id = ids[idx] if idx < len(ids) else None
        items.append(VectorItem(embedding=embedding, metadata=metadata, id=item_id))

    updated = client.update(items)
    return {"updated": updated}
