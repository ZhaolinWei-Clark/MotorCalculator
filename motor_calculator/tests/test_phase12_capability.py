"""Phase 12: MTPA, field weakening and the torque-speed capability envelope.

The tests that carry the most weight are the identities: a non-salient machine
must give ``id = 0`` exactly, the closed-form MTPA must agree with the derivative
condition it came from, and the new dq voltage must agree with the Phase 9C
authority on the case where both are valid. That last one already earned its
keep -- it caught the capability bridge reading the self inductance instead of
the synchronous inductance, a 6.86 % error that was invisible everywhere else.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from motor_calculator.capability.conventions import (
    CURRENT_BASIS,
    PARK_TRANSFORM,
    TORQUE_FACTOR,
    VOLTAGE_BASIS,
    phase_peak_to_line_rms,
    phase_rms_to_peak,
)
from motor_calculator.capability.envelope import (
    Region,
    classify_region,
    solve_base_speed,
    solve_max_torque_at_speed,
    solve_maximum_speed,
)
from motor_calculator.capability.export import (
    CALIBRATION_STATUS,
    EVIDENCE_STATEMENT,
    build_export_payload,
    export_capability,
    render_summary_zh,
)
from motor_calculator.capability.feasibility import capability_issues
from motor_calculator.capability.limits import (
    LimitError,
    Modulation,
    current_limit_from_peak,
    current_limit_from_rms,
    voltage_limit,
)
from motor_calculator.capability.parameters import (
    CapabilityParameterError,
    CapabilityParameters,
    MachineType,
    bridge_from_analysis,
)
from motor_calculator.capability.persistence import (
    PREFIX,
    from_preferences,
    to_preferences,
)
from motor_calculator.capability.solver import InverterSettings, solve_capability, solve_from_analysis
from motor_calculator.capability.steady_state import (
    dq_voltages,
    mtpa_condition_residual,
    mtpa_locus,
    mtpa_point,
    operating_point,
    torque_nm,
    verify_mtpa_numerically,
    voltage_magnitude,
)
from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.constants import VOLTAGE_REQUIREMENT_MARGIN_FACTOR
from motor_calculator.motor_core.validation import parse_legacy_gui_params
from motor_calculator.motor_core.voltage_semantics import corrected_required_voltage_line_rms_v

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _parameters(Ld: float = 1.0e-3, Lq: float = 1.0e-3, Rs: float = 0.1, psi: float = 0.016, p: int = 8):
    from motor_calculator.capability.parameters import _classify

    return CapabilityParameters(
        schema_version="test",
        convention_version="test",
        Rs=Rs, Ld=Ld, Lq=Lq, psi_pm=psi, pole_pairs=p,
        resistance_temperature_c=80.0,
        provenance=(),
        machine_type=_classify(Ld, Lq),
    )


@pytest.fixture(scope="module")
def baseline_analysis():
    params = dict(APPLICATION_DEFAULTS)
    params["coil_span_slots"] = 1
    return params, LegacyGuiMotorModelBridge(
        parse_legacy_gui_params(params)
    ).run_full_analysis()


@pytest.fixture(scope="module")
def baseline_capability(baseline_analysis):
    params, result = baseline_analysis
    return solve_from_analysis(result, params)


# ===========================================================================
# Part A: conventions (Step 1)
# ===========================================================================


def test_the_convention_is_amplitude_invariant_and_says_so():
    assert PARK_TRANSFORM == "AMPLITUDE_INVARIANT"
    assert CURRENT_BASIS == "PHASE_PEAK"
    assert VOLTAGE_BASIS == "PHASE_PEAK"
    assert TORQUE_FACTOR == 1.5


def test_basis_conversions_are_exact():
    assert phase_rms_to_peak(1.0) == pytest.approx(math.sqrt(2))
    assert phase_peak_to_line_rms(1.0) == pytest.approx(math.sqrt(3) / math.sqrt(2))


def test_the_steady_state_matches_the_dynamics_model_with_zero_derivatives():
    """The capability solver must be the steady state of the simulated model."""

    from motor_calculator.dynamics.pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
    from motor_calculator.dynamics.state import InputState, MotorState

    parameters = _parameters(Ld=1.2e-3, Lq=2.0e-3)
    id_a, iq_a, omega_e = -4.0, 9.0, 900.0
    vd, vq = dq_voltages(parameters, id_a, iq_a, omega_e)

    dynamic = PMSMDynamicParameters(
        Rs=parameters.Rs, Ld=parameters.Ld, Lq=parameters.Lq,
        psi_f=parameters.psi_pm, pole_pairs=parameters.pole_pairs, J=1.0e-4, B=0.0,
    )
    state = MotorState(id=id_a, iq=iq_a, omega_m=omega_e / parameters.pole_pairs, theta=0.0)
    derivatives = PMSMDynamicModel.compute_electrical_derivatives(
        state, InputState(Vd=vd, Vq=vq, load_torque=0.0), dynamic
    )
    assert derivatives.did_dt == pytest.approx(0.0, abs=1e-9)
    assert derivatives.diq_dt == pytest.approx(0.0, abs=1e-9)


def test_the_torque_equation_matches_the_dynamics_model():
    from motor_calculator.dynamics.pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
    from motor_calculator.dynamics.state import MotorState

    parameters = _parameters(Ld=1.2e-3, Lq=2.0e-3)
    dynamic = PMSMDynamicParameters(
        Rs=parameters.Rs, Ld=parameters.Ld, Lq=parameters.Lq,
        psi_f=parameters.psi_pm, pole_pairs=parameters.pole_pairs, J=1.0e-4, B=0.0,
    )
    state = MotorState(id=-3.0, iq=7.0, omega_m=100.0, theta=0.0)
    assert torque_nm(parameters, -3.0, 7.0) == pytest.approx(
        PMSMDynamicModel.compute_electromagnetic_torque(state, dynamic)
    )


# ===========================================================================
# Part B: dq equations (Step 3)
# ===========================================================================


def test_at_zero_speed_the_voltages_reduce_to_resistive_drops():
    parameters = _parameters()
    vd, vq = dq_voltages(parameters, 3.0, 5.0, 0.0)
    assert vd == pytest.approx(parameters.Rs * 3.0)
    assert vq == pytest.approx(parameters.Rs * 5.0)


def test_positive_iq_makes_positive_torque():
    parameters = _parameters()
    assert torque_nm(parameters, 0.0, 10.0) > 0.0
    assert torque_nm(parameters, 0.0, -10.0) < 0.0


def test_negative_id_reduces_the_q_axis_back_emf_term():
    """This is the mechanism field weakening relies on."""

    parameters = _parameters()
    _vd, vq_zero = dq_voltages(parameters, 0.0, 5.0, 1000.0)
    _vd, vq_negative = dq_voltages(parameters, -5.0, 5.0, 1000.0)
    assert vq_negative < vq_zero


def test_voltage_magnitude_grows_with_speed():
    parameters = _parameters()
    magnitudes = [voltage_magnitude(parameters, 0.0, 10.0, w) for w in (0.0, 500.0, 1000.0)]
    assert magnitudes[0] < magnitudes[1] < magnitudes[2]


def test_power_equals_torque_times_mechanical_speed():
    parameters = _parameters()
    point = operating_point(parameters, -2.0, 8.0, 1200.0)
    assert point.mechanical_power_w == pytest.approx(
        point.torque_nm * point.omega_m_rad_s
    )
    assert point.omega_m_rad_s == pytest.approx(1200.0 / parameters.pole_pairs)


# ===========================================================================
# Part C: limits (Steps 4-5)
# ===========================================================================


def test_svpwm_phase_peak_limit_is_vdc_over_sqrt3():
    limit = voltage_limit(48.0, modulation=Modulation.SVPWM)
    assert limit.phase_peak_v == pytest.approx(48.0 / math.sqrt(3))
    assert limit.phase_rms_v == pytest.approx(48.0 / math.sqrt(6))
    assert limit.line_rms_v == pytest.approx(48.0 / math.sqrt(2))


def test_spwm_phase_peak_limit_is_half_the_bus():
    limit = voltage_limit(48.0, modulation=Modulation.SPWM)
    assert limit.phase_peak_v == pytest.approx(24.0)


def test_svpwm_beats_spwm_by_the_expected_fraction():
    svpwm = voltage_limit(48.0, modulation=Modulation.SVPWM).phase_peak_v
    spwm = voltage_limit(48.0, modulation=Modulation.SPWM).phase_peak_v
    assert svpwm / spwm == pytest.approx(2.0 / math.sqrt(3))
    assert svpwm / spwm == pytest.approx(1.1547, abs=1e-4)


def test_the_svpwm_limit_agrees_with_the_existing_switching_model():
    """The capability solver and dynamics/modulation must not disagree."""

    source = (
        REPOSITORY_ROOT / "motor_calculator" / "dynamics" / "modulation" / "svpwm.py"
    ).read_text(encoding="utf-8")
    assert "sqrt(3)" in source or "sqrt{3}" in source
    assert voltage_limit(100.0).phase_peak_v == pytest.approx(100.0 / math.sqrt(3))


def test_the_utilization_factor_is_an_engineering_assumption():
    limit = voltage_limit(48.0, utilization=0.9)
    assert limit.utilization_classification == "ENGINEERING_ASSUMPTION"
    assert limit.phase_peak_v == pytest.approx(48.0 / math.sqrt(3) * 0.9)
    assert "工程假设" in limit.derivation_zh


def test_overmodulation_is_refused_rather_than_modelled():
    with pytest.raises(LimitError, match="overmodulation"):
        voltage_limit(48.0, utilization=1.2)


def test_the_current_limit_converts_rms_to_peak_explicitly():
    limit = current_limit_from_rms(10.0)
    assert limit.peak_a == pytest.approx(10.0 * math.sqrt(2))
    assert limit.rms_a == pytest.approx(10.0)
    assert "41.4" in limit.note_zh


def test_the_current_limit_circle_is_in_the_peak_basis():
    limit = current_limit_from_peak(10.0)
    assert limit.contains(6.0, 8.0)
    assert not limit.contains(8.0, 8.0)


# ===========================================================================
# Part D: MTPA (Steps 6-8)
# ===========================================================================


def test_non_salient_mtpa_gives_id_exactly_zero():
    """The hard identity. Not approximately zero: exactly zero."""

    parameters = _parameters(Ld=1.0e-3, Lq=1.0e-3)
    assert parameters.machine_type is MachineType.NON_SALIENT
    point = mtpa_point(parameters, 15.0)
    assert point.id_a == 0.0
    assert point.iq_a == 15.0
    assert point.method == "NON_SALIENT_ID_ZERO"


def test_non_salient_mtpa_is_id_zero_at_every_current():
    parameters = _parameters(Ld=1.0e-3, Lq=1.0e-3)
    for point in mtpa_locus(parameters, 20.0, points=15):
        assert point.id_a == 0.0


def test_salient_mtpa_satisfies_the_analytical_condition():
    parameters = _parameters(Ld=1.0e-3, Lq=2.5e-3)
    assert parameters.machine_type is MachineType.SALIENT_IPM
    for magnitude in (2.0, 8.0, 15.0, 30.0):
        point = mtpa_point(parameters, magnitude)
        assert point.condition_residual == pytest.approx(0.0, abs=1e-12)
        assert mtpa_condition_residual(parameters, point.id_a, magnitude) == pytest.approx(
            0.0, abs=1e-12
        )


def test_salient_mtpa_matches_an_independent_numerical_search():
    """The closed form is checked against a method that shares none of its algebra."""

    parameters = _parameters(Ld=1.0e-3, Lq=2.5e-3)
    for magnitude in (5.0, 12.0, 25.0):
        analytic = mtpa_point(parameters, magnitude)
        numeric_id, numeric_torque = verify_mtpa_numerically(parameters, magnitude)
        assert analytic.id_a == pytest.approx(numeric_id, abs=magnitude * 1.0e-3)
        assert analytic.torque_nm == pytest.approx(numeric_torque, rel=1.0e-6)
        assert analytic.torque_nm >= numeric_torque - 1.0e-9


def test_salient_mtpa_uses_negative_id_and_beats_id_zero():
    parameters = _parameters(Ld=1.0e-3, Lq=2.5e-3)
    point = mtpa_point(parameters, 15.0)
    assert point.id_a < 0.0
    assert point.torque_nm > torque_nm(parameters, 0.0, 15.0)


def test_inverse_saliency_is_not_assumed_away():
    parameters = _parameters(Ld=2.5e-3, Lq=1.0e-3)
    assert parameters.machine_type is MachineType.INVERSE_SALIENT
    point = mtpa_point(parameters, 15.0)
    assert point.id_a > 0.0
    assert point.torque_nm > torque_nm(parameters, 0.0, 15.0)


def test_the_mtpa_locus_is_monotonic_in_torque():
    parameters = _parameters(Ld=1.0e-3, Lq=2.5e-3)
    locus = mtpa_locus(parameters, 25.0, points=25)
    torques = [point.torque_nm for point in locus]
    assert torques == sorted(torques)
    assert all(
        locus[index].current_magnitude_a <= locus[index + 1].current_magnitude_a
        for index in range(len(locus) - 1)
    )


def test_salient_torque_per_amp_exceeds_the_non_salient_machine():
    salient = mtpa_point(_parameters(Ld=1.0e-3, Lq=2.5e-3), 15.0)
    plain = mtpa_point(_parameters(Ld=1.0e-3, Lq=1.0e-3), 15.0)
    assert salient.torque_per_amp_nm_per_a > plain.torque_per_amp_nm_per_a


# ===========================================================================
# Part E: base speed, field weakening, maximum speed (Steps 9-12)
# ===========================================================================


def test_base_speed_is_where_the_mtpa_point_meets_the_voltage_limit():
    parameters = _parameters()
    current = current_limit_from_peak(16.0)
    voltage = voltage_limit(48.0)
    base = solve_base_speed(parameters, current, voltage)
    assert base.resolved
    assert base.voltage_utilization == pytest.approx(1.0, abs=1e-6)
    assert base.current_utilization == pytest.approx(1.0)
    # Just below base speed the MTPA point is feasible; just above it is not.
    below = voltage_magnitude(parameters, base.id_a, base.iq_a, base.omega_e_rad_s * 0.99)
    above = voltage_magnitude(parameters, base.id_a, base.iq_a, base.omega_e_rad_s * 1.01)
    assert below < voltage.phase_peak_v < above


def test_base_speed_is_not_rated_speed(baseline_capability):
    base = baseline_capability.base_speed
    assert base.resolved
    assert base.speed_rpm != pytest.approx(APPLICATION_DEFAULTS["n_rated"], rel=0.01)


def test_a_higher_bus_voltage_raises_base_speed():
    parameters = _parameters()
    current = current_limit_from_peak(16.0)
    low = solve_base_speed(parameters, current, voltage_limit(48.0))
    high = solve_base_speed(parameters, current, voltage_limit(96.0))
    assert high.speed_rpm > low.speed_rpm


def test_field_weakening_uses_negative_id(baseline_capability):
    weakening = [
        point
        for point in baseline_capability.feasible_points
        if point.speed_rpm > baseline_capability.base_speed.speed_rpm * 1.05
    ]
    assert weakening
    assert all(point.id_a < 0.0 for point in weakening)


def test_field_weakening_respects_both_constraints(baseline_capability):
    current = baseline_capability.current_limit
    voltage = baseline_capability.voltage_limit
    for point in baseline_capability.feasible_points:
        assert point.current_magnitude_a <= current.peak_a * (1.0 + 1.0e-6)
        assert point.voltage_magnitude_v <= voltage.phase_peak_v * (1.0 + 1.0e-6)


def test_below_base_speed_the_solution_is_the_mtpa_point(baseline_capability):
    base = baseline_capability.base_speed
    low = [
        point
        for point in baseline_capability.feasible_points
        if point.speed_rpm < base.speed_rpm * 0.9
    ]
    assert low
    for point in low:
        assert point.id_a == pytest.approx(0.0, abs=1e-9)
        assert point.torque_nm == pytest.approx(baseline_capability.peak_torque_nm, rel=1e-9)


def test_the_id_trajectory_approaches_the_characteristic_current(baseline_capability):
    """A physical signature: id converges to -psi/Ld, not to an arbitrary value."""

    characteristic = baseline_capability.parameters.characteristic_current_a
    deepest = min(point.id_a for point in baseline_capability.feasible_points)
    assert deepest == pytest.approx(-characteristic, rel=0.02)


def test_maximum_speed_is_solved_not_extrapolated():
    parameters = _parameters()
    current = current_limit_from_peak(16.0)
    voltage = voltage_limit(48.0)
    maximum = solve_maximum_speed(parameters, current, voltage, search_ceiling_rpm=3.0e4)
    point = solve_max_torque_at_speed(
        parameters,
        maximum.omega_e_rad_s,
        current,
        voltage,
    )
    assert point is not None
    assert point.torque_nm > 0.0


def test_a_weak_current_limit_gives_a_bounded_maximum_speed():
    """Imax below the characteristic current means a finite top speed."""

    parameters = _parameters(psi=0.05, Ld=2.0e-3)
    characteristic = parameters.characteristic_current_a
    current = current_limit_from_peak(characteristic * 0.5)
    maximum = solve_maximum_speed(
        parameters, current, voltage_limit(48.0), search_ceiling_rpm=5.0e4
    )
    assert maximum.bounded
    assert maximum.speed_rpm > 0.0


def test_above_maximum_speed_there_is_no_feasible_point():
    parameters = _parameters(psi=0.05, Ld=2.0e-3)
    current = current_limit_from_peak(parameters.characteristic_current_a * 0.5)
    voltage = voltage_limit(48.0)
    maximum = solve_maximum_speed(parameters, current, voltage, search_ceiling_rpm=5.0e4)
    beyond = solve_max_torque_at_speed(
        parameters, maximum.omega_e_rad_s * 1.05, current, voltage
    )
    assert beyond is None or beyond.torque_nm <= 1.0e-6


# ===========================================================================
# Part F: regions (Step 11)
# ===========================================================================


def test_regions_come_from_active_constraints_not_speed(baseline_capability):
    for point in baseline_capability.feasible_points:
        if point.region is Region.MTPA_CURRENT_LIMITED:
            assert "CURRENT_LIMIT" in point.active_constraints
            assert "VOLTAGE_LIMIT" not in point.active_constraints
        elif point.region is Region.CURRENT_AND_VOLTAGE_LIMITED:
            assert set(point.active_constraints) >= {"CURRENT_LIMIT", "VOLTAGE_LIMIT"}
        elif point.region is Region.VOLTAGE_LIMITED_FIELD_WEAKENING:
            assert "VOLTAGE_LIMIT" in point.active_constraints
            assert "CURRENT_LIMIT" not in point.active_constraints


def test_the_baseline_shows_all_three_operating_regions(baseline_capability):
    regions = set(baseline_capability.regions_present())
    assert Region.MTPA_CURRENT_LIMITED in regions
    assert Region.CURRENT_AND_VOLTAGE_LIMITED in regions


def test_region_classification_is_a_pure_function_of_the_point():
    parameters = _parameters()
    current = current_limit_from_peak(16.0)
    voltage = voltage_limit(48.0)
    point = operating_point(parameters, 0.0, 16.0, 10.0)
    region, active = classify_region(point, current, voltage, parameters)
    assert region is Region.MTPA_CURRENT_LIMITED
    assert "CURRENT_LIMIT" in active


# ===========================================================================
# Part G: envelope and constant power (Steps 13-15)
# ===========================================================================


def test_the_envelope_is_deterministic(baseline_analysis):
    params, analysis = baseline_analysis
    first = solve_from_analysis(analysis, params)
    second = solve_from_analysis(analysis, params)
    assert [p.speed_rpm for p in first.envelope] == [p.speed_rpm for p in second.envelope]
    assert [p.torque_nm for p in first.envelope] == [p.torque_nm for p in second.envelope]


def test_the_envelope_samples_densely_near_base_speed(baseline_capability):
    base = baseline_capability.base_speed.speed_rpm
    near = [
        point for point in baseline_capability.envelope
        if 0.95 * base <= point.speed_rpm <= 1.10 * base
    ]
    assert len(near) >= 4


def test_power_equals_torque_times_speed_across_the_envelope(baseline_capability):
    for point in baseline_capability.feasible_points:
        assert point.mechanical_power_w == pytest.approx(
            point.torque_nm * point.omega_m_rad_s, rel=1e-12
        )


def test_torque_is_flat_below_base_speed_then_falls(baseline_capability):
    base = baseline_capability.base_speed.speed_rpm
    points = baseline_capability.feasible_points
    below = [p.torque_nm for p in points if p.speed_rpm < base * 0.95]
    above = [p.torque_nm for p in points if p.speed_rpm > base * 1.5]
    assert max(below) - min(below) < 1.0e-9
    assert above and max(above) < min(below)


def test_constant_power_is_measured_not_forced(baseline_capability):
    assessment = baseline_capability.constant_power
    assert assessment.classification == "ENGINEERING_REPORTING_THRESHOLD"
    if assessment.exists:
        assert assessment.power_spread_percent <= assessment.tolerance * 100.0
        assert assessment.end_rpm > assessment.start_rpm
    else:
        assert "没有" in assessment.note_zh


def test_a_machine_without_a_plateau_is_reported_as_such():
    """A very low current limit cannot sustain power; that must be said."""

    parameters = _parameters(psi=0.05, Ld=2.0e-3)
    result = solve_capability(
        parameters,
        current_limit_from_peak(parameters.characteristic_current_a * 0.3),
        voltage_limit(48.0),
        search_ceiling_rpm=2.0e4,
    )
    assert not result.constant_power.exists


# ===========================================================================
# Part H: parameter provenance (Steps 16-18)
# ===========================================================================


def test_psi_pm_comes_from_one_source_and_cross_checks(baseline_analysis):
    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    entry = parameters.get("psi_pm")
    assert entry.provenance == "PRODUCTION_DERIVED"
    assert "Ke_phase_peak_per_mechanical_rad_s / p" in entry.conversion
    assert "交叉核对" in entry.note_zh
    # The two independent routes agree exactly.
    omega_e = analysis.performance.mechanical_speed_rpm * 2 * math.pi / 60 * parameters.pole_pairs
    alternative = phase_rms_to_peak(analysis.electrical.back_emf_phase_rms_v) / omega_e
    assert parameters.psi_pm == pytest.approx(alternative, rel=1e-12)


def test_ld_and_lq_use_the_synchronous_inductance_not_the_self_inductance(baseline_analysis):
    """The bug the Phase 9C cross-check caught. L_s = L_ph - M, not L_ph."""

    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    assert parameters.Ld == pytest.approx(analysis.electrical.phase_synchronous_inductance_h)
    assert parameters.Ld == pytest.approx(analysis.electrical.line_inductance_h)
    assert parameters.Ld != pytest.approx(analysis.electrical.phase_inductance_h)


def test_isotropy_is_an_assumption_and_is_labelled(baseline_analysis):
    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    assert parameters.machine_type is MachineType.NON_SALIENT
    assert parameters.get("Ld").provenance == "ISOTROPIC_ASSUMPTION"
    assert parameters.get("Lq").provenance == "ISOTROPIC_ASSUMPTION"
    assert any("工程假设" in warning for warning in parameters.warnings_zh)


def test_explicit_saliency_overrides_the_assumption(baseline_analysis):
    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(
        analysis, params, d_axis_inductance_h=1.0e-3, q_axis_inductance_h=2.2e-3
    )
    assert parameters.machine_type is MachineType.SALIENT_IPM
    assert parameters.get("Ld").provenance == "USER_SUPPLIED_SALIENT"
    assert parameters.warnings_zh == ()


def test_resistance_is_not_temperature_corrected(baseline_analysis):
    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    assert parameters.Rs == pytest.approx(analysis.electrical.phase_resistance_ohm)
    assert parameters.resistance_temperature_c == pytest.approx(params["Temp_coil"])
    assert "不做任何额外温度修正" in parameters.get("Rs").note_zh


def test_an_unusable_result_is_refused_not_guessed():
    class Empty:
        pass

    with pytest.raises(CapabilityParameterError):
        bridge_from_analysis(Empty(), {"p": 8})


# ===========================================================================
# Part I: the voltage-authority cross-check (Step 22)
# ===========================================================================


def test_the_dq_voltage_agrees_with_the_phase9c_authority(baseline_analysis):
    """The load-bearing cross-check. Must agree to machine precision."""

    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    electrical, performance = analysis.electrical, analysis.performance
    omega_e = performance.mechanical_speed_rpm * 2 * math.pi / 60 * parameters.pole_pairs

    authority = corrected_required_voltage_line_rms_v(
        back_emf_phase_rms_v=electrical.back_emf_phase_rms_v,
        phase_current_rms_a=performance.phase_current_rms_a,
        phase_resistance_ohm=electrical.phase_resistance_ohm,
        synchronous_inductance_h=electrical.phase_synchronous_inductance_h,
        electrical_angular_speed_rad_s=omega_e,
        margin_factor=1.0,
    )
    iq = phase_rms_to_peak(performance.phase_current_rms_a)
    dq_line_rms = phase_peak_to_line_rms(
        voltage_magnitude(parameters, 0.0, iq, omega_e)
    )
    assert dq_line_rms == pytest.approx(authority, rel=1e-12)


def test_the_dq_voltage_reproduces_the_production_reported_voltage(baseline_analysis):
    """Including production's own engineering margin factor."""

    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    performance = analysis.performance
    omega_e = performance.mechanical_speed_rpm * 2 * math.pi / 60 * parameters.pole_pairs
    iq = phase_rms_to_peak(performance.phase_current_rms_a)
    dq_line_rms = phase_peak_to_line_rms(voltage_magnitude(parameters, 0.0, iq, omega_e))
    assert dq_line_rms * VOLTAGE_REQUIREMENT_MARGIN_FACTOR == pytest.approx(
        performance.required_voltage_line_rms_v, rel=1e-12
    )


