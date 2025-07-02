# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""PDF text extraction Lambda.

Triggered for each single-page PDF under ``PDF_TEXT_PAGE_PREFIX``. The
page is read using :mod:`fitz` and the text from ``get_text("json")`` is
converted to Markdown and stored as
``TEXT_PAGE_PREFIX/{documentId}/page_NNN.md``.

Environment variables
---------------------
``BUCKET_NAME``
    Name of the S3 bucket used for both input and output. **Required.**
``PDF_TEXT_PAGE_PREFIX``
    Prefix where single-page PDFs with embedded text are stored. Defaults
    to ``"text-pages/"``.
``TEXT_PAGE_PREFIX``
    Destination prefix for the extracted Markdown. Defaults to
    ``"text-pages/"``.
"""

from __future__ import annotations

import json
import os
from typing import Iterable
from models import S3Event, LambdaResponse
from statistics import median

import boto3
from common_utils import get_config, configure_logger
import fitz  # PyMuPDF
try:
    from botocore.exceptions import ClientError, BotoCoreError
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    class ClientError(Exception):
        pass

    class BotoCoreError(Exception):
        pass
from ocr_module import post_process_text, convert_to_markdown

__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

s3_client = boto3.client("s3")



def _iter_records(event: S3Event) -> Iterable[dict]:
    """Yield S3 event records from *event*."""

    records = event.Records if hasattr(event, "Records") else event.get("Records", [])
    for record in records:
        yield record


def _results_to_layout_text(results: list[tuple[list[list[int]], str]]) -> str:
    """Return text arranged using bounding boxes from PDF extraction."""

    if not results:
        return ""

    boxes = []
    for box, text in results:
        top = min(pt[1] for pt in box)
        bottom = max(pt[1] for pt in box)
        left = min(pt[0] for pt in box)
        boxes.append({"top": top, "bottom": bottom, "left": left, "text": text})

    boxes.sort(key=lambda b: (b["top"], b["left"]))

    heights = [b["bottom"] - b["top"] for b in boxes]
    line_height = median(heights) if heights else 1
    group_thresh = line_height * 0.6

    lines: list[list[dict]] = []
    current = [boxes[0]]
    for b in boxes[1:]:
        if b["top"] - current[-1]["top"] > group_thresh:
            lines.append(current)
            current = [b]
        else:
            current.append(b)
    lines.append(current)

    para_thresh = line_height * 1.5
    output_lines: list[str] = []
    table_buffer: list[list[str]] = []
    prev_bottom = lines[0][0]["bottom"]

    def flush_table() -> None:
        """Write buffered table rows to ``output_lines`` and clear the buffer."""

        nonlocal table_buffer
        if not table_buffer:
            return
        header = table_buffer[0]
        md = ["| " + " | ".join(header) + " |"]
        md.append("| " + " | ".join(["---"] * len(header)) + " |")
        for row in table_buffer[1:]:
            md.append("| " + " | ".join(row) + " |")
        output_lines.extend(md)
        table_buffer = []

    for line in lines:
        line.sort(key=lambda item: item["left"])
        cells = [item["text"] for item in line]
        top = line[0]["top"]
        bottom = max(item["bottom"] for item in line)
        if len(cells) > 1:
            table_buffer.append(cells)
        else:
            flush_table()
            if top - prev_bottom > para_thresh:
                output_lines.append("")
            output_lines.append(" ".join(cells))
        prev_bottom = bottom

    flush_table()
    return "\n".join(output_lines)


def _json_to_markdown(text_json: str) -> str:
    """Convert ``page.get_text('json')`` output to Markdown."""

    try:
        data = json.loads(text_json)
    except json.JSONDecodeError:
        logger.error("Invalid JSON text")
        return ""

    results: list[tuple[list[list[int]], str]] = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            bbox = line.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            text = " ".join(span.get("text", "") for span in line.get("spans", []))
            text = text.strip()
            if not text:
                continue
            box = [
                [int(bbox[0]), int(bbox[1])],
                [int(bbox[2]), int(bbox[1])],
                [int(bbox[2]), int(bbox[3])],
                [int(bbox[0]), int(bbox[3])],
            ]
            results.append((box, text))

    text = _results_to_layout_text(results)
    text = post_process_text(text)
    return convert_to_markdown(text, 1)


def _extract_text(pdf_bytes: bytes) -> str:
    """Return Markdown text for the first page of the PDF."""

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if not doc.page_count:
            return ""
        page = doc[0]
        text_json = page.get_text("json")
        return _json_to_markdown(text_json)
    return ""


def _handle_record(record: dict) -> None:
    """Process a single S3 event record."""

    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    key = record.get("s3", {}).get("object", {}).get("key")
    bucket_name = get_config("BUCKET_NAME", bucket, key)
    pdf_text_page_prefix = get_config("PDF_TEXT_PAGE_PREFIX", bucket, key) or "text-pages/"
    text_page_prefix = get_config("TEXT_PAGE_PREFIX", bucket, key) or "text-pages/"
    if pdf_text_page_prefix and not pdf_text_page_prefix.endswith("/"):
        pdf_text_page_prefix += "/"
    if text_page_prefix and not text_page_prefix.endswith("/"):
        text_page_prefix += "/"
    if bucket != bucket_name or not key:
        logger.info("Skipping record with bucket=%s key=%s", bucket, key)
        return
    if not key.startswith(pdf_text_page_prefix):
        logger.info("Key %s outside prefix %s - skipping", key, pdf_text_page_prefix)
        return
    if not key.lower().endswith(".pdf"):
        logger.info("Key %s is not a PDF - skipping", key)
        return

    obj = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = obj["Body"].read()
    try:
        text_md = _extract_text(body)
    except (fitz.FileDataError, ValueError) as exc:  # pragma: no cover - expected
        logger.error("Failed to extract text from %s: %s", key, exc)
        return
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected error extracting text from %s", key)
        return

    rel_key = key[len(pdf_text_page_prefix):]
    dest_key = text_page_prefix + os.path.splitext(rel_key)[0] + ".md"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=dest_key,
        Body=text_md.encode("utf-8"),
        ContentType="text/markdown",
    )
    logger.info("Wrote %s", dest_key)

def lambda_handler(event: S3Event, context: dict) -> LambdaResponse:
    """Triggered by pages in ``PDF_TEXT_PAGE_PREFIX``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        S3 event listing the page PDFs.

    1. Extracts embedded text using ``fitz`` and converts it to Markdown.
    2. Writes the output under ``TEXT_PAGE_PREFIX`` for downstream steps.

    Returns
    -------
    :class:`models.LambdaResponse`
        200 status after processing all records.
    """

    logger.info("Received event for 5-pdf-text-extractor: %s", event)
    for rec in _iter_records(event):
        try:
            _handle_record(rec)
        except (ClientError, BotoCoreError, fitz.FileDataError, ValueError) as exc:
            logger.error("Error processing record %s: %s", rec, exc)
        except Exception as exc:  # pragma: no cover - unexpected
            logger.exception("Unexpected error processing record %s", rec)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "5-pdf-text-extractor executed"})
    }
