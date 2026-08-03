"""User-oriented configuration and internal solver preset selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TypeVar

from .simulation_results import SimulationConfidence


class SimulationAccuracy(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    HIGH_ACCURACY = "high_accuracy"


class SolverPreference(str, Enum):
    AUTO = "auto"
    EULER = "euler"
    RK4 = "rk4"


class FallbackPolicy(str, Enum):
    STATIC = "static"
    FAIL = "fail"


EnumType = TypeVar("EnumType", bound=Enum)


def _coerce_enum(enum_type: type[EnumType], value: EnumType | str, field_name: str) -> EnumType:
    if isinstance(value, enum_type):
        return value
    normalized = str(value).strip().lower()
    try:
        return enum_type(normalized)
    except ValueError as exc:
        supported = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {supported}") from exc


@dataclass(frozen=True)
class SimulationConfig:
    """Public simulation choices; timestep remains an internal preset detail."""

    simulation_time: float
    accuracy_level: SimulationAccuracy | str = SimulationAccuracy.BALANCED
    solver_preference: SolverPreference | str = SolverPreference.AUTO
    fallback_policy: FallbackPolicy | str = FallbackPolicy.STATIC

    def __post_init__(self) -> None:
        if not math.isfinite(self.simulation_time) or self.simulation_time <= 0.0:
            raise ValueError("simulation_time must be a finite value greater than zero")
        object.__setattr__(
            self,
            "accuracy_level",
            _coerce_enum(SimulationAccuracy, self.accuracy_level, "accuracy_level"),
        )
        object.__setattr__(
            self,
            "solver_preference",
            _coerce_enum(SolverPreference, self.solver_preference, "solver_preference"),
        )
        object.__setattr__(
            self,
            "fallback_policy",
            _coerce_enum(FallbackPolicy, self.fallback_policy, "fallback_policy"),
        )


@dataclass(frozen=True)
class ResolvedSimulationSettings:
    """Internal numerical settings selected from a public configuration."""

    time_step: float
    solver_name: str
    confidence_level: SimulationConfidence
    warning_messages: tuple[str, ...]


_ACCURACY_PRESETS = {
    SimulationAccuracy.FAST: (5.0e-3, "Euler", SimulationConfidence.LOW),
    SimulationAccuracy.BALANCED: (1.0e-3, "RK4", SimulationConfidence.MEDIUM),
    SimulationAccuracy.HIGH_ACCURACY: (1.0e-4, "RK4", SimulationConfidence.HIGH),
}


def select_simulation_settings(config: SimulationConfig) -> ResolvedSimulationSettings:
    """Resolve solver and timestep without exposing timestep as user input."""

    time_step, automatic_solver, confidence_level = _ACCURACY_PRESETS[config.accuracy_level]
    solver_name = automatic_solver
    warnings = []

    if config.solver_preference is SolverPreference.EULER:
        solver_name = "Euler"
    elif config.solver_preference is SolverPreference.RK4:
        solver_name = "RK4"

    if config.accuracy_level is SimulationAccuracy.FAST:
        warnings.append(
            "FAST uses a coarse numerical preset; review with BALANCED or HIGH_ACCURACY before relying on transients."
        )
    if solver_name == "Euler" and config.accuracy_level is not SimulationAccuracy.FAST:
        confidence_level = SimulationConfidence.LOW
        warnings.append("Euler was explicitly selected instead of the recommended RK4 solver for this accuracy level.")

    return ResolvedSimulationSettings(
        time_step=time_step,
        solver_name=solver_name,
        confidence_level=confidence_level,
        warning_messages=tuple(warnings),
    )
