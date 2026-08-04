"""Explicit three-phase copper loss and temperature-dependent resistance."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class ResistanceTemperatureConfig:
    """Linear copper resistance-temperature relationship.

    The default coefficient, 0.00393 / degree C, is an explicit approximate
    copper value near 20 degree C and remains configurable by the caller.
    """

    resistance_ref_ohm: float
    reference_temperature_c: float = 20.0
    copper_temperature_coefficient_per_c: float = 0.00393

    def __post_init__(self) -> None:
        for name, value in (
            ("resistance_ref_ohm", self.resistance_ref_ohm),
            ("reference_temperature_c", self.reference_temperature_c),
            (
                "copper_temperature_coefficient_per_c",
                self.copper_temperature_coefficient_per_c,
            ),
        ):
            _require_finite(name, value)
        if self.resistance_ref_ohm < 0.0:
            raise ValueError("resistance_ref_ohm must be non-negative")
        if self.copper_temperature_coefficient_per_c < 0.0:
            raise ValueError(
                "copper_temperature_coefficient_per_c must be non-negative"
            )

    def resistance_at_temperature(self, temperature_c: float) -> float:
        _require_finite("temperature_c", temperature_c)
        resistance = self.resistance_ref_ohm * (
            1.0
            + self.copper_temperature_coefficient_per_c
            * (temperature_c - self.reference_temperature_c)
        )
        if resistance < 0.0:
            raise ValueError("linear resistance model produced a negative resistance")
        return resistance


class CopperLossModel:
    """Compute balanced three-phase I-squared-R loss with explicit semantics."""

    @staticmethod
    def compute_from_phase_rms(
        phase_current_rms_a: float,
        phase_resistance_ohm: float,
    ) -> float:
        for name, value in (
            ("phase_current_rms_a", phase_current_rms_a),
            ("phase_resistance_ohm", phase_resistance_ohm),
        ):
            _require_finite(name, value)
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
        return 3.0 * phase_current_rms_a**2 * phase_resistance_ohm

    @classmethod
    def compute_from_dq_peak(
        cls,
        id_a: float,
        iq_a: float,
        phase_resistance_ohm: float,
    ) -> float:
        """Use amplitude-invariant dq peak values for a balanced sinusoid.

        ``I_phase_rms^2 = (id^2 + iq^2) / 2``, so the three-phase loss is
        ``1.5 * Rs * (id^2 + iq^2)``.
        """

        for name, value in (("id_a", id_a), ("iq_a", iq_a)):
            _require_finite(name, value)
        phase_rms = math.hypot(id_a, iq_a) / math.sqrt(2.0)
        return cls.compute_from_phase_rms(phase_rms, phase_resistance_ohm)
