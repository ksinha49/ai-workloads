import pytest
import io
import types
import sys
try:
    import boto3
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal env
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *a, **k: None
    sys.modules['boto3'] = boto3

class DummyS3:
    def __init__(self):
        self.objects = {}
        self.tags = {}

    def get_object(self, Bucket, Key):
        data = self.objects.get((Bucket, Key), b"")
        return {"Body": io.BytesIO(data)}

    def put_object(self, Bucket, Key, Body, **kwargs):
        if hasattr(Body, "read"):
            data = Body.read()
        else:
            data = Body
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.objects[(Bucket, Key)] = data
        return {}

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise self.exceptions.ClientError({"Error": {"Code": "404"}}, "head_object")
        return {}

    def get_object_tagging(self, Bucket, Key):
        tagset = [
            {"Key": k, "Value": v}
            for k, v in self.tags.get((Bucket, Key), {}).items()
        ]
        return {"TagSet": tagset}

    class exceptions:
        class ClientError(Exception):
            def __init__(self, response, op):
                super().__init__("client error")
                self.response = response
                self.operation_name = op

@pytest.fixture
def s3_stub(monkeypatch):
    stub = DummyS3()
    monkeypatch.setattr(boto3, "client", lambda name, *a, **k: stub if name == "s3" else None)
    return stub

def _stub_module(name, attrs=None):
    mod = types.ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod

class _DummyPage:
    def extract_text(self):
        return "APS Summary Hello World A 1"


class _DummyReader:
    def __init__(self, *a, **k):
        self.pages = [_DummyPage()]


_stub_module("PyPDF2", {"PdfReader": _DummyReader, "PdfWriter": object})

