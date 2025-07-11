import json
import importlib.util
import os

from models import S3Event


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_on_demand_ocr(monkeypatch, s3_stub, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    text_doc_prefix = "text-docs/"
    hocr_prefix = "hocr/"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = text_doc_prefix
    config[f"{prefix}/HOCR_PREFIX"] = hocr_prefix
    module = load_lambda("on_demand", "services/idp/src/on_demand_ocr_lambda.py")

    s3_stub.objects[("bucket", "uploads/doc.pdf")] = b"data"

    monkeypatch.setattr(
        module,
        "_ocr_document",
        lambda b, e, d, t, doc: (["## Page 1\n\nocr\n"], [{"pageNumber": 1, "words": []}]),
    )

    event = {"Records": [{"body": json.dumps({"bucket": "bucket", "key": "uploads/doc.pdf"})}]}
    module.lambda_handler(event, {})

    out = json.loads(s3_stub.objects[("bucket", f"{text_doc_prefix}doc.json")].decode())
    assert out["documentId"] == "doc"
    assert out["pageCount"] == 1
    hocr = json.loads(s3_stub.objects[("bucket", f"{hocr_prefix}doc.json")].decode())
    assert hocr["documentId"] == "doc"
