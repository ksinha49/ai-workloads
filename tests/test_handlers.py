import json
import importlib.util
import os
import io
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.file_ingestion.models import FileProcessingEvent, ProcessingStatusEvent
from services.summarization.models import SummaryEvent


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    config[f"{prefix}/OFFICE_PREFIX"] = "office-docs/"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = "text-docs/"
    module = load_lambda("office", "services/idp/2-office-extractor/app.py")

    s3_stub.objects[("bucket", "office-docs/test.docx")] = b"data"

    monkeypatch.setattr(module, "_extract_docx", lambda b: ["## Page 1\n\ntext\n"])
    monkeypatch.setattr(module, "_extract_pptx", lambda b: ["## Page 1\n\ntext\n"])
    monkeypatch.setattr(module, "_extract_xlsx", lambda b: ["## Page 1\n\ntext\n"])

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": "office-docs/test.docx"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    out_key = "text-docs/test.json"
    payload = json.loads(s3_stub.objects[("bucket", out_key)].decode())
    assert payload["documentId"] == "test"
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
    config[f"{prefix}/PDF_TEXT_PAGE_PREFIX"] = "text-pages/"
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = "text-pages/"
    module = load_lambda("pdf_text", "services/idp/5-pdf-text-extractor/app.py")

    s3_stub.objects[("bucket", "text-pages/doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_extract_text", lambda b: "## Page 1\n\nhello\n")

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": "text-pages/doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", "text-pages/doc1/page_001.md")].decode()
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = "scan-pages/"
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = "text-pages/"
    module = load_lambda("ocr", "services/idp/6-pdf-ocr-extractor/app.py")

    s3_stub.objects[("bucket", "scan-pages/doc1/page_001.pdf")] = b"data"

    monkeypatch.setattr(module, "_rasterize_page", lambda b, dpi: object())
    monkeypatch.setattr(module, "_ocr_image", lambda img, e, t, d: "## Page 1\n\nocr\n")

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": "scan-pages/doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", "text-pages/doc1/page_001.md")].decode()
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor_trocr(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = "scan-pages/"
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = "text-pages/"
    config[f"{prefix}/OCR_ENGINE"] = "trocr"
    config[f"{prefix}/TROCR_ENDPOINT"] = "http://example"
    module = load_lambda("ocr_trocr", "services/idp/6-pdf-ocr-extractor/app.py")

    s3_stub.objects[("bucket", "scan-pages/doc1/page_001.pdf")] = b"data"

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
                    "object": {"key": "scan-pages/doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", "text-pages/doc1/page_001.md")].decode()
    assert called["engine"] == "trocr"
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_pdf_ocr_extractor_docling(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/PDF_SCAN_PAGE_PREFIX"] = "scan-pages/"
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = "text-pages/"
    config[f"{prefix}/OCR_ENGINE"] = "docling"
    config[f"{prefix}/DOCLING_ENDPOINT"] = "http://example"
    module = load_lambda("ocr_docling", "services/idp/6-pdf-ocr-extractor/app.py")

    s3_stub.objects[("bucket", "scan-pages/doc1/page_001.pdf")] = b"data"

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
                    "object": {"key": "scan-pages/doc1/page_001.pdf"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    md = s3_stub.objects[("bucket", "text-pages/doc1/page_001.md")].decode()
    assert called["engine"] == "docling"
    schema = {"documentId": "doc1", "pageNumber": 1, "content": md}
    validate_schema(schema)


def test_combine(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/PDF_PAGE_PREFIX"] = "pdf-pages/"
    config[f"{prefix}/TEXT_PAGE_PREFIX"] = "text-pages/"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = "text-docs/"
    module = load_lambda("combine", "services/idp/7-combine/app.py")

    s3_stub.objects[("bucket", "pdf-pages/doc1/manifest.json")] = json.dumps(
        {"documentId": "doc1", "pages": 2}
    ).encode()
    s3_stub.objects[("bucket", "text-pages/doc1/page_001.md")] = b"## Page 1\n\none\n"
    s3_stub.objects[("bucket", "text-pages/doc1/page_002.md")] = b"## Page 2\n\ntwo\n"

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": "text-pages/doc1/page_001.md"},
                }
            }
        ]
    }
    module.lambda_handler(event, {})

    output = json.loads(s3_stub.objects[("bucket", "text-docs/doc1.json")].decode())
    assert output["documentId"] == "doc1"
    assert output["pageCount"] == 2
    for i, page in enumerate(output["pages"], start=1):
        validate_schema(
            {"documentId": output["documentId"], "pageNumber": i, "content": page}
        )


