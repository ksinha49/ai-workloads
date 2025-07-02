# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
"""Extract entities using text retrieved from vector search."""

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
ENTITIES_ENDPOINT = get_config("ENTITIES_ENDPOINT") or os.environ.get("ENTITIES_ENDPOINT")

lambda_client = boto3.client("lambda")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered during retrieval to extract entities from results.

    1. Runs a vector search via ``VECTOR_SEARCH_FUNCTION`` to gather context
       for the query.
    2. Posts the query and context to the configured entity extraction service.

    Returns a dictionary with the extracted entities.
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
        return {"entities": {}}
    logger.info("Vector search returned %d matches", len(result.get("matches", [])))
    context_text = " ".join(
        m.get("metadata", {}).get("text", "") for m in result.get("matches", [])
    )
    logger.info("Calling entity extraction service at %s", ENTITIES_ENDPOINT)
    try:
        r = httpx.post(ENTITIES_ENDPOINT, json={"query": query, "context": context_text})
        r.raise_for_status()
    except Exception:
        logger.exception("Entity extraction service request failed")
        return {"entities": {}}
    logger.info("Entity extraction service returned status %s", r.status_code)
    return {"entities": r.json()}

