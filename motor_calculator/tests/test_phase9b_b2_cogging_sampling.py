"""Phase 9B Batch B2: deterministic adaptive cogging sampling.

Phase 9 classified the fixed 360-point grid as CONFIRMED_NUMERICAL_DEFECT: the
waveform carries spatial orders up to 3*LCM(2p, Q) cycles per mechanical
revolution, and 42 of 56 realistic slot/pole combinations violate Nyquist. The
reported peak happened to survive only because linspace(0, 2*pi, 360) leaves
359 distinct intervals and 359 is prime, which turns aliasing into a
permutation of the sample set.

This batch derives the sample count from the represented spatial content and
takes the peak analytically so it no longer depends on that accident.

Legacy `k_cogging` input semantics are NOT redefined here.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.motor_core.constants import (
    COGGING_HIGHEST_HARMONIC_MULTIPLE,
    COGGING_MAXIMUM_SAMPLES,
    COGGING_MINIMUM_INTERVALS,
    COGGING_SAMPLES_PER_HIGHEST_CYCLE,
    COGGING_SHAPE_PEAK_FACTOR,
)


# Deliberately spans low / medium / high LCM and a previously aliased geometry.
GEOMETRIES = {
    "low_lcm": {"p": 10, "slots": 12},            # 2p=20 Q=12 -> LCM 60,  3*LCM 180
    "medium_lcm": {"p": 8, "slots": 24},          # 2p=16 Q=24 -> LCM 48,  3*LCM 144
    "previously_aliased": {"p": 10, "slots": 48},  # 2p=20 Q=48 -> LCM 240, 3*LCM 720
    "high_lcm": {"p": 20, "slots": 27},           # 2p=40 Q=27 -> LCM 1080, 3*LCM 3240
}

# Pre-B2 values on the fixed 360-point grid (recorded @ e4d966e).
PRE_B2_SAMPLE_COUNT = 360
PRE_B2_PEAK_RATIO = 1.1283815825


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _evaluate(overrides, *, coreless=False):
    raw = _application_defaults()
    raw.update(overrides)
    raw["coreless"] = coreless
    parsed = parse_legacy_gui_params(raw)
    return parsed, LegacyGuiMotorModelBridge(parsed).run_full_analysis()


def _lcm(parsed):
    pole_count = 2 * int(parsed["p"])
    slot_count = int(parsed["slots"])
    return pole_count * slot_count // math.gcd(pole_count, slot_count)


def _reference_torque(parsed):
    return 9.55 * float(parsed["P_rated"]) / float(parsed["n_rated"])


def _dense_shape(lcm, samples=2_000_001):
    theta = np.linspace(0.0, 2.0 * math.pi, samples)
    return np.sin(lcm * theta) + 0.3 * np.sin(2 * lcm * theta) + 0.1 * np.sin(3 * lcm * theta)


# ---------------------------------------------------------------------------
# The sampling rule itself
# ---------------------------------------------------------------------------


def test_b2_rule_constants_are_documented_and_sane():
    assert COGGING_HIGHEST_HARMONIC_MULTIPLE == 3  # model contains N, 2N, 3N
    assert COGGING_SAMPLES_PER_HIGHEST_CYCLE >= 4  # strict Nyquist needs > 2
    assert COGGING_MINIMUM_INTERVALS == 359        # preserves the previous density floor
    assert COGGING_MAXIMUM_SAMPLES > COGGING_MINIMUM_INTERVALS
    assert COGGING_SHAPE_PEAK_FACTOR == pytest.approx(1.1283820906416413, abs=1e-13)


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_sample_count_follows_the_derived_rule(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    theta = np.asarray(result.waveforms["cogging"]["rotor_position_rad"])

    highest_order = COGGING_HIGHEST_HARMONIC_MULTIPLE * _lcm(parsed)
    expected_intervals = max(
        COGGING_MINIMUM_INTERVALS, COGGING_SAMPLES_PER_HIGHEST_CYCLE * highest_order
    )
    expected_samples = min(expected_intervals + 1, COGGING_MAXIMUM_SAMPLES)

    assert theta.size == expected_samples


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_every_geometry_now_satisfies_nyquist(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    theta = np.asarray(result.waveforms["cogging"]["rotor_position_rad"])

    intervals = theta.size - 1  # linspace duplicates the endpoint, by design
    highest_order = COGGING_HIGHEST_HARMONIC_MULTIPLE * _lcm(parsed)
    assert intervals > 2 * highest_order, (
        f"{case}: {intervals} intervals cannot resolve order {highest_order}"
    )


def test_b2_endpoint_duplication_is_explicit_and_accounted_for():
    """The closed curve is kept for plotting, but the effective sample rate is
    intervals = n - 1, which is what the Nyquist rule is written against."""

    _parsed, result = _evaluate(GEOMETRIES["medium_lcm"])
    theta = np.asarray(result.waveforms["cogging"]["rotor_position_rad"])

    assert float(theta[0]) == 0.0
    assert float(theta[-1]) == pytest.approx(2.0 * math.pi, rel=1e-15)
    step = float(theta[1] - theta[0])
    assert step == pytest.approx(2.0 * math.pi / (theta.size - 1), rel=1e-12)


def test_b2_sample_count_is_capped_for_pathological_geometry():
    parsed, result = _evaluate({"p": 50, "slots": 99})
    theta = np.asarray(result.waveforms["cogging"]["rotor_position_rad"])

    assert _lcm(parsed) == 9900
    assert theta.size == COGGING_MAXIMUM_SAMPLES
    assert np.all(np.isfinite(np.asarray(result.waveforms["cogging"]["cogging_torque_nm"])))


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_result_is_deterministic(case):
    first = _evaluate(GEOMETRIES[case])[1].waveforms["cogging"]["cogging_torque_nm"]
    second = _evaluate(GEOMETRIES[case])[1].waveforms["cogging"]["cogging_torque_nm"]

    assert np.array_equal(np.asarray(first), np.asarray(second))


# ---------------------------------------------------------------------------
# Aliasing is actually resolved
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_plotted_waveform_is_no_longer_aliased(case):
    """A correctly sampled trace crosses zero about 2*LCM times per revolution."""

    parsed, result = _evaluate(GEOMETRIES[case])
    waveform = np.asarray(result.waveforms["cogging"]["cogging_torque_nm"])
    sign_changes = int(np.count_nonzero(np.diff(np.sign(waveform))))

    expected = 2 * _lcm(parsed)
    assert sign_changes == pytest.approx(expected, rel=0.02), (
        f"{case}: {sign_changes} sign changes vs the physical {expected}"
    )


def test_b2_documents_the_pre_correction_aliasing():
    """Regression anchor: on the old fixed grid a 2p=20/Q=48 machine showed
    roughly half the physical ripple frequency."""

    parsed, _result = _evaluate(GEOMETRIES["previously_aliased"])
    lcm = _lcm(parsed)
    theta = np.linspace(0.0, 2.0 * math.pi, PRE_B2_SAMPLE_COUNT)
    legacy = np.sin(lcm * theta) + 0.3 * np.sin(2 * lcm * theta) + 0.1 * np.sin(3 * lcm * theta)
    legacy_sign_changes = int(np.count_nonzero(np.diff(np.sign(legacy))))

    assert legacy_sign_changes < 2 * lcm * 0.75  # visibly aliased
    assert 3 * lcm > (PRE_B2_SAMPLE_COUNT - 1) / 2  # and it violated Nyquist


# ---------------------------------------------------------------------------
# Peak / RMS / fundamental fidelity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_peak_is_analytic_and_sampling_independent(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    reported = float(result.performance.cogging_torque_peak_nm)
    expected = (
        COGGING_SHAPE_PEAK_FACTOR
        * float(parsed["k_cogging"])
        * _reference_torque(parsed)
    )

    assert reported == pytest.approx(expected, rel=1e-12)
    # ...and it agrees with a dense numerical reference. The reference is itself
    # discretely sampled, so it converges to the analytic factor only to ~1e-7.
    dense_peak = float(np.abs(_dense_shape(_lcm(parsed))).max())
    assert COGGING_SHAPE_PEAK_FACTOR == pytest.approx(dense_peak, rel=1e-6)
    assert COGGING_SHAPE_PEAK_FACTOR >= dense_peak  # analytic is the true supremum


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_sampled_peak_now_matches_the_analytic_peak(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    waveform = np.asarray(result.waveforms["cogging"]["cogging_torque_nm"])

    assert float(np.abs(waveform).max()) == pytest.approx(
        float(result.performance.cogging_torque_peak_nm), rel=5e-3
    )


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_rms_matches_a_dense_reference(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    waveform = np.asarray(result.waveforms["cogging"]["cogging_torque_nm"])
    scale = float(parsed["k_cogging"]) * _reference_torque(parsed)

    sampled_rms = float(np.sqrt(np.mean(waveform**2))) / scale
    dense_rms = float(np.sqrt(np.mean(_dense_shape(_lcm(parsed)) ** 2)))
    assert sampled_rms == pytest.approx(dense_rms, rel=2e-3)


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_fundamental_amplitude_is_recovered_from_the_trace(case):
    """The LCM-order component must come back at amplitude k_cogging * T_ref."""

    parsed, result = _evaluate(GEOMETRIES[case])
    waveform = np.asarray(result.waveforms["cogging"]["cogging_torque_nm"])[:-1]
    lcm = _lcm(parsed)
    n = waveform.size
    spectrum = np.abs(np.fft.rfft(waveform)) / n * 2.0

    expected = float(parsed["k_cogging"]) * _reference_torque(parsed)
    assert float(spectrum[lcm]) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# Explicit cogging ratio semantics (Decision 1) -- outputs only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(GEOMETRIES))
def test_b2_explicit_cogging_ratios_are_published(case):
    parsed, result = _evaluate(GEOMETRIES[case])
    cogging = result.waveforms["cogging"]

    assert cogging["k_cogging_fundamental"] == pytest.approx(float(parsed["k_cogging"]))
    assert cogging["k_cogging_peak"] == pytest.approx(
        COGGING_SHAPE_PEAK_FACTOR * float(parsed["k_cogging"]), rel=1e-12
    )
    assert cogging["k_cogging_peak"] > cogging["k_cogging_fundamental"]


def test_b2_legacy_k_cogging_input_is_not_redefined():
    """The input field keeps its legacy meaning; only the outputs disambiguate."""

    parsed, result = _evaluate(GEOMETRIES["medium_lcm"])
    cogging = result.waveforms["cogging"]

    # legacy k_cogging == the fundamental ratio, which is what it always was.
    assert cogging["k_cogging_fundamental"] == float(parsed["k_cogging"])
    assert cogging["legacy_k_cogging"] == float(parsed["k_cogging"])
    assert "legacy" in cogging["k_cogging_semantics_status"].lower()


def test_b2_coreless_still_returns_a_zero_waveform_of_matching_length():
    parsed, result = _evaluate(GEOMETRIES["medium_lcm"], coreless=True)
    cogging = result.waveforms["cogging"]
    theta = np.asarray(cogging["rotor_position_rad"])
    waveform = np.asarray(cogging["cogging_torque_nm"])

    assert waveform.size == theta.size
    assert not np.any(waveform)
    assert float(result.performance.cogging_torque_peak_nm) == 0.0
    assert cogging["k_cogging_peak"] == 0.0
    assert cogging["k_cogging_fundamental"] == 0.0
