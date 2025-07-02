from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SummaryEvent:
    """Payload consumed by :mod:`file-summary-lambda`."""
    statusCode: int
    organic_bucket: str
    organic_bucket_key: str
    collection_name: Optional[str] = None
    summaries: Optional[List[Dict[str, Any]]] = None
    statusMessage: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryEvent":
        body = data.get("body", data)
        required = {"statusCode", "organic_bucket", "organic_bucket_key", "collection_name"}
        missing = [k for k in required if k not in body]
        if missing:
            raise ValueError(f"Missing required event keys: {', '.join(missing)}")
        keys = {
            "collection_name",
            "statusCode",
            "organic_bucket",
            "organic_bucket_key",
            "summaries",
            "statusMessage",
        }
        extra = {k: v for k, v in body.items() if k not in keys}
        params = {k: body.get(k) for k in keys}
        params["extra"] = extra
        return cls(**params)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        return {k: v for k, v in data.items() if v is not None}