def test_the_low_speed_torque_agrees_with_the_production_torque_constant(baseline_analysis):
    """Step 21: same basis, so the two must agree exactly."""

    params, analysis = baseline_analysis
    parameters = bridge_from_analysis(analysis, params)
    kt_per_peak = analysis.electrical.revised_torque_constant_nm_per_phase_peak_a
    iq = phase_rms_to_peak(analysis.performance.phase_current_rms_a)
    assert torque_nm(parameters, 0.0, iq) == pytest.approx(kt_per_peak * iq, rel=1e-12)
    # And it reproduces the production rated torque at rated current.
    assert torque_nm(parameters, 0.0, iq) == pytest.approx(
        analysis.performance.rated_torque_nm, rel=1e-9
    )


# ===========================================================================
# Part J: feasibility, persistence, export (Steps 27, 29, 30)
# ===========================================================================


def test_capability_issues_do_not_alter_the_design(baseline_capability):
    issues = capability_issues(
        baseline_capability, required_speed_rpm=1.0e5, required_torque_nm=100.0
    )
    codes = {issue.code for issue in issues}
    assert "MAX_SPEED_BELOW_REQUIRED" in codes or "BASE_SPEED_BELOW_REQUIRED" in codes
    assert "CURRENT_LIMIT_EXCEEDED" in codes
    # The result object is unchanged: nothing was adjusted to pass.
    assert baseline_capability.peak_torque_nm > 0.0


