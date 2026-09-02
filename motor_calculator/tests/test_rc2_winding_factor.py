"""RC2: fundamental winding-factor derivation, provenance and fallbacks."""

from __future__ import annotations

import math

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.motor_core.winding_factor import (
    WindingFactorError,
    WindingFactorMode,
    WindingFactorProvenance,
    build_slot_star,
    compute_fundamental_winding_factor,
    distribution_factor,
    format_winding_factor_report_lines_zh,
    format_winding_factor_summary_zh,
    full_pitch_slots,
    harmonic_winding_factors,
    pitch_factor,
    resolve_winding_factor,
    skew_factor,
    slot_electrical_angle_rad,
    slots_per_pole_per_phase,
)


# ---------------------------------------------------------------------------
# Numerical reference cases (STEP 24). Each is hand-checkable.
# ---------------------------------------------------------------------------
#
# Reference A -- classic integer-slot distributed winding
#   slots Q                 = 24
#   poles 2p                = 4        (pole_pairs p = 2)
#   phases m                = 3
#   slot electrical angle   = 2*pi*p/Q = 30 deg
#   q = Q/(2p*m)            = 2        (integer)
#   full pitch              = Q/(2p)   = 6 slots
#   coil span               = 5 slots  (5/6 chording, 150 deg electrical)
#   k_d1 = sin(q*a/2)/(q*sin(a/2)) = sin(30)/(2*sin(15))       = 0.9659258263
#   k_p1 = sin(span_elec/2)        = sin(75)                   = 0.9659258263
#   k_s1 = 1                       (no skew)
#   k_w1 = k_d1*k_p1*k_s1                                      = 0.9330127019
#
# Reference B -- fractional-slot concentrated (tooth-coil) winding
#   Q = 12, 2p = 10 (p = 5), m = 3, a = 150 deg, q = 0.4, span = 1 slot
#   k_d1 = 0.9659258263, k_p1 = sin(75) = 0.9659258263
#   k_w1 = 0.9330127019   (the standard 12-slot/10-pole value)
#
# Reference C -- Q = 9, 2p = 8 (p = 4), span = 1 slot, a = 160 deg, q = 0.375
#   k_w1 = 0.9452         (the standard 9-slot/8-pole value)

REFERENCE_A = {"slots": 24, "pole_pairs": 2, "coil_span_slots": 5}
REFERENCE_B = {"slots": 12, "pole_pairs": 5, "coil_span_slots": 1}
REFERENCE_C = {"slots": 9, "pole_pairs": 4, "coil_span_slots": 1}


def test_reference_a_matches_hand_calculation():
    breakdown = compute_fundamental_winding_factor(**REFERENCE_A)

    assert breakdown.slots_per_pole_per_phase == pytest.approx(2.0)
    assert breakdown.slot_electrical_angle_deg == pytest.approx(30.0)
    assert breakdown.full_pitch_slots == pytest.approx(6.0)
    assert breakdown.coil_span_electrical_deg == pytest.approx(150.0)
    assert breakdown.distribution_factor == pytest.approx(0.9659258263, abs=1e-9)
    assert breakdown.pitch_factor == pytest.approx(0.9659258263, abs=1e-9)
    assert breakdown.skew_factor == pytest.approx(1.0, abs=1e-12)
    assert breakdown.fundamental_winding_factor == pytest.approx(0.9330127019, abs=1e-9)
    assert breakdown.winding_layout == "分布绕组"


def test_reference_a_full_pitch_removes_the_pitch_factor():
    breakdown = compute_fundamental_winding_factor(slots=24, pole_pairs=2, coil_span_slots=6)

    assert breakdown.pitch_factor == pytest.approx(1.0, abs=1e-12)
    assert breakdown.fundamental_winding_factor == pytest.approx(
        breakdown.distribution_factor, abs=1e-12
    )


def test_reference_b_fractional_slot_concentrated_winding():
    breakdown = compute_fundamental_winding_factor(**REFERENCE_B)

    assert breakdown.slots_per_pole_per_phase == pytest.approx(0.4)
    assert breakdown.slots_per_pole_per_phase < 1.0  # fractional q is supported
    assert breakdown.slot_electrical_angle_deg == pytest.approx(150.0)
    assert breakdown.fundamental_winding_factor == pytest.approx(0.9330127019, abs=1e-9)
    assert breakdown.winding_layout == "集中绕组（齿绕）"


def test_reference_c_nine_slot_eight_pole():
    breakdown = compute_fundamental_winding_factor(**REFERENCE_C)

    assert breakdown.fundamental_winding_factor == pytest.approx(0.9452, abs=1e-4)


