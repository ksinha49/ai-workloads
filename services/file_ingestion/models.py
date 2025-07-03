from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

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
