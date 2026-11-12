"""deepdoctection analyzer wrapper: document images/PDFs → structured page dicts → Excel."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

from .excel_writer import write_workbook

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_SUFFIXES = {".pdf"}


def _get_bbox(obj: Any) -> Any:
    for attr in ("bbox", "bounding_box"):
        try:
            value = getattr(obj, attr, None)
        except Exception:
            value = None
        if value is not None:
            return value
    getter = getattr(obj, "get_bounding_box", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return None


def _bbox_to_str(bbox: Any) -> Optional[str]:
    if bbox is None:
        return None
    try:
        return (
            f"({float(bbox.ulx):.1f},{float(bbox.uly):.1f},"
            f"{float(bbox.lrx):.1f},{float(bbox.lry):.1f})"
        )
    except Exception:
        return str(bbox)


def _category_name(obj: Any) -> str:
    value = getattr(obj, "category_name", None)
    if value is None:
        return ""
    return getattr(value, "value", None) or str(value)


def _normalize_grid(csv_grid: Any) -> list[list[str]]:
    if not csv_grid:
        return []
    rows: list[list[str]] = []
    for row in csv_grid:
        rows.append([("" if c is None else str(c)).strip() for c in row])
    return rows


def _grid_from_cells(cells: Sequence[Any], n_rows: int, n_cols: int) -> list[list[str]]:
    """Rebuild a dense grid from cell annotations (handles missing cells)."""
    if n_rows <= 0 or n_cols <= 0:
        return []
    grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
    for cell in cells:
        try:
            r = int(cell.row_number) - 1
            c = int(cell.column_number) - 1
        except Exception:
            continue
        if r < 0 or c < 0 or r >= n_rows or c >= n_cols:
            continue
        text = (getattr(cell, "text", None) or "").strip()
        if text:
            grid[r][c] = text
    return grid


def _extract_cells(table: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cell in getattr(table, "cells", None) or []:
        out.append(
            {
                "row": getattr(cell, "row_number", None),
                "col": getattr(cell, "column_number", None),
                "row_span": getattr(cell, "row_span", 1),
                "col_span": getattr(cell, "column_span", 1),
                "text": (getattr(cell, "text", None) or "").strip(),
                "score": getattr(cell, "score", None),
                "bbox": _bbox_to_str(_get_bbox(cell)),
            }
        )
    out.sort(key=lambda x: (x.get("row") or 0, x.get("col") or 0))
    return out


def page_to_dict(page: Any) -> dict[str, Any]:
    tables = []
    for idx, table in enumerate(getattr(page, "tables", None) or []):
        n_rows = int(getattr(table, "number_of_rows", 0) or 0)
        n_cols = int(getattr(table, "number_of_columns", 0) or 0)
        csv_grid = _normalize_grid(getattr(table, "csv", None))
        cell_grid = _grid_from_cells(getattr(table, "cells", None) or [], n_rows, n_cols)
        # Prefer csv when non-empty; fall back to cell rebuild for robustness
        grid = csv_grid if any(any(c for c in row) for row in csv_grid) else cell_grid
        tables.append(
            {
                "index": idx + 1,
                "score": getattr(table, "score", None),
                "rows": n_rows or len(grid),
                "cols": n_cols or (len(grid[0]) if grid else 0),
                "grid": grid,
                "html": getattr(table, "html", None),
                "cells": _extract_cells(table),
            }
        )

    layouts = []
    for layout in getattr(page, "layouts", None) or []:
        layouts.append(
            {
                "category": _category_name(layout),
                "text": (getattr(layout, "text", None) or "").strip(),
                "score": getattr(layout, "score", None),
                "reading_order": getattr(layout, "reading_order", None),
                "bbox": _bbox_to_str(_get_bbox(layout)),
            }
        )
    layouts.sort(key=lambda x: (x.get("reading_order") is None, x.get("reading_order") or 0))

    return {
        "source": getattr(page, "file_name", None),
        "page_number": getattr(page, "page_number", 0),
        "width": getattr(page, "width", None),
        "height": getattr(page, "height", None),
        "text": getattr(page, "text", None) or "",
        "layouts": layouts,
        "tables": tables,
    }


class DocumentToExcelConverter:
    """
    High-accuracy image/PDF → Excel pipeline powered by deepdoctection.

    Focus:
      - Layout detection + table structure segmentation
      - OCR (DocTR by default)
      - One consolidated .xlsx with Summary / Text / Layouts / per-table sheets
    """

    def __init__(
        self,
        *,
        config_overwrite: Optional[list[str]] = None,
        device: str = "cpu",
    ) -> None:
        import deepdoctection as dd

        # deepdoctection passes DEVICE into torch.device(...), so use a plain
        # device name ("cpu" / "cuda" / "mps"), not a torch.device(...) string.
        overrides = [
            f"DEVICE={device}",
            "USE_LAYOUT=True",
            "USE_TABLE_SEGMENTATION=True",
            "USE_OCR=True",
            "OCR.USE_DOCTR=True",
            "OCR.USE_TESSERACT=False",
            "OCR.USE_TEXTRACT=False",
            "USE_PDF_MINER=False",  # images / scanned docs
        ]
        if config_overwrite:
            overrides.extend(config_overwrite)

        logger.info("Loading deepdoctection analyzer (device=%s)...", device)
        self.analyzer = dd.get_dd_analyzer(config_overwrite=overrides)
        self._dd = dd

    @staticmethod
    def resolve_inputs(path: PathLike) -> Path:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        if p.is_file():
            suffix = p.suffix.lower()
            if suffix not in IMAGE_SUFFIXES | PDF_SUFFIXES:
                raise ValueError(f"Unsupported file type: {suffix}")
            return p
        if p.is_dir():
            return p
        raise ValueError(f"Not a file or directory: {p}")

    def analyze(self, path: PathLike) -> list[dict[str, Any]]:
        target = self.resolve_inputs(path)
        logger.info("Analyzing %s", target)

        # deepdoctection accepts:
        #   - directory of images → path=
        #   - PDF → path=
        #   - single image → path= + bytes=
        kwargs: dict[str, Any] = {"path": str(target)}
        if target.is_file() and target.suffix.lower() in IMAGE_SUFFIXES:
            kwargs["bytes"] = target.read_bytes()

        df = self.analyzer.analyze(**kwargs)
        df.reset_state()
        pages = [page_to_dict(page) for page in df]
        # Keep absolute source path for Excel traceability
        for page in pages:
            if not page.get("source"):
                page["source"] = target.name
            page["source_path"] = str(target)
        logger.info("Extracted %d page(s), %d table(s)", len(pages), sum(len(p["tables"]) for p in pages))
        return pages

    def convert(self, path: PathLike, output: PathLike) -> Path:
        pages = self.analyze(path)
        out = write_workbook(pages, Path(output))
        logger.info("Wrote Excel: %s", out)
        return out


def convert_images_to_excel(
    input_path: PathLike,
    output_path: PathLike,
    *,
    device: str = "cpu",
    config_overwrite: Optional[Iterable[str]] = None,
) -> Path:
    converter = DocumentToExcelConverter(
        device=device,
        config_overwrite=list(config_overwrite) if config_overwrite else None,
    )
    return converter.convert(input_path, output_path)
