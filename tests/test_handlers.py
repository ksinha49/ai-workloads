import json
import importlib.util
import importlib
import os
import io
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))
VECTOR_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services', 'vector-db', 'src')
sys.path.insert(0, VECTOR_SRC)
sys.path.insert(0, os.path.join(VECTOR_SRC, 'proxy'))
from models import FileProcessingEvent, ProcessingStatusEvent
from services.summarization.models import SummaryEvent


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def import_vector_module(name):
    """Import a vector DB module by name, reloading it for isolation."""
    return importlib.reload(importlib.import_module(name))


def _make_fake_send(calls):
    class FakeSQS:
        def send_message(self, QueueUrl=None, MessageBody=None):
            calls.append(json.loads(MessageBody))
            return {"MessageId": "1"}

    return FakeSQS()


def test_office_extractor(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    office_prefix = "office-docs/"
    text_doc_prefix = "text-docs/"
    config[f"{prefix}/OFFICE_PREFIX"] = office_prefix
    config[f"{prefix}/TEXT_DOC_PREFIX"] = text_doc_prefix
    module = load_lambda("office", "services/idp/src/office_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{office_prefix}test.docx")] = b"data"

    monkeypatch.setattr(module, "_extract_docx", lambda b: ["## Page 1\n\ntext\n"])
    monkeypatch.setattr(module, "_extract_pptx", lambda b: ["## Page 1\n\ntext\n"])
    monkeypatch.setattr(module, "_extract_xlsx", lambda b: ["## Page 1\n\ntext\n"])

    event = {
        "document_id": "doc123",
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{office_prefix}test.docx"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    out_key = f"{text_doc_prefix}doc123.json"
    payload = json.loads(s3_stub.objects[("bucket", out_key)].decode())
    assert payload["documentId"] == "doc123"
    assert payload["pageCount"] == 1
    page = {
        "documentId": payload["documentId"],
        "pageNumber": 1,
        "content": payload["pages"][0],
    }
    validate_schema(page)


def test_pdf_text_extractor(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_text_page_prefix = "text-pages/"
    text_page_prefix = "text-pages/"
    config[f"{prefix}/PDF_TEXT_PAGE_PREFIX"] = pdf_text_page_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    module = load_lambda("pdf_text", "services/idp/src/pdf_text_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_text_page_prefix}doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_extract_text", lambda b: "## Page 1\n\nhello\n")

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{pdf_text_page_prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")].decode()
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_scan_prefix = "scan-pages/"
    text_page_prefix = "text-pages/"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = pdf_scan_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    module = load_lambda("ocr", "services/idp/src/pdf_ocr_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_scan_prefix}doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_rasterize_page", lambda b, dpi: object())
    monkeypatch.setattr(module, "_ocr_image", lambda img, e, t, d: "## Page 1\n\nocr\n")

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{pdf_scan_prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")].decode()
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor_trocr(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_scan_prefix = "scan-pages/"
    text_page_prefix = "text-pages/"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = pdf_scan_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    config[f"{prefix}/OCR_ENGINE"] = "trocr"
    config[f"{prefix}/TROCR_ENDPOINT"] = "http://example"
    module = load_lambda("ocr_trocr", "services/idp/src/pdf_ocr_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_scan_prefix}doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_rasterize_page", lambda b, dpi: object())
    called = {}

    def fake(reader, engine, img):
        called["engine"] = engine
        return "ocr", 0.9

    monkeypatch.setattr(module, "_perform_ocr", fake)

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{pdf_scan_prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")].decode()
    assert called["engine"] == "trocr"
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor_ocrmypdf(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_scan_prefix = "scan-pages/"
    text_page_prefix = "text-pages/"
    hocr_prefix = "hocr/"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = pdf_scan_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    config[f"{prefix}/HOCR_PREFIX"] = hocr_prefix
    config[f"{prefix}/OCR_ENGINE"] = "ocrmypdf"
    module = load_lambda("ocr_ocrmypdf", "services/idp/src/pdf_ocr_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_scan_prefix}doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_ocrmypdf_hocr", lambda b: ("ocr", 0.9, b"<hocr></hocr>"))

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{pdf_scan_prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")].decode()
    hocr_json = json.loads(
        s3_stub.objects[("bucket", f"{hocr_prefix}doc1/page_001.json")].decode()
    )
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)
    assert isinstance(hocr_json.get("words"), list)


def test_pdf_ocr_extractor_docling(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_scan_prefix = "scan-pages/"
    text_page_prefix = "text-pages/"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = pdf_scan_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    config[f"{prefix}/OCR_ENGINE"] = "docling"
    config[f"{prefix}/DOCLING_ENDPOINT"] = "http://example"
    module = load_lambda("ocr_docling", "services/idp/src/pdf_ocr_extractor_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_scan_prefix}doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_rasterize_page", lambda b, dpi: object())
    called = {}

    def fake(reader, engine, img):
        called["engine"] = engine
        return "ocr", 0.9

    monkeypatch.setattr(module, "_perform_ocr", fake)

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{pdf_scan_prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")].decode()
    assert called["engine"] == "docling"
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_combine(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    pdf_page_prefix = "pdf-pages/"
    text_page_prefix = "text-pages/"
    text_doc_prefix = "text-docs/"
    hocr_prefix = "hocr/"
    config[f"{prefix}/PDF_PAGE_PREFIX"] = pdf_page_prefix
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = text_page_prefix
    config[f"{prefix}/TEXT_DOC_PREFIX"] = text_doc_prefix
    config[f"{prefix}/HOCR_PREFIX"] = hocr_prefix
    config[f"{prefix}/OCR_ENGINE"] = "ocrmypdf"
    module = load_lambda("combine", "services/idp/src/combine_lambda.py")

    s3_stub.objects[("bucket", f"{pdf_page_prefix}doc1/manifest.json")] = json.dumps(
        {"documentId": "doc1", "pages": 2}
    ).encode()
    s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_001.md")] = b"## Page 1\n\none\n"
    s3_stub.objects[("bucket", f"{text_page_prefix}doc1/page_002.md")] = b"## Page 2\n\ntwo\n"
    s3_stub.objects[("bucket", f"{hocr_prefix}doc1/page_001.json")] = json.dumps({"words": []}).encode()
    s3_stub.objects[("bucket", f"{hocr_prefix}doc1/page_002.json")] = json.dumps({"words": []}).encode()

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{text_page_prefix}doc1/page_001.md"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    output = json.loads(s3_stub.objects[("bucket", f"{text_doc_prefix}doc1.json")].decode())
    assert output["documentId"] == "doc1"
    assert output["pageCount"] == 2
    for i, page in enumerate(output["pages"], start=1):
        validate_schema(
            {"documentId": output["documentId"], "pageNumber": i, "content": page}
        )
    combined_hocr = json.loads(
        s3_stub.objects[("bucket", f"{hocr_prefix}doc1.json")].decode()
    )
    assert combined_hocr["documentId"] == "doc1"
    assert len(combined_hocr["pages"]) == 2


def test_output(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    text_doc_prefix = "text-docs/"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = text_doc_prefix
    config[f"{prefix}/EDI_SEARCH_API_URL"] = "http://example"
    config[f"{prefix}/EDI_SEARCH_API_KEY"] = "key"
    module = load_lambda("output", "services/idp/src/output_lambda.py")

    payload = {
        "documentId": "doc1",
        "type": "pdf",
        "pageCount": 1,
        "pages": ["## Page 1\n\nhi\n"],
    }
    s3_stub.objects[("bucket", f"{text_doc_prefix}doc1.json")] = json.dumps(payload).encode()

    sent = {}
    monkeypatch.setattr(
        module,
        "_post_to_api",
        lambda data, url, key: sent.setdefault("payload", data) or True,
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{text_doc_prefix}doc1.json"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    posted = sent["payload"]
    assert posted["documentId"] == "doc1"
    for i, page in enumerate(posted["pages"], start=1):
        validate_schema(
            {"documentId": posted["documentId"], "pageNumber": i, "content": page}
        )


def test_ocr_image_engines(monkeypatch, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/OCR_ENGINE"] = "easyocr"
    module = load_lambda("ocr_easy", "services/idp/src/pdf_ocr_extractor_lambda.py")
    module.easyocr = __import__("easyocr")
    called = {}

    def fake(r, e, b):
        called["engine"] = e
        called["cls"] = r.__class__.__name__
        return "t", 0

    monkeypatch.setattr(module, "_perform_ocr", fake)
    module._ocr_image(object(), "easyocr", None, None)
    assert called["engine"] == "easyocr"
    assert called["cls"] == "DummyReader"

    import types, sys

    class DummyPaddle:
        def __init__(self, *a, **k):
            pass

    sys.modules["paddleocr"] = types.ModuleType("paddleocr")
    sys.modules["paddleocr"].PaddleOCR = DummyPaddle

    config[f"{prefix}/OCR_ENGINE"] = "paddleocr"
    module = load_lambda("ocr_paddle", "services/idp/src/pdf_ocr_extractor_lambda.py")
    module.easyocr = __import__("easyocr")
    called = {}

    def fake2(r, e, b):
        called["engine"] = e
        called["cls"] = r.__class__.__name__
        return "t", 0

    monkeypatch.setattr(module, "_perform_ocr", fake2)
    module._ocr_image(object(), "paddleocr", None, None)
    assert called["engine"] == "paddleocr"
    assert called["cls"] == "DummyPaddle"

    config[f"{prefix}/OCR_ENGINE"] = "trocr"
    config[f"{prefix}/TROCR_ENDPOINT"] = "http://example"
    module = load_lambda("ocr_trocr_engine", "services/idp/src/pdf_ocr_extractor_lambda.py")
    called = {}

    def fake3(r, e, b):
        called["engine"] = e
        called["ctx"] = r
        return "t", 0

    monkeypatch.setattr(module, "_perform_ocr", fake3)
    module._ocr_image(object(), "trocr", "http://example", None)
    assert called["engine"] == "trocr"
    assert called["ctx"] == "http://example"

    config[f"{prefix}/OCR_ENGINE"] = "docling"
    config[f"{prefix}/DOCLING_ENDPOINT"] = "http://example"
    module = load_lambda(
        "ocr_docling_engine", "services/idp/src/pdf_ocr_extractor_lambda.py"
    )
    called = {}

    def fake4(r, e, b):
        called["engine"] = e
        called["ctx"] = r
        return "t", 0

    monkeypatch.setattr(module, "_perform_ocr", fake4)
    module._ocr_image(object(), "docling", None, "http://example")
    assert called["engine"] == "docling"
    assert called["ctx"] == "http://example"


def test_perform_ocr(monkeypatch):
    import types, sys, importlib.util

    class DummyPaddle:
        def __init__(self, *a, **k):
            pass

        def ocr(self, img):
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], ("pd", 0.8))]

    sys.modules["paddleocr"] = types.ModuleType("paddleocr")
    sys.modules["paddleocr"].PaddleOCR = DummyPaddle

    mod = load_lambda("ocr_real", "common/layers/ocr_layer/python/ocr_module.py")
    monkeypatch.setattr(mod, "preprocess_image_cv2", lambda b: "img")
    monkeypatch.setattr(mod, "_results_to_layout_text", lambda res: "layout")
    monkeypatch.setattr(mod.np, "mean", lambda x: sum(x) / len(x))

    reader = mod.easyocr.Reader()
    text, conf = mod._perform_ocr(reader, "easyocr", b"1")
    assert text == "layout"
    assert conf == 0.9

    pd = DummyPaddle()
    text, conf = mod._perform_ocr(pd, "paddleocr", b"1")
    assert text == "layout"
    assert conf == 0.8

    monkeypatch.setattr(mod, "_remote_trocr", lambda b, url: ("layout", 0.7))
    monkeypatch.setenv("TROCR_ENDPOINT", "http://example")
    text, conf = mod._perform_ocr(None, "trocr", b"1")
    assert text == "layout"
    assert conf == 0.7

    monkeypatch.setattr(mod, "_remote_docling", lambda b, url: ("layout", 0.6))
    monkeypatch.setenv("DOCLING_ENDPOINT", "http://example")
    text, conf = mod._perform_ocr(None, "docling", b"1")
    assert text == "layout"
    assert conf == 0.6

    monkeypatch.setattr(mod, "_ocrmypdf_hocr", lambda b: ("layout", 0.5, b"h"))
    text, conf = mod._perform_ocr(None, "ocrmypdf", b"1")
    assert text == "layout"
    assert conf == 0.5

    with pytest.raises(ValueError):
        mod._perform_ocr(reader, "other", b"1")


def test_embed_model_map_event(monkeypatch, config):
    monkeypatch.setenv("EMBED_MODEL", "sbert")
    monkeypatch.setenv("EMBED_MODEL_MAP", '{"pdf": "openai"}')
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_event", "services/rag-stack/src/embed_lambda.py")
    monkeypatch.setattr(module, "_openai_embed", lambda t: [42])
    module._MODEL_MAP["openai"] = module._openai_embed
    out = module.lambda_handler({"chunks": ["t"], "docType": "pdf"}, {})
    assert out["embeddings"] == [[42]]
    assert out["metadatas"] == [None]


def test_embed_model_map_chunk(monkeypatch, config):
    monkeypatch.setenv("EMBED_MODEL", "sbert")
    monkeypatch.setenv("EMBED_MODEL_MAP", '{"pptx": "cohere"}')
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_chunk", "services/rag-stack/src/embed_lambda.py")
    monkeypatch.setattr(module, "_cohere_embed", lambda t: [24])
    module._MODEL_MAP["cohere"] = module._cohere_embed
    chunk = {"text": "hi", "metadata": {"docType": "pptx"}}
    out = module.lambda_handler({"chunks": [chunk]}, {})
    assert out["embeddings"] == [[24]]
    assert out["metadatas"][0]["docType"] == "pptx"


def test_embed_model_default(monkeypatch, config):
    monkeypatch.setenv("EMBED_MODEL", "cohere")
    monkeypatch.setenv("EMBED_MODEL_MAP", '{"pdf": "openai"}')
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_default", "services/rag-stack/src/embed_lambda.py")
    monkeypatch.setattr(module, "_cohere_embed", lambda t: [7])
    module._MODEL_MAP["cohere"] = module._cohere_embed
    out = module.lambda_handler({"chunks": ["x"], "docType": "txt"}, {})
    assert out["embeddings"] == [[7]]
    assert out["metadatas"] == [None]


def test_text_chunk_doc_type(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk", "services/rag-stack/src/text_chunk_lambda.py")
    event = {"text": "abcdef", "docType": "pdf"}
    result = module.lambda_handler(event, {})
    assert result["docType"] == "pdf"
    assert isinstance(result["chunks"][0], dict)


def test_milvus_delete_lambda(monkeypatch):
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type(
        "Coll",
        (),
        {
            "__init__": lambda self, *a, **k: None,
            "delete": lambda self, expr: types.SimpleNamespace(delete_count=2),
        },
    )
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {}

    def fake_delete(self, ids):
        called["ids"] = list(ids)
        return len(called["ids"])

    monkeypatch.setattr(module, "client", type("C", (), {"delete": fake_delete})())
    res = proxy.lambda_handler({"operation": "delete", "ids": [1, 2]}, {})
    assert called["ids"] == [1, 2]
    assert res["deleted"] == 2


def test_milvus_update_lambda(monkeypatch):
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    received = {}

    def fake_update(items):
        received["items"] = items
        return len(items)

    monkeypatch.setattr(
        module,
        "client",
        type("C", (), {"update": lambda self, items: fake_update(items)})(),
    )
    event = {"embeddings": [[0.1, 0.2]], "metadatas": [{"a": 1}], "ids": [5]}
    res = proxy.lambda_handler(dict(event, operation="update"), {})
    assert len(received["items"]) == 1
    item = received["items"][0]
    assert item.embedding == [0.1, 0.2]
    assert item.metadata == {"a": 1}
    assert item.id == 5
    assert res["updated"] == 1


def test_milvus_create_lambda(monkeypatch):
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.FieldSchema = lambda *a, **k: None
    dummy.CollectionSchema = lambda *a, **k: None
    dummy.DataType = types.SimpleNamespace(INT64=0, FLOAT_VECTOR=1, JSON=2)
    dummy.Collection = type(
        "Coll",
        (),
        {"__init__": lambda self, *a, **k: None, "create_index": lambda *a, **k: None},
    )
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)
    monkeypatch.setattr(mc, "FieldSchema", dummy.FieldSchema, raising=False)
    monkeypatch.setattr(mc, "CollectionSchema", dummy.CollectionSchema, raising=False)
    monkeypatch.setattr(mc, "DataType", dummy.DataType, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {}
    monkeypatch.setattr(
        module,
        "client",
        type(
            "C",
            (),
            {
                "create_collection": lambda self, dimension=768: called.setdefault(
                    "dimension", dimension
                )
            },
        )(),
    )
    res = proxy.lambda_handler({"operation": "create", "dimension": 42}, {})
    assert called["dimension"] == 42
    assert res["created"] is True


def test_milvus_drop_lambda(monkeypatch):
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type(
        "Coll", (), {"__init__": lambda self, *a, **k: None, "drop": lambda self: None}
    )
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {"dropped": False}

    def fake_drop():
        called["dropped"] = True

    monkeypatch.setattr(
        module, "client", type("C", (), {"drop_collection": lambda self: fake_drop()})()
    )
    res = proxy.lambda_handler({"operation": "drop"}, {})
    assert called["dropped"] is True
    assert res["dropped"] is True


def test_es_insert_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    captured = {}

    def fake_insert(self, docs):
        captured["docs"] = list(docs)
        return len(captured["docs"])

    monkeypatch.setattr(module, "client", type("C", (), {"insert": fake_insert})())
    res = proxy.lambda_handler({"operation": "insert", "documents": [{"id": "1", "text": "a"}], "storage_mode": "es"}, {})
    assert captured["docs"][0]["id"] == "1"
    assert res["inserted"] == 1


def test_es_delete_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {}

    def fake_delete(self, ids):
        called["ids"] = list(ids)
        return len(called["ids"])

    monkeypatch.setattr(module, "client", type("C", (), {"delete": fake_delete})())
    res = proxy.lambda_handler({"operation": "delete", "ids": ["1", "2"], "storage_mode": "es"}, {})
    assert called["ids"] == ["1", "2"]
    assert res["deleted"] == 2


def test_es_update_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    captured = {}

    def fake_update(self, docs):
        captured["docs"] = list(docs)
        return len(captured["docs"])

    monkeypatch.setattr(module, "client", type("C", (), {"update": fake_update})())
    res = proxy.lambda_handler({"operation": "update", "documents": [{"id": "1", "text": "x"}], "storage_mode": "es"}, {})
    assert captured["docs"][0]["text"] == "x"
    assert res["updated"] == 1


def test_es_create_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {"created": False}
    monkeypatch.setattr(
        module,
        "client",
        type(
            "C", (), {"create_index": lambda self: called.__setitem__("created", True)}
        )(),
    )
    res = proxy.lambda_handler({"operation": "create-index", "storage_mode": "es"}, {})
    assert called["created"] is True
    assert res["created"] is True


def test_es_drop_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {"dropped": False}
    monkeypatch.setattr(
        module,
        "client",
        type(
            "C", (), {"drop_index": lambda self: called.__setitem__("dropped", True)}
        )(),
    )
    res = proxy.lambda_handler({"operation": "drop-index", "storage_mode": "es"}, {})
    assert called["dropped"] is True
    assert res["dropped"] is True


def test_es_search_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    captured = {}

    def fake_search(self, embedding, top_k=5):
        captured["top_k"] = top_k
        return [{"id": "1"}]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    out = proxy.lambda_handler({"operation": "search", "embedding": [0.1], "top_k": 3, "storage_mode": "es"}, {})
    assert captured["top_k"] == 3
    assert out["matches"][0]["id"] == "1"


def test_es_hybrid_search_lambda(monkeypatch):
    module = import_vector_module("elastic_search_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    captured = {}

    def fake_search(self, embedding, keywords=None, top_k=5):
        captured["kw"] = list(keywords)
        return [{"id": "1"}]

    monkeypatch.setattr(
        module, "client", type("C", (), {"hybrid_search": fake_search})()
    )
    out = proxy.lambda_handler({"operation": "hybrid-search", "embedding": [0.1], "keywords": ["x"], "storage_mode": "es"}, {})
    assert captured["kw"] == ["x"]
    assert out["matches"][0]["id"] == "1"


import sys



def test_llm_router_lambda_handler(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    calls = []
    monkeypatch.setattr(
        sys.modules["boto3"], "client", lambda name: _make_fake_send(calls)
    )
    module = load_lambda(
        "llm_router_lambda", "services/llm-gateway/src/llm_router_lambda.py"
    )
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event1 = {"body": json.dumps({"prompt": "short text"})}
    out1 = module.lambda_handler(event1, {})
    body1 = json.loads(out1["body"])
    assert body1["backend"] == "ollama"
    assert body1["queued"] is True
    assert calls[0]["backend"] == "ollama"

    event2 = {"body": json.dumps({"prompt": "one two three four"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "bedrock"
    assert body2["queued"] is True
    assert calls[1]["backend"] == "bedrock"


def test_llm_router_lambda_handler_backend_override(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    calls = []
    monkeypatch.setattr(
        sys.modules["boto3"], "client", lambda name: _make_fake_send(calls)
    )
    module = load_lambda(
        "llm_router_lambda_override", "services/llm-gateway/src/llm_router_lambda.py"
    )
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": "short text", "backend": "bedrock"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert body["backend"] == "bedrock"
    assert body["queued"] is True
    assert calls[0]["backend"] == "bedrock"

    event2 = {"body": json.dumps({"prompt": "one two three four", "backend": "ollama"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "ollama"
    assert body2["queued"] is True
    assert calls[1]["backend"] == "ollama"



def test_summarize_with_context_router(monkeypatch, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/VECTOR_SEARCH_FUNCTION"] = "vector-search"

    # stub lambda invoke to return a single match with context text
    class FakePayload:
        def __init__(self, data):
            self._data = data

        def read(self):
            return json.dumps(self._data).encode("utf-8")

    def fake_invoke(FunctionName=None, Payload=None):
        # capture payload sent to vector search
        fake_invoke.calls.append(json.loads(Payload))
        return {"Payload": FakePayload({"matches": [{"metadata": {"text": "ctx"}}]})}

    fake_invoke.calls = []

    module = load_lambda(
        "summ_ctx", "services/rag-stack/src/retrieval_lambda.py"
    )
    monkeypatch.setattr(
        module, "lambda_client", type("C", (), {"invoke": staticmethod(fake_invoke)})()
    )
    monkeypatch.setattr(module, "_sbert_embed", lambda t: [0.1])
    module._MODEL_MAP["sbert"] = module._sbert_embed

    sent = {}

    def fake_forward(payload):
        sent["payload"] = payload
        return {"text": "ok"}

    monkeypatch.setattr(module, "forward_to_routellm", fake_forward)

    out = module.lambda_handler(
        {"query": "hi", "model": "phi", "temperature": 0.2, "collection_name": "c"},
        {}
    )
    sent_payload = fake_invoke.calls[0]
    assert "embedding" in sent_payload
    assert isinstance(sent_payload["embedding"], list)
    assert sent_payload["operation"] == "search"
    assert sent["payload"] == {
        "query": "hi",
        "model": "phi",
        "temperature": 0.2,
        "context": "ctx",
        "collection_name": "c",
    }
    assert out["result"] == {"text": "ok"}


def test_rerank_lambda(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("rerank", "services/rag-stack/src/rerank_lambda.py")
    monkeypatch.setattr(module, "_score_pairs", lambda q, d: [0.1, 0.9])
    matches = [
        {"id": 1, "metadata": {"text": "a"}},
        {"id": 2, "metadata": {"text": "b"}},
    ]
    out = module.lambda_handler({"query": "x", "matches": matches, "top_k": 1}, {})
    assert out["matches"][0]["id"] == 2
    assert "rerank_score" in out["matches"][0]


def test_rerank_lambda_cohere(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    monkeypatch.setenv("RERANK_PROVIDER", "cohere")
    module = load_lambda("rerank_co", "services/rag-stack/src/rerank_lambda.py")
    monkeypatch.setattr(module, "_cohere_rerank", lambda q, d: [0.8, 0.1])
    module._PROVIDER_MAP["cohere"] = module._cohere_rerank
    matches = [
        {"id": 1, "metadata": {"text": "a"}},
        {"id": 2, "metadata": {"text": "b"}},
    ]
    out = module.lambda_handler({"query": "x", "matches": matches, "top_k": 1}, {})
    assert out["matches"][0]["id"] == 1


def test_rerank_lambda_invalid(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("rerank_invalid", "services/rag-stack/src/rerank_lambda.py")
    out = module.lambda_handler({"matches": "bad"}, {})
    assert out["matches"] == []


def test_summarize_with_rerank(monkeypatch, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/VECTOR_SEARCH_FUNCTION"] = "vector-search"
    config[f"{prefix}/RERANK_FUNCTION"] = "rerank"
    config[f"{prefix}/VECTOR_SEARCH_CANDIDATES"] = "2"

    class FakePayload:
        def __init__(self, data):
            self._data = data

        def read(self):
            return json.dumps(self._data).encode("utf-8")

    def fake_invoke(FunctionName=None, Payload=None):
        payload = json.loads(Payload)
        if FunctionName == "vector-search":
            fake_invoke.search = payload
            return {
                "Payload": FakePayload(
                    {
                        "matches": [
                            {"metadata": {"text": "t1"}},
                            {"metadata": {"text": "t2"}},
                        ]
                    }
                )
            }
        else:
            fake_invoke.rerank = payload
            return {
                "Payload": FakePayload(
                    {"matches": [{"metadata": {"text": "t2"}, "rerank_score": 0.9}]}
                )
            }

    fake_invoke.rerank = None
    fake_invoke.search = None

    module = load_lambda(
        "summ_ctx_rerank", "services/rag-stack/src/retrieval_lambda.py"
    )
    monkeypatch.setattr(
        module, "lambda_client", type("C", (), {"invoke": staticmethod(fake_invoke)})()
    )
    monkeypatch.setattr(module, "_sbert_embed", lambda t: [0.1])
    module._MODEL_MAP["sbert"] = module._sbert_embed
    monkeypatch.setattr(module, "forward_to_routellm", lambda p: {"text": p["context"]})

    out = module.lambda_handler({"query": "hi", "collection_name": "c"}, {})
    assert fake_invoke.search["operation"] == "search"
    assert fake_invoke.rerank["query"] == "hi"
    assert out["result"] == {"text": "t2"}


def test_text_chunk_event_overrides(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda(
        "chunk_override", "services/rag-stack/src/text_chunk_lambda.py"
    )
    event = {"text": "abcdef", "chunk_size": 3, "chunk_overlap": 1}
    out = module.lambda_handler(event, {})
    assert [c["text"] for c in out["chunks"]] == ["abc", "cde", "ef"]


def test_text_chunk_strategy_override(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk_strategy", "services/rag-stack/src/text_chunk_lambda.py")

    class FakeChunker:
        def __init__(self, max_tokens=0, overlap=0):
            pass

        def chunk(self, text: str, file_name: str | None = None):
            return [type("C", (), {"text": "univ"})]

    monkeypatch.setattr(module, "UniversalFileChunker", FakeChunker)
    out = module.lambda_handler({"text": "abc", "chunkStrategy": "universal"}, {})
    assert [c["text"] for c in out["chunks"]] == ["univ"]


def test_text_chunk_strategy_default(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk_strategy_default", "services/rag-stack/src/text_chunk_lambda.py")

    class FakeChunker:
        def __init__(self, *a, **k):
            raise AssertionError("should not be called")

    monkeypatch.setattr(module, "UniversalFileChunker", FakeChunker)
    out = module.lambda_handler({"text": "abcd", "chunk_size": 2}, {})
    assert [c["text"] for c in out["chunks"]] == ["ab", "cd"]


def test_embed_event_override(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_override", "services/rag-stack/src/embed_lambda.py")
    monkeypatch.setattr(module, "_openai_embed", lambda t: [9])
    module._MODEL_MAP["openai"] = module._openai_embed
    out = module.lambda_handler({"chunks": ["x"], "embedModel": "openai"}, {})
    assert out["embeddings"] == [[9]]
    assert out["metadatas"] == [None]


def test_text_chunk_entities(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    monkeypatch.setenv("EXTRACT_ENTITIES", "true")
    module = load_lambda(
        "chunk_entities", "services/rag-stack/src/text_chunk_lambda.py"
    )
    monkeypatch.setattr(module, "extract_entities", lambda t: ["ORG:Acme"])
    out = module.lambda_handler({"text": "Acme Corp report"}, {})
    md = out["chunks"][0]["metadata"]
    assert md["entities"] == ["ORG:Acme"]


def test_vector_search_top_k(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    called = {}

    def fake_search(self, embedding, top_k=5):
        called["top_k"] = top_k
        return [type("R", (), {"id": 1, "score": 0.1, "metadata": {}})]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    proxy.lambda_handler({"operation": "search", "embedding": [0.1], "top_k": 7}, {})
    assert called["top_k"] == 7


def test_vector_search_invalid(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    out = proxy.lambda_handler({"operation": "search", "embedding": "bad"}, {})
    assert out["matches"] == []


def test_vector_search_filters(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")

    def fake_search(self, embedding, top_k=5):
        meta1 = {"department": "HR", "team": "x", "user": "u1"}
        meta2 = {"department": "IT", "team": "y", "user": "u2"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = proxy.lambda_handler({"operation": "search", "embedding": [0.1], "department": "HR"}, {})
    assert (
        len(res["matches"]) == 1 and res["matches"][0]["metadata"]["department"] == "HR"
    )


def test_vector_search_entity_filter(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")

    def fake_search(self, embedding, top_k=5):
        meta1 = {"entities": ["ORG:Acme"]}
        meta2 = {"entities": ["ORG:Other"]}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = proxy.lambda_handler({"operation": "search", "embedding": [0.1], "entities": ["ORG:Acme"]}, {})
    assert len(res["matches"]) == 1 and res["matches"][0]["metadata"]["entities"] == [
        "ORG:Acme"
    ]


def test_vector_search_guid_filter(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")

    def fake_search(self, embedding, top_k=5):
        meta1 = {"file_guid": "g1", "file_name": "a"}
        meta2 = {"file_guid": "g2", "file_name": "b"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = proxy.lambda_handler({"operation": "search", "embedding": [0.1], "file_guid": "g2"}, {})
    assert len(res["matches"]) == 1 and res["matches"][0]["metadata"]["file_guid"] == "g2"


def test_file_processing_passthrough(monkeypatch, s3_stub):
    module = load_lambda(
        "file_proc2", "services/file-ingestion/src/file_processing_lambda.py"
    )
    monkeypatch.setattr(module, "copy_file_to_idp", lambda b, k: "s3://dest/key")
    event = FileProcessingEvent(
        file="s3://bucket/test.pdf",
        ingest_params={"chunk_size": 2},
        collection_name="c",
    )
    out = module.process_files(event, {})
    assert out["ingest_params"] == {"chunk_size": 2}
    assert out["collection_name"] == "c"


def test_summary_lambda_forwards():
    module = load_lambda(
        "sum_lambda", "services/summarization/src/file_summary_lambda.py"
    )
    event = SummaryEvent(
        collection_name="c",
        file_guid="g",
        document_id="d",
        statusCode=200,
        organic_bucket="b",
        organic_bucket_key="extracted/x.pdf",
        summaries=[{"Title": "T", "content": "ok"}],
    )
    resp = module.lambda_handler(event, {})
    body = resp["body"]
    assert resp["statusCode"] == 200
    assert body["file_guid"] == "g" and body["document_id"] == "d"
    assert body["summaries"] == [{"Title": "T", "content": "ok"}]


def test_summary_lambda_docx():
    module = load_lambda(
        "sum_lambda2", "services/summarization/src/file_summary_lambda.py"
    )

    event = SummaryEvent(
        collection_name="c",
        file_guid="g",
        document_id="d",
        statusCode=200,
        organic_bucket="b",
        organic_bucket_key="extracted/x.pdf",
        summaries=[{"Title": "T", "content": "ok"}],
    )
    resp = module.lambda_handler(event, {})
    body = resp["body"]
    assert resp["statusCode"] == 200
    assert body["summaries"][0]["Title"] == "T" and body["file_guid"] == "g"


def test_processing_status(monkeypatch, s3_stub, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/IDP_BUCKET"] = "bucket"
    text_doc_prefix = "text-docs/"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = text_doc_prefix
    module = load_lambda(
        "status_lambda", "services/file-ingestion/src/file_processing_status_lambda.py"
    )
    monkeypatch.setattr(module, "s3_client", s3_stub)
    s3_stub.objects[("bucket", f"{text_doc_prefix}doc.json")] = b"x"
    event = ProcessingStatusEvent(document_id="doc")
    resp = module.lambda_handler(event, {})
    assert resp["statusCode"] == 200
    assert resp["body"]["fileupload_status"] == "COMPLETE"


def test_text_chunk_guid_metadata(config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk_guid", "services/rag-stack/src/text_chunk_lambda.py")
    event = {"text": "hello world", "file_guid": "abc", "file_name": "f.pdf"}
    out = module.lambda_handler(event, {})
    md = out["chunks"][0]["metadata"]
    import hashlib
    expected_hash = hashlib.sha256("hello world".encode("utf-8")).hexdigest()
    assert md["file_guid"] == "abc" and md["file_name"] == "f.pdf"
    assert md["hash_key"] == expected_hash


def test_embed_propagates_guid(config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    chunk_mod = load_lambda("chunk_guid", "services/rag-stack/src/text_chunk_lambda.py")
    embed_mod = load_lambda("embed_guid", "services/rag-stack/src/embed_lambda.py")
    embed_mod._MODEL_MAP["sbert"] = lambda t: [0.0]
    chunks = chunk_mod.lambda_handler({"text": "hello", "file_guid": "g", "file_name": "n"}, {})["chunks"]
    out = embed_mod.lambda_handler({"chunks": chunks}, {})
    md = out["metadatas"][0]
    import hashlib
    expected_hash = hashlib.sha256("hello".encode("utf-8")).hexdigest()
    assert md["file_guid"] == "g" and md["file_name"] == "n" and md["hash_key"] == expected_hash


def test_milvus_insert_adds_guid(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")
    monkeypatch.setattr(module, "client", type("C", (), {"insert": lambda s, i, upsert=True: len(i)})())
    event = {"embeddings": [[0.1]], "metadatas": [{}], "file_guid": "g", "file_name": "n"}
    res = proxy.lambda_handler(dict(event, operation="insert"), {})
    assert res["inserted"] == 1


def test_vector_search_guid_filter(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    import types, sys

    dummy = types.ModuleType("pymilvus")
    dummy.Collection = type("Coll", (), {"__init__": lambda self, *a, **k: None})
    dummy.connections = types.SimpleNamespace(connect=lambda alias, host, port: None)
    monkeypatch.setitem(sys.modules, "pymilvus", dummy)
    import common_utils.milvus_client as mc

    monkeypatch.setattr(mc, "Collection", dummy.Collection, raising=False)
    monkeypatch.setattr(mc, "connections", dummy.connections, raising=False)

    module = import_vector_module("milvus_handler_lambda")
    proxy = import_vector_module("vector_db_proxy_lambda")

    def fake_search(self, embedding, top_k=5):
        meta1 = {"file_guid": "g1", "file_name": "a"}
        meta2 = {"file_guid": "g2", "file_name": "b"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = proxy.lambda_handler({"operation": "search", "embedding": [0.1], "file_guid": "g2"}, {})
    assert len(res["matches"]) == 1
    assert res["matches"][0]["metadata"]["file_guid"] == "g2"


def test_detect_pii_ml(monkeypatch, validate_pii_schema):
    module = load_lambda(
        "detect_pii_ml", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    class DummyRes:
        def __init__(self, etype, start, end):
            self.entity_type = etype
            self.start = start
            self.end = end

    class DummyEngine:
        def analyze(self, text, language="en"):
            return [DummyRes("PERSON", 0, 4)]

    monkeypatch.setattr(module, "_build_engine", lambda *a, **k: DummyEngine())

    out = module.lambda_handler({"text": "John 123-45-6789"}, {})
    validate_pii_schema(out)
    assert any(
        e.get("text") == "John" and e.get("type") == "PERSON" and e.get("start") == 0 and e.get("end") == 4
        for e in out["entities"]
    )
    assert any(e["type"] == "SSN" for e in out["entities"])


def test_detect_pii_regex(monkeypatch, validate_pii_schema):
    module = load_lambda(
        "detect_pii_regex", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )
    monkeypatch.setattr(module, "_build_engine", lambda *a, **k: None)

    out = module.lambda_handler({"text": "Card 4111 1111 1111 1111"}, {})
    validate_pii_schema(out)
    assert any(e["type"] == "CREDIT_CARD" for e in out["entities"])


def test_detect_pii_medical_domain(monkeypatch, validate_pii_schema):
    module = load_lambda(
        "detect_pii_medical", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    class DummyRes:
        def __init__(self, etype, start, end):
            self.entity_type = etype
            self.start = start
            self.end = end

    class DummyEngine:
        def analyze(self, text, language="en"):
            return [DummyRes("PATIENT", 0, 4)]

    monkeypatch.setattr(module, "_build_engine", lambda *a, **k: DummyEngine())

    out = module.lambda_handler({"text": "Jane", "domain": "Medical"}, {})
    validate_pii_schema(out)
    assert any(e["type"] == "PATIENT" for e in out["entities"])


def test_detect_pii_legal_regex(monkeypatch, validate_pii_schema):
    module = load_lambda(
        "detect_pii_legal", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    monkeypatch.setattr(module, "_build_engine", lambda *a, **k: None)
    text = "case 12-12345"
    out = module.lambda_handler({"text": text, "classification": "Legal"}, {})
    validate_pii_schema(out)
    assert any(e["type"] == "CASE_NUMBER" for e in out["entities"])


def test_detect_pii_legal_domain(monkeypatch, validate_pii_schema):
    module = load_lambda(
        "detect_pii_legal_domain", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    class DummyRes:
        def __init__(self, etype, start, end):
            self.entity_type = etype
            self.start = start
            self.end = end

    called = {}

    class DummyEngine:
        def analyze(self, text, language="en"):
            return [DummyRes("LAWYER", 0, 3)]

    def fake_load(*args, **kwargs):
        called["loaded"] = True
        return DummyEngine()

    monkeypatch.setattr(module, "_build_engine", fake_load)
    monkeypatch.setattr(module, "_load_model", lambda: (_ for _ in ()).throw(AssertionError()))

    out = module.lambda_handler({"text": "Bob", "domain": "Legal"}, {})
    validate_pii_schema(out)
    assert called.get("loaded")
    assert any(e["type"] == "LAWYER" for e in out["entities"])


def test_detect_pii_custom_regex(monkeypatch, validate_pii_schema):
    pattern = {"FOO": r"foo\d+"}
    monkeypatch.setenv("REGEX_PATTERNS", json.dumps(pattern))
    module = load_lambda(
        "detect_pii_custom", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    monkeypatch.setattr(module, "_build_engine", lambda *a, **k: None)
    out = module.lambda_handler({"text": "foo123"}, {})
    validate_pii_schema(out)
    assert any(e["type"] == "FOO" for e in out["entities"])


class _DummyRes:
    def __init__(self, typ, start, end, score=1.0):
        self.entity_type = typ
        self.start = start
        self.end = end
        self.score = score


def test_detect_and_mask(monkeypatch):
    import types, sys
    class FakeGen:
        def __init__(self):
            self.count = 0
        def name(self):
            self.count += 1
            return f"name{self.count}"
        def company(self):
            return "company"
        def city(self):
            return "city"
        def address(self):
            return "addr"
        def phone_number(self):
            return "phone"
        def email(self):
            return "email"
        def word(self):
            return "word"
    fake = FakeGen()
    monkeypatch.setitem(sys.modules, "faker", types.SimpleNamespace(Faker=lambda: fake))

    detect = load_lambda(
        "detect_mask", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    class DummyEngine:
        def analyze(self, text, language="en"):
            return [_DummyRes("PERSON", 0, 5, 0.95), _DummyRes("PERSON", 10, 13, 0.95)]

    monkeypatch.setattr(detect, "_build_engine", lambda *a, **k: DummyEngine())

    entities = detect.lambda_handler({"text": "Alice met Bob."}, {})["entities"]

    monkeypatch.setenv("ANON_MODE", "mask")
    mask = load_lambda("mask", "services/anonymization/src/mask_text_lambda.py")

    out = mask.lambda_handler({"text": "Alice met Bob.", "entities": entities}, {})
    assert out["text"] == "[PERSON] met [PERSON]."


def test_detect_and_mask_confidence(monkeypatch):
    import types, sys
    class FakeGen:
        def __init__(self):
            self.count = 0
        def name(self):
            self.count += 1
            return f"name{self.count}"
        def company(self):
            return "company"
        def city(self):
            return "city"
        def address(self):
            return "addr"
        def phone_number(self):
            return "phone"
        def email(self):
            return "email"
        def word(self):
            return "word"
    fake = FakeGen()
    monkeypatch.setitem(sys.modules, "faker", types.SimpleNamespace(Faker=lambda: fake))

    detect = load_lambda(
        "detect_mask_conf", "services/anonymization/src/detect_sensitive_info_lambda.py"
    )

    monkeypatch.setattr(detect, "_build_engine", lambda *a, **k: None)

    def fake_ml(text, engine=None):
        return [
            {"text": "Alice", "type": "PERSON", "start": 0, "end": 5, "score": 0.8},
            {"text": "Bob", "type": "PERSON", "start": 10, "end": 13, "score": 0.95},
        ]

    monkeypatch.setattr(detect, "_ml_entities", fake_ml)
    monkeypatch.setattr(detect, "_regex_entities", lambda *a, **k: [])

    entities = detect.lambda_handler({"text": "Alice met Bob."}, {})["entities"]

    monkeypatch.setenv("ANON_MODE", "mask")
    monkeypatch.setenv("ANON_CONFIDENCE", "0.9")
    mask = load_lambda("mask_conf", "services/anonymization/src/mask_text_lambda.py")

    out = mask.lambda_handler({"text": "Alice met Bob.", "entities": entities}, {})
    assert out["text"] == "Alice met [PERSON]."
