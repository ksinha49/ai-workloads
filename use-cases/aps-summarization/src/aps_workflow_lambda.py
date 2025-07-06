"""APS specific post processing for summarization."""
from __future__ import annotations

from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the optional APS workflow step."""
    return event

