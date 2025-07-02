"""Main router entrypoint for the LLM routing service.

This module exposes :func:`route_event` used by the router Lambda
(:mod:`router-lambda/app.py`).  ``route_event`` delegates to
:class:`CascadingRouter` which chains together the heuristic and
predictive routers with a generative fallback.
"""

from __future__ import annotations

from typing import Any, Dict

from cascading_router import CascadingRouter


def route_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Route *event* through the cascading router and return the result."""
    router = CascadingRouter()
    return router.route(event)
