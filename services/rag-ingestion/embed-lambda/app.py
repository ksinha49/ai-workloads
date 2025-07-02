# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Embed text chunks using a configurable embedding provider."""

from __future__ import annotations

import os
import json
import logging
from common_utils import configure_logger

from typing import Any, Dict, List

from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

DEFAULT_EMBED_MODEL = (
    get_config("EMBED_MODEL") or os.environ.get("EMBED_MODEL", "sbert")
)
_MAP_RAW = get_config("EMBED_MODEL_MAP") or os.environ.get("EMBED_MODEL_MAP", "{}")
try:
    DEFAULT_EMBED_MODEL_MAP = json.loads(_MAP_RAW) if _MAP_RAW else {}
except json.JSONDecodeError:
    DEFAULT_EMBED_MODEL_MAP = {}


_SBERT_MODEL = None


def _sbert_embed(text: str) -> List[float]:
    """Embed ``text`` using a SentenceTransformer model."""

    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        model_path = (
            get_config("SBERT_MODEL")
            or os.environ.get("SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )
        if model_path.startswith("s3://"):
            import boto3
            from common_utils import parse_s3_uri

            bucket, key = parse_s3_uri(model_path)
            dest = os.path.join("/tmp", os.path.basename(key))
            boto3.client("s3").download_file(bucket, key, dest)
            model_path = dest

        from sentence_transformers import SentenceTransformer  # type: ignore

        _SBERT_MODEL = SentenceTransformer(model_path)

    return _SBERT_MODEL.encode([text])[0].tolist()


def _openai_embed(text: str) -> List[float]:
    """Embed ``text`` using the OpenAI API."""

    import openai  # type: ignore

    model = get_config("OPENAI_EMBED_MODEL") or os.environ.get(
        "OPENAI_EMBED_MODEL", "text-embedding-ada-002"
    )
    resp = openai.Embedding.create(input=[text], model=model)
    return resp["data"][0]["embedding"]


def _cohere_embed(text: str) -> List[float]:
    """Embed ``text`` using the Cohere API."""

    import cohere  # type: ignore

    api_key = get_config("COHERE_API_KEY", decrypt=True) or os.environ.get("COHERE_API_KEY")
    client = cohere.Client(api_key)
    resp = client.embed([text])
    return resp.embeddings[0]


_MODEL_MAP = {
    "sbert": _sbert_embed,
    "sentence": _sbert_embed,
    "openai": _openai_embed,
    "cohere": _cohere_embed,
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered by the ingestion workflow to embed text chunks.

    1. Selects an embedding model based on document type or configuration.
    2. Generates embeddings for each chunk and preserves any metadata.

    Returns the list of embeddings and corresponding metadata.
    """

    chunks = event.get("chunks", [])
    doc_type = event.get("docType") or event.get("type")
    file_guid = event.get("file_guid")
    file_name = event.get("file_name")
    embed_model = event.get("embedModel", DEFAULT_EMBED_MODEL)
    embed_map_raw = event.get("embedModelMap")
    try:
        embed_model_map = (
            json.loads(embed_map_raw) if embed_map_raw else DEFAULT_EMBED_MODEL_MAP
        )
    except json.JSONDecodeError:
        embed_model_map = DEFAULT_EMBED_MODEL_MAP

    embeddings: List[List[float]] = []
    metadatas: List[Any] = []
    for chunk in chunks:
        text = chunk
        meta = None
        c_type = doc_type
        if isinstance(chunk, dict):
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {})
            c_type = meta.get("docType") or meta.get("type") or c_type
        if file_guid:
            meta = dict(meta or {})
            meta.setdefault("file_guid", file_guid)
        if file_name:
            meta = dict(meta or {})
            meta.setdefault("file_name", file_name)
        model_name = embed_model_map.get(c_type, embed_model)
        embed_fn = _MODEL_MAP.get(model_name, _sbert_embed)
        try:
            embedding = embed_fn(text)
        except Exception as exc:  # pragma: no cover - dependency failures
            logger.exception("Embedding using model %s failed", model_name)
            return {"error": str(exc)}

        embeddings.append(embedding)
        metadatas.append(meta)

    return {"embeddings": embeddings, "metadatas": metadatas}