@pytest.fixture(autouse=True)
def external_stubs():
    _stub_module("fitz", {"open": lambda *a, **k: types.SimpleNamespace(page_count=1, __iter__=lambda self: [], __getitem__=lambda self, i: types.SimpleNamespace(get_text=lambda: ""), __enter__=lambda self: self, __exit__=lambda self, exc_type, exc, tb: None)})
    _stub_module("docx", {"Document": lambda *a, **k: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="doc text")])})
    _stub_module("pptx", {"Presentation": lambda *a, **k: types.SimpleNamespace(slides=[types.SimpleNamespace(shapes=[types.SimpleNamespace(text="slide text")])])})
    class Sheet:
        def __init__(self):
            self._rows = [[1, 2]]
        def iter_rows(self, values_only=True):
            for row in self._rows:
                yield row
    _stub_module("openpyxl", {"load_workbook": lambda *a, **k: [Sheet()]})
    _stub_module("cv2", {"imencode": lambda ext, img: (True, b"1"), "cvtColor": lambda img, code: img, "COLOR_BGRA2BGR": 0})
    class DummyReader:
        def __init__(self, *a, **k):
            pass
        def readtext(self, img, detail=1):
            return [([[0,0],[1,0],[1,1],[0,1]], "text", 0.9)]
    _stub_module("easyocr", {"Reader": DummyReader})
    class DummyPaddle:
        def __init__(self, *a, **k):
            pass
        def ocr(self, img):
            return [([[0,0],[1,0],[1,1],[0,1]], ("pd", 0.8))]
    _stub_module("paddleocr", {"PaddleOCR": DummyPaddle})
    class DummyPage:
        def extract_text(self):
            return ""

    class DummyReader:
        def __init__(self, *a, **k):
            self.pages = [DummyPage()]

    _stub_module("PyPDF2", {"PdfReader": DummyReader, "PdfWriter": object})
    _stub_module("httpx", {"post": lambda *a, **k: types.SimpleNamespace(json=lambda: {}, raise_for_status=lambda: None)})
    _stub_module(
        "ocr_module",
        {
            "post_process_text": lambda t: t,
            "convert_to_markdown": lambda t, n: f"## Page {n}\n\n{t}\n",
            "easyocr": DummyReader,
            "_perform_ocr": lambda reader, engine, img: ("text", 0.0),
        },
    )
    _stub_module("unidecode", {"unidecode": lambda x: x})
    class FPDF:
        def __init__(self, *a, **k):
            self.font_size = 10
        def set_margins(self, *a):
            pass
        def add_page(self):
            pass
        def set_xy(self, *a):
            pass
        def set_x(self, *a):
            pass
        def get_y(self):
            return 0
        def add_font(self, *a, **k):
            pass
        def set_font(self, *a, **k):
            if "size" in k:
                self.font_size = k["size"]
        def multi_cell(self, *a, **k):
            pass
        def ln(self, *a):
            pass
        class _Table:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                pass
            def row(self):
                class R:
                    def cell(self, *a, **k):
                        pass
                return R()
        def table(self):
            return self._Table()
        def output(self, dest="S"):
            return b"%PDF-1.4"

    _stub_module("fpdf", {"FPDF": FPDF})
    import os, textwrap
    fpdf_dir = "/root/.pyenv/versions/3.12.10/lib/python3.12/site-packages/fpdf"
    os.makedirs(fpdf_dir, exist_ok=True)
    with open(os.path.join(fpdf_dir, "__init__.py"), "w") as fh:
        fh.write(textwrap.dedent(
            """
            class FPDF:
                def __init__(self, *a, **k):
                    self.font_size = 10
                def set_margins(self, *a):
                    pass
                def add_page(self):
                    pass
                def set_xy(self, *a):
                    pass
                def set_x(self, *a):
                    pass
                def get_y(self):
                    return 0
                def add_font(self, *a, **k):
                    pass
                def set_font(self, *a, **k):
                    if 'size' in k:
                        self.font_size = k['size']
                def multi_cell(self, *a, **k):
                    pass
                def ln(self, *a):
                    pass
                class _Table:
                    def __enter__(self):
                        return self
                    def __exit__(self, exc_type, exc, tb):
                        pass
                    def row(self):
                        class R:
                            def cell(self, *a, **k):
                                pass
                        return R()
                def table(self):
                    return self._Table()
                def output(self, dest='S'):
                    return b'%PDF-1.4'
            """
        ))
    _stub_module("numpy", {"frombuffer": lambda *a, **k: [], "uint8": int, "reshape": lambda *a, **k: [], "mean": lambda x: 0, "ndarray": object})
    class DummyES:
        def __init__(self, *a, **k):
            self.indices = types.SimpleNamespace(create=lambda **kw: None, delete=lambda **kw: None)
        def index(self, **kw):
            pass
        def delete(self, **kw):
            pass
        def search(self, **kw):
            return {"hits": {"hits": []}}
    _stub_module("elasticsearch", {"Elasticsearch": DummyES})
    _stub_module("nbformat", {"reads": lambda s, as_version=4: types.SimpleNamespace(cells=[])})
    _stub_module(
        "pygments.lexers",
        {"guess_lexer_for_filename": lambda fn, txt: types.SimpleNamespace(name="python")},
    )
    class DummyParser:
        def set_language(self, lang):
            pass

        def parse(self, data):
            return types.SimpleNamespace(root_node=types.SimpleNamespace(children=[]))

    class DummyLanguage:
        @staticmethod
        def build_library(out, langs):
            return out

        def __init__(self, path, name):
            pass

    _stub_module("tree_sitter", {"Language": DummyLanguage, "Parser": DummyParser})
    _stub_module("tree_sitter_languages", {})
    class DummyEncoding:
        def encode(self, text):
            return list(range(len(text)))

        def decode(self, tokens):
            return "x" * len(tokens)

    _stub_module("tiktoken", {"get_encoding": lambda n: DummyEncoding()})
    yield


@pytest.fixture(autouse=True)
def router_layer_path():
    import sys, os
    sys.path.insert(0, os.path.join(os.getcwd(), 'common/layers/router-layer/python'))
    yield


@pytest.fixture(autouse=True)
def invocation_layer_path():
    import sys, os
    sys.path.insert(0, os.path.join(os.getcwd(), 'common/layers/llm-invocation-layer/python'))
    yield


@pytest.fixture(autouse=True)
def chunking_layer_path():
    import sys, os
    sys.path.insert(0, os.path.join(os.getcwd(), 'common/layers/chunking-layer/python'))
    yield

@pytest.fixture
def validate_schema():
    def _check(obj):
        assert isinstance(obj, dict)
        assert set(obj) == {"documentId", "pageNumber", "content"}
        assert isinstance(obj["documentId"], str)
        assert isinstance(obj["pageNumber"], int)
        assert isinstance(obj["content"], str)
    return _check


@pytest.fixture
def config(monkeypatch, s3_stub):
    import sys, os
    sys.path.insert(0, os.path.join(os.getcwd(), 'common/layers/common-utils/python'))
    import common_utils.get_ssm as g
    g._SSM_CACHE.clear()
    params = {}
    monkeypatch.setattr(g, "s3_client", s3_stub)
    monkeypatch.setattr(g, "get_values_from_ssm", lambda name, decrypt=False: params.get(name))
    return params
