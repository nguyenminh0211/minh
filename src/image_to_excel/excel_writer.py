"""Write structured document extraction results into a single .xlsx workbook."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows


_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)
_WRAP = Alignment(wrap_text=True, vertical="top")

# openpyxl marks values starting with "=" as formulas (data_type "f").
# Force those OCR literals back to plain text so Excel shows the original string.
_FORMULA_LIKE_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _set_cell_value(cell, value: Any) -> None:
    """Write a cell value without allowing formula interpretation."""
    cell.value = value
    if isinstance(value, str) and value.startswith(_FORMULA_LIKE_PREFIXES):
        cell.data_type = "s"


def _autosize(ws, max_width: int = 48) -> None:
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 0
        for cell in col:
            if cell.value is None:
                continue
            width = max(width, min(len(str(cell.value)), max_width))
        ws.column_dimensions[letter].width = max(width + 2, 10)


def _style_header_row(ws, row_idx: int = 1) -> None:
    for cell in ws[row_idx]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = _THIN


def _write_dataframe(ws, df: pd.DataFrame, *, header: bool = True) -> None:
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=header), start=1):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx)
            _set_cell_value(cell, value)
            cell.alignment = _WRAP
            cell.border = _THIN
    if header and len(df.columns):
        _style_header_row(ws, 1)
    _autosize(ws)


def _write_grid(ws, grid: list[list[Any]], *, treat_first_as_header: bool = True) -> None:
    for r_idx, row in enumerate(grid, start=1):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx)
            _set_cell_value(cell, value)
            cell.alignment = _WRAP
            cell.border = _THIN
    if treat_first_as_header and grid:
        _style_header_row(ws, 1)
    _autosize(ws)


def _safe_sheet_name(name: str, used: set[str]) -> str:
    cleaned = "".join(ch if ch not in r"[]:*?/\"" else "_" for ch in name).strip() or "Sheet"
    cleaned = cleaned[:31]
    base = cleaned
    i = 2
    while cleaned in used:
        suffix = f"_{i}"
        cleaned = (base[: 31 - len(suffix)] + suffix)[:31]
        i += 1
    used.add(cleaned)
    return cleaned


def write_workbook(pages: list[dict[str, Any]], output_path: Path) -> Path:
    """
    Build one Excel file from extracted page dicts.

    Expected page keys:
      - source, page_number, width, height, text
      - layouts: list[{category, text, score, reading_order, bbox}]
      - tables: list[{index, score, rows, cols, grid, html}]
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    used_names: set[str] = set()

    # --- Summary ---
    summary_rows = []
    total_tables = 0
    for page in pages:
        n_tables = len(page.get("tables") or [])
        total_tables += n_tables
        summary_rows.append(
            {
                "source": page.get("source"),
                "page_number": page.get("page_number"),
                "width": page.get("width"),
                "height": page.get("height"),
                "tables": n_tables,
                "layouts": len(page.get("layouts") or []),
                "text_chars": len(page.get("text") or ""),
            }
        )
    ws = wb.active
    ws.title = _safe_sheet_name("Summary", used_names)
    _write_dataframe(
        ws,
        pd.DataFrame(
            [
                {
                    "pages": len(pages),
                    "tables_total": total_tables,
                    "output": str(output_path),
                }
            ]
        ),
    )
    ws2 = wb.create_sheet(_safe_sheet_name("Pages", used_names))
    _write_dataframe(ws2, pd.DataFrame(summary_rows))

    # --- Narrative text ---
    text_rows = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if text:
            text_rows.append(
                {
                    "source": page.get("source"),
                    "page_number": page.get("page_number"),
                    "text": text,
                }
            )
    ws_text = wb.create_sheet(_safe_sheet_name("Text", used_names))
    _write_dataframe(ws_text, pd.DataFrame(text_rows or [{"source": "", "page_number": "", "text": ""}]))

    # --- Layout segments ---
    layout_rows = []
    for page in pages:
        for layout in page.get("layouts") or []:
            layout_rows.append(
                {
                    "source": page.get("source"),
                    "page_number": page.get("page_number"),
                    "category": layout.get("category"),
                    "reading_order": layout.get("reading_order"),
                    "score": layout.get("score"),
                    "bbox": layout.get("bbox"),
                    "text": layout.get("text"),
                }
            )
    ws_lay = wb.create_sheet(_safe_sheet_name("Layouts", used_names))
    _write_dataframe(
        ws_lay,
        pd.DataFrame(
            layout_rows
            or [
                {
                    "source": "",
                    "page_number": "",
                    "category": "",
                    "reading_order": "",
                    "score": "",
                    "bbox": "",
                    "text": "",
                }
            ]
        ),
    )

    # --- Tables: one sheet per table (structure-preserving) ---
    for page in pages:
        source_stem = Path(str(page.get("source") or "doc")).stem
        page_no = page.get("page_number", 0)
        for table in page.get("tables") or []:
            idx = table.get("index", 0)
            name = _safe_sheet_name(f"T{page_no}_{idx}_{source_stem}", used_names)
            ws_t = wb.create_sheet(name)
            grid = table.get("grid") or []
            if grid:
                _write_grid(ws_t, grid, treat_first_as_header=True)
            else:
                ws_t["A1"] = "(empty table)"
            # meta as freeze comment row below
            meta_row = (len(grid) or 1) + 2
            ws_t.cell(row=meta_row, column=1, value="score").font = Font(italic=True, color="666666")
            ws_t.cell(row=meta_row, column=2, value=table.get("score"))
            ws_t.cell(row=meta_row + 1, column=1, value="rows×cols").font = Font(italic=True, color="666666")
            ws_t.cell(
                row=meta_row + 1,
                column=2,
                value=f"{table.get('rows')}×{table.get('cols')}",
            )

    # --- All cells flat (audit / high accuracy QA) ---
    cell_rows = []
    for page in pages:
        for table in page.get("tables") or []:
            for cell in table.get("cells") or []:
                cell_rows.append(
                    {
                        "source": page.get("source"),
                        "page_number": page.get("page_number"),
                        "table_index": table.get("index"),
                        "row": cell.get("row"),
                        "col": cell.get("col"),
                        "row_span": cell.get("row_span"),
                        "col_span": cell.get("col_span"),
                        "text": cell.get("text"),
                        "score": cell.get("score"),
                    }
                )
    ws_cells = wb.create_sheet(_safe_sheet_name("TableCells", used_names))
    _write_dataframe(
        ws_cells,
        pd.DataFrame(
            cell_rows
            or [
                {
                    "source": "",
                    "page_number": "",
                    "table_index": "",
                    "row": "",
                    "col": "",
                    "row_span": "",
                    "col_span": "",
                    "text": "",
                    "score": "",
                }
            ]
        ),
    )

    wb.save(output_path)
    return output_path
