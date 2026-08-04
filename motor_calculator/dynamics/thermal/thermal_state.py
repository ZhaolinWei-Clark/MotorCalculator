"""Immutable state and configuration for a one-node thermal sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


class ThermalIntegrationMethod(str, Enum):
    EULER = "euler"
    RK4 = "rk4"


@dataclass(frozen=True)
class ThermalState:
    winding_temperature_c: float

    def __post_init__(self) -> None:
        _require_finite("winding_temperature_c", self.winding_temperature_c)


@dataclass(frozen=True)
class ThermalDerivative:
    winding_temperature_rate_c_per_s: float

    def __post_init__(self) -> None:
        _require_finite(
            "winding_temperature_rate_c_per_s",
            self.winding_temperature_rate_c_per_s,
        )


@dataclass(frozen=True)
class ThermalConfig:
    ambient_temperature_c: float
    thermal_resistance_c_per_w: float
    thermal_capacitance_j_per_c: float
    initial_temperature_c: float
    warning_temperature_c: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("ambient_temperature_c", self.ambient_temperature_c),
            ("thermal_resistance_c_per_w", self.thermal_resistance_c_per_w),
            ("thermal_capacitance_j_per_c", self.thermal_capacitance_j_per_c),
            ("initial_temperature_c", self.initial_temperature_c),
        ):
            _require_finite(name, value)
        if self.thermal_resistance_c_per_w <= 0.0:
            raise ValueError("thermal_resistance_c_per_w must be greater than zero")
        if self.thermal_capacitance_j_per_c <= 0.0:
            raise ValueError("thermal_capacitance_j_per_c must be greater than zero")
        if self.warning_temperature_c is not None:
            _require_finite("warning_temperature_c", self.warning_temperature_c)
            if self.warning_temperature_c <= self.ambient_temperature_c:
                raise ValueError(
                    "warning_temperature_c must be greater than ambient temperature"
                )

    @property
    def time_constant_s(self) -> float:
        return (
            self.thermal_resistance_c_per_w
            * self.thermal_capacitance_j_per_c
        )

    def steady_state_temperature_c(self, loss_power_w: float) -> float:
        _require_finite("loss_power_w", loss_power_w)
        if loss_power_w < 0.0:
            raise ValueError("loss_power_w must be non-negative")
        return (
            self.ambient_temperature_c
            + loss_power_w * self.thermal_resistance_c_per_w
        )


@dataclass(frozen=True)
class ThermalElectricalCouplingConfig:
    """Optional multi-rate thermal/electrical coupling controls."""

    enabled: bool = False
    enable_resistance_feedback: bool = False
    thermal_update_period_s: float = 0.1
    integration_method: ThermalIntegrationMethod = ThermalIntegrationMethod.RK4
    flux_density_proxy: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        if not isinstance(self.enable_resistance_feedback, bool):
            raise TypeError("enable_resistance_feedback must be a bool")
        _require_finite("thermal_update_period_s", self.thermal_update_period_s)
        if self.thermal_update_period_s <= 0.0:
            raise ValueError("thermal_update_period_s must be greater than zero")
        if not isinstance(self.integration_method, ThermalIntegrationMethod):
            raise TypeError("integration_method must be a ThermalIntegrationMethod")
        if self.flux_density_proxy is not None:
            _require_finite("flux_density_proxy", self.flux_density_proxy)
            if self.flux_density_proxy < 0.0:
                raise ValueError("flux_density_proxy must be non-negative")
