"""Shared dataclasses describing Lambda events and responses."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
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
    document_id: Optional[str] = None


@dataclass
class FileProcessingEvent:
    """Event payload for :mod:`file-processing-lambda`."""

    file: str
    ingest_params: Optional[Dict[str, Any]] = None
    retrieve_params: Optional[Dict[str, Any]] = None
    router_params: Optional[Dict[str, Any]] = None
    llm_params: Optional[Dict[str, Any]] = None
    collection_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileProcessingEvent":
        if "file" not in data:
            raise ValueError("file missing from event")
        if "collection_name" not in data or data.get("collection_name") is None:
            raise ValueError("collection_name missing from event")
        keys = {
            "file",
            "ingest_params",
            "retrieve_params",
            "router_params",
            "llm_params",
            "collection_name",
        }
        extra = {k: v for k, v in data.items() if k not in keys}
        params = {k: data.get(k) for k in keys}
        params["extra"] = extra
        return cls(**params)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class ProcessingStatusEvent:
    """Event payload for :mod:`file-processing-status-lambda`."""

    document_id: str
    fileupload_status: Optional[str] = None
    text_doc_key: Optional[str] = None
    collection_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingStatusEvent":
        body = data.get("body", data)
        if "document_id" not in body:
            raise ValueError("document_id missing from event")
        keys = {"document_id", "fileupload_status", "text_doc_key", "collection_name"}
        extra = {k: v for k, v in body.items() if k not in keys}
        params = {k: body.get(k) for k in keys}
        params["extra"] = extra
        return cls(**params)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class DetectedEntity:
    """Single PII entity returned by ``detect_sensitive_info_lambda``."""

    text: str
    type: str
    start: int
    end: int
    score: float | None = None


@dataclass
class DetectPiiResponse:
    """Output schema for ``detect_sensitive_info_lambda``."""

    entities: List[DetectedEntity]


__all__ = [
    "LambdaResponse",
    "FileAssemblyEvent",
    "FileAssemblyResult",
    "LlmRouterEvent",
    "LlmInvocationEvent",
    "S3Record",
    "S3Event",
    "FileProcessingEvent",
    "ProcessingStatusEvent",
    "DetectedEntity",
    "DetectPiiResponse",
]

