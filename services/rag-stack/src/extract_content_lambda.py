# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Call a content extraction service using search results as context."""

from __future__ import annotations

import os
import json
import logging
from common_utils import configure_logger
import boto3
import httpx
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass

from typing import Any, Dict
import json

from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

LAMBDA_FUNCTION = get_config("VECTOR_SEARCH_FUNCTION") or os.environ.get("VECTOR_SEARCH_FUNCTION")
CONTENT_ENDPOINT = get_config("CONTENT_ENDPOINT") or os.environ.get("CONTENT_ENDPOINT")

lambda_client = boto3.client("lambda")


def _process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch structured content from context.

    1. Performs a vector search using ``VECTOR_SEARCH_FUNCTION`` and gathers the
       text from the returned matches.
    2. Sends the query and context to the external content service.

    Returns the service response in a ``content`` field.
    """

    query = event.get("query")
    emb = event.get("embedding")
    logger.info("Invoking vector search function %s", LAMBDA_FUNCTION)
    try:
        payload = {"embedding": emb, "operation": "search"}
        storage_mode = event.get("storage_mode")
        if storage_mode:
            payload["storage_mode"] = storage_mode
        resp = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            Payload=json.dumps(payload).encode("utf-8"),
        )
        result = json.loads(resp["Payload"].read())
    except Exception:
        logger.exception("Vector search invocation failed")
        return {"content": {}}
    logger.info("Vector search returned %d matches", len(result.get("matches", [])))
    context_text = " ".join(
        m.get("metadata", {}).get("text", "") for m in result.get("matches", [])
    )
    logger.info("Calling content service at %s", CONTENT_ENDPOINT)
    try:
        r = httpx.post(CONTENT_ENDPOINT, json={"query": query, "context": context_text})
        r.raise_for_status()
    except HTTPError as exc:
        logger.exception("Content service request failed")
        return {"content": {}, "error": str(exc)}
    logger.info("Content service returned status %s", r.status_code)
    return {"content": r.json()}


def lambda_handler(event: Dict[str, Any], context: Any) -> Any:
    """Entry point supporting SQS events."""
    if "Records" in event:
        return [
            _process_event(json.loads(r.get("body", "{}"))) for r in event["Records"]
        ]
    return _process_event(event)

