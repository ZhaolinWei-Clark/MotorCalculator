"""Phase 12: steady-state motor + inverter capability.

MTPA, base speed, field weakening and the torque-speed envelope, derived from
the parameters production already produces. Adds no physics to the production
kernel and modifies none of it.

Read :mod:`.conventions` first: it fixes peak-versus-RMS for every quantity in
this package, and every other module reads the convention from there.
"""

from __future__ import annotations

from .conventions import CONVENTION_SCHEMA_VERSION, CURRENT_BASIS, VOLTAGE_BASIS
from .limits import Modulation, current_limit_from_rms, voltage_limit
from .parameters import CapabilityParameters, MachineType, bridge_from_analysis
from .solver import InverterSettings, solve_capability, solve_from_analysis
from .steady_state import mtpa_point, torque_nm

CAPABILITY_VERSION = "phase12.capability.v1"

__all__ = [
    "CAPABILITY_VERSION",
    "CONVENTION_SCHEMA_VERSION",
    "CURRENT_BASIS",
    "VOLTAGE_BASIS",
    "CapabilityParameters",
    "InverterSettings",
    "MachineType",
    "Modulation",
    "bridge_from_analysis",
    "current_limit_from_rms",
    "mtpa_point",
    "solve_capability",
    "solve_from_analysis",
    "torque_nm",
    "voltage_limit",
]
