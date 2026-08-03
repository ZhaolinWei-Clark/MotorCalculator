"""Sandbox-only DC bus voltage envelope for PMSM dq simulations."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DCBusConfig:
    """Simplified inverter supply metadata in SI units.

    Phase 6F enforces only the voltage envelope. ``current_limit_a`` and
    ``inverter_efficiency`` are validated placeholders for later phases and do
    not yet alter currents, losses, torque, or DC-bus power.
    """

    nominal_voltage_v: float
    current_limit_a: float | None = None
    inverter_efficiency: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.nominal_voltage_v) or self.nominal_voltage_v <= 0.0:
            raise ValueError("nominal_voltage_v must be a finite value greater than zero")
        if self.current_limit_a is not None:
            if not math.isfinite(self.current_limit_a) or self.current_limit_a <= 0.0:
                raise ValueError("current_limit_a must be None or a finite value greater than zero")
        if self.inverter_efficiency is not None:
            if not math.isfinite(self.inverter_efficiency) or not 0.0 < self.inverter_efficiency <= 1.0:
                raise ValueError("inverter_efficiency must be None or within (0, 1]")


@dataclass(frozen=True)
class VoltageLimitResult:
    """One commanded and applied dq voltage pair."""

    vd_command_v: float
    vq_command_v: float
    vd_actual_v: float
    vq_actual_v: float
    voltage_limit_v: float
    was_limited: bool
    saturation_ratio: float
    warning_messages: tuple[str, ...] = ()


class InverterVoltageLimiter:
    """Apply a circular Vdc/sqrt(3) dq voltage envelope.

    This is a sinusoidal/SVPWM-compatible average-voltage assumption. It is
    not a PWM waveform, switching-device, or modulation-timing model.
    """

    @staticmethod
    def compute_voltage_limit(dc_bus_config: DCBusConfig) -> float:
        return dc_bus_config.nominal_voltage_v / math.sqrt(3.0)

    @classmethod
    def apply_limit(
        cls,
        vd_command: float,
        vq_command: float,
        dc_bus_config: DCBusConfig,
    ) -> VoltageLimitResult:
        if not math.isfinite(vd_command) or not math.isfinite(vq_command):
            raise ValueError("dq voltage commands must be finite")

        voltage_limit = cls.compute_voltage_limit(dc_bus_config)
        command_magnitude = math.hypot(vd_command, vq_command)
        saturation_ratio = command_magnitude / voltage_limit
        was_limited = saturation_ratio > 1.0

        if was_limited:
            scale = 1.0 / saturation_ratio
            vd_actual = vd_command * scale
            vq_actual = vq_command * scale
            warnings = (
                f"DQ voltage command exceeded the Vdc/sqrt(3) envelope ({voltage_limit:.6g} V) and was scaled.",
            )
        else:
            vd_actual = vd_command
            vq_actual = vq_command
            warnings = ()

        return VoltageLimitResult(
            vd_command_v=vd_command,
            vq_command_v=vq_command,
            vd_actual_v=vd_actual,
            vq_actual_v=vq_actual,
            voltage_limit_v=voltage_limit,
            was_limited=was_limited,
            saturation_ratio=saturation_ratio,
            warning_messages=warnings,
        )
