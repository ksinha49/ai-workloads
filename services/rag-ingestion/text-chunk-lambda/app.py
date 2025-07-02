# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Split large text into overlapping chunks."""

from __future__ import annotations

import os
import json
import logging
from common_utils import configure_logger

from typing import Any, Dict, List

from common_utils.get_ssm import get_config
from common_utils import extract_entities

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

try:
    DEFAULT_CHUNK_SIZE = int(
        get_config("CHUNK_SIZE") or os.environ.get("CHUNK_SIZE", "1000")
    )
except ValueError:
    logger.error("Invalid CHUNK_SIZE value - using default 1000")
    DEFAULT_CHUNK_SIZE = 1000

try:
    DEFAULT_CHUNK_OVERLAP = int(
        get_config("CHUNK_OVERLAP") or os.environ.get("CHUNK_OVERLAP", "100")
    )
except ValueError:
    logger.error("Invalid CHUNK_OVERLAP value - using default 100")
    DEFAULT_CHUNK_OVERLAP = 100
EXTRACT_ENTITIES = (
    get_config("EXTRACT_ENTITIES") or os.environ.get("EXTRACT_ENTITIES", "false")
).lower() == "true"


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split ``text`` using ``chunk_size`` and ``overlap``."""

    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered by API or workflow requests to split text.

    1. Splits the input text into overlapping chunks and optionally extracts
       entities from each chunk.
    2. Packages the chunks and metadata for the embedding step.

    Returns a dictionary containing the chunk list.
    """

    text = event.get("text", "")
    doc_type = event.get("docType") or event.get("type")
    metadata = event.get("metadata", {})
    file_guid = event.get("file_guid")
    file_name = event.get("file_name")
    chunk_size = event.get("chunk_size", DEFAULT_CHUNK_SIZE)
    try:
        chunk_size = int(chunk_size)
    except ValueError:
        logger.error(
            "Invalid chunk_size %s - falling back to default %s",
            chunk_size,
            DEFAULT_CHUNK_SIZE,
        )
        chunk_size = DEFAULT_CHUNK_SIZE

    overlap = event.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
    try:
        overlap = int(overlap)
    except ValueError:
        logger.error(
            "Invalid chunk_overlap %s - falling back to default %s",
            overlap,
            DEFAULT_CHUNK_OVERLAP,
        )
        overlap = DEFAULT_CHUNK_OVERLAP
    chunks = chunk_text(text, chunk_size, overlap)
    chunk_list = []
    for c in chunks:
        meta = {**metadata}
        if doc_type:
            meta["docType"] = doc_type
        if file_guid:
            meta["file_guid"] = file_guid
        if file_name:
            meta["file_name"] = file_name
        chunk_list.append({"text": c, "metadata": meta})
    if EXTRACT_ENTITIES:
        for idx, chunk in enumerate(chunk_list):
            try:
                ents = extract_entities(chunk["text"])
            except Exception:  # pragma: no cover - runtime safety
                logger.exception("extract_entities failed for chunk %s", idx)
                continue
            if ents:
                chunk.setdefault("metadata", {})["entities"] = ents
    payload: Dict[str, Any] = {"chunks": chunk_list}
    if doc_type:
        payload["docType"] = doc_type
    if metadata:
        payload["metadata"] = metadata
    return payload
