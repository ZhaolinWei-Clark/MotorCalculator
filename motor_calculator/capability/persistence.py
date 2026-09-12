"""Phase 12: persisting the inverter inputs, and only the inputs.

Inverter settings are *inputs*: a user chose them and expects them back. The
capability curves are *derived*, deterministic functions of those inputs and the
design, so they are recomputed rather than stored. Storing them would create a
second source of truth that silently goes stale the moment any design input
changes -- the same trap Phase 10H avoided by not persisting derived winding
factors.

Same mechanism as Phases 10H and 11A: flat scalar keys under a namespace inside
the existing ``ui_preferences`` map, so ``PROJECT_SCHEMA_VERSION`` does not move
and every project written before this phase keeps loading byte-identically.
"""

from __future__ import annotations

from typing import Any, Mapping

from .limits import DEFAULT_UTILIZATION, Modulation
from .solver import InverterSettings

CAPABILITY_PERSISTENCE_SCHEMA_VERSION = "phase12.capability_persistence.v1"

PREFIX = "capability."
SCHEMA_KEY = PREFIX + "schema_version"

#: The key whose absence means "this project predates capability settings".
MODULATION_KEY = PREFIX + "modulation"


def to_preferences(settings: InverterSettings) -> dict[str, Any]:
    """Flatten the inverter settings into ``ui_preferences`` scalar keys."""

    payload: dict[str, Any] = {
        SCHEMA_KEY: CAPABILITY_PERSISTENCE_SCHEMA_VERSION,
        MODULATION_KEY: settings.modulation.value,
        PREFIX + "dc_bus_voltage_v": float(settings.dc_bus_voltage_v),
        PREFIX + "voltage_utilization": float(settings.voltage_utilization),
        PREFIX + "low_speed_points": int(settings.low_speed_points),
        PREFIX + "weakening_points": int(settings.weakening_points),
    }
    if settings.current_limit_rms_a is not None:
        payload[PREFIX + "current_limit_rms_a"] = float(settings.current_limit_rms_a)
    return payload


def from_preferences(
    preferences: Mapping[str, Any] | None, *, default_dc_bus_voltage_v: float
) -> InverterSettings:
    """Rebuild the inverter settings, defaulting cleanly for older projects.

    A project with no capability keys is not an error: it simply predates this
    phase, and gets the defaults derived from its own DC bus voltage.
    """

    preferences = preferences or {}

    def number(key: str, fallback):
        raw = preferences.get(PREFIX + key)
        if raw is None:
            return fallback
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return fallback
        return value

    raw_modulation = preferences.get(MODULATION_KEY)
    try:
        modulation = (
            Modulation(str(raw_modulation).strip().upper())
            if raw_modulation
            else Modulation.SVPWM
        )
    except ValueError:
        modulation = Modulation.SVPWM

    utilization = number("voltage_utilization", DEFAULT_UTILIZATION)
    if not 0.0 < utilization <= 1.0:
        utilization = DEFAULT_UTILIZATION

    current_limit = preferences.get(PREFIX + "current_limit_rms_a")
    return InverterSettings(
        dc_bus_voltage_v=number("dc_bus_voltage_v", float(default_dc_bus_voltage_v)),
        modulation=modulation,
        voltage_utilization=utilization,
        current_limit_rms_a=(
            float(current_limit) if current_limit not in (None, "") else None
        ),
        low_speed_points=int(number("low_speed_points", 6)),
        weakening_points=int(number("weakening_points", 24)),
    )
