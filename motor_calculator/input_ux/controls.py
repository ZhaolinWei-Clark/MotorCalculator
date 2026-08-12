"""Pure synchronization rules for interactive engineering controls."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .units import DisplayUnitPreferences, convert_display_value, format_engineering_value


@dataclass(frozen=True)
class SliderSpec:
    field_name: str
    canonical_minimum: float
    canonical_maximum: float
    canonical_step: float
    quantity: str
    canonical_unit: str


@dataclass(frozen=True)
class SliderSyncResult:
    numeric_text: str
    slider_value: float | None
    within_display_range: bool
    guidance: str


SLIDER_SPECS = {
    "g_side": SliderSpec("g_side", 0.2, 5.0, 0.05, "length", "mm"),
    "n_rated": SliderSpec("n_rated", 100.0, 10000.0, 50.0, "speed", "rpm"),
    "k_w": SliderSpec("k_w", 0.50, 1.0, 0.005, "ratio", "ratio"),
}


def _display_unit(spec: SliderSpec, preferences: DisplayUnitPreferences) -> str:
    if spec.quantity == "length":
        return preferences.length
    if spec.quantity == "speed":
        return preferences.speed
    return spec.canonical_unit


def slider_range_for_units(spec: SliderSpec, preferences: DisplayUnitPreferences) -> tuple[float, float, float]:
    unit = _display_unit(spec, preferences)
    if spec.quantity in {"length", "speed"}:
        return tuple(
            convert_display_value(value, spec.quantity, spec.canonical_unit, unit)
            for value in (spec.canonical_minimum, spec.canonical_maximum, spec.canonical_step)
        )
    return spec.canonical_minimum, spec.canonical_maximum, spec.canonical_step


def slider_from_numeric_text(
    text: str, spec: SliderSpec, preferences: DisplayUnitPreferences
) -> SliderSyncResult:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return SliderSyncResult(str(text), None, False, "Enter a numeric value")
    if not math.isfinite(value):
        return SliderSyncResult(str(text), None, False, "Enter a finite numeric value")
    minimum, maximum, _step = slider_range_for_units(spec, preferences)
    if minimum <= value <= maximum:
        return SliderSyncResult(format_engineering_value(value), value, True, "Quick-adjust range")
    return SliderSyncResult(format_engineering_value(value), None, False, "Outside quick-adjust range")


def slider_to_numeric_text(value: float, spec: SliderSpec, preferences: DisplayUnitPreferences) -> SliderSyncResult:
    minimum, maximum, step = slider_range_for_units(spec, preferences)
    bounded = min(max(float(value), minimum), maximum)
    steps = round((bounded - minimum) / step)
    rounded = minimum + steps * step
    if abs(rounded) < step * 1e-9:
        rounded = 0.0
    return SliderSyncResult(format_engineering_value(rounded), rounded, True, "Quick-adjust range")


def parse_spinbox_integer(text: str, *, minimum: int = 1) -> int:
    stripped = str(text).strip()
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ValueError("Value must be an integer") from exc
    if str(value) != stripped and stripped not in {f"+{value}"}:
        raise ValueError("Value must be an integer without a fractional part")
    if value < minimum:
        raise ValueError(f"Value must be at least {minimum}")
    return value
