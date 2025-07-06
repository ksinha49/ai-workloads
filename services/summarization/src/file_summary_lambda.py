"""Generate a summary document or simply forward results."""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional
from fpdf import FPDF

from common_utils import lambda_response
from services.summarization.models import SummaryEvent

FONT_DIR = os.environ.get("FONT_DIR")


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
    pdf: FPDF, font_size: int, bold_size: int, title: str, font_name: str = "Helvetica"
) -> None:
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


def lambda_handler(event: SummaryEvent | dict, context: Any) -> dict:
    if isinstance(event, dict):
        event = SummaryEvent.from_dict(event)
    font_dir = event.extra.get("font_dir") if isinstance(event, SummaryEvent) else None
    if event.output_format == "pdf":  # pragma: no cover - used in production
        pdf = FPDF(unit="mm", format="A4")
        font_name = _register_fonts(pdf, font_dir)
        _add_title_page(pdf, 10, 12, "Summary", font_name)
        pdf.output(dest="S")  # discard - ensures fonts are loaded
    return lambda_response(200, event.to_dict())


__all__ = [
    "_add_title_page",
    "_write_paragraph",
    "_render_table",
    "lambda_handler",
]