@pytest.mark.parametrize(
    "slots, pole_pairs, q",
    [(24, 2, 2), (36, 3, 2), (48, 4, 2), (24, 4, 1), (36, 2, 3), (72, 6, 2)],
)
def test_star_distribution_factor_matches_the_integer_slot_closed_form(slots, pole_pairs, q):
    """The star must reduce to sin(q*a/2)/(q*sin(a/2)) whenever q is an integer."""

    alpha = slot_electrical_angle_rad(slots, pole_pairs)
    closed_form = abs(math.sin(q * alpha / 2.0) / (q * math.sin(alpha / 2.0)))

    assert slots_per_pole_per_phase(slots, pole_pairs) == pytest.approx(q)
    assert distribution_factor(slots, pole_pairs) == pytest.approx(closed_form, abs=1e-12)


def test_pitch_factor_is_sin_of_half_the_electrical_span():
    for span in (1, 2, 3, 4, 5, 6):
        expected = abs(math.sin(span * slot_electrical_angle_rad(24, 2) / 2.0))
        assert pitch_factor(span, 24, 2) == pytest.approx(expected, abs=1e-12)
    assert pitch_factor(6, 24, 2) == pytest.approx(1.0, abs=1e-12)


def test_skew_factor_is_unity_without_skew_and_decreases_with_skew():
    assert skew_factor(0.0, 24, 2) == 1.0
    one_slot = skew_factor(1.0, 24, 2)
    two_slots = skew_factor(2.0, 24, 2)
    assert 0.0 < two_slots < one_slot < 1.0
    # sinc form: sin(x)/x with x = n*sigma/2
    sigma = slot_electrical_angle_rad(24, 2)
    assert one_slot == pytest.approx(math.sin(sigma / 2.0) / (sigma / 2.0), abs=1e-12)


def test_skew_reduces_the_resulting_winding_factor():
    without = compute_fundamental_winding_factor(**REFERENCE_A)
    with_skew = compute_fundamental_winding_factor(**REFERENCE_A, skew_slots=1.0)

    assert with_skew.skew_factor < 1.0
    assert with_skew.fundamental_winding_factor < without.fundamental_winding_factor
    assert with_skew.fundamental_winding_factor == pytest.approx(
        without.fundamental_winding_factor * with_skew.skew_factor, abs=1e-12
    )


def test_full_pitch_helper():
    assert full_pitch_slots(24, 2) == pytest.approx(6.0)
    assert full_pitch_slots(12, 5) == pytest.approx(1.2)


@pytest.mark.parametrize("slots, pole_pairs", [(10, 4), (14, 5), (8, 3), (20, 4), (11, 5)])
def test_unbalanced_slot_pole_combinations_are_rejected_not_approximated(slots, pole_pairs):
    assert not build_slot_star(slots, pole_pairs).balanced
    with pytest.raises(WindingFactorError):
        compute_fundamental_winding_factor(
            slots=slots, pole_pairs=pole_pairs, coil_span_slots=1
        )


def test_auto_result_is_deterministic():
    values = {
        compute_fundamental_winding_factor(**REFERENCE_A).fundamental_winding_factor
        for _ in range(10)
    }
    assert len(values) == 1


def test_harmonic_factors_are_kept_separate_from_the_fundamental():
    harmonics = harmonic_winding_factors(**REFERENCE_B, harmonics=(1, 5, 7))

    assert harmonics[1] == pytest.approx(0.9330127019, abs=1e-9)
    # The fundamental must not be reused as if it described every harmonic.
    assert harmonics[5] != pytest.approx(harmonics[1], abs=1e-3)
    assert harmonics[7] != pytest.approx(harmonics[1], abs=1e-3)


# ---------------------------------------------------------------------------
# Resolution policy: AUTO / MANUAL / fallbacks
# ---------------------------------------------------------------------------


def _parsed(**overrides):
    return parse_legacy_gui_params(build_sample_legacy_params(**overrides))


def test_manual_mode_preserves_the_exact_input_value():
    parsed = _parsed(k_w=0.8123)
    resolution = resolve_winding_factor(parsed, mode=WindingFactorMode.MANUAL)

    assert resolution.value == 0.8123
    assert resolution.mode is WindingFactorMode.MANUAL
    assert resolution.provenance is WindingFactorProvenance.MANUAL_USER
    assert resolution.breakdown is None
    assert not resolution.is_auto


def test_auto_without_a_coil_span_does_not_assume_full_pitch():
    parsed = _parsed(k_w=0.91)
    resolution = resolve_winding_factor(parsed, mode=WindingFactorMode.AUTO)

    assert resolution.provenance is WindingFactorProvenance.NOT_ENOUGH_GEOMETRY
    assert resolution.value == 0.91  # manual value preserved verbatim
    assert resolution.breakdown is None
    assert "整距" in resolution.reason_zh


def test_auto_with_a_coil_span_derives_the_value_and_records_the_breakdown():
    parsed = _parsed(slots=24, p=2, k_w=0.91)
    resolution = resolve_winding_factor(
        parsed, mode=WindingFactorMode.AUTO, coil_span_slots=5
    )

    assert resolution.provenance is WindingFactorProvenance.AUTO_GEOMETRY
    assert resolution.is_auto
    assert resolution.value == pytest.approx(0.9330127019, abs=1e-9)
    assert resolution.manual_value == 0.91
    assert resolution.breakdown is not None
    assert resolution.breakdown.distribution_factor == pytest.approx(0.9659258263, abs=1e-9)
    assert resolution.breakdown.pitch_factor == pytest.approx(0.9659258263, abs=1e-9)
    assert resolution.breakdown.skew_factor == 1.0


