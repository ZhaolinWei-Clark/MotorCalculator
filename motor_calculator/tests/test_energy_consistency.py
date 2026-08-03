"""Mechanical power consistency checks for the PMSM dynamics sandbox."""

from __future__ import annotations

import pytest

from dynamics import (
    InputState,
    MotorState,
    PMSMDynamicModel,
    PMSMDynamicParameters,
    RK4Integrator,
    SimulationRunner,
)


def test_mechanical_power_equals_electromagnetic_torque_times_mechanical_speed():
    parameters = PMSMDynamicParameters(
        Rs=0.3,
        Ld=0.004,
        Lq=0.006,
        psi_f=0.09,
        pole_pairs=5,
        J=0.015,
        B=0.001,
    )
    state = MotorState(id=-1.5, iq=8.0, omega_m=125.0, theta=2.0)

    torque = PMSMDynamicModel.compute_electromagnetic_torque(state, parameters)
    mechanical_power = PMSMDynamicModel.compute_mechanical_power(state, parameters)

    assert mechanical_power == pytest.approx(torque * state.omega_m)


def test_simulation_result_monitors_requested_electrical_and_mechanical_power():
    parameters = PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.01,
        B=0.002,
    )
    input_state = InputState(Vd=2.0, Vq=24.0, load_torque=0.5)
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=parameters,
        input_profile=input_state,
        simulation_time=0.02,
        time_step=0.001,
    )

    assert len(result.electrical_power) == len(result.time)
    assert len(result.mechanical_power) == len(result.time)
    for id_value, iq_value, speed, torque, electrical_power, mechanical_power in zip(
        result.id,
        result.iq,
        result.speed,
        result.torque,
        result.electrical_power,
        result.mechanical_power,
    ):
        assert electrical_power == pytest.approx(input_state.Vd * id_value + input_state.Vq * iq_value)
        assert mechanical_power == pytest.approx(torque * speed)
