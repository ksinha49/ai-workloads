"""Generate a summary document or simply forward results."""
from __future__ import annotations

import json
from typing import Any, List
from fpdf import FPDF

from common_utils import lambda_response
from services.summarization.models import SummaryEvent


def _add_title_page(pdf: FPDF, font_size: int, bold_size: int, title: str) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", bold_size)
    pdf.multi_cell(0, 10, title)
    pdf.ln(10)
    pdf.set_font("Helvetica", size=font_size)


def _write_paragraph(pdf: FPDF, text: str, font_size: int, bold_size: int) -> None:
    pdf.set_font("Helvetica", size=font_size)
    pdf.multi_cell(0, 10, text)


def _render_table(pdf: FPDF, rows: List[List[str]]) -> None:
    col_width = 40
    pdf.set_font("Helvetica", size=10)
    for row in rows:
        for cell in row:
            pdf.multi_cell(col_width, 10, str(cell), border=1)
        pdf.ln()


def lambda_handler(event: SummaryEvent | dict, context: Any) -> dict:
    if isinstance(event, dict):
        event = SummaryEvent.from_dict(event)
    return lambda_response(200, event.to_dict())


__all__ = [
    "_add_title_page",
    "_write_paragraph",
    "_render_table",
    "lambda_handler",
]
