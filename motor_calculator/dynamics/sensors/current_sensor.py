"""Optional phase-current measurement non-idealities for the FOC sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .measurement import SensorMeasurement, ideal_measurement


@dataclass(frozen=True)
class CurrentSensorConfig:
    """Gain, offset, noise, and bipolar ADC quantization assumptions."""

    offset_a: float = 0.0
    gain_error_fraction: float = 0.0
    noise_std_a: float = 0.0
    resolution_bits: int | None = None
    full_scale_a: float | None = None
    enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("offset_a", self.offset_a),
            ("gain_error_fraction", self.gain_error_fraction),
            ("noise_std_a", self.noise_std_a),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if self.noise_std_a < 0.0:
            raise ValueError("noise_std_a must be non-negative")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")
        if (self.resolution_bits is None) != (self.full_scale_a is None):
            raise ValueError(
                "resolution_bits and full_scale_a must either both be set or both be None"
            )
        if self.resolution_bits is not None:
            if (
                isinstance(self.resolution_bits, bool)
                or not isinstance(self.resolution_bits, int)
                or self.resolution_bits < 2
            ):
                raise ValueError("resolution_bits must be an integer of at least 2")
            if not math.isfinite(self.full_scale_a) or self.full_scale_a <= 0.0:
                raise ValueError("full_scale_a must be finite and greater than zero")


class CurrentSensor:
    """Measure current in the documented gain, offset, noise, quantize order."""

    def __init__(self, config: CurrentSensorConfig | None = None) -> None:
        self.config = config or CurrentSensorConfig()

    def measure(
        self,
        true_current_a: float,
        rng: random.Random | None = None,
    ) -> SensorMeasurement:
        if not math.isfinite(true_current_a):
            raise ValueError("true_current_a must be finite")
        if not self.config.enabled:
            return ideal_measurement(true_current_a)

        measured = true_current_a * (1.0 + self.config.gain_error_fraction)
        measured += self.config.offset_a
        noise_applied = self.config.noise_std_a > 0.0
        if noise_applied:
            if rng is None:
                raise ValueError("an explicit RNG is required when current noise is enabled")
            measured += rng.gauss(0.0, self.config.noise_std_a)

        quantized = self.config.resolution_bits is not None
        warnings: list[str] = []
        if quantized:
            full_scale = self.config.full_scale_a
            if measured < -full_scale or measured > full_scale:
                warnings.append("Current measurement exceeded full scale and was clipped.")
            measured = min(max(measured, -full_scale), full_scale)
            levels = (1 << self.config.resolution_bits) - 1
            step = 2.0 * full_scale / levels
            code = round((measured + full_scale) / step)
            measured = -full_scale + code * step

        return SensorMeasurement(
            true_value=true_current_a,
            measured_value=measured,
            measurement_error=measured - true_current_a,
            quantized=quantized,
            noise_applied=noise_applied,
            warning_messages=tuple(warnings),
        )