def test_a_comfortable_requirement_produces_no_blocking_issue(baseline_capability):
    issues = capability_issues(
        baseline_capability, required_speed_rpm=500.0, required_torque_nm=1.0
    )
    assert not any(issue.severity in {"ERROR", "SEVERE_DESIGN_RISK"} for issue in issues)


def test_inverter_settings_round_trip():
    settings = InverterSettings(
        dc_bus_voltage_v=72.0, modulation=Modulation.SPWM,
        voltage_utilization=0.92, current_limit_rms_a=18.5,
    )
    restored = from_preferences(to_preferences(settings), default_dc_bus_voltage_v=48.0)
    assert restored.dc_bus_voltage_v == pytest.approx(72.0)
    assert restored.modulation is Modulation.SPWM
    assert restored.voltage_utilization == pytest.approx(0.92)
    assert restored.current_limit_rms_a == pytest.approx(18.5)


def test_a_project_without_capability_keys_gets_clean_defaults():
    restored = from_preferences({"input_mode": "ADVANCED"}, default_dc_bus_voltage_v=60.0)
    assert restored.dc_bus_voltage_v == pytest.approx(60.0)
    assert restored.modulation is Modulation.SVPWM
    assert restored.voltage_utilization == pytest.approx(1.0)
    assert restored.current_limit_rms_a is None


