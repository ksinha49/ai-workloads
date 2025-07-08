"""Parse raw email messages stored in S3 and save attachments."""
from __future__ import annotations

import os
import uuid
import email
import boto3
from common_utils import configure_logger, lambda_response, iter_s3_records

logger = configure_logger(__name__)
_s3 = boto3.client("s3")

ATTACHMENTS_BUCKET = os.environ.get("ATTACHMENTS_BUCKET", "")


def _process_record(bucket: str, key: str) -> None:
    obj = _s3.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    msg = email.message_from_bytes(data)

    metadata = dict(msg.items())
    body_parts = []
    attachments = []
    prefix = uuid.uuid4().hex + "/"

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename:
            key_name = prefix + filename
            _s3.put_object(Bucket=ATTACHMENTS_BUCKET, Key=key_name, Body=payload)
            attachments.append(f"s3://{ATTACHMENTS_BUCKET}/{key_name}")
        else:
            charset = part.get_content_charset() or "utf-8"
            try:
                body_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                body_parts.append(payload.decode("utf-8", errors="replace"))



def lambda_handler(event: dict, context: object) -> dict:
    for rec in iter_s3_records(event):
        bucket = rec["s3"]["bucket"]["name"]
        key = rec["s3"]["object"]["key"]
        try:
            _process_record(bucket, key)
        except Exception as exc:  # pragma: no cover - unexpected failures
            logger.exception("Failed to process %s/%s", bucket, key)
    return lambda_response(200, "processed")
