"""Optional rotor-position and encoder quantization model."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from ..transforms import electrical_angle
from .measurement import SensorMeasurement


@dataclass(frozen=True)
class PositionSensorConfig:
    """Mechanical offset, encoder resolution, and angle-noise assumptions."""

    mechanical_offset_rad: float = 0.0
    resolution_counts_per_rev: int | None = None
    noise_std_rad: float = 0.0
    enabled: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.mechanical_offset_rad):
            raise ValueError("mechanical_offset_rad must be finite")
        if not math.isfinite(self.noise_std_rad) or self.noise_std_rad < 0.0:
            raise ValueError("noise_std_rad must be finite and non-negative")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        if self.resolution_counts_per_rev is not None:
            if (
                isinstance(self.resolution_counts_per_rev, bool)
                or not isinstance(self.resolution_counts_per_rev, int)
                or self.resolution_counts_per_rev <= 0
            ):
                raise ValueError("resolution_counts_per_rev must be a positive integer")


@dataclass(frozen=True)
class PositionMeasurement:
    """Wrapped mechanical measurement plus existing electrical-angle mapping."""

    true_value: float
    measured_value: float
    measurement_error: float
    quantized: bool
    noise_applied: bool
    electrical_angle_rad: float
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("true_value", self.true_value),
            ("measured_value", self.measured_value),
            ("measurement_error", self.measurement_error),
            ("electrical_angle_rad", self.electrical_angle_rad),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if not isinstance(self.quantized, bool):
            raise TypeError("quantized must be a bool")
        if not isinstance(self.noise_applied, bool):
            raise TypeError("noise_applied must be a bool")
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))


class PositionSensor:
    """Apply offset, noise, encoder quantization, then mechanical wrapping."""

    def __init__(self, config: PositionSensorConfig | None = None) -> None:
        self.config = config or PositionSensorConfig()

    def measure(
        self,
        theta_m_true_rad: float,
        pole_pairs: int,
        rng: random.Random | None = None,
    ) -> PositionMeasurement:
        if not math.isfinite(theta_m_true_rad):
            raise ValueError("theta_m_true_rad must be finite")
        true_wrapped = theta_m_true_rad % math.tau
        if not self.config.enabled:
            measured = true_wrapped
            return PositionMeasurement(
                true_value=true_wrapped,
                measured_value=measured,
                measurement_error=0.0,
                quantized=False,
                noise_applied=False,
                electrical_angle_rad=electrical_angle(measured, pole_pairs),
            )

        measured = theta_m_true_rad + self.config.mechanical_offset_rad
        noise_applied = self.config.noise_std_rad > 0.0
        if noise_applied:
            if rng is None:
                raise ValueError("an explicit RNG is required when position noise is enabled")
            measured += rng.gauss(0.0, self.config.noise_std_rad)

        quantized = self.config.resolution_counts_per_rev is not None
        if quantized:
            step = math.tau / self.config.resolution_counts_per_rev
            measured = round(measured / step) * step
        measured %= math.tau
        error = _shortest_angle_difference(measured, true_wrapped)
        return PositionMeasurement(
            true_value=true_wrapped,
            measured_value=measured,
            measurement_error=error,
            quantized=quantized,
            noise_applied=noise_applied,
            electrical_angle_rad=electrical_angle(measured, pole_pairs),
        )


def _shortest_angle_difference(measured: float, true: float) -> float:
    return (measured - true + math.pi) % math.tau - math.pi
