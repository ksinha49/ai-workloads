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

from typing import Any, Dict

from common_utils.get_ssm import get_config

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

LAMBDA_FUNCTION = get_config("VECTOR_SEARCH_FUNCTION") or os.environ.get("VECTOR_SEARCH_FUNCTION")
CONTENT_ENDPOINT = get_config("CONTENT_ENDPOINT") or os.environ.get("CONTENT_ENDPOINT")

lambda_client = boto3.client("lambda")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered during retrieval to fetch structured content.

    1. Performs a vector search using ``VECTOR_SEARCH_FUNCTION`` and gathers the
       text from the returned matches.
    2. Sends the query and context to the external content service.

    Returns the service response in a ``content`` field.
    """

    query = event.get("query")
    emb = event.get("embedding")
    logger.info("Invoking vector search function %s", LAMBDA_FUNCTION)
    try:
        resp = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            Payload=json.dumps({"embedding": emb}).encode("utf-8"),
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
    except Exception:
        logger.exception("Content service request failed")
        return {"content": {}}
    logger.info("Content service returned status %s", r.status_code)
    return {"content": r.json()}

