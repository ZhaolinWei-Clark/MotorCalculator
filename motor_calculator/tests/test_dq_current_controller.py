"""PI and dq current-control foundation checks for Phase 6G."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    CurrentControlSimulationRunner,
    DCBusConfig,
    DQCurrentController,
    DQCurrentReference,
    InverterVoltageLimiter,
    MotorState,
    PIController,
    PMSMDynamicParameters,
    SimulationStatus,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=1.0,
        Ld=0.01,
        Lq=0.01,
        psi_f=0.001,
        pole_pairs=2,
        J=100.0,
        B=0.0,
    )


def _initial_state() -> MotorState:
    return MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def test_zero_current_error_produces_zero_voltage_correction():
    controller = DQCurrentController(kp=5.0, ki=100.0)

    command = controller.compute_voltage_command(
        id_ref=2.0,
        iq_ref=-3.0,
        id_actual=2.0,
        iq_actual=-3.0,
        dt=0.001,
    )

    assert command.vd_command_v == 0.0
    assert command.vq_command_v == 0.0
    assert controller.d_axis_controller.integral_state == 0.0
    assert controller.q_axis_controller.integral_state == 0.0


def test_step_current_reference_drives_closed_loop_current_response():
    controller = DQCurrentController(kp=5.0, ki=100.0)

    def step_reference(time_s: float) -> DQCurrentReference:
        return DQCurrentReference(
            id_ref=0.0,
            iq_ref=0.0 if time_s < 0.005 else 1.0,
            load_torque=0.0,
        )

    result = CurrentControlSimulationRunner(controller).run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        reference_profile=step_reference,
        simulation_time=0.05,
        time_step=0.0001,
        inverter_config=DCBusConfig(nominal_voltage_v=100.0),
    )

    step_index = min(range(len(result.time)), key=lambda index: abs(result.time[index] - 0.005))
    assert result.iq[step_index] == pytest.approx(0.0, abs=1.0e-12)
    assert result.iq[-1] > 0.9
    assert result.iq[-1] < 1.05
    assert result.status is SimulationStatus.SUCCESS


def test_pi_integral_accumulates_once_per_compute_call():
    controller = PIController(kp=0.0, ki=2.0)

    first_output = controller.compute(error=3.0, dt=0.1)
    second_output = controller.compute(error=3.0, dt=0.1)

    assert controller.integral_state == pytest.approx(0.6)
    assert first_output == pytest.approx(0.6)
    assert second_output == pytest.approx(1.2)


def test_dq_controller_reset_clears_both_integral_states():
    controller = DQCurrentController(kp=1.0, ki=2.0)
    controller.compute_voltage_command(1.0, -2.0, 0.0, 0.0, 0.1)

    controller.reset()

    assert controller.d_axis_controller.integral_state == 0.0
    assert controller.q_axis_controller.integral_state == 0.0


def test_controller_output_is_compatible_with_inverter_saturation():
    controller = DQCurrentController(kp=50.0, ki=10.0)
    command = controller.compute_voltage_command(1.0, 1.0, 0.0, 0.0, 0.01)
    before_tracking = (
        controller.d_axis_controller.integral_state,
        controller.q_axis_controller.integral_state,
    )

    limited = InverterVoltageLimiter.apply_limit(
        command.vd_command_v,
        command.vq_command_v,
        DCBusConfig(nominal_voltage_v=24.0),
    )
    controller.track_applied_voltage(
        command,
        limited.vd_actual_v,
        limited.vq_actual_v,
        dt=0.01,
    )

    assert limited.was_limited is True
    assert math.hypot(limited.vd_actual_v, limited.vq_actual_v) == pytest.approx(
        limited.voltage_limit_v
    )
    assert limited.vd_actual_v / limited.vq_actual_v == pytest.approx(1.0)
    assert controller.d_axis_controller.anti_windup_enabled is False
    assert controller.q_axis_controller.anti_windup_enabled is False
    assert before_tracking == (
        controller.d_axis_controller.integral_state,
        controller.q_axis_controller.integral_state,
    )


def test_current_control_runner_records_inverter_saturation_metadata():
    result = CurrentControlSimulationRunner(
        DQCurrentController(kp=20.0, ki=0.0)
    ).run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        reference_profile=DQCurrentReference(id_ref=0.0, iq_ref=10.0, load_torque=0.0),
        simulation_time=0.001,
        time_step=0.0001,
        inverter_config=DCBusConfig(nominal_voltage_v=24.0),
    )

    assert result.status is SimulationStatus.WARNING
    assert result.inverter_limited_count == len(result.time) - 1
    assert result.max_voltage_saturation_ratio > 1.0
    assert result.voltage_limit_warnings
    assert all(math.isfinite(value) for value in result.iq)
