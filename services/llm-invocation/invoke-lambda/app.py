# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Lambda to invoke an LLM backend.

This function abstracts the Bedrock/Ollama API calls so the router and
routing strategies can delegate all model interactions here.
"""

from __future__ import annotations

import logging
from common_utils import configure_logger
from typing import Any, Dict
from models import LlmInvocationEvent, LambdaResponse

from llm_invoke import (
    invoke_bedrock_openai,
    invoke_bedrock_runtime,
    invoke_ollama,
)
from llm_invocation.backends import BEDROCK_OPENAI_ENDPOINTS
from httpx import HTTPStatusError
import json

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)


def _response(status: int, body: dict) -> dict:
    """Helper to build a consistent Lambda response."""
    return {"statusCode": status, "body": body}




def _process_event(event: LlmInvocationEvent) -> LambdaResponse:
    """Handle one invocation request.

    Parameters
    ----------
    event : :class:`models.LlmInvocationEvent`
        Normalised payload forwarded from the router.

    1. Validates the request parameters and selects the appropriate backend
       implementation.
    2. Forwards the prompt to Bedrock or Ollama and captures the response.

    Returns
    -------
    :class:`models.LambdaResponse`
        Raw backend response wrapped in an HTTP style object.
    """
    from dataclasses import asdict
    data = event if isinstance(event, dict) else asdict(event)
    backend = data.get("backend")
    prompt = data.get("prompt")
    system_prompt = data.get("system_prompt")
    if not backend or not prompt:
        return {"message": "Missing backend or prompt"}

    from dataclasses import asdict
    payload = dict(event) if isinstance(event, dict) else asdict(event)
    payload.pop("backend", None)
    payload.pop("system_prompt", None)

    try:
        if backend == "bedrock":
            if BEDROCK_OPENAI_ENDPOINTS:
                if "prompt" in payload:
                    messages = []
                    if system_prompt is not None:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    payload["messages"] = messages
                    payload.pop("prompt", None)
                return invoke_bedrock_openai(payload)
            return invoke_bedrock_runtime(prompt, payload.get("model"), system_prompt)
        if system_prompt is not None:
            payload["system"] = system_prompt
        return invoke_ollama(payload)
    except HTTPStatusError as exc:
        logger.error(
            "LLM request failed [%d]: %s", exc.response.status_code, exc.response.text
        )
        return _response(
            500,
            {
                "error": f"{exc.response.status_code}: {exc.response.text}",
            },
        )
    except Exception as exc:  # pragma: no cover - unexpected failures
        logger.exception("Unexpected error in llm invocation")
        return _response(500, {"error": str(exc)})


def lambda_handler(event: LlmInvocationEvent, context: Any) -> Any:
    """Entry point compatible with SQS events."""
    if isinstance(event, dict) and "Records" in event:
        return [
            _process_event(json.loads(r.get("body", "{}"))) for r in event["Records"]
        ]
    return _process_event(event)