def test_only_inputs_are_persisted_never_derived_curves():
    payload = to_preferences(InverterSettings(dc_bus_voltage_v=48.0))
    assert all(key.startswith(PREFIX) for key in payload)
    text = json.dumps(payload)
    for derived in ("torque", "envelope", "base_speed", "peak_power"):
        assert derived not in text


def test_capability_persistence_does_not_move_the_project_schema():
    from motor_calculator.project.schema import PROJECT_SCHEMA_VERSION

    assert PROJECT_SCHEMA_VERSION == 1


def test_the_export_carries_provenance_and_the_evidence_statement(baseline_capability, tmp_path):
    exported = export_capability(baseline_capability, tmp_path)
    payload = json.loads(exported.json_path.read_text(encoding="utf-8"))
    assert payload["evidence"] == EVIDENCE_STATEMENT
    assert payload["calibration_status"] == "NONE"
    assert payload["bases"]["current"] == "PHASE_PEAK"
    assert payload["bases"]["voltage"] == "PHASE_PEAK"
    assert payload["inverter"]["modulation"] == "SVPWM"
    assert payload["base_speed"]["resolved"]
    assert {item["name"] for item in payload["parameters"]} == {"psi_pm", "Rs", "Ld", "Lq"}
    assert exported.csv_path.is_file()


