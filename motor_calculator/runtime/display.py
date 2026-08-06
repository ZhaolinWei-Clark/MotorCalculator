"""Small Windows display-scaling helpers that do not redesign the GUI."""

from __future__ import annotations

import ctypes
import sys


def enable_windows_dpi_awareness() -> str:
    """Request system-aware scaling before Tk creates the first window."""

    if sys.platform != "win32":
        return "not_windows"
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return "system_dpi_aware"
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "legacy_dpi_aware"
        except (AttributeError, OSError):
            return "unavailable"


def bounded_window_size(
    requested_width: int,
    requested_height: int,
    screen_width: int,
    screen_height: int,
    *,
    coverage: float = 0.95,
) -> tuple[int, int]:
    """Keep the existing layout within the visible desktop at common scaling levels."""

    if not 0.5 <= coverage <= 1.0:
        raise ValueError("coverage must be between 0.5 and 1.0")
    values = (requested_width, requested_height, screen_width, screen_height)
    if any(value <= 0 for value in values):
        raise ValueError("window and screen dimensions must be positive")
    return (
        min(requested_width, max(1, int(screen_width * coverage))),
        min(requested_height, max(1, int(screen_height * coverage))),
    )
