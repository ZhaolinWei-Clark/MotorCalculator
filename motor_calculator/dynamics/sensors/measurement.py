"""Read-only measurement metadata shared by sandbox sensor models."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SensorMeasurement:
    """One scalar true/measured pair and explicit non-ideality metadata."""

    true_value: float
    measured_value: float
    measurement_error: float
    quantized: bool
    noise_applied: bool
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("true_value", self.true_value),
            ("measured_value", self.measured_value),
            ("measurement_error", self.measurement_error),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if not isinstance(self.quantized, bool):
            raise TypeError("quantized must be a bool")
        if not isinstance(self.noise_applied, bool):
            raise TypeError("noise_applied must be a bool")
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))


def ideal_measurement(true_value: float) -> SensorMeasurement:
    """Return exact feedback without introducing any sensor-side state."""

    return SensorMeasurement(
        true_value=true_value,
        measured_value=true_value,
        measurement_error=0.0,
        quantized=False,
        noise_applied=False,
    )
