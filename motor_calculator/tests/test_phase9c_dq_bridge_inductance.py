"""Phase 9C Step 6: dq bridge must use the same synchronous inductance.

The corrected static voltage path uses L_s = L_ph - M. Before Phase 9C the
dynamic/dq bridge in analysis_service mapped Ld = Lq = L_ph, so the same machine
carried two different inductances depending on which path evaluated it.

The dq equations themselves are NOT modified.
"""

from __future__ import annotations

import math

import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.analysis_service import (
    DynamicAnalysisSettings,
    dq_bridge_parameters,
)
from motor_calculator.dynamics.pmsm_model import PMSMDynamicModel
from motor_calculator.dynamics.state import InputState, MotorState
from motor_calculator.motor_core.voltage_semantics import (
    dq_steady_state_required_voltage_line_rms_v,
)


V2_VALUES = {
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 1800.0,
    "N_ph_turns": 42,
    "d_wire": 1.2,
    "n_parallel": 3,
    "slot_type": "半闭口槽",
    "coreless": False,
}


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _evaluate(values):
    raw = _application_defaults()
    raw.update(values)
    parsed = parse_legacy_gui_params(raw)
    return parsed, LegacyGuiMotorModelBridge(parsed).run_full_analysis()


def test_synchronous_inductance_differs_from_the_phase_self_inductance():
    """Documents why this correction is needed at all."""

    _parsed, result = _evaluate(V2_VALUES)
    electrical = result.electrical

    assert electrical.mutual_inductance_h < 0.0
    assert electrical.line_inductance_h == pytest.approx(
        electrical.phase_inductance_h - electrical.mutual_inductance_h, abs=1e-18
    )
    assert electrical.line_inductance_h / electrical.phase_inductance_h == pytest.approx(
        1.15, rel=1e-12
    )


def test_dq_bridge_uses_the_synchronous_inductance():
    parsed, result = _evaluate(V2_VALUES)
    parameters = dq_bridge_parameters(parsed, result)

    assert parameters.Ld == pytest.approx(result.electrical.line_inductance_h, rel=1e-15)
    assert parameters.Lq == parameters.Ld
    # The pre-9C value must no longer be used.
    assert parameters.Ld != pytest.approx(result.electrical.phase_inductance_h, rel=1e-9)


def test_dq_bridge_flux_linkage_and_resistance_are_unchanged():
    parsed, result = _evaluate(V2_VALUES)
    parameters = dq_bridge_parameters(parsed, result)
    electrical = result.electrical

    assert parameters.Rs == pytest.approx(electrical.phase_resistance_ohm, rel=1e-15)
    assert parameters.psi_f == pytest.approx(
        electrical.torque_constant_nm_per_phase_peak_a / (1.5 * int(parsed["p"])),
        rel=1e-15,
    )
    assert parameters.pole_pairs == int(parsed["p"])


def test_static_and_dq_steady_state_voltage_now_agree_through_the_bridge():
    """The whole point of the correction: one machine, one inductance."""

    parsed, result = _evaluate(V2_VALUES)
    parameters = dq_bridge_parameters(parsed, result)
    performance = result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz

    through_bridge = dq_steady_state_required_voltage_line_rms_v(
        magnet_flux_linkage_wb=parameters.psi_f,
        phase_current_rms_a=performance.phase_current_rms_a,
        phase_resistance_ohm=parameters.Rs,
        synchronous_inductance_h=parameters.Lq,
        electrical_angular_speed_rad_s=omega_e,
    )
    assert through_bridge == pytest.approx(
        float(performance.required_voltage_line_rms_v), rel=1e-12
    )


def test_dq_equations_themselves_are_untouched():
    """compute_electrical_derivatives must still be the Phase 6 equations."""

    parsed, result = _evaluate(V2_VALUES)
    parameters = dq_bridge_parameters(parsed, result)
    state = MotorState(id=0.0, iq=3.0, omega_m=100.0, theta=0.0)
    inputs = InputState(Vd=1.0, Vq=2.0, load_torque=0.0)

    derivatives = PMSMDynamicModel.compute_electrical_derivatives(
        state, inputs, parameters
    )
    omega_e = parameters.pole_pairs * state.omega_m

    assert derivatives.omega_e == pytest.approx(omega_e)
    assert derivatives.did_dt == pytest.approx(
        (inputs.Vd - parameters.Rs * state.id + omega_e * parameters.Lq * state.iq)
        / parameters.Ld
    )
    assert derivatives.diq_dt == pytest.approx(
        (
            inputs.Vq
            - parameters.Rs * state.iq
            - omega_e * (parameters.Ld * state.id + parameters.psi_f)
        )
        / parameters.Lq
    )


def test_dynamic_analysis_reports_the_synchronous_inductance_mapping():
    from motor_calculator.analysis_service import run_dynamic_analysis

    parsed, result = _evaluate(V2_VALUES)
    settings = DynamicAnalysisSettings(
        simulation_time_s=0.02,
        speed_reference_rpm=1800.0,
        initial_speed_rpm=0.0,
        load_torque_nm=0.0,
        inertia_kg_m2=1e-3,
        viscous_friction_nm_per_rad_s=1e-4,
    )
    outcome = run_dynamic_analysis(parsed, result, settings)
    notes = "\n".join(outcome.mapping_notes)

    assert "同步电感" in notes
    assert "L_ph - M" in notes or "L_ph − M" in notes
    assert outcome.result is not None
