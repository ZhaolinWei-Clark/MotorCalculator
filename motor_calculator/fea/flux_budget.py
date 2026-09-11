"""Phase 10D: the multiplicative residual budget for a back-EMF comparison.

Phase 10C established that a Ke comparison tests only the product ``N * k_w * Phi``
and split it into a winding-factor part and a flux part. Phase 10D measured the
field directly and found that the flux part was itself two different things, and
that the winding-factor part was still being taken from a winding the solver never
meshed.

This module states the whole budget as one product, with each factor traceable to
a measurement:

``k_w meshed / k_w assumed``
    The winding factor of the geometry that was actually meshed, against the one
    the comparison divided by. A side-by-side double layer puts the two sides of
    a coil one slot pitch *plus one layer width* apart, which is not the pitch a
    slot-EMF star assumes.

``flat-top to fundamental``
    The analytical pole flux is a flat-top lumped value over the magnet arc, but
    ``E = 4.44 f N k_w Phi`` requires the *fundamental* flux per pole. Pure
    geometry, no fitted content.

``waveform and axial averaging``
    What is left once the two conventions above are aligned: the real air-gap
    waveform in a thick coreless gap is far more sinusoidal than the assumed
    rectangle, and the winding occupies a finite axial thickness over which the
    field varies.

``sine EMF rounding``
    ``4.44`` against the exact ``2*pi/sqrt(2)``.

Nothing here is fitted to a solver and nothing here changes a production value.
A budget whose factors multiply back to the observed residual is a decomposition;
one that does not is an admission that something is still unexplained, and the
remainder is reported either way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FLUX_BUDGET_SCHEMA_VERSION = "phase10d.flux_budget.v1"

#: Below this the remainder is numerical noise rather than missing physics.
RESOLVED_REMAINDER_TOLERANCE = 5.0e-4


@dataclass(frozen=True)
class FluxResidualBudget:
    """A back-EMF residual expressed as a product of measured factors."""

    schema_version: str
    winding_factor_meshed: float
    winding_factor_assumed: float
    analytical_flat_top_flux_wb: float
    fea_fundamental_flux_wb: float
    pole_arc_coefficient: float
    sine_emf_factor: float
    observed_ke_ratio: float

    @property
    def winding_factor_term(self) -> float:
        return self.winding_factor_meshed / self.winding_factor_assumed

    @property
    def convention_term(self) -> float:
        """Flat-top to fundamental, for an ideal rectangular pole."""

        alpha = self.pole_arc_coefficient
        return (8.0 / math.pi**2) * math.sin(alpha * math.pi / 2.0) / alpha

    @property
    def ideal_rectangle_fundamental_flux_wb(self) -> float:
        return self.analytical_flat_top_flux_wb * self.convention_term

    @property
    def waveform_term(self) -> float:
        """What the field does that an ideal rectangle does not."""

        return self.fea_fundamental_flux_wb / self.ideal_rectangle_fundamental_flux_wb

    @property
    def sine_emf_term(self) -> float:
        return (2.0 * math.pi / math.sqrt(2.0)) / self.sine_emf_factor

    @property
    def reconstructed_ratio(self) -> float:
        return (
            self.winding_factor_term
            * self.convention_term
            * self.waveform_term
            * self.sine_emf_term
        )

    @property
    def unresolved_remainder(self) -> float:
        """``reconstructed / observed - 1``. Zero means fully decomposed."""

        return self.reconstructed_ratio / self.observed_ke_ratio - 1.0

    @property
    def is_fully_decomposed(self) -> bool:
        return abs(self.unresolved_remainder) < RESOLVED_REMAINDER_TOLERANCE

    def as_rows(self) -> tuple[tuple[str, float, float], ...]:
        """``(label, factor, percent)`` ordered largest contribution first."""

        rows = [
            ("winding factor: meshed vs assumed", self.winding_factor_term),
            ("convention: flat-top flux vs fundamental", self.convention_term),
            ("waveform and axial averaging", self.waveform_term),
            ("sine EMF rounding", self.sine_emf_term),
        ]
        rows.sort(key=lambda item: abs(item[1] - 1.0), reverse=True)
        return tuple((label, factor, (factor - 1.0) * 100.0) for label, factor in rows)


def meshed_winding_factor(
    *, coil_pitch_m: float, coil_side_width_m: float, pole_pitch_m: float
) -> float:
    """Fundamental winding factor of a finite-width coil at a measured pitch.

    ``sin(pi/2 * pitch/tau)`` is the pitch factor for the fundamental, and
    ``sinc(pi * w / (2 tau))`` accounts for a coil side spread over a finite
    circumferential width rather than concentrated at a point. Both are exact
    for the fundamental; neither is fitted.
    """

    for name, value in (
        ("coil_pitch_m", coil_pitch_m),
        ("coil_side_width_m", coil_side_width_m),
        ("pole_pitch_m", pole_pitch_m),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be finite and positive")

    k = math.pi / pole_pitch_m
    pitch_factor = abs(math.sin(k * coil_pitch_m / 2.0))
    half_width = k * coil_side_width_m / 2.0
    width_factor = math.sin(half_width) / half_width
    return pitch_factor * width_factor


def build_flux_residual_budget(
    *,
    winding_factor_meshed: float,
    winding_factor_assumed: float,
    analytical_flat_top_flux_wb: float,
    fea_fundamental_flux_wb: float,
    pole_arc_coefficient: float,
    sine_emf_factor: float,
    observed_ke_ratio: float,
) -> FluxResidualBudget:
    """Assemble the budget, validating every input is usable."""

    for name, value in (
        ("winding_factor_meshed", winding_factor_meshed),
        ("winding_factor_assumed", winding_factor_assumed),
        ("analytical_flat_top_flux_wb", analytical_flat_top_flux_wb),
        ("fea_fundamental_flux_wb", fea_fundamental_flux_wb),
        ("sine_emf_factor", sine_emf_factor),
        ("observed_ke_ratio", observed_ke_ratio),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
    if not 0.0 < pole_arc_coefficient <= 1.0:
        raise ValueError("pole_arc_coefficient must be within (0, 1]")
    for name, value in (
        ("winding_factor_meshed", winding_factor_meshed),
        ("winding_factor_assumed", winding_factor_assumed),
    ):
        if value > 1.0:
            raise ValueError(f"{name} must not exceed 1")

    return FluxResidualBudget(
        schema_version=FLUX_BUDGET_SCHEMA_VERSION,
        winding_factor_meshed=winding_factor_meshed,
        winding_factor_assumed=winding_factor_assumed,
        analytical_flat_top_flux_wb=analytical_flat_top_flux_wb,
        fea_fundamental_flux_wb=fea_fundamental_flux_wb,
        pole_arc_coefficient=pole_arc_coefficient,
        sine_emf_factor=sine_emf_factor,
        observed_ke_ratio=observed_ke_ratio,
    )
