"""Immutable time-series result records for dynamics sandbox runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .state import MotorState


class SimulationStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FALLBACK_STATIC = "fallback_static"
    FAILED = "failed"


class SimulationConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNSPECIFIED = "unspecified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SimulationResult:
    """Sampled state and torque histories in SI units."""

    time: tuple[float, ...]
    id: tuple[float, ...]
    iq: tuple[float, ...]
    speed: tuple[float, ...]
    position: tuple[float, ...]
    torque: tuple[float, ...]
    electrical_power: tuple[float, ...]
    mechanical_power: tuple[float, ...]
    status: SimulationStatus = SimulationStatus.SUCCESS
    warning_messages: tuple[str, ...] = ()
    solver_used: str = "unspecified"
    confidence_level: SimulationConfidence = SimulationConfidence.UNSPECIFIED
    fallback_reason: str | None = None
    steady_state_result: object | None = None
    transient_response_available: bool = True
    inverter_limited_count: int = 0
    max_voltage_saturation_ratio: float = 0.0
    voltage_limit_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))
        object.__setattr__(self, "voltage_limit_warnings", tuple(self.voltage_limit_warnings))
        if (
            isinstance(self.inverter_limited_count, bool)
            or not isinstance(self.inverter_limited_count, int)
            or self.inverter_limited_count < 0
        ):
            raise ValueError("inverter_limited_count must be a non-negative integer")
        if not math.isfinite(self.max_voltage_saturation_ratio) or self.max_voltage_saturation_ratio < 0.0:
            raise ValueError("max_voltage_saturation_ratio must be finite and non-negative")
        expected_length = len(self.time)
        fallback_or_failed = self.status in {SimulationStatus.FALLBACK_STATIC, SimulationStatus.FAILED}
        if fallback_or_failed:
            if expected_length != 0 or any(self.series):
                raise ValueError("fallback and failed results must not contain transient series")
            if self.transient_response_available:
                raise ValueError("fallback and failed results must mark transient response unavailable")
            if self.status is SimulationStatus.FALLBACK_STATIC and self.steady_state_result is None:
                raise ValueError("static fallback requires a steady_state_result")
            return

        if expected_length == 0 or any(len(series) != expected_length for series in self.series):
            raise ValueError("simulation result series must be non-empty and have equal lengths")
        if not self.transient_response_available:
            raise ValueError("dynamic results must mark transient response available")
        if any(not math.isfinite(value) for series in self.series for value in series):
            raise ValueError("simulation result contains a non-finite value")

    @property
    def series(self) -> tuple[tuple[float, ...], ...]:
        return (
            self.time,
            self.id,
            self.iq,
            self.speed,
            self.position,
            self.torque,
            self.electrical_power,
            self.mechanical_power,
        )

    @property
    def final_state(self) -> MotorState:
        if not self.transient_response_available:
            raise ValueError("transient response is unavailable for this result")
        return MotorState(
            id=self.id[-1],
            iq=self.iq[-1],
            omega_m=self.speed[-1],
            theta=self.position[-1],
        )

    @classmethod
    def fallback_static(
        cls,
        *,
        reason: str,
        steady_state_result: object,
        solver_used: str,
        warning_messages: tuple[str, ...] = (),
    ) -> "SimulationResult":
        fallback_note = "Dynamic transient response is unavailable; the supplied steady-state fallback is returned."
        return cls(
            time=(),
            id=(),
            iq=(),
            speed=(),
            position=(),
            torque=(),
            electrical_power=(),
            mechanical_power=(),
            status=SimulationStatus.FALLBACK_STATIC,
            warning_messages=(*warning_messages, fallback_note),
            solver_used=solver_used,
            confidence_level=SimulationConfidence.UNAVAILABLE,
            fallback_reason=reason,
            steady_state_result=steady_state_result,
            transient_response_available=False,
        )

    @classmethod
    def failed(
        cls,
        *,
        reason: str,
        solver_used: str,
        warning_messages: tuple[str, ...] = (),
    ) -> "SimulationResult":
        return cls(
            time=(),
            id=(),
            iq=(),
            speed=(),
            position=(),
            torque=(),
            electrical_power=(),
            mechanical_power=(),
            status=SimulationStatus.FAILED,
            warning_messages=warning_messages,
            solver_used=solver_used,
            confidence_level=SimulationConfidence.UNAVAILABLE,
            fallback_reason=reason,
            transient_response_available=False,
        )
