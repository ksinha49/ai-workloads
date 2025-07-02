"""Cascading routing logic used by the router Lambda.

``handle_cascading_route`` implements the *weak then strong* pattern. It
invokes a cheaper Bedrock model first and escalates to a stronger model
only when :func:`is_response_sufficient` deems the weak model response
inadequate.  The :class:`CascadingRouter` class from an earlier design is
retained for compatibility but is not required for this strategy.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from heuristic_router import HeuristicRouter
from predictive_router import PredictiveRouter
from generative_router import GenerativeRouter

__all__ = [
    "CascadingRouter",
    "handle_cascading_route",
    "invoke_bedrock_model",
    "is_response_sufficient",
]


class CascadingRouter:
    """Route requests through multiple strategies until one succeeds."""

    def __init__(self) -> None:
        self.heuristic = HeuristicRouter()
        self.predictive = PredictiveRouter()
        self.generative = GenerativeRouter()

    def route(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Return a response from the first router that yields one."""
        for router in (self.heuristic, self.predictive, self.generative):
            resp = router.try_route(event)
            if resp is not None:
                return resp
        raise RuntimeError("No router produced a response")

def invoke_bedrock_model(lambda_client: Any, model_id: str, prompt: str) -> str:
    """Invoke the llm invocation lambda for a Bedrock model."""
    fn = os.environ.get("LLM_INVOCATION_FUNCTION")
    if not fn:
        raise RuntimeError("LLM_INVOCATION_FUNCTION not set")
    resp = lambda_client.invoke(
        FunctionName=fn,
        Payload=json.dumps({"backend": "bedrock", "prompt": prompt, "model": model_id}).encode("utf-8"),
    )
    data = json.loads(resp["Payload"].read())
    return data.get("reply", "")


def is_response_sufficient(response: str) -> bool:
    """Basic heuristic to decide if ``response`` should be accepted."""
    response_lower = response.lower()
    insufficient_phrases = [
        "i can't",
        "i am unable",
        "i do not know",
        "as an ai",
        "i cannot provide",
    ]
    if any(phrase in response_lower for phrase in insufficient_phrases):
        return False
    if len(response.split()) < 20:
        return False
    return True


def handle_cascading_route(
    prompt: str, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Return a response for ``prompt`` using weak/strong Bedrock models.

    The function first calls the cheaper *weak* model.  If
    :func:`is_response_sufficient` determines the reply is inadequate it
    escalates to the more powerful model. ``config`` may contain a
    ``lambda_client`` for invoking the LLM lambda along with optional
    ``weak_model_id`` and ``strong_model_id`` values.  Missing identifiers
    are read from the ``WEAK_MODEL_ID`` and ``STRONG_MODEL_ID``
    environment variables respectively.  A client is created when not
    supplied.
    """
    config = config or {}
    lambda_client = config.get("lambda_client")
    if lambda_client is None:
        import boto3

        lambda_client = boto3.client("lambda")

    weak_model_id = config.get("weak_model_id") or os.environ.get("WEAK_MODEL_ID")
    strong_model_id = config.get("strong_model_id") or os.environ.get("STRONG_MODEL_ID")

    weak_model_response = invoke_bedrock_model(lambda_client, weak_model_id, prompt)

    if is_response_sufficient(weak_model_response):
        return {
            "routed_by": "cascading",
            "model_used": weak_model_id,
            "response": weak_model_response,
            "trace": ["Attempted weak model, response was sufficient."],
        }

    strong_model_response = invoke_bedrock_model(lambda_client, strong_model_id, prompt)
    return {
        "routed_by": "cascading",
        "model_used": strong_model_id,
        "response": strong_model_response,
        "trace": [
            "Attempted weak model, response was insufficient.",
            f"Weak model response: {weak_model_response[:100]}...",
            "Escalated to strong model.",
        ],
    }

