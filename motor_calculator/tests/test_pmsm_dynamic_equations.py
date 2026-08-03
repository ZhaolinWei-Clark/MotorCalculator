"""Independent analytical checks for the Phase 6B PMSM dq equations."""

from __future__ import annotations

import pytest

from dynamics import InputState, MotorState, PMSMDynamicModel, PMSMDynamicParameters


def test_pmsm_derivatives_match_analytical_equations():
    parameters = PMSMDynamicParameters(
        Rs=0.4,
        Ld=0.006,
        Lq=0.008,
        psi_f=0.12,
        pole_pairs=3,
        J=0.02,
        B=0.003,
    )
    state = MotorState(id=2.0, iq=5.0, omega_m=100.0, theta=0.7)
    input_state = InputState(Vd=8.0, Vq=90.0, load_torque=1.2)

    derivatives = PMSMDynamicModel.compute_derivatives(state, input_state, parameters)

    omega_e = parameters.pole_pairs * state.omega_m
    expected_torque = 1.5 * parameters.pole_pairs * (
        parameters.psi_f * state.iq
        + (parameters.Ld - parameters.Lq) * state.id * state.iq
    )
    expected_did_dt = (
        input_state.Vd - parameters.Rs * state.id + omega_e * parameters.Lq * state.iq
    ) / parameters.Ld
    expected_diq_dt = (
        input_state.Vq
        - parameters.Rs * state.iq
        - omega_e * (parameters.Ld * state.id + parameters.psi_f)
    ) / parameters.Lq
    expected_domega_dt = (
        expected_torque - input_state.load_torque - parameters.B * state.omega_m
    ) / parameters.J

    assert derivatives.did_dt == pytest.approx(expected_did_dt)
    assert derivatives.diq_dt == pytest.approx(expected_diq_dt)
    assert derivatives.domega_dt == pytest.approx(expected_domega_dt)
    assert derivatives.dtheta_dt == pytest.approx(state.omega_m)


def test_surface_pmsm_torque_reduces_to_magnet_torque_term():
    parameters = PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.01,
        B=0.0,
    )
    state = MotorState(id=20.0, iq=3.0, omega_m=0.0, theta=0.0)

    torque = PMSMDynamicModel.compute_electromagnetic_torque(state, parameters)

    assert torque == pytest.approx(1.5 * parameters.pole_pairs * parameters.psi_f * state.iq)
