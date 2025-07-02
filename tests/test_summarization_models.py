import pytest
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.file_ingestion.models import FileProcessingEvent, ProcessingStatusEvent
from services.summarization.models import SummaryEvent


def test_file_processing_event_missing():
    with pytest.raises(ValueError):
        FileProcessingEvent.from_dict({})

def test_file_processing_event_no_collection():
    with pytest.raises(ValueError):
        FileProcessingEvent.from_dict({"file": "f"})


def test_summary_event_missing():
    with pytest.raises(ValueError):
        SummaryEvent.from_dict({"collection_name": "c"})


def test_processing_status_event_from_body():
    data = {"body": {"document_id": "d", "foo": 1}}
    evt = ProcessingStatusEvent.from_dict(data)
    assert evt.document_id == "d" and evt.extra["foo"] == 1
