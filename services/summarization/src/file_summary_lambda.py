"""Generate a summary document or simply forward results."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from common_utils import lambda_response
from common_utils.get_ssm import get_values_from_ssm
from services.summarization.models import SummaryEvent

FONT_DIR = os.environ.get("FONT_DIR")
SUMMARY_LABELS: Dict[str, str] = {}


def _load_labels(label_path: Optional[str] = None, font_dir: Optional[str] = None) -> Dict[str, str]:
    """Load summary labels from ``label_path`` or ``font_dir``."""

    global SUMMARY_LABELS
    path = label_path
    if not path and font_dir:
        test_path = os.path.join(font_dir, "summary_labels.json")
        if os.path.isfile(test_path):
            path = test_path
    labels: Dict[str, str] = {}
    if path:
        try:  # pragma: no cover - optional
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as fh:
                    labels = json.load(fh)
            else:
                data = get_values_from_ssm(path)
                if data:
                    labels = json.loads(data)
        except Exception:
            labels = {}
    SUMMARY_LABELS = labels
    return labels


def _register_fonts(pdf: FPDF, font_dir: Optional[str] = None) -> str:
    """Register custom fonts if available and return the font name."""

    dir_path = font_dir or FONT_DIR
    if dir_path and os.path.isdir(dir_path):
        try:  # pragma: no cover - best effort
            pdf.add_font("DejaVu", "", os.path.join(dir_path, "DejaVuSans.ttf"), uni=True)
            pdf.add_font("DejaVu", "B", os.path.join(dir_path, "DejaVuSans-Bold.ttf"), uni=True)
            return "DejaVu"
        except Exception:
            pass
    return "Helvetica"


def _add_title_page(
    pdf: FPDF,
    font_size: int,
    bold_size: int,
    title: Optional[str] = None,
    font_name: str = "Helvetica",
) -> None:
    title = title or SUMMARY_LABELS.get("summary_heading", "Summary")
    pdf.add_page()
    pdf.set_font(font_name, "B", bold_size)
    pdf.multi_cell(0, 10, title)
    pdf.ln(10)
    pdf.set_font(font_name, size=font_size)


def _write_paragraph(
    pdf: FPDF, text: str, font_size: int, bold_size: int, font_name: str = "Helvetica"
) -> None:
    pdf.set_font(font_name, size=font_size)
    pdf.multi_cell(0, 10, text)


def _render_table(pdf: FPDF, rows: List[List[str]], font_name: str = "Helvetica") -> None:
    col_width = 40
    pdf.set_font(font_name, size=10)
    for row in rows:
        for cell in row:
            pdf.multi_cell(col_width, 10, str(cell), border=1)
        pdf.ln()


def _finish_pdf(pdf: FPDF, font_size: int, bold_size: int, font_name: str = "Helvetica") -> None:
    """Append the closing text to ``pdf`` if available."""

    closing = SUMMARY_LABELS.get("summary_closing_text")
    if closing:
        _write_paragraph(pdf, closing, font_size, bold_size, font_name)


def lambda_handler(event: SummaryEvent | dict, context: Any) -> dict:
    if isinstance(event, dict):
        event = SummaryEvent.from_dict(event)
    font_dir = event.extra.get("font_dir") if isinstance(event, SummaryEvent) else None
    labels_path = event.extra.get("labels_path") if isinstance(event, SummaryEvent) else None
    _load_labels(labels_path, font_dir)
    if event.output_format == "pdf":  # pragma: no cover - used in production
        pdf = FPDF(unit="mm", format="A4")
        font_name = _register_fonts(pdf, font_dir)
        _add_title_page(pdf, 10, 12, font_name=font_name)
        _finish_pdf(pdf, 10, 12, font_name)
        pdf.output(dest="S")  # discard - ensures fonts are loaded
    return lambda_response(200, event.to_dict())


__all__ = [
    "_add_title_page",
    "_write_paragraph",
    "_render_table",
    "_finish_pdf",
    "lambda_handler",
]
