"""Multiplicative decomposition of a back-EMF comparison.

Back-EMF is proportional to ``N * k_w * flux``, so a Ke comparison tests only
that product. When the entered winding factor does not match the winding the
solver meshed, an agreeing Ke can be two offsetting errors rather than two
correct sub-models. This module makes that arithmetic explicit.

Nothing here changes an analytical value. It reports ratios between numbers
other code produced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DECOMPOSITION_SCHEMA_VERSION = "phase10c.fea.decomposition.v1"

#: Why the decomposition multiplies rather than adds.
#:
#: ``Ke = N * k_w * flux`` is a product, so the errors compose as a product too.
#: Adding "+7.39%" and "-7.06%" gives +0.33%, which is close to the observed
#: -0.31% only by coincidence of small numbers; the exact statement is
#: ``(1 + e_kw) * (1 + e_flux) - 1``.
MULTIPLICATIVE_RATIONALE = (
    "Ke is proportional to the product N * k_w * flux, so the component errors "
    "compose multiplicatively: the net ratio is the product of the ratios, not "
    "their sum. An additive approximation is not used."
)


@dataclass(frozen=True)
class KeErrorDecomposition:
    """How a back-EMF ratio splits into a winding-factor part and a flux part."""

    schema_version: str
    # Inputs
    winding_factor_entered: float
    winding_factor_geometric: float
    analytical_flux_per_pole_wb: float
    fea_equivalent_flux_per_pole_wb: float
    ke_analytical_entered: float
    ke_analytical_self_consistent: float
    ke_fea: float
    # Ratios (analytical / FEA convention throughout)
    winding_factor_ratio: float
    flux_ratio: float
    net_ke_ratio_historical: float
    net_ke_ratio_self_consistent: float
    reconstructed_net_ratio: float
    reconstruction_residual: float
    # Two known basis factors that separate the naive product from the observed
    # ratio. Reported rather than absorbed, so the reconstruction is exact.
    sine_emf_factor_ratio: float
    fea_total_to_fundamental_rms_ratio: float
    reconstructed_net_ratio_exact: float
    reconstruction_residual_exact: float
    rationale: str

    @property
    def winding_factor_error_percent(self) -> float:
        return (self.winding_factor_ratio - 1.0) * 100.0

    @property
    def flux_error_percent(self) -> float:
        return (self.flux_ratio - 1.0) * 100.0

    @property
    def historical_ke_error_percent(self) -> float:
        """Signed FEA-minus-analytical error, matching the comparison layer."""

        return (1.0 / self.net_ke_ratio_historical - 1.0) * 100.0

    @property
    def self_consistent_ke_error_percent(self) -> float:
        return (1.0 / self.net_ke_ratio_self_consistent - 1.0) * 100.0

    @property
    def cancellation_is_confirmed(self) -> bool:
        """True when the two component errors demonstrably offset each other.

        Both components must be materially larger than the historical net, and
        must pull in opposite directions.
        """

        net = abs(self.net_ke_ratio_historical - 1.0)
        kw = abs(self.winding_factor_ratio - 1.0)
        flux = abs(self.flux_ratio - 1.0)
        opposed = (self.winding_factor_ratio - 1.0) * (self.flux_ratio - 1.0) < 0.0
        return opposed and kw > 5.0 * net and flux > 5.0 * net


def fea_equivalent_flux_per_pole_wb(
    *,
    fundamental_flux_linkage_peak_wb_turn: float,
    turns_per_phase: int,
    winding_factor_geometric: float,
) -> float:
    """Fundamental flux per pole implied by a solved flux linkage.

    ``lambda_peak = N * k_w * flux``, so dividing the *measured* fundamental
    flux linkage by the turns and by the winding factor of the winding that was
    actually meshed gives the flux per pole the field implies.

    This is a *fundamental effective* flux per pole, not the literal total flux
    crossing one pole face: the flux linkage was reduced to its fundamental
    before the division, and the winding factor is itself a fundamental-only
    projection.
    """

    if turns_per_phase <= 0:
        raise ValueError("turns_per_phase must be positive")
    if not 0.0 < winding_factor_geometric <= 1.0:
        raise ValueError("winding_factor_geometric must be within (0, 1]")
    return fundamental_flux_linkage_peak_wb_turn / (
        float(turns_per_phase) * winding_factor_geometric
    )


def decompose_ke_error(
    *,
    winding_factor_entered: float,
    winding_factor_geometric: float,
    analytical_flux_per_pole_wb: float,
    fea_equivalent_flux_per_pole_wb: float,
    ke_analytical_entered: float,
    ke_analytical_self_consistent: float,
    ke_fea: float,
    sine_emf_factor: float | None = None,
    fea_total_to_fundamental_rms_ratio: float = 1.0,
) -> KeErrorDecomposition:
    """Split the historical Ke ratio into its winding-factor and flux parts.

    ``winding_factor_ratio * flux_ratio`` alone does not reproduce the observed
    Ke ratio exactly, and the gap is not noise. Two known basis factors separate
    them, and both are reported rather than absorbed:

    * the analytical back-EMF constant is the rounded ``4.44`` rather than the
      exact ``2*pi/sqrt(2) = 4.4428829...``, which understates analytical Ke by
      0.0649%;
    * the FEA Ke is a *total* RMS carrying the solved waveform's harmonics,
      while the flux ratio is built from the *fundamental* flux linkage.

    Pass ``sine_emf_factor`` to include the first; the second comes from the
    measured total-to-fundamental RMS ratio.
    """

    for name, value in (
        ("winding_factor_entered", winding_factor_entered),
        ("winding_factor_geometric", winding_factor_geometric),
        ("analytical_flux_per_pole_wb", analytical_flux_per_pole_wb),
        ("fea_equivalent_flux_per_pole_wb", fea_equivalent_flux_per_pole_wb),
        ("ke_analytical_entered", ke_analytical_entered),
        ("ke_analytical_self_consistent", ke_analytical_self_consistent),
        ("ke_fea", ke_fea),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be finite and positive")

    if fea_total_to_fundamental_rms_ratio <= 0.0:
        raise ValueError("fea_total_to_fundamental_rms_ratio must be positive")

    winding_factor_ratio = winding_factor_entered / winding_factor_geometric
    flux_ratio = analytical_flux_per_pole_wb / fea_equivalent_flux_per_pole_wb
    net_historical = ke_analytical_entered / ke_fea
    net_self_consistent = ke_analytical_self_consistent / ke_fea
    reconstructed = winding_factor_ratio * flux_ratio

    exact_sine_factor = 2.0 * math.pi / math.sqrt(2.0)
    sine_ratio = (
        sine_emf_factor / exact_sine_factor if sine_emf_factor is not None else 1.0
    )
    reconstructed_exact = (
        reconstructed * sine_ratio / fea_total_to_fundamental_rms_ratio
    )

    return KeErrorDecomposition(
        schema_version=DECOMPOSITION_SCHEMA_VERSION,
        winding_factor_entered=winding_factor_entered,
        winding_factor_geometric=winding_factor_geometric,
        analytical_flux_per_pole_wb=analytical_flux_per_pole_wb,
        fea_equivalent_flux_per_pole_wb=fea_equivalent_flux_per_pole_wb,
        ke_analytical_entered=ke_analytical_entered,
        ke_analytical_self_consistent=ke_analytical_self_consistent,
        ke_fea=ke_fea,
        winding_factor_ratio=winding_factor_ratio,
        flux_ratio=flux_ratio,
        net_ke_ratio_historical=net_historical,
        net_ke_ratio_self_consistent=net_self_consistent,
        reconstructed_net_ratio=reconstructed,
        reconstruction_residual=reconstructed - net_historical,
        sine_emf_factor_ratio=sine_ratio,
        fea_total_to_fundamental_rms_ratio=fea_total_to_fundamental_rms_ratio,
        reconstructed_net_ratio_exact=reconstructed_exact,
        reconstruction_residual_exact=reconstructed_exact - net_historical,
        rationale=MULTIPLICATIVE_RATIONALE,
    )
