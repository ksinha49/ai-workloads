import pytest
import importlib.util
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))
from models import FileProcessingEvent, ProcessingStatusEvent
from services.summarization.models import SummaryEvent


def test_file_processing_event_missing():
    with pytest.raises(ValueError):
        FileProcessingEvent.from_dict({})

def test_file_processing_event_no_collection():
    with pytest.raises(ValueError):
        FileProcessingEvent.from_dict({"file": "f"})


def test_summary_event_missing():
    with pytest.raises(ValueError):
        SummaryEvent.from_dict({"collection_name": "c", "statusCode": 200})


def test_summary_event_roundtrip():
    data = {
        "collection_name": "c",
        "file_guid": "g",
        "document_id": "d",
        "statusCode": 200,
        "organic_bucket": "b",
        "organic_bucket_key": "k",
        "summaries": [{"t": 1}],
        "foo": "bar",
    }
    evt = SummaryEvent.from_dict(data)
    assert evt.collection_name == "c" and evt.extra["foo"] == "bar"
    out = evt.to_dict()
    assert out["foo"] == "bar" and out["organic_bucket_key"] == "k"


def test_summary_event_missing_required():
    with pytest.raises(ValueError):
        SummaryEvent.from_dict({
            "collection_name": "c",
            "file_guid": "g",
            "document_id": "d",
            "organic_bucket": "b",
            "organic_bucket_key": "k",
            "summaries": [],
        })


def test_processing_status_event_from_body():
    data = {"body": {"document_id": "d", "foo": 1}}
    evt = ProcessingStatusEvent.from_dict(data)
    assert evt.document_id == "d" and evt.extra["foo"] == 1
