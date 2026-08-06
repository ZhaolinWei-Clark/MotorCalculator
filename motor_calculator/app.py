"""Application entry point for source and packaged execution."""

from __future__ import annotations

import sys
from pathlib import Path


if not getattr(sys, "frozen", False):
    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

from motor_calculator.gui.main_window import main


if __name__ == "__main__":
    main()
