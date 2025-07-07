"""Client utilities for interacting with a RouteLLM service."""

from __future__ import annotations

import os
from typing import Any, Dict

__all__ = [
    "forward_to_routellm",
    "handle_routellm_route",
]

import httpx
try:  # pragma: no cover - optional dependency
    from httpx import HTTPError
except Exception:  # pragma: no cover - allow import without httpx
    class HTTPError(Exception):
        pass
from common_utils import configure_logger
from common_utils.get_ssm import get_config

ROUTELLM_ENDPOINT = get_config("ROUTELLM_ENDPOINT") or os.environ.get("ROUTELLM_ENDPOINT", "")
logger = configure_logger(__name__)


def forward_to_routellm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward ``payload`` to the configured RouteLLM endpoint."""
    if not ROUTELLM_ENDPOINT:
        raise RuntimeError("ROUTELLM_ENDPOINT not configured")
    try:
        resp = httpx.post(ROUTELLM_ENDPOINT, json=payload)
        resp.raise_for_status()
    except HTTPError as exc:
        logger.exception("RouteLLM request failed")
        return {"prompts": [], "error": str(exc)}
    return resp.json()


def handle_routellm_route(prompt: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Forward *prompt* to RouteLLM with optional *config*."""
    payload = {"prompt": prompt}
    if config:
        payload.update(config)
    return forward_to_routellm(payload)

