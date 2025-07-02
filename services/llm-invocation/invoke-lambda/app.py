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

from llm_invoke import (
    invoke_bedrock_openai,
    invoke_bedrock_runtime,
    invoke_ollama,
)
from llm_invocation.backends import BEDROCK_OPENAI_ENDPOINTS
from httpx import HTTPStatusError

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)




def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Triggered by the router to invoke a specific LLM backend.

    1. Validates the request parameters and selects the appropriate backend
       implementation.
    2. Forwards the prompt to Bedrock or Ollama and captures the response.

    Returns the raw backend response as a dictionary.
    """
    backend = event.get("backend")
    prompt = event.get("prompt")
    system_prompt = event.get("system_prompt")
    if not backend or not prompt:
        return {"message": "Missing backend or prompt"}

    payload = dict(event)
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
    except HTTPStatusError as e:
        logger.error(
            "LLM request failed [%d]: %s", e.response.status_code, e.response.text
        )
        raise
    except Exception:
        logger.exception("Unexpected error in llm invocation")
        raise
