"""Unit tests for Excel export (no deepdoctection models required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_to_excel.excel_writer import write_workbook  # noqa: E402


def test_write_workbook_creates_table_sheet(tmp_path: Path) -> None:
    pages = [
        {
            "source": "demo.png",
            "page_number": 1,
            "width": 100,
            "height": 100,
            "text": "Hello",
            "layouts": [
                {
                    "category": "title",
                    "text": "Hello",
                    "score": 0.9,
                    "reading_order": 1,
                    "bbox": "(1,1,2,2)",
                }
            ],
            "tables": [
                {
                    "index": 1,
                    "score": 0.8,
                    "rows": 2,
                    "cols": 2,
                    "grid": [["A", "B"], ["1", "2"]],
                    "html": None,
                    "cells": [
                        {"row": 1, "col": 1, "row_span": 1, "col_span": 1, "text": "A", "score": None},
                        {"row": 1, "col": 2, "row_span": 1, "col_span": 1, "text": "B", "score": None},
                        {"row": 2, "col": 1, "row_span": 1, "col_span": 1, "text": "1", "score": None},
                        {"row": 2, "col": 2, "row_span": 1, "col_span": 1, "text": "2", "score": None},
                    ],
                }
            ],
        }
    ]
    out = write_workbook(pages, tmp_path / "out.xlsx")
    assert out.exists()

    from openpyxl import load_workbook

    wb = load_workbook(out)
    assert "Summary" in wb.sheetnames
    assert "Text" in wb.sheetnames
    assert "TableCells" in wb.sheetnames
    table_sheets = [n for n in wb.sheetnames if n.startswith("T1_")]
    assert len(table_sheets) == 1
    ws = wb[table_sheets[0]]
    assert ws["A1"].value == "A"
    assert ws["B2"].value == "2"


def test_formula_like_text_is_not_stored_as_formula(tmp_path: Path) -> None:
    pages = [
        {
            "source": "demo.png",
            "page_number": 1,
            "width": 10,
            "height": 10,
            "text": "=1+1",
            "layouts": [],
            "tables": [
                {
                    "index": 1,
                    "score": 0.9,
                    "rows": 1,
                    "cols": 1,
                    "grid": [["=SUM(A1:A2)", "+123", "-45", "@cmd"]],
                    "html": None,
                    "cells": [],
                }
            ],
        }
    ]
    out = write_workbook(pages, tmp_path / "formula.xlsx")
    from openpyxl import load_workbook

    wb = load_workbook(out)
    ws_text = wb["Text"]
    assert ws_text["C2"].value == "=1+1"
    assert ws_text["C2"].data_type == "s"
    ws_t = wb[[n for n in wb.sheetnames if n.startswith("T1_")][0]]
    assert ws_t["A1"].value == "=SUM(A1:A2)"
    assert ws_t["A1"].data_type == "s"
    assert ws_t["B1"].value == "+123"
    assert ws_t["C1"].value == "-45"
    assert ws_t["D1"].value == "@cmd"
