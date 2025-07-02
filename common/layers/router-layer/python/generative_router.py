"""Generative fallback router and self-reflection routing helper."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import boto3

__all__ = [
    "GenerativeRouter",
    "handle_generative_route",
    "invoke_bedrock_model",
    "handle_generative_self_reflection",
]


class GenerativeRouter:
    """Directly call an LLM backend when other routers do not apply."""

    def try_route(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return *event* with a ``backend`` key set to ``'bedrock'``."""

        # This stub simply marks the backend for later handling
        event = dict(event)
        event.setdefault("backend", "bedrock")
        return event


def handle_generative_route(prompt: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Route *prompt* using :class:`GenerativeRouter` with optional *config*."""
    event = {"prompt": prompt}
    if config:
        event.update(config)
    router = GenerativeRouter()
    result = router.try_route(event)
    if result is None:
        raise RuntimeError("Generative router returned no result")
    return result


def invoke_bedrock_model(lambda_client: Any, model_id: str, prompt: str) -> str:
    """Invoke the LLM invocation lambda for a Bedrock model."""
    fn = os.environ.get("LLM_INVOCATION_FUNCTION")
    if not fn:
        raise RuntimeError("LLM_INVOCATION_FUNCTION not set")
    resp = lambda_client.invoke(
        FunctionName=fn,
        Payload=json.dumps({"backend": "bedrock", "prompt": prompt, "model": model_id}).encode("utf-8"),
    )
    data = json.loads(resp["Payload"].read())
    return data.get("reply", "")


def handle_generative_self_reflection(
    prompt: str, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Route ``prompt`` using a self-reflection approach."""

    config = config or {}
    lambda_client = config.get("lambda_client")
    if lambda_client is None:
        lambda_client = boto3.client("lambda")

    weak_model_id = config.get("weak_model_id") or os.environ.get("WEAK_MODEL_ID")
    strong_model_id = config.get("strong_model_id") or os.environ.get("STRONG_MODEL_ID")

    reflection_prompt = (
        "On a scale of 1 to 10, where 1 is not confident at all and 10 is very confident, "
        "how confident are you that you can provide a high-quality and accurate answer to the following user query? "
        "Only respond with a single number.\n\nUser Query: \"{}\"".format(prompt)
    )

    confidence_response = invoke_bedrock_model(lambda_client, weak_model_id, reflection_prompt)

    try:
        match = re.search(r"\d+", confidence_response)
        confidence_score = int(match.group()) if match else 0
    except (ValueError, AttributeError):
        confidence_score = 0

    if confidence_score >= 7:
        model_to_use = weak_model_id
        trace = f"Weak model self-reported confidence of {confidence_score}/10. Routing to weak model."
    else:
        model_to_use = strong_model_id
        trace = f"Weak model self-reported confidence of {confidence_score}/10. Escalating to strong model."

    response = invoke_bedrock_model(lambda_client, model_to_use, prompt)

    return {
        "routed_by": "generative_self_reflection",
        "model_used": model_to_use,
        "response": response,
        "trace": [trace],
    }

