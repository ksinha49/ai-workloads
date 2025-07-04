"""Utilities for handling S3 event records."""

from typing import Iterable, Dict, Any

from models import S3Event

__all__ = ["iter_s3_records"]


def iter_s3_records(event: S3Event) -> Iterable[Dict[str, Any]]:
    """Yield each S3 event record contained in ``event``.

    Parameters
    ----------
    event : :class:`models.S3Event`
        Event object or dictionary from an S3-triggered Lambda.
    """
    records = event.Records if hasattr(event, "Records") else event.get("Records", [])
    for record in records:
        yield record
