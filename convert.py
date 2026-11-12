#!/usr/bin/env python3
"""Convenience entrypoint: ./convert.py samples/sample_invoice.png -o output/sample.xlsx"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from image_to_excel.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
