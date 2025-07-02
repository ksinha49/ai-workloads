# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Insert embeddings into a Milvus collection."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger
from typing import Any, List

from common_utils import MilvusClient, VectorItem
from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

UPSERT = (get_config("MILVUS_UPSERT") or os.environ.get("MILVUS_UPSERT", "true")).lower() == "true"

client = MilvusClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to add embeddings to Milvus.

    1. Creates ``VectorItem`` objects for each embedding and optional metadata.
    2. Inserts the items using ``upsert`` behaviour if configured.

    Returns the number of vectors inserted.
    """

    embeddings: List[List[float]] = event.get("embeddings", [])
    metadatas: List[Any] = event.get("metadatas", [])
    ids = event.get("ids") or []

    items: List[VectorItem] = []
    for idx, embedding in enumerate(embeddings):
        metadata = metadatas[idx] if idx < len(metadatas) else None
        item_id = ids[idx] if idx < len(ids) else None
        items.append(VectorItem(embedding=embedding, metadata=metadata, id=item_id))

    inserted = client.insert(items, upsert=UPSERT)
    return {"inserted": inserted}

