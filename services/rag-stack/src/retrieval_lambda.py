# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Retrieve context from vector search results and forward the request.

Originally this handler only produced a summary. The implementation now
supports arbitrary payloads by forwarding the assembled context to an
external service via the RouteLLM router.
"""

from __future__ import annotations

import os
import json
import logging
from common_utils import configure_logger
from common_utils.error_utils import log_exception
import boto3
from routellm_integration import forward_to_routellm
import hashlib

from typing import Any, Dict
from pydantic import BaseModel, ValidationError

from common_utils.get_ssm import get_config
from common_utils.get_secret import get_secret

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

LAMBDA_FUNCTION = get_config("VECTOR_SEARCH_FUNCTION") or os.environ.get("VECTOR_SEARCH_FUNCTION")
RERANK_FUNCTION = get_config("RERANK_FUNCTION") or os.environ.get("RERANK_FUNCTION")
SEARCH_CANDIDATES = int(
    get_config("VECTOR_SEARCH_CANDIDATES")
    or os.environ.get("VECTOR_SEARCH_CANDIDATES", "5")
)
SUMMARY_ENDPOINT = get_config("SUMMARY_ENDPOINT") or os.environ.get("SUMMARY_ENDPOINT")
ROUTELLM_ENDPOINT = get_config("ROUTELLM_ENDPOINT") or os.environ.get("ROUTELLM_ENDPOINT")

lambda_client = boto3.client("lambda")


class RetrievalEvent(BaseModel):
    collection_name: str
    query: str | None = None
    embedding: list[float] | None = None
    embedModel: str | None = None
    department: str | None = None
    team: str | None = None
    user: str | None = None
    storage_mode: str | None = None

    class Config:
        extra = "allow"

DEFAULT_EMBED_MODEL = (
    get_config("EMBED_MODEL") or os.environ.get("EMBED_MODEL", "sbert")
)

_SBERT_MODEL = None


def _sbert_embed(text: str) -> list[float]:
    """Embed ``text`` using a SentenceTransformer model."""

    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        model_path = (
            get_config("SBERT_MODEL")
            or os.environ.get("SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )
        efs_dir = get_config("MODEL_EFS_PATH") or os.environ.get("MODEL_EFS_PATH")
        if efs_dir:
            candidate = os.path.join(efs_dir, os.path.basename(model_path))
            if os.path.exists(candidate):
                model_path = candidate
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


def _openai_embed(text: str) -> list[float]:
    """Embed ``text`` using the OpenAI API."""

    import openai  # type: ignore

    model = get_config("OPENAI_EMBED_MODEL") or os.environ.get(
        "OPENAI_EMBED_MODEL", "text-embedding-ada-002"
    )
    resp = openai.Embedding.create(input=[text], model=model)
    return resp["data"][0]["embedding"]


def _cohere_embed(text: str) -> list[float]:
    """Embed ``text`` using the Cohere API."""

    import cohere  # type: ignore

    secret = get_config("COHERE_SECRET_NAME") or os.environ.get(
        "COHERE_SECRET_NAME", "COHERE_API_KEY"
    )
    api_key = get_secret(secret)
    client = cohere.Client(api_key)
    resp = client.embed([text])
    return resp.embeddings[0]


_MODEL_MAP = {
    "sbert": _sbert_embed,
    "sentence": _sbert_embed,
    "openai": _openai_embed,
    "cohere": _cohere_embed,
}


def _simple_embed(text: str) -> list[float]:
    """Generate a deterministic embedding for ``text``."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255 for b in digest[:32]]


def _embed_query(text: str, model: str | None = None) -> list[float]:
    """Return an embedding for ``text`` using the configured model."""

    model_name = model or DEFAULT_EMBED_MODEL
    embed_fn = _MODEL_MAP.get(model_name, _sbert_embed)
    try:
        return embed_fn(text)
    except Exception:  # pragma: no cover - fallback for missing deps
        logger.exception("Embedding failed, using simple embedding")
        return _simple_embed(text)


def _process_event(event: RetrievalEvent) -> Dict[str, Any]:
    """Handle a single retrieval request.

    1. Performs a vector search (and optional re-ranking) to gather context for
       the query.
    2. Forwards the request and context to an external service via the router.

    Returns the service response in a ``result`` field.
    """

    if event.collection_name is None:
        raise ValueError("collection_name missing from event")

    query = event.query
    emb = event.embedding
    if emb is None and query:
        logger.info("Embedding query using model %s", event.embedModel)
        emb = _embed_query(query, event.embedModel)
    search_payload = {"embedding": emb} if emb is not None else {}
    if RERANK_FUNCTION:
        search_payload["top_k"] = SEARCH_CANDIDATES
    for key in ("department", "team", "user"):
        val = getattr(event, key)
        if val is not None:
            search_payload[key] = val
    search_payload["collection_name"] = event.collection_name
    search_payload["operation"] = "search"
    if event.storage_mode:
        search_payload["storage_mode"] = event.storage_mode
    logger.info(
        "Invoking vector search function %s with payload %s",
        LAMBDA_FUNCTION,
        search_payload,
    )
    try:
        resp = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            Payload=json.dumps(search_payload).encode("utf-8"),
        )
        result = json.loads(resp["Payload"].read())
    except Exception as exc:
        log_exception("Vector search invocation failed", exc, logger)
        return {"result": {}}
    logger.info("Vector search returned %d matches", len(result.get("matches", [])))
    matches = result.get("matches", [])
    if RERANK_FUNCTION and query:
        rerank_payload = {"query": query, "matches": matches, "top_k": SEARCH_CANDIDATES}
        logger.info("Invoking rerank function %s with %d candidates", RERANK_FUNCTION, len(matches))
        try:
            rresp = lambda_client.invoke(
                FunctionName=RERANK_FUNCTION,
                Payload=json.dumps(rerank_payload).encode("utf-8"),
            )
            matches = json.loads(rresp["Payload"].read()).get("matches", matches)
        except Exception as exc:
            log_exception("Rerank invocation failed", exc, logger)
    logger.info("Using %d matches after rerank", len(matches))
    context_text = " ".join(
        m.get("metadata", {}).get("text", "") for m in matches
    )
    router_payload = {
        k: v
        for k, v in event.model_dump().items()
        if k != "embedding" and v is not None
    }
    router_payload["context"] = context_text
    logger.info("Forwarding payload to router at %s", ROUTELLM_ENDPOINT)
    try:
        response = forward_to_routellm(router_payload)
    except Exception as exc:
        log_exception("RouterLLM request failed", exc, logger)
        return {"result": {}}
    logger.info("Router returned payload keys: %s", list(response.keys()))
    return {"result": response}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point handling both direct and SQS invocations."""
    if "Records" in event:
        results = []
        for r in event["Records"]:
            try:
                ev = RetrievalEvent.parse_obj(json.loads(r.get("body", "{}")))
            except ValidationError as exc:
                log_exception("Invalid event", exc, logger)
                results.append({"result": {}})
            else:
                results.append(_process_event(ev))
        return results
    try:
        ev = RetrievalEvent.parse_obj(event)
    except ValidationError as exc:
        log_exception("Invalid event", exc, logger)
        return {"result": {}}
    return _process_event(ev)

