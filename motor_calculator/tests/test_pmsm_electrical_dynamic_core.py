"""Phase 6E validation for the coupled PMSM dq electrical core."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    EulerIntegrator,
    InputState,
    MotorState,
    PMSMDynamicModel,
    PMSMDynamicParameters,
    RK4Integrator,
    SimulationRunner,
)


def _parameters(
    *,
    Rs: float = 1.0,
    Ld: float = 0.01,
    Lq: float = 0.01,
    psi_f: float = 0.1,
    pole_pairs: int = 2,
    J: float = 0.1,
    B: float = 0.0,
) -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=Rs,
        Ld=Ld,
        Lq=Lq,
        psi_f=psi_f,
        pole_pairs=pole_pairs,
        J=J,
        B=B,
    )


def _zero_state() -> MotorState:
    return MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def test_zero_voltage_origin_is_a_steady_state():
    parameters = _parameters()
    input_state = InputState(Vd=0.0, Vq=0.0, load_torque=0.0)

    derivatives = PMSMDynamicModel.compute_derivatives(_zero_state(), input_state, parameters)
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=_zero_state(),
        motor_parameters=parameters,
        input_profile=input_state,
        simulation_time=0.02,
        time_step=1.0e-3,
    )

    assert derivatives.did_dt == 0.0
    assert derivatives.diq_dt == 0.0
    assert derivatives.domega_dt == 0.0
    assert all(value == 0.0 for value in result.id)
    assert all(value == 0.0 for value in result.iq)
    assert all(value == 0.0 for value in result.speed)


def test_constant_d_axis_voltage_matches_independent_rl_step_response():
    parameters = _parameters()
    voltage = 2.0
    simulation_time = 0.05
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=_zero_state(),
        motor_parameters=parameters,
        input_profile=InputState(Vd=voltage, Vq=0.0, load_torque=0.0),
        simulation_time=simulation_time,
        time_step=1.0e-4,
    )
    expected_id = voltage / parameters.Rs * (
        1.0 - math.exp(-parameters.Rs * simulation_time / parameters.Ld)
    )

    assert result.id[-1] == pytest.approx(expected_id, rel=1.0e-10, abs=1.0e-12)
    assert result.iq[-1] == pytest.approx(0.0, abs=1.0e-12)
    assert result.speed[-1] == pytest.approx(0.0, abs=1.0e-12)


def test_constant_q_axis_voltage_couples_current_torque_and_speed():
    parameters = _parameters(J=0.05)
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=_zero_state(),
        motor_parameters=parameters,
        input_profile=InputState(Vd=0.0, Vq=5.0, load_torque=0.0),
        simulation_time=0.02,
        time_step=1.0e-4,
    )

    assert result.iq[-1] > 0.0
    assert result.torque[-1] > 0.0
    assert result.speed[-1] > 0.0


def test_salient_pmsm_torque_matches_required_dq_relationship():
    parameters = _parameters(Ld=0.006, Lq=0.009, psi_f=0.12, pole_pairs=3)
    state = MotorState(id=-2.0, iq=7.0, omega_m=80.0, theta=0.0)

    torque = PMSMDynamicModel.compute_electromagnetic_torque(state, parameters)
    expected = 1.5 * parameters.pole_pairs * (
        parameters.psi_f * state.iq
        + (parameters.Ld - parameters.Lq) * state.id * state.iq
    )

    assert torque == pytest.approx(expected)


def test_dq_electrical_power_splits_into_copper_storage_and_electromagnetic_power():
    parameters = _parameters(Rs=0.4, Ld=0.006, Lq=0.008, psi_f=0.12, pole_pairs=3)
    state = MotorState(id=2.0, iq=5.0, omega_m=100.0, theta=0.0)
    input_state = InputState(Vd=8.0, Vq=90.0, load_torque=1.2)

    electrical = PMSMDynamicModel.compute_electrical_derivatives(state, input_state, parameters)
    torque = PMSMDynamicModel.compute_electromagnetic_torque(state, parameters)
    three_phase_input_power = 1.5 * (input_state.Vd * state.id + input_state.Vq * state.iq)
    copper_power = 1.5 * parameters.Rs * (state.id**2 + state.iq**2)
    magnetic_storage_rate = 1.5 * (
        parameters.Ld * state.id * electrical.did_dt
        + parameters.Lq * state.iq * electrical.diq_dt
    )
    electromagnetic_power = torque * state.omega_m

    assert three_phase_input_power == pytest.approx(
        copper_power + magnetic_storage_rate + electromagnetic_power,
        rel=1.0e-12,
        abs=1.0e-10,
    )


def test_rk4_electrical_response_converges_to_analytic_solution():
    parameters = _parameters()
    input_state = InputState(Vd=2.0, Vq=0.0, load_torque=0.0)
    simulation_time = 0.05
    expected_id = input_state.Vd / parameters.Rs * (
        1.0 - math.exp(-parameters.Rs * simulation_time / parameters.Ld)
    )

    def current_error(integrator: EulerIntegrator | RK4Integrator, time_step: float) -> float:
        result = SimulationRunner(integrator=integrator).run(
            initial_state=_zero_state(),
            motor_parameters=parameters,
            input_profile=input_state,
            simulation_time=simulation_time,
            time_step=time_step,
        )
        return abs(result.id[-1] - expected_id)

    rk4_errors = [current_error(RK4Integrator(), dt) for dt in (1.0e-2, 1.0e-3, 1.0e-4)]
    euler_medium_error = current_error(EulerIntegrator(), 1.0e-3)

    assert rk4_errors[2] < rk4_errors[1] < rk4_errors[0]
    assert rk4_errors[1] < euler_medium_error


def test_torque_driven_mechanical_derivative_contract_remains_available():
    parameters = _parameters(J=0.5, B=0.1)
    state = MotorState(id=0.0, iq=0.0, omega_m=2.0, theta=0.0)

    derivative = PMSMDynamicModel.compute_mechanical_speed_derivative(
        state=state,
        electromagnetic_torque=3.0,
        load_torque=1.0,
        parameters=parameters,
    )

    assert derivative == pytest.approx((3.0 - 1.0 - 0.1 * 2.0) / 0.5)
