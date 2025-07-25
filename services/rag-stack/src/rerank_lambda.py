"""Re-rank vector search results using a configurable rerank provider."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from typing import Any, Dict, List, Callable
from pydantic import BaseModel, ValidationError
import json

from common_utils.get_ssm import get_config
from common_utils.get_secret import get_secret

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))
DEFAULT_MODEL = get_config("CROSS_ENCODER_MODEL") or os.environ.get(
    "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
# Optional EFS path to load the cross encoder without downloading from S3
EFS_MODEL_PATH = get_config("CROSS_ENCODER_EFS_PATH") or os.environ.get(
    "CROSS_ENCODER_EFS_PATH"
)
# RERANK_PROVIDER selects the rerank provider (e.g. cohere, nvidia).
DEFAULT_PROVIDER = (
    get_config("RERANK_PROVIDER") or os.environ.get("RERANK_PROVIDER", "huggingface")
)

_CE_MODEL = None


class RerankEvent(BaseModel):
    query: str = ""
    matches: List[Dict[str, Any]] = []
    top_k: int = TOP_K

    class Config:
        extra = "allow"


def _hf_score_pairs(query: str, docs: List[str]) -> List[float]:
    """Score using a HuggingFace cross encoder."""

    model = _load_model()
    if model is None:
        return [0.0] * len(docs)
    try:
        scores = model.predict([(query, d) for d in docs])
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        return [float(s) for s in scores]
    except Exception:  # pragma: no cover - fallback when prediction fails
        logger.exception("Cross encoder prediction failed")
        return [0.0] * len(docs)


def _cohere_rerank(query: str, docs: List[str]) -> List[float]:
    """Score documents using the Cohere rerank API."""

    import cohere  # type: ignore

    secret = get_config("COHERE_SECRET_NAME") or os.environ.get(
        "COHERE_SECRET_NAME", "COHERE_API_KEY"
    )
    api_key = get_secret(secret)
    client = cohere.Client(api_key)
    try:
        resp = client.rerank(query=query, documents=docs, top_n=len(docs))
        return [float(r.relevance_score) for r in resp]
    except Exception:  # pragma: no cover - network or dependency issues
        logger.exception("Cohere rerank failed")
        return [0.0] * len(docs)


def _nvidia_rerank(query: str, docs: List[str]) -> List[float]:
    """Score documents using an NVIDIA service."""

    import httpx  # type: ignore

    endpoint = get_config("NVIDIA_RERANK_ENDPOINT") or os.environ.get(
        "NVIDIA_RERANK_ENDPOINT"
    )
    n_secret = get_config("NVIDIA_SECRET_NAME") or os.environ.get(
        "NVIDIA_SECRET_NAME", "NVIDIA_API_KEY"
    )
    api_key = get_secret(n_secret)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    payload = {"query": query, "documents": docs}
    try:
        resp = httpx.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [float(s) for s in data.get("scores", [])]
    except HTTPError:  # pragma: no cover - network or dependency issues
        logger.exception("NVIDIA rerank failed")
        return [0.0] * len(docs)


def _load_model():
    """Return a :class:`CrossEncoder` model, downloading it on first use."""

    global _CE_MODEL
    if _CE_MODEL is not None:
        return _CE_MODEL
    model_path = EFS_MODEL_PATH or DEFAULT_MODEL
    if not EFS_MODEL_PATH:
        base = get_config("MODEL_EFS_PATH") or os.environ.get("MODEL_EFS_PATH")
        if base:
            candidate = os.path.join(base, os.path.basename(DEFAULT_MODEL))
            if os.path.exists(candidate):
                model_path = candidate
    try:
        if model_path.startswith("s3://"):
            import boto3
            from common_utils import parse_s3_uri

            bucket, key = parse_s3_uri(model_path)
            dest = os.path.join("/tmp", os.path.basename(key))
            boto3.client("s3").download_file(bucket, key, dest)
            model_path = dest
        from sentence_transformers import CrossEncoder  # type: ignore

        _CE_MODEL = CrossEncoder(model_path)
    except Exception:  # pragma: no cover - fallback when deps missing
        logger.exception("Failed to load cross encoder")
        _CE_MODEL = None
    return _CE_MODEL


_PROVIDER_MAP: Dict[str, Callable[[str, List[str]], List[float]]] = {
    "huggingface": _hf_score_pairs,
    "cohere": _cohere_rerank,
    "nvidia": _nvidia_rerank,
}


def _score_pairs(query: str, docs: List[str]) -> List[float]:
    """Score each document for *query* using the selected rerank provider."""

    provider = DEFAULT_PROVIDER.lower()
    score_fn = _PROVIDER_MAP.get(provider, _hf_score_pairs)
    return score_fn(query, docs)


def _process_event(event: RerankEvent) -> Dict[str, Any]:
    """Re-rank vector search results.

    1. Scores each match against the query using the configured rerank provider.
    2. Sorts the matches by score and trims the list to ``top_k`` entries.

    Returns the re-ranked matches in descending order.
    """

    query = event.query or ""
    matches: List[Dict[str, Any]] = event.matches
    top_k = int(event.top_k)
    logger.info("Re-ranking %d matches with top_k=%s", len(matches), top_k)
    texts = [m.get("metadata", {}).get("text", "") for m in matches]
    scores = _score_pairs(query, texts) if query else [0.0] * len(matches)
    reranked = [
        {**m, "rerank_score": scores[i] if i < len(scores) else 0.0}
        for i, m in enumerate(matches)
    ]
    reranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    logger.info("Returning %d re-ranked matches", min(len(reranked), top_k))
    return {"matches": reranked[:top_k]}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point supporting SQS events."""
    if "Records" in event:
        results = []
        for r in event["Records"]:
            try:
                ev = RerankEvent.parse_obj(json.loads(r.get("body", "{}")))
            except ValidationError as exc:
                logger.error("Invalid event: %s", exc)
                results.append({"matches": []})
            else:
                results.append(_process_event(ev))
        return results
    try:
        ev = RerankEvent.parse_obj(event)
    except ValidationError as exc:
        logger.error("Invalid event: %s", exc)
        return {"matches": []}
    return _process_event(ev)
