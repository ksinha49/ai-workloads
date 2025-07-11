"""Extract key fields and signatures from OCR text."""
from __future__ import annotations

from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Placeholder Lambda that returns sample field data."""
    body = event.get("body") or event
    result = {
        "fields": {"PolNumber": "PN123"},
        "signatures": {"Applicant": "Jane Doe"},
    }
    if "text_doc_key" in body:
        result["text_doc_key"] = body["text_doc_key"]
    return {"statusCode": 200, "body": result}
