"""Sandbox-only voltage-margin-based PMSM field-weakening foundation."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class FieldWeakeningVoltageEstimate:
    """Steady-state dq voltage estimate used only by the control sandbox."""

    vd_v: float
    vq_v: float

    def __post_init__(self) -> None:
        _require_finite("vd_v", self.vd_v)
        _require_finite("vq_v", self.vq_v)

    @property
    def magnitude_v(self) -> float:
        return math.hypot(self.vd_v, self.vq_v)


@dataclass(frozen=True)
class FieldWeakeningResult:
    """Negative d-axis command and voltage-envelope diagnostic metadata."""

    id_weakening_command: float
    voltage_margin: float
    weakening_active: bool
    warning: str | None
    voltage_required_v: float
    voltage_available_v: float

    def __post_init__(self) -> None:
        for name, value in (
            ("id_weakening_command", self.id_weakening_command),
            ("voltage_margin", self.voltage_margin),
            ("voltage_required_v", self.voltage_required_v),
            ("voltage_available_v", self.voltage_available_v),
        ):
            _require_finite(name, value)
        if self.id_weakening_command > 0.0:
            raise ValueError("id_weakening_command must not be positive")
        if not isinstance(self.weakening_active, bool):
            raise TypeError("weakening_active must be a bool")


class FieldWeakeningController:
    """Generate a bounded negative ``id`` command from dq voltage margin.

    This foundation uses the average inverter envelope ``Vdc/sqrt(3)`` and a
    steady-state voltage estimate. It does not solve the full voltage/current
    constrained optimization problem and does not model PWM or saturation.
    """

    def __init__(
        self,
        current_limit_a: float,
        weakening_gain: float = 1.0,
    ) -> None:
        _require_finite("current_limit_a", current_limit_a)
        _require_finite("weakening_gain", weakening_gain)
        if current_limit_a <= 0.0:
            raise ValueError("current_limit_a must be greater than zero")
        if weakening_gain <= 0.0 or weakening_gain > 1.0:
            raise ValueError("weakening_gain must be within (0, 1]")
        self.current_limit_a = current_limit_a
        self.weakening_gain = weakening_gain

    def compute_weakening_command(
        self,
        speed_rad_s: float,
        vd_command_v: float,
        vq_command_v: float,
        dc_bus_voltage_v: float,
        motor_parameters,
    ) -> FieldWeakeningResult:
        """Return zero below the voltage envelope or bounded negative ``id`` above it."""

        for name, value in (
            ("speed_rad_s", speed_rad_s),
            ("vd_command_v", vd_command_v),
            ("vq_command_v", vq_command_v),
            ("dc_bus_voltage_v", dc_bus_voltage_v),
        ):
            _require_finite(name, value)
        if dc_bus_voltage_v <= 0.0:
            raise ValueError("dc_bus_voltage_v must be greater than zero")

        pole_pairs = getattr(motor_parameters, "pole_pairs", None)
        ld = getattr(motor_parameters, "Ld", math.nan)
        if (
            isinstance(pole_pairs, bool)
            or not isinstance(pole_pairs, int)
            or pole_pairs <= 0
        ):
            raise ValueError("motor_parameters.pole_pairs must be a positive integer")
        if not isinstance(ld, (int, float)) or not math.isfinite(ld) or ld <= 0.0:
            raise ValueError("motor_parameters.Ld must be finite and greater than zero")

        voltage_available = dc_bus_voltage_v / math.sqrt(3.0)
        voltage_required = math.hypot(vd_command_v, vq_command_v)
        voltage_margin = voltage_available - voltage_required
        if voltage_margin >= 0.0:
            return FieldWeakeningResult(
                id_weakening_command=0.0,
                voltage_margin=voltage_margin,
                weakening_active=False,
                warning=None,
                voltage_required_v=voltage_required,
                voltage_available_v=voltage_available,
            )

        omega_e = abs(pole_pairs * speed_rad_s)
        if omega_e <= 1.0e-12:
            return FieldWeakeningResult(
                id_weakening_command=0.0,
                voltage_margin=voltage_margin,
                weakening_active=False,
                warning=(
                    "Voltage demand exceeded the envelope at near-zero speed; "
                    "flux weakening cannot resolve this condition."
                ),
                voltage_required_v=voltage_required,
                voltage_available_v=voltage_available,
            )

        if abs(vd_command_v) < voltage_available:
            target_vq_magnitude = math.sqrt(
                max(voltage_available * voltage_available - vd_command_v * vd_command_v, 0.0)
            )
        else:
            target_vq_magnitude = 0.0
        q_axis_reduction_v = max(
            abs(vq_command_v) - target_vq_magnitude,
            -voltage_margin,
        )
        raw_id = -self.weakening_gain * q_axis_reduction_v / (omega_e * ld)
        id_command = max(raw_id, -self.current_limit_a)
        limit_note = " The d-axis current limit was reached." if id_command != raw_id else ""
        return FieldWeakeningResult(
            id_weakening_command=id_command,
            voltage_margin=voltage_margin,
            weakening_active=True,
            warning=(
                "Simplified field weakening requested negative id because the "
                f"estimated dq voltage exceeded Vdc/sqrt(3).{limit_note}"
            ),
            voltage_required_v=voltage_required,
            voltage_available_v=voltage_available,
        )

    def compute_id_reference(self, *args, **kwargs) -> FieldWeakeningResult:
        """Compatibility alias for callers that name the output as an id reference."""

        return self.compute_weakening_command(*args, **kwargs)

    @staticmethod
    def estimate_steady_state_voltage(
        speed_rad_s: float,
        id_reference_a: float,
        iq_reference_a: float,
        motor_parameters,
    ) -> FieldWeakeningVoltageEstimate:
        """Estimate dq voltage with derivative terms set to zero."""

        for name, value in (
            ("speed_rad_s", speed_rad_s),
            ("id_reference_a", id_reference_a),
            ("iq_reference_a", iq_reference_a),
        ):
            _require_finite(name, value)
        omega_e = motor_parameters.pole_pairs * speed_rad_s
        vd_v = (
            motor_parameters.Rs * id_reference_a
            - omega_e * motor_parameters.Lq * iq_reference_a
        )
        vq_v = (
            motor_parameters.Rs * iq_reference_a
            + omega_e * (motor_parameters.Ld * id_reference_a + motor_parameters.psi_f)
        )
        return FieldWeakeningVoltageEstimate(vd_v=vd_v, vq_v=vq_v)
