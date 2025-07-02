"""Shared dataclasses describing Lambda events and responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LambdaResponse:
    """Standard HTTP-style Lambda response."""

    statusCode: int
    body: Any


@dataclass
class FileAssemblyEvent:
    """Payload sent to the file-assembly Lambda."""

    organic_bucket: str
    organic_bucket_key: str
    summary_bucket_name: str
    summary_bucket_key: str


@dataclass
class FileAssemblyResult:
    """Body returned by :func:`file_assembly.lambda_handler`."""

    summarized_file: str
    merged: bool


@dataclass
class LlmRouterEvent:
    """Event structure for the LLM router Lambda."""

    body: Optional[str] = None


@dataclass
class LlmInvocationEvent:
    """Request forwarded from the router to the invocation Lambda."""

    backend: str
    prompt: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    # Additional generation parameters may be included
    extra: Dict[str, Any] | None = None


@dataclass
class S3Record:
    """Single record from an S3 event."""

    bucket: str
    key: str


@dataclass
class S3Event:
    """Wrapper for S3 event records used by the IDP Lambdas."""

    Records: List[Dict[str, Any]]

