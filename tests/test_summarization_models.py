import pytest
import importlib.util
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_models_spec = importlib.util.spec_from_file_location(
    "file_ingestion_models",
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "services",
        "file-ingestion",
        "models.py",
    ),
)
_models = importlib.util.module_from_spec(_models_spec)
sys.modules[_models_spec.name] = _models
_models_spec.loader.exec_module(_models)
FileProcessingEvent = _models.FileProcessingEvent
ProcessingStatusEvent = _models.ProcessingStatusEvent
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
