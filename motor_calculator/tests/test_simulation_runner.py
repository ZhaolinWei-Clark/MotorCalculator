"""End-to-end behavior checks for the Phase 6B simulation runner."""

from __future__ import annotations

import pytest

from dynamics import InputState, MotorState, PMSMDynamicParameters, SimulationRunner
from dynamics.examples import (
    run_load_step_example,
    run_startup_example,
    run_steady_state_verification_example,
)


def test_runner_returns_aligned_series_and_does_not_mutate_initial_state():
    initial_state = MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)
    parameters = PMSMDynamicParameters(
        Rs=1.0,
        Ld=0.01,
        Lq=0.01,
        psi_f=0.05,
        pole_pairs=2,
        J=0.02,
        B=0.001,
    )

    result = SimulationRunner().run(
        initial_state=initial_state,
        motor_parameters=parameters,
        input_profile=InputState(Vd=0.0, Vq=5.0, load_torque=0.0),
        simulation_time=0.01,
        time_step=0.001,
    )

    assert len(result.time) == 11
    assert all(len(series) == len(result.time) for series in result.series)
    assert result.time[-1] == pytest.approx(0.01)
    assert initial_state == MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def test_runner_does_not_add_zero_length_step_for_float_ratio_roundoff():
    parameters = PMSMDynamicParameters(
        Rs=1.0,
        Ld=0.01,
        Lq=0.01,
        psi_f=0.05,
        pole_pairs=2,
        J=0.02,
        B=0.001,
    )

    result = SimulationRunner().run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=parameters,
        input_profile=InputState(Vd=0.0, Vq=0.0, load_torque=0.0),
        simulation_time=0.07,
        time_step=0.005,
    )

    assert len(result.time) == 15
    assert result.time[-1] == pytest.approx(0.07)
    assert all(right > left for left, right in zip(result.time, result.time[1:]))


def test_startup_example_accelerates_from_rest():
    result = run_startup_example()

    assert result.speed[0] == 0.0
    assert result.speed[-1] > result.speed[0]


def test_load_step_example_shows_speed_drop_and_current_response():
    result = run_load_step_example()
    step_index = result.time.index(1.0)

    assert result.speed[-1] < result.speed[step_index]
    assert result.iq[-1] > result.iq[step_index]


def test_steady_state_example_reaches_torque_balance():
    verification = run_steady_state_verification_example()

    assert abs(verification.final_domega_dt) < 1.0e-5
    assert abs(verification.final_torque_error) < 1.0e-6
