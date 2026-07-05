"""Application entry point for the refactored motor calculator."""

try:
    from gui.main_window import main
except ImportError:  # pragma: no cover - package-style import path
    from .gui.main_window import main


if __name__ == "__main__":
    main()
