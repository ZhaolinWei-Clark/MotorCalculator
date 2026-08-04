"""Extensible, explicitly provisional iron-loss interfaces."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from .loss_results import IronLossEstimate


class IronLossModel(Protocol):
    def compute(
        self,
        electrical_frequency_hz: float,
        flux_density_proxy: float | None,
        temperature_c: float,
    ) -> IronLossEstimate: ...


class UnavailableIronLossModel:
    """Default model used when defensible material/loss-map data is absent."""

    @staticmethod
    def compute(
        electrical_frequency_hz: float,
        flux_density_proxy: float | None,
        temperature_c: float,
    ) -> IronLossEstimate:
        _validate_inputs(electrical_frequency_hz, flux_density_proxy, temperature_c)
        return IronLossEstimate(
            loss_w=None,
            available=False,
            provisional=True,
            method="unavailable",
            assumptions=("No validated iron-loss coefficients or loss map supplied.",),
            warning_messages=(
                "Iron loss is unavailable and is excluded from total loss.",
            ),
        )


@dataclass(frozen=True)
class ProvisionalIronLossModel:
    """Simple caller-parameterized frequency/flux proxy model.

    ``Pfe = kh * f * Bproxy^2 + ke * f^2 * Bproxy^2``. The coefficients
    are never defaulted because they require material and geometry evidence.
    """

    hysteresis_coefficient: float
    eddy_coefficient: float

    def __post_init__(self) -> None:
        for name, value in (
            ("hysteresis_coefficient", self.hysteresis_coefficient),
            ("eddy_coefficient", self.eddy_coefficient),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

    def compute(
        self,
        electrical_frequency_hz: float,
        flux_density_proxy: float | None,
        temperature_c: float,
    ) -> IronLossEstimate:
        _validate_inputs(electrical_frequency_hz, flux_density_proxy, temperature_c)
        if flux_density_proxy is None:
            return UnavailableIronLossModel.compute(
                electrical_frequency_hz, flux_density_proxy, temperature_c
            )
        flux_squared = flux_density_proxy**2
        loss = (
            self.hysteresis_coefficient * electrical_frequency_hz * flux_squared
            + self.eddy_coefficient
            * electrical_frequency_hz**2
            * flux_squared
        )
        return IronLossEstimate(
            loss_w=loss,
            available=True,
            provisional=True,
            method="provisional_frequency_flux_proxy",
            assumptions=(
                "Flux density is a caller-supplied proxy, not a solved field value.",
                "Temperature dependence of provisional coefficients is not modeled.",
            ),
            warning_messages=(
                "Iron loss is provisional and must not be treated as validated accuracy.",
            ),
        )


def _validate_inputs(
    electrical_frequency_hz: float,
    flux_density_proxy: float | None,
    temperature_c: float,
) -> None:
    if not math.isfinite(electrical_frequency_hz) or electrical_frequency_hz < 0.0:
        raise ValueError("electrical_frequency_hz must be finite and non-negative")
    if flux_density_proxy is not None:
        if not math.isfinite(flux_density_proxy) or flux_density_proxy < 0.0:
            raise ValueError("flux_density_proxy must be None or finite and non-negative")
    if not math.isfinite(temperature_c):
        raise ValueError("temperature_c must be finite")
