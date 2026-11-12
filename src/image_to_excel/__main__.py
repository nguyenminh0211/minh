"""CLI: python -m image_to_excel INPUT -o OUTPUT.xlsx"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image_to_excel",
        description=(
            "Extract text and tables from document images/PDFs with deepdoctection "
            "and write one accurate Excel workbook."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to an image, a PDF, or a directory of images (.png/.jpg/...)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/document.xlsx",
        help="Output .xlsx path (default: output/document.xlsx)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
        help="Torch device (default: cpu)",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra deepdoctection config override (repeatable)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Allow `python -m image_to_excel` from repo without installing the package
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from image_to_excel.converter import DocumentToExcelConverter

    converter = DocumentToExcelConverter(device=args.device, config_overwrite=args.config or None)
    out = converter.convert(args.input, args.output)
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
