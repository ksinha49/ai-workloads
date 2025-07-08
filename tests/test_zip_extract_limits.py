import importlib.util
import io
import json
import zipfile


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_event(key="path/in.zip"):
    body = json.dumps({"detail": {"bucket": {"name": "bucket"}, "object": {"key": key}}})
    return {"Records": [{"body": body}]}


def test_rejects_large_entry(monkeypatch, s3_stub, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("file.pdf", b"abcdef")
    s3_stub.objects[("bucket", "path/in.zip")] = buf.getvalue()

    monkeypatch.setenv("ZIP_MAX_FILE_BYTES", "5")
    module = load_lambda("zip_extract_large", "services/zip-processing/src/zip_extract_lambda.py")
    out = module.extract_zip_file(_make_event())
    assert out["statusCode"] == 400


def test_rejects_total_size(monkeypatch, s3_stub, config):
    config["/parameters/aio/ameritasAI/SERVER_ENV"] = "dev"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("f1.pdf", b"1234")
        zf.writestr("f2.pdf", b"5678")
    s3_stub.objects[("bucket", "path/in.zip")] = buf.getvalue()

    monkeypatch.setenv("ZIP_MAX_FILE_BYTES", "10")
    monkeypatch.setenv("ZIP_MAX_ARCHIVE_BYTES", "6")
    module = load_lambda("zip_extract_total", "services/zip-processing/src/zip_extract_lambda.py")
    out = module.extract_zip_file(_make_event())
    assert out["statusCode"] == 400

