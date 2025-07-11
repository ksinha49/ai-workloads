from __future__ import annotations

"""Redact PII regions in PDF or image files using bounding boxes.

The Lambda accepts a JSON payload with these fields:

- ``file`` – ``s3://`` URI of the source file to redact.
- ``hocr`` – combined hOCR JSON with word bounding boxes.
- ``entities`` – list of PII entities containing ``start`` and ``end`` offsets.

The redacted file is written back to the same bucket under ``REDACTED_PREFIX``.
"""

import io
import json
import logging
import os
from typing import Any, Dict, Iterable, List

import boto3
from common_utils import configure_logger, get_config, lambda_response, parse_s3_uri
from common_utils.error_utils import error_response, log_exception

try:  # optional dependencies may be mocked in tests
    import fitz  # type: ignore
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - fallback stubs
    fitz = None  # type: ignore
    Image = ImageDraw = None  # type: ignore

logger = configure_logger(__name__)

s3_client = boto3.client("s3")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _iter_words(hocr: Dict[str, Any]) -> Iterable[tuple[int, int, List[int]]]:
    """Yield ``(offset, page_number, bbox)`` for each word in *hocr*."""

    offset = 0
    for page_idx, page in enumerate(hocr.get("pages", []), start=1):
        words = page.get("words", [])
        for word in words:
            text = str(word.get("text", ""))
            bbox = word.get("bbox")
            if bbox and len(text) > 0:
                for i in range(len(text)):
                    yield offset + i, page_idx, bbox
            offset += len(text) + 1  # space between words
        offset += 1  # newline between pages


def _map_boxes(hocr: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[int, List[List[int]]]:
    """Return mapping of page number to bounding boxes for ``entities``."""

    index_map: Dict[int, tuple[int, List[int]]] = {}
    for off, page, box in _iter_words(hocr):
        index_map[off] = (page, box)

    pages: Dict[int, List[List[int]]] = {}
    for ent in entities:
        start = int(ent.get("start", 0))
        end = int(ent.get("end", start))
        for i in range(start, end):
            if i in index_map:
                page, box = index_map[i]
                pages.setdefault(page, []).append(box)
    for page, box_list in pages.items():
        unique = []
        for b in box_list:
            if b not in unique:
                unique.append(b)
        pages[page] = unique
    return pages


def _redact_pdf(data: bytes, boxes: Dict[int, List[List[int]]]) -> bytes:
    """Return PDF bytes with ``boxes`` obscured."""

    if not fitz:  # pragma: no cover - dependency missing
        return data
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_idx, page in enumerate(doc, start=1):
            for bbox in boxes.get(page_idx, []):
                rect = fitz.Rect(*bbox)
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
        out = io.BytesIO()
        doc.save(out)
    return out.getvalue()


def _redact_image(data: bytes, boxes: List[List[int]]) -> bytes:
    """Return image bytes with ``boxes`` obscured."""

    if not Image:  # pragma: no cover - dependency missing
        return data
    with Image.open(io.BytesIO(data)) as img:
        draw = ImageDraw.Draw(img)
        for bbox in boxes:
            draw.rectangle(bbox, fill="white")
        out = io.BytesIO()
        img.save(out, format=img.format or "PNG")
    return out.getvalue()


def _redact_and_upload(bucket: str, key: str, hocr: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, str]:
    """Redact ``key`` in ``bucket`` and upload the result."""

    dest_prefix = get_config("REDACTED_PREFIX", bucket, key) or os.environ.get("REDACTED_PREFIX", "redacted/")
    if dest_prefix and not dest_prefix.endswith("/"):
        dest_prefix += "/"
    dest_key = dest_prefix + os.path.basename(key)

    obj = s3_client.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()

    boxes = _map_boxes(hocr, entities)
    ext = os.path.splitext(key)[1].lower()
    if ext == ".pdf":
        redacted = _redact_pdf(body, boxes)
        content_type = "application/pdf"
    else:
        page_boxes = boxes.get(1, [])
        redacted = _redact_image(body, page_boxes)
        content_type = obj.get("ContentType") or "image/png"

    s3_client.put_object(Bucket=bucket, Key=dest_key, Body=redacted, ContentType=content_type)
    logger.info("Wrote %s", dest_key)
    return {"redacted_file": f"s3://{bucket}/{dest_key}"}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Entry point for the file redaction Lambda."""

    try:
        body = event.get("body", event)
        file_uri = body.get("file")
        if not file_uri:
            raise ValueError("file missing from event")
        hocr = body.get("hocr")
        if isinstance(hocr, str):
            hocr = json.loads(hocr)
        entities = body.get("entities", [])
        bucket, key = parse_s3_uri(file_uri)
        result = _redact_and_upload(bucket, key, hocr or {}, entities)
        return lambda_response(200, result)
    except Exception as exc:
        log_exception("File redaction failed", exc, logger)
        return error_response(logger, 500, "Redaction failed", exc)
