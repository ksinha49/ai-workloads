import importlib.util
import io
import sys
import types


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class FakeReader:
    def __init__(self, data):
        if hasattr(data, "read"):
            data = data.read()
        if isinstance(data, bytes):
            data = data.decode()
        self.pages = [FakePage(t) for t in data.split("|") if t]


class FakeWriter:
    def __init__(self):
        self.pages = []

    def add_page(self, page):
        self.pages.append(page)

    def write(self, fh):
        fh.write("|".join(p.extract_text() for p in self.pages).encode())


def _make_pdf(text):
    writer = FakeWriter()
    writer.add_page(FakePage(text))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_merge_pdfs(monkeypatch):
    fake_module = types.SimpleNamespace(PdfReader=FakeReader, PdfWriter=FakeWriter)
    monkeypatch.setitem(sys.modules, "PyPDF2", fake_module)

    module = load_lambda("merge", "services/file-assembly/src/file_assembly_lambda.py")
    monkeypatch.setattr(module, "PdfReader", FakeReader)
    monkeypatch.setattr(module, "PdfWriter", FakeWriter)

    summary_pdf = _make_pdf("summary")
    original_pdf = _make_pdf("original")
    merged = module.merge_pdfs(summary_pdf, original_pdf)
    reader = FakeReader(io.BytesIO(merged))
    texts = [p.extract_text() for p in reader.pages]
    assert texts == ["summary", "original"]


def test_lambda_handler_success(monkeypatch):
    module = load_lambda("handler", "services/file-assembly/src/file_assembly_lambda.py")

    def fake_assemble(event, context, s3_client):
        return {"ok": True}

    monkeypatch.setattr(module, "assemble_files", fake_assemble)
    monkeypatch.setattr(module, "lambda_response", lambda s, b: {"statusCode": s, "body": b})

    out = module.lambda_handler({}, {})
    assert out["statusCode"] == 200
    assert out["body"] == {"ok": True}


def test_lambda_handler_error(monkeypatch):
    module = load_lambda("handler_err", "services/file-assembly/src/file_assembly_lambda.py")

    def boom(event, context, s3_client):
        raise ValueError("boom")

    monkeypatch.setattr(module, "assemble_files", boom)
    monkeypatch.setattr(module, "lambda_response", lambda s, b: {"statusCode": s, "body": b})

    out = module.lambda_handler({}, {})
    assert out["statusCode"] == 500
    assert "error" in out["body"]
