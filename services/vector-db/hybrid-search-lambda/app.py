# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Perform hybrid keyword and vector search against Milvus."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger
from typing import Any, Dict, List

from pymilvus import Collection, connections

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

HOST = get_config("MILVUS_HOST") or os.environ.get("MILVUS_HOST", "localhost")
PORT = int(get_config("MILVUS_PORT") or os.environ.get("MILVUS_PORT", "19530"))
COLLECTION_NAME = get_config("MILVUS_COLLECTION") or os.environ.get("MILVUS_COLLECTION", "docs")
TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))

connections.connect(alias="default", host=HOST, port=PORT)
collection = Collection(COLLECTION_NAME)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered to run a hybrid keyword and vector search.

    1. Searches Milvus with the provided embedding and retrieves the top
       matches.
    2. Optionally filters the results by keywords before returning them.

    Returns the best matches up to ``top_k`` entries.
    """

    embedding = event.get("embedding")
    keywords: List[str] = event.get("keywords", [])
    top_k = int(event.get("top_k", TOP_K))
    res = collection.search(
        [embedding],
        "embedding",
        {"metric_type": "L2"},
        limit=top_k,
        output_fields=["metadata"],
    )
    matches = [
        {"id": r.id, "score": r.distance, "metadata": r.entity.get("metadata")}
        for r in res[0]
    ]
    if keywords:
        filtered = []
        for m in matches:
            text = str(m.get("metadata", {}).get("text", "")).lower()
            if any(k.lower() in text for k in keywords):
                filtered.append(m)
        matches = filtered

    return {"matches": matches[:top_k]}

