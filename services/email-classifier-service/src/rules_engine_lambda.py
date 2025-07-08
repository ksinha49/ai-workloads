"""Rules Engine Lambda

Evaluates incoming emails against dynamic rules and extracts data
according to the matched rule's instructions.
"""

from __future__ import annotations

import json
import os
import boto3
from botocore.exceptions import ClientError
from common_utils import configure_logger, lambda_response

logger = configure_logger(__name__)
_sqs = boto3.client("sqs")
_dynamo = boto3.resource("dynamodb")

RULES_TABLE = os.environ.get("RULES_TABLE", "")
DEST_QUEUE_URL = os.environ.get("DEST_QUEUE_URL", "")

def _load_rules():  # pragma: no cover - simple table scan
    if not RULES_TABLE:
        return []
    table = _dynamo.Table(RULES_TABLE)
    return table.scan().get("Items", [])


def _match(rule, email):
    crit = json.loads(rule.get("matchCriteria", "{}"))
    from_crit = crit.get("from", {})
    subject_crit = crit.get("subject", {})
    body_crit = crit.get("body", {})
    sender = email.get("from", "")
    subject = email.get("subject", "")
    body = email.get("body", "")
    if "contains" in from_crit and from_crit["contains"] not in sender:
        return False
    if "equals" in from_crit and from_crit["equals"] != sender:
        return False
    if "startsWith" in subject_crit and not subject.startswith(subject_crit["startsWith"]):
        return False
    if "contains" in subject_crit and subject_crit["contains"] not in subject:
        return False
    if "regex" in body_crit:
        import re
        if not re.search(body_crit["regex"], body):
            return False
    return True


def lambda_handler(event, context):  # pragma: no cover - demonstration only
    email = json.loads(event.get("body", "{}"))
    for rule in sorted(_load_rules(), key=lambda r: int(r.get("priority", 0))):
        if _match(rule, email):
            extraction = json.loads(rule.get("extractionMap", "{}"))
            result = {}
            for key, cfg in extraction.items():
                src = email.get(cfg.get("source", ""), "")
                regex = cfg.get("regex")
                if regex:
                    import re
                    m = re.search(regex, src)
                    if m:
                        result[key] = m.group(1)
                else:
                    result[key] = src
            dest = json.loads(rule.get("outputAction", "{}"))
            if dest.get("type") == "webhook":
                _sqs.send_message(QueueUrl=DEST_QUEUE_URL, MessageBody=json.dumps(result))
            else:
                _sqs.send_message(QueueUrl=DEST_QUEUE_URL, MessageBody=json.dumps(result))
            return lambda_response(200, result)
    return lambda_response(204, "no match")