def test_the_export_never_claims_experimental_validation(baseline_capability, tmp_path):
    exported = export_capability(baseline_capability, tmp_path)
    text = exported.json_path.read_text(encoding="utf-8")
    assert "NOT_EXPERIMENTALLY_VALIDATED" in text
    assert "EXPERIMENTALLY_SUPPORTED" not in text
    assert "EXPERIMENTAL_MEASUREMENT" not in text
    summary = render_summary_zh(baseline_capability)
    assert "未经实验验证" in summary


def test_the_envelope_csv_declares_its_bases(baseline_capability, tmp_path):
    exported = export_capability(baseline_capability, tmp_path)
    text = exported.csv_path.read_text(encoding="utf-8")
    assert "id_peak_a" in text and "iq_peak_a" in text
    assert "vd_peak_v" in text and "voltage_magnitude_peak_v" in text
    assert "PHASE_PEAK" in text


# ===========================================================================
# Production physics and calibration
# ===========================================================================


def test_production_physics_is_untouched_by_phase12():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_the_legacy_baseline_fixture_is_untouched():
    path = REPOSITORY_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
    )


def test_no_calibration_was_introduced_in_phase12():
    negations = ("not ", "no ", "never", "非", "不", "未", "NONE")
    package = REPOSITORY_ROOT / "motor_calculator" / "capability"
    for path in sorted(package.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "calibrat" not in line.lower() and "标定" not in line:
                continue
            if "calibration_status" in line.lower():
                continue
            window = "".join(lines[index : index + 3])
            assert any(marker in window for marker in negations), f"{path.name}: {line}"


def test_no_fitted_coefficient_enters_the_capability_solver():
    """Every constant in the solver is a derivation, a tolerance or a threshold."""

    package = REPOSITORY_ROOT / "motor_calculator" / "capability"
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("curve_fit", "polyfit", "least_squares", "fudge", "tuned"):
            assert forbidden not in text, f"{path.name}: {forbidden}"


def test_the_capability_package_does_not_import_production_physics():
    """It reads results, it does not reach into the kernel."""

    package = REPOSITORY_ROOT / "motor_calculator" / "capability"
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "motor_core.calculations" not in text
        assert "from ..motor_core import" not in text
