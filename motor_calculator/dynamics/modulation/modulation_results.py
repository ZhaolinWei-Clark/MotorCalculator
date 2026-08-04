"""Data contracts for sandbox-only average SVPWM modulation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


class VoltageApplicationMode(str, Enum):
    """Selectable sandbox voltage paths; the legacy simple limiter is default."""

    SIMPLE_DQ_LIMIT = "simple_dq_limit"
    SVPWM_AVERAGE = "svpwm_average"


@dataclass(frozen=True)
class SVPWMConfig:
    """Configuration for an average-value, non-switching SVPWM model."""

    enabled: bool
    dc_bus_voltage_v: float
    allow_overmodulation: bool = False
    minimum_duty: float = 0.0
    maximum_duty: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        _require_finite("dc_bus_voltage_v", self.dc_bus_voltage_v)
        if self.dc_bus_voltage_v <= 0.0:
            raise ValueError("dc_bus_voltage_v must be greater than zero")
        if not isinstance(self.allow_overmodulation, bool):
            raise TypeError("allow_overmodulation must be a bool")
        for name, value in (
            ("minimum_duty", self.minimum_duty),
            ("maximum_duty", self.maximum_duty),
        ):
            _require_finite(name, value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        if self.minimum_duty >= self.maximum_duty:
            raise ValueError("minimum_duty must be less than maximum_duty")

    @property
    def duty_span(self) -> float:
        return self.maximum_duty - self.minimum_duty

    @property
    def linear_voltage_limit_v(self) -> float:
        return self.duty_span * self.dc_bus_voltage_v / math.sqrt(3.0)


@dataclass(frozen=True)
class SVPWMResult:
    """One command-to-average-voltage SVPWM conversion result."""

    sector: int
    modulation_index: float
    duty_a: float
    duty_b: float
    duty_c: float
    phase_voltage_a_avg_v: float
    phase_voltage_b_avg_v: float
    phase_voltage_c_avg_v: float
    alpha_voltage_avg_v: float
    beta_voltage_avg_v: float
    vd_actual_v: float
    vq_actual_v: float
    overmodulation_active: bool
    voltage_saturated: bool
    warning_messages: tuple[str, ...] = ()
    vd_controller_frame_v: float | None = None
    vq_controller_frame_v: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.sector, bool) or self.sector not in range(1, 7):
            raise ValueError("sector must be an integer from 1 through 6")
        for name, value in (
            ("modulation_index", self.modulation_index),
            ("duty_a", self.duty_a),
            ("duty_b", self.duty_b),
            ("duty_c", self.duty_c),
            ("phase_voltage_a_avg_v", self.phase_voltage_a_avg_v),
            ("phase_voltage_b_avg_v", self.phase_voltage_b_avg_v),
            ("phase_voltage_c_avg_v", self.phase_voltage_c_avg_v),
            ("alpha_voltage_avg_v", self.alpha_voltage_avg_v),
            ("beta_voltage_avg_v", self.beta_voltage_avg_v),
            ("vd_actual_v", self.vd_actual_v),
            ("vq_actual_v", self.vq_actual_v),
        ):
            _require_finite(name, value)
        if self.modulation_index < 0.0:
            raise ValueError("modulation_index must be non-negative")
        for name, value in (
            ("vd_controller_frame_v", self.vd_controller_frame_v),
            ("vq_controller_frame_v", self.vq_controller_frame_v),
        ):
            if value is not None:
                _require_finite(name, value)
        if not isinstance(self.overmodulation_active, bool):
            raise TypeError("overmodulation_active must be a bool")
        if not isinstance(self.voltage_saturated, bool):
            raise TypeError("voltage_saturated must be a bool")
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))

    @property
    def duties(self) -> tuple[float, float, float]:
        return (self.duty_a, self.duty_b, self.duty_c)

    @property
    def average_phase_voltages_v(self) -> tuple[float, float, float]:
        return (
            self.phase_voltage_a_v,
            self.phase_voltage_b_v,
            self.phase_voltage_c_v,
        )

    @property
    def phase_voltage_a_v(self) -> float:
        return self.phase_voltage_a_avg_v

    @property
    def phase_voltage_b_v(self) -> float:
        return self.phase_voltage_b_avg_v

    @property
    def phase_voltage_c_v(self) -> float:
        return self.phase_voltage_c_avg_v

    @property
    def alpha_voltage_v(self) -> float:
        return self.alpha_voltage_avg_v

    @property
    def beta_voltage_v(self) -> float:
        return self.beta_voltage_avg_v
