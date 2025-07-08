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
try:  # pragma: no cover - optional dependency
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - allow import without botocore
    BotoCoreError = ClientError = Exception  # type: ignore
import json
from common_utils import configure_logger, get_config
from models import LlmRouterEvent, LambdaResponse
from main_router import route_event
from predictive_router import invoke_classifier

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

INVOCATION_QUEUE_URL = get_config("INVOCATION_QUEUE_URL") or os.environ.get(
    "INVOCATION_QUEUE_URL"
)
sqs_client = boto3.client("sqs")

DEFAULT_PROMPT_COMPLEXITY_THRESHOLD = 20
PROMPT_COMPLEXITY_THRESHOLD = int(
    get_config("PROMPT_COMPLEXITY_THRESHOLD")
    or os.environ.get("PROMPT_COMPLEXITY_THRESHOLD", str(DEFAULT_PROMPT_COMPLEXITY_THRESHOLD))
)

# allowlist of permitted backends
DEFAULT_ALLOWED_BACKENDS = {"bedrock", "ollama"}
_raw_backends = get_config("ALLOWED_BACKENDS") or os.environ.get("ALLOWED_BACKENDS")
if not _raw_backends:
    try:  # pragma: no cover - SSM may be unavailable in tests
        _raw_backends = get_config("ALLOWED_BACKENDS")
    except Exception:
        _raw_backends = None

if _raw_backends:
    ALLOWED_BACKENDS = {b.strip().lower() for b in _raw_backends.split(",") if b.strip()}
else:
    ALLOWED_BACKENDS = DEFAULT_ALLOWED_BACKENDS
# maximum prompt length accepted by the router
MAX_PROMPT_LENGTH = int(get_config("MAX_PROMPT_LENGTH") or os.environ.get("MAX_PROMPT_LENGTH", "4096"))


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

    try:
        from markupsafe import escape as _escape  # type: ignore
    except Exception:  # pragma: no cover - fallback when dependency missing
        from html import escape as _escape

    # Escape any HTML/JS content
    safe = str(_escape(prompt))
    # Remove control characters but allow common whitespace
    safe = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", safe)
    payload["prompt"] = safe
    return payload


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
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Error queueing LLM invocation")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }

    return {
        "statusCode": 202,
        "body": json.dumps({"backend": backend, "queued": True}),
    }


