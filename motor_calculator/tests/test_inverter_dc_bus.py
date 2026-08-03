"""Voltage-envelope and runner integration checks for Phase 6F."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    DCBusConfig,
    InverterVoltageLimiter,
    InputState,
    MotorState,
    PMSMDynamicParameters,
    RK4Integrator,
    SimulationConfig,
    SimulationRunner,
    SimulationStatus,
    UserSimulationRunner,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.01,
        B=0.002,
    )


def _initial_state() -> MotorState:
    return MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def test_voltage_below_limit_remains_unchanged():
    result = InverterVoltageLimiter.apply_limit(
        vd_command=3.0,
        vq_command=4.0,
        dc_bus_config=DCBusConfig(nominal_voltage_v=48.0),
    )

    assert result.vd_actual_v == 3.0
    assert result.vq_actual_v == 4.0
    assert result.was_limited is False
    assert result.saturation_ratio == pytest.approx(5.0 / (48.0 / math.sqrt(3.0)))
    assert result.warning_messages == ()


def test_voltage_above_limit_is_scaled_without_changing_direction():
    result = InverterVoltageLimiter.apply_limit(
        vd_command=30.0,
        vq_command=40.0,
        dc_bus_config=DCBusConfig(nominal_voltage_v=48.0),
    )

    assert result.was_limited is True
    assert math.hypot(result.vd_actual_v, result.vq_actual_v) == pytest.approx(result.voltage_limit_v)
    assert result.vq_actual_v / result.vd_actual_v == pytest.approx(40.0 / 30.0)
    assert result.saturation_ratio == pytest.approx(50.0 / result.voltage_limit_v)
    assert result.warning_messages


def test_zero_voltage_command_does_not_divide_by_zero():
    result = InverterVoltageLimiter.apply_limit(
        vd_command=0.0,
        vq_command=0.0,
        dc_bus_config=DCBusConfig(nominal_voltage_v=48.0),
    )

    assert result.vd_actual_v == 0.0
    assert result.vq_actual_v == 0.0
    assert result.saturation_ratio == 0.0
    assert result.was_limited is False


def test_voltage_limit_is_dc_bus_voltage_over_sqrt_three():
    config = DCBusConfig(nominal_voltage_v=300.0)

    assert InverterVoltageLimiter.compute_voltage_limit(config) == pytest.approx(300.0 / math.sqrt(3.0))


def test_runner_without_inverter_preserves_existing_ideal_voltage_behavior():
    runner = SimulationRunner(integrator=RK4Integrator())
    run_arguments = dict(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.5),
        simulation_time=0.02,
        time_step=0.001,
    )

    ideal_result = runner.run(**run_arguments)
    high_bus_result = runner.run(
        **run_arguments,
        inverter_config=DCBusConfig(nominal_voltage_v=1000.0),
    )

    assert ideal_result.series == high_bus_result.series
    assert ideal_result.status is SimulationStatus.SUCCESS
    assert ideal_result.inverter_limited_count == 0
    assert ideal_result.max_voltage_saturation_ratio == 0.0
    assert ideal_result.voltage_limit_warnings == ()


def test_limited_simulation_records_sample_metadata_and_warnings():
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.0),
        simulation_time=0.01,
        time_step=0.001,
        inverter_config=DCBusConfig(nominal_voltage_v=24.0),
    )

    assert result.status is SimulationStatus.WARNING
    assert result.inverter_limited_count == len(result.time)
    assert result.max_voltage_saturation_ratio == pytest.approx(math.sqrt(3.0))
    assert result.voltage_limit_warnings
    assert result.warning_messages == result.voltage_limit_warnings


def test_user_simulation_path_preserves_inverter_limit_metadata():
    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.0),
        config=SimulationConfig(simulation_time=0.01),
        inverter_config=DCBusConfig(nominal_voltage_v=24.0),
    )

    assert result.status is SimulationStatus.WARNING
    assert result.solver_used == "RK4"
    assert result.inverter_limited_count == len(result.time)
    assert result.voltage_limit_warnings
    assert all(message in result.warning_messages for message in result.voltage_limit_warnings)


def test_dc_bus_optional_fields_are_metadata_only_in_phase6f():
    base = DCBusConfig(nominal_voltage_v=48.0)
    annotated = DCBusConfig(
        nominal_voltage_v=48.0,
        current_limit_a=10.0,
        inverter_efficiency=0.95,
    )

    base_result = InverterVoltageLimiter.apply_limit(30.0, 40.0, base)
    annotated_result = InverterVoltageLimiter.apply_limit(30.0, 40.0, annotated)

    assert annotated_result == base_result
