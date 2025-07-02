"""Query the knowledge base using the summarization Lambda."""

from __future__ import annotations

import json
import os
import logging
from common_utils import configure_logger
import boto3

# Module Metadata
__author__ = "Koushik Sinha"
__version__ = "1.0.0"
__modified_by__ = "Koushik Sinha"

logger = configure_logger(__name__)

SUMMARY_FUNCTION_ARN = os.environ.get("SUMMARY_FUNCTION_ARN")

lambda_client = boto3.client("lambda")


def lambda_handler(event: dict, context: object) -> dict:
    """Triggered by API queries against the knowledge base.

    1. Forwards the request payload to the summarization Lambda specified by
       ``SUMMARY_FUNCTION_ARN``.

    Returns the JSON response from that function.
    """

    resp = lambda_client.invoke(
        FunctionName=SUMMARY_FUNCTION_ARN,
        Payload=json.dumps(event).encode("utf-8"),
    )
    return json.loads(resp["Payload"].read())
