"""Client utilities for interacting with a RouteLLM service."""

from __future__ import annotations

import os
from typing import Any, Dict

__all__ = [
    "forward_to_routellm",
    "handle_routellm_route",
]

import httpx

ROUTELLM_ENDPOINT = os.environ.get("ROUTELLM_ENDPOINT", "")


def forward_to_routellm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward ``payload`` to the configured RouteLLM endpoint."""
    if not ROUTELLM_ENDPOINT:
        raise RuntimeError("ROUTELLM_ENDPOINT not configured")
    resp = httpx.post(ROUTELLM_ENDPOINT, json=payload)
    resp.raise_for_status()
    return resp.json()


def handle_routellm_route(prompt: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Forward *prompt* to RouteLLM with optional *config*."""
    payload = {"prompt": prompt}
    if config:
        payload.update(config)
    return forward_to_routellm(payload)

