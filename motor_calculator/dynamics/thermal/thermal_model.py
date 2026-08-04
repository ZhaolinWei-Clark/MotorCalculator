"""First-order lumped thermal RC dynamics and numerical integration."""

from __future__ import annotations

import math

from .thermal_state import (
    ThermalConfig,
    ThermalDerivative,
    ThermalIntegrationMethod,
    ThermalState,
)


class LumpedThermalModel:
    """One winding-temperature node connected to a fixed ambient sink."""

    @staticmethod
    def compute_derivative(
        state: ThermalState,
        loss_power_w: float,
        config: ThermalConfig,
    ) -> ThermalDerivative:
        if not math.isfinite(loss_power_w) or loss_power_w < 0.0:
            raise ValueError("loss_power_w must be finite and non-negative")
        cooling_power_w = (
            state.winding_temperature_c - config.ambient_temperature_c
        ) / config.thermal_resistance_c_per_w
        return ThermalDerivative(
            winding_temperature_rate_c_per_s=(
                loss_power_w - cooling_power_w
            )
            / config.thermal_capacitance_j_per_c
        )

    @classmethod
    def step(
        cls,
        state: ThermalState,
        loss_power_w: float,
        dt: float,
        config: ThermalConfig,
        method: ThermalIntegrationMethod = ThermalIntegrationMethod.RK4,
    ) -> ThermalState:
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and greater than zero")
        if not isinstance(method, ThermalIntegrationMethod):
            raise TypeError("method must be a ThermalIntegrationMethod")
        if method is ThermalIntegrationMethod.EULER:
            derivative = cls.compute_derivative(state, loss_power_w, config)
            return ThermalState(
                state.winding_temperature_c
                + derivative.winding_temperature_rate_c_per_s * dt
            )

        def rate(temperature_c: float) -> float:
            return cls.compute_derivative(
                ThermalState(temperature_c), loss_power_w, config
            ).winding_temperature_rate_c_per_s

        temperature = state.winding_temperature_c
        k1 = rate(temperature)
        k2 = rate(temperature + 0.5 * dt * k1)
        k3 = rate(temperature + 0.5 * dt * k2)
        k4 = rate(temperature + dt * k3)
        return ThermalState(
            temperature + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        )
