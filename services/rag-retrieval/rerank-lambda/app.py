"""Re-rank vector search results using a cross-encoder."""

from __future__ import annotations

import os
import logging
from common_utils import configure_logger
from typing import Any, Dict, List
import json

from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

TOP_K = int(get_config("TOP_K") or os.environ.get("TOP_K", "5"))
DEFAULT_MODEL = get_config("CROSS_ENCODER_MODEL") or os.environ.get(
    "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

_CE_MODEL = None


def _load_model():
    """Return a :class:`CrossEncoder` model, downloading it on first use."""

    global _CE_MODEL
    if _CE_MODEL is not None:
        return _CE_MODEL
    model_path = DEFAULT_MODEL
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


def _score_pairs(query: str, docs: List[str]) -> List[float]:
    """Score each document for *query* using the loaded cross encoder."""

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


def _process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Re-rank vector search results.

    1. Scores each match against the query using a cross-encoder model.
    2. Sorts the matches by score and trims the list to ``top_k`` entries.

    Returns the re-ranked matches in descending order.
    """

    query = event.get("query") or ""
    matches: List[Dict[str, Any]] = event.get("matches", [])
    top_k = int(event.get("top_k", TOP_K))
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
        return [
            _process_event(json.loads(r.get("body", "{}"))) for r in event["Records"]
        ]
    return _process_event(event)
