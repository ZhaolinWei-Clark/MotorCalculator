"""Optional direct rotor-speed measurement non-idealities."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .measurement import SensorMeasurement, ideal_measurement


@dataclass(frozen=True)
class SpeedSensorConfig:
    """Direct speed corruption; sample period is metadata in Phase 6M."""

    offset_rad_s: float = 0.0
    gain_error_fraction: float = 0.0
    noise_std_rad_s: float = 0.0
    sample_period_s: float | None = None
    enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("offset_rad_s", self.offset_rad_s),
            ("gain_error_fraction", self.gain_error_fraction),
            ("noise_std_rad_s", self.noise_std_rad_s),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if self.noise_std_rad_s < 0.0:
            raise ValueError("noise_std_rad_s must be non-negative")
        if self.sample_period_s is not None:
            if not math.isfinite(self.sample_period_s) or self.sample_period_s <= 0.0:
                raise ValueError("sample_period_s must be finite and greater than zero")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")


class SpeedSensor:
    """Apply gain, offset, and optional noise to direct speed feedback."""

    def __init__(self, config: SpeedSensorConfig | None = None) -> None:
        self.config = config or SpeedSensorConfig()

    def measure(
        self,
        true_speed_rad_s: float,
        rng: random.Random | None = None,
    ) -> SensorMeasurement:
        if not math.isfinite(true_speed_rad_s):
            raise ValueError("true_speed_rad_s must be finite")
        if not self.config.enabled:
            return ideal_measurement(true_speed_rad_s)

        measured = true_speed_rad_s * (1.0 + self.config.gain_error_fraction)
        measured += self.config.offset_rad_s
        noise_applied = self.config.noise_std_rad_s > 0.0
        if noise_applied:
            if rng is None:
                raise ValueError("an explicit RNG is required when speed noise is enabled")
            measured += rng.gauss(0.0, self.config.noise_std_rad_s)
        return SensorMeasurement(
            true_value=true_speed_rad_s,
            measured_value=measured,
            measurement_error=measured - true_speed_rad_s,
            quantized=False,
            noise_applied=noise_applied,
        )