def test_output(monkeypatch, s3_stub, validate_schema, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/BUCKET_NAME"] = "bucket"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = "text-docs/"
    config[f"{prefix}/EDI_SEARCH_API_URL"] = "http://example"
    config[f"{prefix}/EDI_SEARCH_API_KEY"] = "key"
    module = load_lambda("output", "services/idp/8-output/app.py")

    payload = {
        "documentId": "doc1",
        "type": "pdf",
        "pageCount": 1,
        "pages": ["## Page 1\n\nhi\n"],
    }
    s3_stub.objects[("bucket", "text-docs/doc1.json")] = json.dumps(payload).encode()

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
                    "object": {"key": "text-docs/doc1.json"},
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
    module = load_lambda("ocr_easy", "services/idp/6-pdf-ocr-extractor/app.py")
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
    module = load_lambda("ocr_paddle", "services/idp/6-pdf-ocr-extractor/app.py")
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
    module = load_lambda("ocr_trocr_engine", "services/idp/6-pdf-ocr-extractor/app.py")
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
        "ocr_docling_engine", "services/idp/6-pdf-ocr-extractor/app.py"
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

    with pytest.raises(ValueError):
        mod._perform_ocr(reader, "other", b"1")


def test_embed_model_map_event(monkeypatch, config):
    monkeypatch.setenv("EMBED_MODEL", "sbert")
    monkeypatch.setenv("EMBED_MODEL_MAP", '{"pdf": "openai"}')
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_event", "services/rag-ingestion/embed-lambda/app.py")
    monkeypatch.setattr(module, "_openai_embed", lambda t: [42])
    module._MODEL_MAP["openai"] = module._openai_embed
    out = module.lambda_handler({"chunks": ["t"], "docType": "pdf"}, {})
    assert out["embeddings"] == [[42]]
    assert out["metadatas"] == [None]


def test_embed_model_map_chunk(monkeypatch, config):
    monkeypatch.setenv("EMBED_MODEL", "sbert")
    monkeypatch.setenv("EMBED_MODEL_MAP", '{"pptx": "cohere"}')
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_chunk", "services/rag-ingestion/embed-lambda/app.py")
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
    module = load_lambda("embed_default", "services/rag-ingestion/embed-lambda/app.py")
    monkeypatch.setattr(module, "_cohere_embed", lambda t: [7])
    module._MODEL_MAP["cohere"] = module._cohere_embed
    out = module.lambda_handler({"chunks": ["x"], "docType": "txt"}, {})
    assert out["embeddings"] == [[7]]
    assert out["metadatas"] == [None]


def test_text_chunk_doc_type(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk", "services/rag-ingestion/text-chunk-lambda/app.py")
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

    module = load_lambda(
        "milvus_delete", "services/vector-db/milvus-delete-lambda/app.py"
    )
    called = {}

    def fake_delete(self, ids):
        called["ids"] = list(ids)
        return len(called["ids"])

    monkeypatch.setattr(module, "client", type("C", (), {"delete": fake_delete})())
    res = module.lambda_handler({"ids": [1, 2]}, {})
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

    module = load_lambda(
        "milvus_update", "services/vector-db/milvus-update-lambda/app.py"
    )
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
    res = module.lambda_handler(event, {})
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

    module = load_lambda(
        "milvus_create", "services/vector-db/milvus-create-lambda/app.py"
    )
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
    res = module.lambda_handler({"dimension": 42}, {})
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

    module = load_lambda("milvus_drop", "services/vector-db/milvus-drop-lambda/app.py")
    called = {"dropped": False}

    def fake_drop():
        called["dropped"] = True

    monkeypatch.setattr(
        module, "client", type("C", (), {"drop_collection": lambda self: fake_drop()})()
    )
    res = module.lambda_handler({}, {})
    assert called["dropped"] is True
    assert res["dropped"] is True


def test_es_insert_lambda(monkeypatch):
    module = load_lambda("es_insert", "services/vector-db/es-insert-lambda/app.py")
    captured = {}

    def fake_insert(self, docs):
        captured["docs"] = list(docs)
        return len(captured["docs"])

    monkeypatch.setattr(module, "client", type("C", (), {"insert": fake_insert})())
    res = module.lambda_handler({"documents": [{"id": "1", "text": "a"}]}, {})
    assert captured["docs"][0]["id"] == "1"
    assert res["inserted"] == 1


def test_es_delete_lambda(monkeypatch):
    module = load_lambda("es_delete", "services/vector-db/es-delete-lambda/app.py")
    called = {}

    def fake_delete(self, ids):
        called["ids"] = list(ids)
        return len(called["ids"])

    monkeypatch.setattr(module, "client", type("C", (), {"delete": fake_delete})())
    res = module.lambda_handler({"ids": ["1", "2"]}, {})
    assert called["ids"] == ["1", "2"]
    assert res["deleted"] == 2


def test_es_update_lambda(monkeypatch):
    module = load_lambda("es_update", "services/vector-db/es-update-lambda/app.py")
    captured = {}

    def fake_update(self, docs):
        captured["docs"] = list(docs)
        return len(captured["docs"])

    monkeypatch.setattr(module, "client", type("C", (), {"update": fake_update})())
    res = module.lambda_handler({"documents": [{"id": "1", "text": "x"}]}, {})
    assert captured["docs"][0]["text"] == "x"
    assert res["updated"] == 1


def test_es_create_lambda(monkeypatch):
    module = load_lambda("es_create", "services/vector-db/es-create-lambda/app.py")
    called = {"created": False}
    monkeypatch.setattr(
        module,
        "client",
        type(
            "C", (), {"create_index": lambda self: called.__setitem__("created", True)}
        )(),
    )
    res = module.lambda_handler({}, {})
    assert called["created"] is True
    assert res["created"] is True


def test_es_drop_lambda(monkeypatch):
    module = load_lambda("es_drop", "services/vector-db/es-drop-lambda/app.py")
    called = {"dropped": False}
    monkeypatch.setattr(
        module,
        "client",
        type(
            "C", (), {"drop_index": lambda self: called.__setitem__("dropped", True)}
        )(),
    )
    res = module.lambda_handler({}, {})
    assert called["dropped"] is True
    assert res["dropped"] is True


def test_es_search_lambda(monkeypatch):
    module = load_lambda("es_search", "services/vector-db/es-search-lambda/app.py")
    captured = {}

    def fake_search(self, embedding, top_k=5):
        captured["top_k"] = top_k
        return [{"id": "1"}]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    out = module.lambda_handler({"embedding": [0.1], "top_k": 3}, {})
    assert captured["top_k"] == 3
    assert out["matches"][0]["id"] == "1"


def test_es_hybrid_search_lambda(monkeypatch):
    module = load_lambda(
        "es_hybrid", "services/vector-db/es-hybrid-search-lambda/app.py"
    )
    captured = {}

    def fake_search(self, embedding, keywords=None, top_k=5):
        captured["kw"] = list(keywords)
        return [{"id": "1"}]

    monkeypatch.setattr(
        module, "client", type("C", (), {"hybrid_search": fake_search})()
    )
    out = module.lambda_handler({"embedding": [0.1], "keywords": ["x"]}, {})
    assert captured["kw"] == ["x"]
    assert out["matches"][0]["id"] == "1"


import sys


def test_llm_router_choose_backend(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    module = load_lambda("llm_router_app", "services/llm-router/router-lambda/app.py")
    assert module._choose_backend("one two") == "ollama"
    assert module._choose_backend("one two three four") == "bedrock"


def test_llm_router_lambda_handler(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    calls = []
    monkeypatch.setattr(
        sys.modules["boto3"], "client", lambda name: _make_fake_send(calls)
    )
    module = load_lambda(
        "llm_router_lambda", "services/llm-router/router-lambda/app.py"
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
        "llm_router_lambda_override", "services/llm-router/router-lambda/app.py"
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


def test_llm_router_choose_backend_default(monkeypatch):
    monkeypatch.delenv("PROMPT_COMPLEXITY_THRESHOLD", raising=False)
    module = load_lambda(
        "llm_router_app_default", "services/llm-router/router-lambda/app.py"
    )
    short_prompt = " ".join(["w"] * 5)
    long_prompt = " ".join(["w"] * 25)
    assert module._choose_backend(short_prompt) == "ollama"
    assert module._choose_backend(long_prompt) == "bedrock"


def test_llm_router_lambda_handler_default(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.delenv("PROMPT_COMPLEXITY_THRESHOLD", raising=False)
    calls = []
    monkeypatch.setattr(
        sys.modules["boto3"], "client", lambda name: _make_fake_send(calls)
    )
    module = load_lambda(
        "llm_router_lambda_default", "services/llm-router/router-lambda/app.py"
    )
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event1 = {"body": json.dumps({"prompt": "short text"})}
    out1 = module.lambda_handler(event1, {})
    body1 = json.loads(out1["body"])
    assert body1["backend"] == "ollama"
    assert body1["queued"] is True
    assert calls[0]["backend"] == "ollama"

    long_prompt = " ".join(["w"] * 25)
    event2 = {"body": json.dumps({"prompt": long_prompt})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "bedrock"
    assert body2["queued"] is True
    assert calls[1]["backend"] == "bedrock"


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
        "summ_ctx", "services/rag-retrieval/summarize-with-context-lambda/app.py"
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
    assert sent["payload"] == {
        "query": "hi",
        "model": "phi",
        "temperature": 0.2,
        "context": "ctx",
        "collection_name": "c",
    }
    assert out["summary"] == {"text": "ok"}


def test_rerank_lambda(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("rerank", "services/rag-retrieval/rerank-lambda/app.py")
    monkeypatch.setattr(module, "_score_pairs", lambda q, d: [0.1, 0.9])
    matches = [
        {"id": 1, "metadata": {"text": "a"}},
        {"id": 2, "metadata": {"text": "b"}},
    ]
    out = module.lambda_handler({"query": "x", "matches": matches, "top_k": 1}, {})
    assert out["matches"][0]["id"] == 2
    assert "rerank_score" in out["matches"][0]


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

    module = load_lambda(
        "summ_ctx_rerank", "services/rag-retrieval/summarize-with-context-lambda/app.py"
    )
    monkeypatch.setattr(
        module, "lambda_client", type("C", (), {"invoke": staticmethod(fake_invoke)})()
    )
    monkeypatch.setattr(module, "_sbert_embed", lambda t: [0.1])
    module._MODEL_MAP["sbert"] = module._sbert_embed
    monkeypatch.setattr(module, "forward_to_routellm", lambda p: {"text": p["context"]})

    out = module.lambda_handler({"query": "hi", "collection_name": "c"}, {})
    assert fake_invoke.rerank["query"] == "hi"
    assert out["summary"] == {"text": "t2"}


def test_text_chunk_event_overrides(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda(
        "chunk_override", "services/rag-ingestion/text-chunk-lambda/app.py"
    )
    event = {"text": "abcdef", "chunk_size": 3, "chunk_overlap": 1}
    out = module.lambda_handler(event, {})
    assert [c["text"] for c in out["chunks"]] == ["abc", "cde", "ef"]


def test_embed_event_override(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_override", "services/rag-ingestion/embed-lambda/app.py")
    monkeypatch.setattr(module, "_openai_embed", lambda t: [9])
    module._MODEL_MAP["openai"] = module._openai_embed
    out = module.lambda_handler({"chunks": ["x"], "embedModel": "openai"}, {})
    assert out["embeddings"] == [[9]]
    assert out["metadatas"] == [None]


def test_text_chunk_entities(monkeypatch, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    monkeypatch.setenv("EXTRACT_ENTITIES", "true")
    module = load_lambda(
        "chunk_entities", "services/rag-ingestion/text-chunk-lambda/app.py"
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

    module = load_lambda(
        "vector_search", "services/vector-db/vector-search-lambda/app.py"
    )
    called = {}

    def fake_search(self, embedding, top_k=5):
        called["top_k"] = top_k
        return [type("R", (), {"id": 1, "score": 0.1, "metadata": {}})]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    module.lambda_handler({"embedding": [0.1], "top_k": 7}, {})
    assert called["top_k"] == 7


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

    module = load_lambda(
        "vector_search", "services/vector-db/vector-search-lambda/app.py"
    )

    def fake_search(self, embedding, top_k=5):
        meta1 = {"department": "HR", "team": "x", "user": "u1"}
        meta2 = {"department": "IT", "team": "y", "user": "u2"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = module.lambda_handler({"embedding": [0.1], "department": "HR"}, {})
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

    module = load_lambda(
        "vector_search_ent", "services/vector-db/vector-search-lambda/app.py"
    )

    def fake_search(self, embedding, top_k=5):
        meta1 = {"entities": ["ORG:Acme"]}
        meta2 = {"entities": ["ORG:Other"]}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = module.lambda_handler({"embedding": [0.1], "entities": ["ORG:Acme"]}, {})
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

    module = load_lambda(
        "vector_search_guid", "services/vector-db/vector-search-lambda/app.py"
    )

    def fake_search(self, embedding, top_k=5):
        meta1 = {"file_guid": "g1", "file_name": "a"}
        meta2 = {"file_guid": "g2", "file_name": "b"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = module.lambda_handler({"embedding": [0.1], "file_guid": "g2"}, {})
    assert len(res["matches"]) == 1 and res["matches"][0]["metadata"]["file_guid"] == "g2"


def test_file_processing_passthrough(monkeypatch):
    module = load_lambda(
        "file_proc2", "services/file-ingestion/file-processing-lambda/app.py"
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


def test_summary_lambda_forwards(monkeypatch):
    import types, sys

    # ensure httpx provides Timeout and HTTPStatusError
    sys.modules["httpx"].Timeout = object
    sys.modules["httpx"].HTTPStatusError = type("E", (Exception,), {})
    sys.modules["fpdf"] = types.ModuleType("fpdf")
    sys.modules["fpdf"].FPDF = object
    sys.modules["unidecode"] = types.ModuleType("unidecode")
    sys.modules["unidecode"].unidecode = lambda x: x

    module = load_lambda(
        "sum_lambda", "services/summarization/file-summary-lambda/app.py"
    )
    captured = {}

    def fake_create(summaries):
        captured["summaries"] = summaries
        return io.BytesIO(b"d")

    def fake_upload(buf, bucket, key):
        captured["bucket"] = bucket
        captured["key"] = key

    monkeypatch.setattr(module, "create_summary_pdf", fake_create)
    monkeypatch.setattr(module, "upload_buffer_to_s3", fake_upload)

    event = SummaryEvent(
        collection_name="c",
        statusCode=200,
        organic_bucket="b",
        organic_bucket_key="extracted/x.pdf",
        summaries=[{"Title": "T", "content": "ok"}],
    )
    module.lambda_handler(event, {})
    assert captured["summaries"] == [("T", "ok")]
    assert captured["bucket"] == "b"
    assert captured["key"] == "summary/x.pdf"


def test_processing_status(monkeypatch, s3_stub, config):
    prefix = "/parameters/aio/ameritasAI/dev"
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    config[f"{prefix}/IDP_BUCKET"] = "bucket"
    config[f"{prefix}/TEXT_DOC_PREFIX"] = "text-docs/"
    module = load_lambda(
        "status_lambda", "services/file-ingestion/file-processing-status-lambda/app.py"
    )
    monkeypatch.setattr(module, "s3_client", s3_stub)
    s3_stub.objects[("bucket", "text-docs/doc.json")] = b"x"
    event = ProcessingStatusEvent(document_id="doc")
    resp = module.lambda_handler(event, {})
    assert resp["statusCode"] == 200
    assert resp["body"]["fileupload_status"] == "COMPLETE"


def test_text_chunk_guid_metadata(config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("chunk_guid", "services/rag-ingestion/text-chunk-lambda/app.py")
    event = {"text": "hello world", "file_guid": "abc", "file_name": "f.pdf"}
    out = module.lambda_handler(event, {})
    md = out["chunks"][0]["metadata"]
    assert md["file_guid"] == "abc" and md["file_name"] == "f.pdf"


def test_embed_propagates_guid(config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    module = load_lambda("embed_guid", "services/rag-ingestion/embed-lambda/app.py")
    module._MODEL_MAP["sbert"] = lambda t: [0.0]
    event = {"chunks": [{"text": "x", "metadata": {}}], "file_guid": "g", "file_name": "n"}
    out = module.lambda_handler(event, {})
    assert out["metadatas"][0]["file_guid"] == "g" and out["metadatas"][0]["file_name"] == "n"


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

    module = load_lambda("milvus_ins", "services/vector-db/milvus-insert-lambda/app.py")
    monkeypatch.setattr(module, "client", type("C", (), {"insert": lambda s, i, upsert=True: len(i)})())
    event = {"embeddings": [[0.1]], "metadatas": [{}], "file_guid": "g", "file_name": "n"}
    res = module.lambda_handler(event, {})
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

    module = load_lambda(
        "vector_search_guid", "services/vector-db/vector-search-lambda/app.py"
    )

    def fake_search(self, embedding, top_k=5):
        meta1 = {"file_guid": "g1", "file_name": "a"}
        meta2 = {"file_guid": "g2", "file_name": "b"}
        return [
            type("R", (), {"id": 1, "score": 0.1, "metadata": meta1}),
            type("R", (), {"id": 2, "score": 0.2, "metadata": meta2}),
        ]

    monkeypatch.setattr(module, "client", type("C", (), {"search": fake_search})())
    res = module.lambda_handler({"embedding": [0.1], "file_guid": "g2"}, {})
    assert len(res["matches"]) == 1
    assert res["matches"][0]["metadata"]["file_guid"] == "g2"
