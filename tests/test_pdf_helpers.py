import importlib.util
import importlib
import json
import io
import os
import sys
from PyPDF2 import PdfReader
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "pdf", "services/summarization/src/file_summary_lambda.py"
    )
    module = importlib.util.module_from_spec(spec)
    import sys
    if hasattr(sys.modules.get("httpx"), "post"):
        sys.modules["httpx"].Timeout = object
        sys.modules["httpx"].HTTPStatusError = type("E", (Exception,), {})
    import os
    path = "/root/.pyenv/versions/3.12.10/lib/python3.12/site-packages/fpdf/__init__.py"
    spec_real = importlib.util.spec_from_file_location(
        "fpdf", path, submodule_search_locations=[os.path.dirname(path)]
    )
    real_mod = importlib.util.module_from_spec(spec_real)
    sys.modules.pop("fpdf", None)
    spec_real.loader.exec_module(real_mod)
    sys.modules["fpdf"] = real_mod
    spec.loader.exec_module(module)
    return module


def test_add_title_page(config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/SUMMARY_PDF_FONT_SIZE'] = '10'
    config[f'{prefix}/SUMMARY_PDF_FONT_SIZE_BOLD'] = '12'
    module = load_module()
    from fpdf import FPDF
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_margins(20, 20)
    module._add_title_page(pdf, 10, 12, "APS Summary")
    data = pdf.output(dest='S')
    text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "APS Summary" in text


def test_write_paragraph(config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_module()
    from fpdf import FPDF
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()
    module._write_paragraph(pdf, "Hello World", 10, 12)
    data = pdf.output(dest='S')
    text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "Hello World" in text


def test_render_table(config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/SUMMARY_PDF_FONT_SIZE'] = '10'
    module = load_module()
    from fpdf import FPDF
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()
    module._render_table(pdf, [["A", "B"], ["1", "2"]])
    data = pdf.output(dest='S')
    text = PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "A" in text and "1" in text


def test_labels_heading_and_closing(tmp_path):
    module = load_module()
    labels = {"summary_heading": "Custom Heading", "summary_closing_text": "--END--"}
    label_file = tmp_path / "summary_labels.json"
    label_file.write_text(json.dumps(labels))
    module._load_labels(str(label_file), None)

    class DummyPDF:
        def __init__(self):
            self.texts = []

        def add_page(self):
            pass

        def set_font(self, *a, **k):
            pass

        def multi_cell(self, w, h, txt, border=0):
            self.texts.append(txt)

        def ln(self, *a):
            pass

    pdf = DummyPDF()
    module._add_title_page(pdf, 10, 12)
    module._finish_pdf(pdf, 10, 12)
    assert "Custom Heading" in pdf.texts[0]
    assert "--END--" in pdf.texts[-1]
