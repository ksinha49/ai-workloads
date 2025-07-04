"""Utilities for building Lambda-style HTTP responses."""

from typing import Any, Dict

__all__ = ["lambda_response"]


def lambda_response(status: int, body: Any) -> Dict[str, Any]:
    """Return a standard Lambda response dictionary."""
    return {"statusCode": status, "body": body}
