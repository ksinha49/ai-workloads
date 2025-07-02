# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  Simple router Lambda that directs prompts to either a Bedrock
  OpenAI-compatible endpoint or an Ollama endpoint based on prompt
  complexity.
Version: 1.0.0
"""

from __future__ import annotations

import logging
from common_utils import configure_logger
import os
from typing import Any, Dict

import json
from main_router import route_event

import boto3

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

INVOCATION_FUNCTION = os.environ.get("LLM_INVOCATION_FUNCTION")
lambda_client = boto3.client("lambda")

DEFAULT_PROMPT_COMPLEXITY_THRESHOLD = 20
PROMPT_COMPLEXITY_THRESHOLD = int(
    os.environ.get("PROMPT_COMPLEXITY_THRESHOLD", str(DEFAULT_PROMPT_COMPLEXITY_THRESHOLD))
)
def _choose_backend(prompt: str) -> str:
    """Return which backend to use based on prompt complexity."""
    complexity = len(prompt.split())
    if complexity >= PROMPT_COMPLEXITY_THRESHOLD:
        return "bedrock"
    return "ollama"


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered by HTTP or Lambda invocations to route LLM prompts.

    1. Parses the request payload and chooses a backend based on the provided
       strategy or prompt complexity.
    2. Invokes the LLM invocation Lambda with the selected backend.

    Returns the backend response wrapped in an HTTP style object.
    """
    body_content = event.get("body")
    if body_content is not None:
        try:
            payload = json.loads(body_content or "{}")
        except json.JSONDecodeError:
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid JSON"})}
    else:
        payload = dict(event)

    if not payload.get("prompt"):
        return {"statusCode": 400, "body": json.dumps({"message": "Missing 'prompt'"})}

    backend = payload.get("backend")
    strategy = payload.get("strategy")

    if not backend:
        if strategy and strategy != "complexity":
            logger.info("Strategy '%s' not implemented, using complexity", strategy)
        backend = route_event(payload).get("backend")

    if not INVOCATION_FUNCTION:
        raise RuntimeError("LLM_INVOCATION_FUNCTION not configured")

    request_payload = dict(payload)
    request_payload["backend"] = backend
    request_payload.pop("strategy", None)

    try:
        resp = lambda_client.invoke(
            FunctionName=INVOCATION_FUNCTION,
            Payload=json.dumps(request_payload).encode("utf-8"),
        )
        data = json.loads(resp["Payload"].read())
        data["backend"] = backend
        return {"statusCode": 200, "body": json.dumps(data)}
    except Exception:  # pragma: no cover - unexpected invocation error
        logger.exception("Unexpected error in router lambda")
        raise


