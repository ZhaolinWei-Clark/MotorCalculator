"""Outer-loop speed PI controller for the PMSM dynamics sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class SpeedControllerConfig:
    """Explicit outer-loop gains, q-current limits, and baseline d reference."""

    kp: float
    ki: float
    iq_min_a: float
    iq_max_a: float
    anti_windup_gain: float
    default_id_ref_a: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("kp", self.kp),
            ("ki", self.ki),
            ("iq_min_a", self.iq_min_a),
            ("iq_max_a", self.iq_max_a),
            ("anti_windup_gain", self.anti_windup_gain),
            ("default_id_ref_a", self.default_id_ref_a),
        ):
            _require_finite(name, value)
        if self.kp < 0.0 or self.ki < 0.0 or self.anti_windup_gain < 0.0:
            raise ValueError("kp, ki, and anti_windup_gain must be non-negative")
        if self.iq_min_a >= self.iq_max_a:
            raise ValueError("iq_min_a must be less than iq_max_a")


@dataclass(frozen=True)
class SpeedControllerState:
    """Read-only snapshot of the speed PI integral state."""

    integral_error: float

    def __post_init__(self) -> None:
        _require_finite("integral_error", self.integral_error)


@dataclass(frozen=True)
class SpeedControllerOutput:
    """Current references and saturation metadata from one outer-loop update."""

    speed_error_rad_s: float
    iq_ref_unsaturated_a: float
    iq_ref_actual_a: float
    id_ref_a: float
    current_limit_active: bool
    saturation_error_a: float

    def __post_init__(self) -> None:
        for name, value in (
            ("speed_error_rad_s", self.speed_error_rad_s),
            ("iq_ref_unsaturated_a", self.iq_ref_unsaturated_a),
            ("iq_ref_actual_a", self.iq_ref_actual_a),
            ("id_ref_a", self.id_ref_a),
            ("saturation_error_a", self.saturation_error_a),
        ):
            _require_finite(name, value)
        if not isinstance(self.current_limit_active, bool):
            raise TypeError("current_limit_active must be a bool")


class SpeedController:
    """Generate bounded dq current references, never voltage commands."""

    def __init__(self, config: SpeedControllerConfig) -> None:
        if not isinstance(config, SpeedControllerConfig):
            raise TypeError("config must be a SpeedControllerConfig")
        self.config = config
        self._integral_error = 0.0

    @property
    def state(self) -> SpeedControllerState:
        return SpeedControllerState(integral_error=self._integral_error)

    @property
    def anti_windup_enabled(self) -> bool:
        return self.config.anti_windup_gain > 0.0

    def update(
        self,
        omega_ref_rad_s: float,
        omega_measured_rad_s: float,
        dt: float,
    ) -> SpeedControllerOutput:
        """Advance the speed PI once and return limited current references."""

        _require_finite("omega_ref_rad_s", omega_ref_rad_s)
        _require_finite("omega_measured_rad_s", omega_measured_rad_s)
        _require_finite("dt", dt)
        if dt <= 0.0:
            raise ValueError("dt must be greater than zero")

        speed_error = omega_ref_rad_s - omega_measured_rad_s
        self._integral_error += speed_error * dt
        iq_ref_unsaturated = (
            self.config.kp * speed_error
            + self.config.ki * self._integral_error
        )
        iq_ref_actual = min(
            max(iq_ref_unsaturated, self.config.iq_min_a),
            self.config.iq_max_a,
        )
        saturation_error = iq_ref_actual - iq_ref_unsaturated
        self._integral_error += (
            self.config.anti_windup_gain * saturation_error * dt
        )

        return SpeedControllerOutput(
            speed_error_rad_s=speed_error,
            iq_ref_unsaturated_a=iq_ref_unsaturated,
            iq_ref_actual_a=iq_ref_actual,
            id_ref_a=self.config.default_id_ref_a,
            current_limit_active=iq_ref_actual != iq_ref_unsaturated,
            saturation_error_a=saturation_error,
        )

    def reset(self) -> None:
        self._integral_error = 0.0
