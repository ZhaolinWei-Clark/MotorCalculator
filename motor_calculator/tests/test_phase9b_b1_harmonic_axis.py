"""Phase 9B Batch B1: harmonic order mapping only.

Phase 9 classified this as PRESENTATION_DEFECT: the Fourier decomposition is
correct, only the order label was wrong (`k * pole_pairs` instead of
`k / pole_pairs`). These tests fix the corrected mapping in place and pin the
amplitudes, Bg_avg and Bg_rms so the correction stays presentation-only.

Endpoint sampling is deliberately NOT changed in this batch.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params


# Recorded before B1 on codex/phase9b-controlled-formula-corrections @ 8aaf2db.
# B1 must not move any of these.
PRE_B1_FLUX_INVARIANTS = {
    2: {"bg_avg": 0.47627468317123495, "bg_rms": 0.5686932270130303, "peak_amplitude": 0.7712059752265177},
    4: {"bg_avg": 0.47627468317123495, "bg_rms": 0.5686932270130302, "peak_amplitude": 0.7712205623786551},
    8: {"bg_avg": 0.47627468317123495, "bg_rms": 0.5686932270130302, "peak_amplitude": 0.7710732901134528},
}

SPECTRUM_LENGTH = 50


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _flux(pole_pairs: int):
    raw = _application_defaults()
    raw["p"] = pole_pairs
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return parsed, result, result.waveforms["flux"]


def _fundamental_bin(spectrum) -> int:
    values = np.asarray(spectrum)
    return int(np.argmax(values[1:])) + 1


# ---------------------------------------------------------------------------
# The decomposition itself must be untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pole_pairs", sorted(PRE_B1_FLUX_INVARIANTS))
def test_b1_does_not_move_the_fourier_amplitudes_or_bg_statistics(pole_pairs):
    _parsed, _result, flux = _flux(pole_pairs)
    expected = PRE_B1_FLUX_INVARIANTS[pole_pairs]

    assert float(flux["air_gap_flux_density_average_t"]) == expected["bg_avg"]
    assert float(flux["air_gap_flux_density_rms_t"]) == expected["bg_rms"]

    spectrum = np.asarray(flux["spectrum"])
    assert spectrum.size == SPECTRUM_LENGTH
    assert float(spectrum[_fundamental_bin(spectrum)]) == expected["peak_amplitude"]


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12])
def test_b1_spectrum_still_matches_the_analytical_square_wave_fundamental(pole_pairs):
    """Analytical reference: a bipolar square wave of duty alpha has a
    fundamental amplitude of 4/pi * B_pk * sin(pi*alpha/2)."""

    parsed, result, flux = _flux(pole_pairs)
    spectrum = np.asarray(flux["spectrum"])
    alpha = float(parsed["alpha_p"])
    peak = float(result.magnetic.air_gap_flux_density_peak_t)
    analytic = 4.0 / math.pi * peak * math.sin(math.pi * alpha / 2.0)

    assert float(spectrum[_fundamental_bin(spectrum)]) == pytest.approx(analytic, rel=5e-3)


def test_b1_endpoint_sampling_is_unchanged():
    """B1 must not touch sampling; that is a separate, deferred decision."""

    _parsed, _result, flux = _flux(8)
    angles = np.asarray(flux["mechanical_angle_deg"])

    assert angles.size == 720
    assert float(angles[0]) == 0.0
    assert float(angles[-1]) == 360.0  # endpoint still duplicated, on purpose


# ---------------------------------------------------------------------------
# The corrected order mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12])
def test_b1_fundamental_is_labelled_electrical_order_one(pole_pairs):
    _parsed, _result, flux = _flux(pole_pairs)
    spectrum = np.asarray(flux["spectrum"])
    electrical = np.asarray(flux["electrical_harmonic_order"])

    assert electrical.size == spectrum.size
    assert float(electrical[_fundamental_bin(spectrum)]) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12])
def test_b1_mechanical_order_is_the_raw_bin_index(pole_pairs):
    _parsed, _result, flux = _flux(pole_pairs)
    mechanical = np.asarray(flux["mechanical_harmonic_order"])

    assert np.array_equal(mechanical, np.arange(mechanical.size, dtype=float))
    # The fundamental sits at pole_pairs cycles per mechanical revolution.
    spectrum = np.asarray(flux["spectrum"])
    assert float(mechanical[_fundamental_bin(spectrum)]) == float(pole_pairs)


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12])
def test_b1_electrical_and_mechanical_orders_are_consistent(pole_pairs):
    _parsed, _result, flux = _flux(pole_pairs)
    electrical = np.asarray(flux["electrical_harmonic_order"])
    mechanical = np.asarray(flux["mechanical_harmonic_order"])

    assert np.allclose(electrical, mechanical / pole_pairs, rtol=0.0, atol=1e-12)


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12])
def test_b1_legacy_harmonics_key_now_carries_the_electrical_order(pole_pairs):
    """`harmonics` never had a defensible meaning (it was k*p, neither electrical
    nor mechanical). It is corrected in place; it is not part of the frozen
    baseline, any export, or any project snapshot."""

    _parsed, _result, flux = _flux(pole_pairs)

    assert np.array_equal(
        np.asarray(flux["harmonics"]), np.asarray(flux["electrical_harmonic_order"])
    )


# ---------------------------------------------------------------------------
# The reported defect: the p=8 fundamental was filtered out of the plot
# ---------------------------------------------------------------------------


PLOT_ORDER_LIMIT = 25


@pytest.mark.parametrize("pole_pairs", [1, 2, 4, 8, 12, 20])
def test_b1_fundamental_survives_the_plot_order_filter(pole_pairs):
    _parsed, _result, flux = _flux(pole_pairs)
    spectrum = np.asarray(flux["spectrum"])
    electrical = np.asarray(flux["electrical_harmonic_order"])

    visible = electrical <= PLOT_ORDER_LIMIT
    assert bool(visible[_fundamental_bin(spectrum)]), (
        f"p={pole_pairs}: the fundamental must be visible under the plot filter"
    )
    assert int(visible.sum()) >= 2


def test_b1_documents_the_pre_correction_failure_for_p8():
    """Regression anchor for the exact defect: under the old k*pole_pairs
    mapping a p=8 machine plotted only 4 sub-fundamental leakage bins."""

    _parsed, _result, flux = _flux(8)
    spectrum = np.asarray(flux["spectrum"])
    legacy_mapping = np.arange(spectrum.size, dtype=float) * 8.0  # the old formula
    legacy_visible = legacy_mapping <= PLOT_ORDER_LIMIT

    assert int(legacy_visible.sum()) == 4
    assert not bool(legacy_visible[_fundamental_bin(spectrum)])

    # ...and the corrected mapping fixes exactly that.
    corrected_visible = np.asarray(flux["electrical_harmonic_order"]) <= PLOT_ORDER_LIMIT
    assert bool(corrected_visible[_fundamental_bin(spectrum)])
