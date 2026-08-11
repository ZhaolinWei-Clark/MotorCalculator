"""Small Windows display-scaling helpers that do not redesign the GUI."""

from __future__ import annotations

import ctypes
import math
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


def dpi_scaled_window_size(
    requested_width: int,
    requested_height: int,
    tk_scaling: float,
) -> tuple[int, int]:
    """Scale the legacy 96-DPI window request for a DPI-aware process."""

    if requested_width <= 0 or requested_height <= 0:
        raise ValueError("requested dimensions must be positive")
    if not math.isfinite(tk_scaling) or tk_scaling <= 0.0:
        raise ValueError("tk_scaling must be finite and positive")
    baseline_tk_scaling = 96.0 / 72.0
    scale_factor = max(1.0, tk_scaling / baseline_tk_scaling)
    return round(requested_width * scale_factor), round(requested_height * scale_factor)


def windows_work_area(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    """Return the Windows desktop work area, excluding taskbars when available."""

    if screen_width <= 0 or screen_height <= 0:
        raise ValueError("screen dimensions must be positive")
    if sys.platform != "win32":
        return 0, 0, screen_width, screen_height

    class Rect(ctypes.Structure):
        _fields_ = (
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        )

    rectangle = Rect()
    try:
        succeeded = ctypes.windll.user32.SystemParametersInfoW(
            0x0030,
            0,
            ctypes.byref(rectangle),
            0,
        )
    except (AttributeError, OSError):
        succeeded = False
    if not succeeded or rectangle.right <= rectangle.left or rectangle.bottom <= rectangle.top:
        return 0, 0, screen_width, screen_height
    return rectangle.left, rectangle.top, rectangle.right, rectangle.bottom