def test_auto_falls_back_to_manual_for_an_unsupported_topology():
    parsed = _parsed(slots=10, p=4, k_w=0.88)
    resolution = resolve_winding_factor(
        parsed, mode=WindingFactorMode.AUTO, coil_span_slots=1
    )

    assert resolution.provenance is WindingFactorProvenance.NOT_SUPPORTED_FOR_AUTO_CALCULATION
    assert resolution.value == 0.88
    assert resolution.mode is WindingFactorMode.MANUAL


def test_auto_ignores_unparsable_span_and_skew_inputs():
    parsed = _parsed(slots=24, p=2, k_w=0.9)

    blank = resolve_winding_factor(parsed, mode="auto", coil_span_slots="   ")
    assert blank.provenance is WindingFactorProvenance.NOT_ENOUGH_GEOMETRY

    garbage = resolve_winding_factor(parsed, mode="auto", coil_span_slots="abc")
    assert garbage.provenance is WindingFactorProvenance.NOT_ENOUGH_GEOMETRY

    bad_skew = resolve_winding_factor(
        parsed, mode="auto", coil_span_slots="5", skew_slots="not-a-number"
    )
    assert bad_skew.provenance is WindingFactorProvenance.AUTO_GEOMETRY
    assert bad_skew.breakdown.skew_factor == 1.0  # unusable skew degrades to "no skew"


def test_legacy_and_preset_provenance_are_distinguishable():
    parsed = _parsed(k_w=0.93)
    for provenance in (
        WindingFactorProvenance.LEGACY_PROJECT,
        WindingFactorProvenance.PRESET,
        WindingFactorProvenance.MANUAL_USER,
    ):
        resolution = resolve_winding_factor(
            parsed, mode=WindingFactorMode.MANUAL, manual_provenance=provenance
        )
        assert resolution.provenance is provenance
        assert resolution.value == 0.93
        assert not resolution.is_auto
        assert resolution.provenance_label_zh


def test_resolution_dict_is_export_ready():
    parsed = _parsed(slots=24, p=2)
    payload = resolve_winding_factor(
        parsed, mode="auto", coil_span_slots=5
    ).to_dict()

    assert payload["winding_factor_mode"] == "auto"
    assert payload["winding_factor_provenance"] == "AUTO_GEOMETRY"
    assert payload["winding_factor_provenance_label_zh"] == "自动计算"
    assert payload["winding_factor_breakdown"]["method"] == "slot_emf_star_fundamental"
    assert payload["winding_factor"] == pytest.approx(0.9330127019, abs=1e-9)


def test_summary_and_report_text_expose_provenance_and_sub_factors():
    parsed = _parsed(slots=24, p=2)
    auto = resolve_winding_factor(parsed, mode="auto", coil_span_slots=5)
    manual = resolve_winding_factor(parsed, mode="manual")

    summary = format_winding_factor_summary_zh(auto)
    assert "自动计算" in summary and "k_d" in summary and "k_p" in summary and "k_s" in summary
    assert "手动指定" in format_winding_factor_summary_zh(manual)

    report = "\n".join(format_winding_factor_report_lines_zh(auto))
    assert "基波绕组系数 k_w1" in report
    assert "分布系数 k_d" in report
    assert "节距系数 k_p" in report
    assert "偏斜系数 k_s" in report
    assert "槽极配合" in report


# ---------------------------------------------------------------------------
# Downstream effect (STEP 15)
# ---------------------------------------------------------------------------


def test_winding_factor_scales_back_emf_and_constants_proportionally():
    low = LegacyGuiMotorModelBridge(_parsed(k_w=0.80)).run_full_analysis()
    high = LegacyGuiMotorModelBridge(_parsed(k_w=1.00)).run_full_analysis()

    ratio = 1.00 / 0.80
    assert high.electrical.back_emf_line_rms_v / low.electrical.back_emf_line_rms_v == pytest.approx(
        ratio, rel=1e-12
    )
    assert (
        high.electrical.legacy_back_emf_constant_line_rms_v_per_krpm
        / low.electrical.legacy_back_emf_constant_line_rms_v_per_krpm
    ) == pytest.approx(ratio, rel=1e-12)
    assert (
        high.electrical.legacy_torque_constant_nm_per_phase_rms_a
        / low.electrical.legacy_torque_constant_nm_per_phase_rms_a
    ) == pytest.approx(ratio, rel=1e-12)
    # Rated current follows 1/k_w, so k_w is a high-impact engineering input.
    assert high.performance.phase_current_rms_a < low.performance.phase_current_rms_a
    assert high.performance.required_voltage_v > low.performance.required_voltage_v
