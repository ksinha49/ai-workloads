"""Predictive routing logic leveraging Bedrock models.

This module implements a simple *predictive* strategy which uses one
Bedrock model to classify the prompt complexity and then routes the
request to either a weak or strong Bedrock model based on that
classification.  It mirrors the design of the standalone example from
the repository documentation but integrates with the existing router
infrastructure so it can be chained with other strategies.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import boto3

__all__ = [
    "PredictiveRouter",
    "handle_predictive_route",
    "invoke_bedrock_model",
    "invoke_classifier",
]


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


def invoke_classifier(lambda_client: Any, classifier_model_id: str, prompt: str) -> str:
    """Classify ``prompt`` as simple or complex using ``classifier_model_id``."""

    classifier_prompt = (
        "You are a prompt complexity classifier. Your task is to classify the "
        "following user prompt as either 'simple' or 'complex'.\n\n"
        "- A 'simple' prompt can be answered with a short, factual statement, a "
        "brief summary, or a direct question.\n"
        "- A 'complex' prompt requires multi-step reasoning, in-depth explanation, "
        "creative content generation, or code generation.\n\n"
        "Respond with only a single word: 'simple' or 'complex'.\n\n"
        f"User prompt to classify: \"{prompt}\""
    )

    response = invoke_bedrock_model(lambda_client, classifier_model_id, classifier_prompt)
    result = response.strip().lower()
    if "complex" in result:
        return "complex"
    if "simple" in result:
        return "simple"
    return "simple"


class PredictiveRouter:
    """Predict the best backend using a Bedrock model."""

    def __init__(self) -> None:
        """Create a Lambda client and read model identifiers from the environment."""

        self.lambda_client = boto3.client("lambda")
        self.weak_model_id = os.environ.get("WEAK_MODEL_ID")
        self.strong_model_id = os.environ.get("STRONG_MODEL_ID")

    def _classify_prompt(self, prompt: str) -> str:
        """Return ``'simple'`` or ``'complex'`` for *prompt* using the weak model."""

        return invoke_classifier(self.lambda_client, self.weak_model_id, prompt)

    def try_route(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a routing decision for *event* or ``None`` when undecidable."""

        prompt = str(event.get("prompt", ""))
        if not prompt:
            return None

        classification = self._classify_prompt(prompt)

        selected_model = (
            self.strong_model_id if classification == "complex" else self.weak_model_id
        )

        routed = dict(event)
        routed["backend"] = "bedrock"
        if selected_model:
            routed["model"] = selected_model
        return routed


def handle_predictive_route(prompt: str, config: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """Attempt to select a backend using :class:`PredictiveRouter`."""
    event = {"prompt": prompt}
    if config:
        event.update(config)
    router = PredictiveRouter()
    return router.try_route(event)

