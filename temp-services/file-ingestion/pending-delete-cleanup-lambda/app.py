import os
import datetime
import boto3
from common_utils import configure_logger
from common_utils.get_ssm import get_config

logger = configure_logger(__name__)

_s3 = boto3.client("s3")

DELETE_AFTER_DAYS = int(
    get_config("DELETE_AFTER_DAYS") or os.environ.get("DELETE_AFTER_DAYS", "1")
)
CLEANUP_BUCKETS = [
    b.strip()
    for b in (
        get_config("CLEANUP_BUCKETS") or os.environ.get("CLEANUP_BUCKETS", "")
    ).split(",")
    if b.strip()
]

def lambda_handler(event, context):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=DELETE_AFTER_DAYS)
    deleted = 0
    for bucket in CLEANUP_BUCKETS:
        token = None
        while True:
            resp = _s3.list_objects_v2(Bucket=bucket, ContinuationToken=token) if token else _s3.list_objects_v2(Bucket=bucket)
            for obj in resp.get("Contents", []):
                if obj.get("LastModified", datetime.datetime.utcnow()) >= cutoff:
                    continue
                tags = _s3.get_object_tagging(Bucket=bucket, Key=obj["Key"]).get("TagSet", [])
                if any(t["Key"] == "pending-delete" and t["Value"] == "true" for t in tags):
                    _s3.delete_object(Bucket=bucket, Key=obj["Key"])
                    deleted += 1
            if resp.get("IsTruncated"):
                token = resp.get("NextContinuationToken")
            else:
                break
    logger.info("Deleted %s objects", deleted)
    return {"deleted": deleted}
