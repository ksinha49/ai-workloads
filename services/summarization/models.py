from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SummaryEvent:
    """Event payload for the file summary Lambda."""

    collection_name: str
    file_guid: str
    document_id: str
    statusCode: int
    organic_bucket: str
    organic_bucket_key: str
    summaries: List[Dict[str, Any]]
    output_format: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryEvent":
        body = data.get("body", data)
        required = {
            "collection_name",
            "file_guid",
            "document_id",
            "statusCode",
            "organic_bucket",
            "organic_bucket_key",
            "summaries",
        }
        if not required.issubset(body):
            missing = ", ".join(sorted(required - body.keys()))
            raise ValueError(f"{missing} missing from event")
        keys = required | {"output_format"}
        extra = {k: v for k, v in body.items() if k not in keys}
        params = {k: body.get(k) for k in keys}
        params["extra"] = extra
        return cls(**params)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        return {k: v for k, v in data.items() if v is not None}


__all__ = ["SummaryEvent"]
