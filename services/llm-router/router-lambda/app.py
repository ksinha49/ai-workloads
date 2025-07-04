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
import os
import re
from typing import Any, Dict

import boto3
import json
from common_utils import configure_logger
from models import LlmRouterEvent, LambdaResponse
from main_router import route_event
from predictive_router import invoke_classifier

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

INVOCATION_QUEUE_URL = os.environ.get("INVOCATION_QUEUE_URL")
sqs_client = boto3.client("sqs")

DEFAULT_PROMPT_COMPLEXITY_THRESHOLD = 20
PROMPT_COMPLEXITY_THRESHOLD = int(
    os.environ.get("PROMPT_COMPLEXITY_THRESHOLD", str(DEFAULT_PROMPT_COMPLEXITY_THRESHOLD))
)

# allowlist of permitted backends
ALLOWED_BACKENDS = {"bedrock", "ollama"}
# maximum prompt length accepted by the router
MAX_PROMPT_LENGTH = int(os.environ.get("MAX_PROMPT_LENGTH", "4096"))


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize the incoming payload."""

    # optionally validate payload structure if jsonschema is available
    schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "backend": {"type": "string"},
            "strategy": {"type": "string"},
        },
        "required": ["prompt"],
    }
    try:  # pragma: no cover - jsonschema may not be installed
        from jsonschema import validate, ValidationError

        try:
            validate(instance=payload, schema=schema)
        except ValidationError as exc:
            raise ValueError(f"invalid payload: {exc.message}") from exc
    except Exception:
        pass

    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError("prompt too long")
    if payload.get("backend") and payload["backend"] not in ALLOWED_BACKENDS:
        raise ValueError("unsupported backend")

    # Strip non-printable characters that could be used for injection
    safe = re.sub(r"[^\x20-\x7E]+", "", prompt)
    # Remove characters commonly used in injection attacks
    safe = re.sub(r"[<>\"']", "", safe)
    payload["prompt"] = safe
    return payload
def _choose_backend(prompt: str) -> str:
    """Return which backend to use based on prompt complexity."""
    classifier_model = os.environ.get("CLASSIFIER_MODEL_ID") or os.environ.get("WEAK_MODEL_ID")
    if classifier_model:
        try:
            result = invoke_classifier(boto3.client("lambda"), classifier_model, prompt)
            if result == "complex":
                return "bedrock"
            if result == "simple":
                return "ollama"
        except Exception as exc:  # pragma: no cover - ML model failure
            logger.exception("Classifier error: %s", exc)

    complexity = len(prompt.split())
    if complexity >= PROMPT_COMPLEXITY_THRESHOLD:
        return "bedrock"
    return "ollama"


def lambda_handler(event: LlmRouterEvent, context: Any) -> LambdaResponse:
    """Triggered by HTTP or Lambda invocations to route LLM prompts.

    Parameters
    ----------
    event : :class:`models.LlmRouterEvent`
        Incoming API Gateway or direct invocation payload.

    The function parses ``event.body`` as JSON, selects a backend based on the
    configured strategy and forwards the request to the invocation Lambda.

    Returns
    -------
    :class:`models.LambdaResponse`
        Backend response wrapped in an HTTP style object.
    """
    body_content = event.body if hasattr(event, "body") else event.get("body")
    if body_content is not None:
        try:
            payload = json.loads(body_content or "{}")
        except json.JSONDecodeError:
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid JSON"})}
    else:
        try:
            from dataclasses import asdict
            payload = asdict(event)
        except TypeError:
            payload = dict(event)

    if not payload.get("prompt"):
        return {"statusCode": 400, "body": json.dumps({"message": "Missing 'prompt'"})}
    try:
        payload = _sanitize_payload(payload)
    except ValueError as exc:
        return {"statusCode": 400, "body": json.dumps({"message": str(exc)})}

    backend = payload.get("backend")
    strategy = payload.get("strategy")

    if not backend:
        if strategy and strategy != "complexity":
            logger.info("Strategy '%s' not implemented, using complexity", strategy)
        backend = route_event(payload).get("backend")

    if not INVOCATION_QUEUE_URL:
        raise RuntimeError("INVOCATION_QUEUE_URL not configured")

    request_payload = dict(payload)
    request_payload["backend"] = backend
    request_payload.pop("strategy", None)

    try:
        sqs_client.send_message(
            QueueUrl=INVOCATION_QUEUE_URL,
            MessageBody=json.dumps(request_payload),
        )
    except Exception as exc:  # pragma: no cover - queue failure
        logger.exception("Error queueing LLM invocation")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }

    return {
        "statusCode": 202,
        "body": json.dumps({"backend": backend, "queued": True}),
    }


