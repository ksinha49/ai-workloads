# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Split large text into overlapping chunks."""

from __future__ import annotations

import os
import json
import logging
from common_utils import configure_logger
from chunking import UniversalFileChunker

from typing import Any, Dict, Iterable, List

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
DEFAULT_CHUNK_STRATEGY = (
    get_config("CHUNK_STRATEGY") or os.environ.get("CHUNK_STRATEGY", "simple")
)
_MAP_RAW = get_config("CHUNK_STRATEGY_MAP") or os.environ.get("CHUNK_STRATEGY_MAP", "{}")
try:
    DEFAULT_CHUNK_STRATEGY_MAP = json.loads(_MAP_RAW) if _MAP_RAW else {}
except json.JSONDecodeError:
    DEFAULT_CHUNK_STRATEGY_MAP = {}
EXTRACT_ENTITIES = (
    get_config("EXTRACT_ENTITIES") or os.environ.get("EXTRACT_ENTITIES", "false")
).lower() == "true"


def _iter_paragraphs(text: str) -> Iterable[str]:
    """Yield paragraphs from ``text`` one at a time."""

    import re

    start = 0
    for match in re.finditer(r"\n\s*\n", text):
        para = text[start : match.start()].strip()
        if para:
            yield para
        start = match.end()
    tail = text[start:].strip()
    if tail:
        yield tail


def chunk_text(text: str, chunk_size: int, overlap: int) -> Iterable[str]:
    """Yield ``text`` in chunks using paragraph and sentence boundaries.

    ``overlap`` only applies when a single sentence exceeds ``chunk_size`` and we
    fall back to character-based splitting.
    """

    import re

    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size

    for para in _iter_paragraphs(text):
        current = ""
        # Split paragraph into sentences. This is a heuristic but avoids an
        # external dependency.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        for s in sentences:
            if len(s) > chunk_size:
                # Flush any accumulated chunk before falling back to character
                # based splitting for very long sentences.
                if current:
                    yield current
                    current = ""
                for i in range(0, len(s), step):
                    yield s[i : i + chunk_size]
                continue

            if not current:
                current = s
            elif len(current) + len(s) + 1 <= chunk_size:
                current = f"{current} {s}"
            else:
                yield current
                current = s
        if current:
            yield current


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

    strategy = event.get("chunkStrategy", DEFAULT_CHUNK_STRATEGY)
    map_raw = event.get("chunkStrategyMap")
    try:
        strategy_map = (
            json.loads(map_raw) if map_raw else DEFAULT_CHUNK_STRATEGY_MAP
        )
    except json.JSONDecodeError:
        strategy_map = DEFAULT_CHUNK_STRATEGY_MAP
    resolved = strategy_map.get(doc_type, strategy)

    if resolved == "universal":
        file_chunks = UniversalFileChunker(chunk_size, overlap).chunk(
            text, file_name
        )
        chunks = [fc.text for fc in file_chunks]
    else:
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
