"""GUI-only display-unit conversion while preserving canonical project units."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping


LENGTH_FIELDS = frozenset({
    "D_out", "D_in", "g_side", "D_stator_out", "D_stator_in", "h_stator",
    "h_coil", "h_yoke", "h_slot", "w_slot_top", "w_slot_bottom",
    "h_slot_opening", "w_slot_opening", "h_wedge", "h_mag", "w_magnet",
    "L_magnet", "d_wire",
})
SPEED_FIELDS = frozenset({"n_rated"})
TEMPERATURE_FIELDS = frozenset({"Temp_coil"})


@dataclass(frozen=True)
class DisplayUnitPreferences:
    length: str = "mm"
    speed: str = "rpm"
    temperature: str = "degC"
    angle: str = "degree"

    def __post_init__(self) -> None:
        if self.length not in {"mm", "m"}:
            raise ValueError("length display unit must be mm or m")
        if self.speed not in {"rpm", "rad/s"}:
            raise ValueError("speed display unit must be rpm or rad/s")
        if self.temperature not in {"degC", "K"}:
            raise ValueError("temperature display unit must be degC or K")
        if self.angle not in {"degree", "rad"}:
            raise ValueError("angle display unit must be degree or rad")


def convert_display_value(value: float, quantity: str, from_unit: str, to_unit: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("display value must be finite")
    if from_unit == to_unit:
        return value
    if quantity == "length":
        if (from_unit, to_unit) == ("mm", "m"):
            return float(Decimal(str(value)) / Decimal("1000"))
        if (from_unit, to_unit) == ("m", "mm"):
            return float(Decimal(str(value)) * Decimal("1000"))
    elif quantity == "speed":
        if (from_unit, to_unit) == ("rpm", "rad/s"):
            return value * 2.0 * math.pi / 60.0
        if (from_unit, to_unit) == ("rad/s", "rpm"):
            return value * 60.0 / (2.0 * math.pi)
    elif quantity == "temperature":
        if (from_unit, to_unit) == ("degC", "K"):
            return float(Decimal(str(value)) + Decimal("273.15"))
        if (from_unit, to_unit) == ("K", "degC"):
            return float(Decimal(str(value)) - Decimal("273.15"))
    elif quantity == "angle":
        if (from_unit, to_unit) == ("degree", "rad"):
            return math.radians(value)
        if (from_unit, to_unit) == ("rad", "degree"):
            return math.degrees(value)
    raise ValueError(f"Unsupported {quantity} display conversion: {from_unit} -> {to_unit}")


def format_engineering_value(value: float) -> str:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("display value must be finite")
    concise = f"{numeric:.12g}"
    # Clean machine-level conversion noise without discarding meaningful entered digits.
    if math.isclose(float(concise), numeric, rel_tol=0.0, abs_tol=1e-15 * max(1.0, abs(numeric))):
        return concise
    return repr(numeric)


def canonical_to_display_inputs(
    canonical: Mapping[str, Any], preferences: DisplayUnitPreferences
) -> dict[str, Any]:
    displayed = dict(canonical)
    for field in LENGTH_FIELDS & canonical.keys():
        displayed[field] = convert_display_value(canonical[field], "length", "mm", preferences.length)
    for field in SPEED_FIELDS & canonical.keys():
        displayed[field] = convert_display_value(canonical[field], "speed", "rpm", preferences.speed)
    for field in TEMPERATURE_FIELDS & canonical.keys():
        displayed[field] = convert_display_value(canonical[field], "temperature", "degC", preferences.temperature)
    return displayed


def display_to_canonical_inputs(
    displayed: Mapping[str, Any], preferences: DisplayUnitPreferences
) -> dict[str, Any]:
    canonical = dict(displayed)
    for field in LENGTH_FIELDS & displayed.keys():
        canonical[field] = convert_display_value(displayed[field], "length", preferences.length, "mm")
    for field in SPEED_FIELDS & displayed.keys():
        canonical[field] = convert_display_value(displayed[field], "speed", preferences.speed, "rpm")
    for field in TEMPERATURE_FIELDS & displayed.keys():
        canonical[field] = convert_display_value(displayed[field], "temperature", preferences.temperature, "degC")
    return canonical
