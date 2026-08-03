"""Signal-chain and isolation verification for the Phase 6I FOC skeleton."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from dynamics import (
    DCBusConfig,
    DQCurrentController,
    EulerIntegrator,
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCStepInput,
    InverterVoltageLimiter,
    MotorState,
    PMSMDynamicParameters,
    StateDerivatives,
    run_foc_current_control_simulation,
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


def _runner(
    *,
    kp: float = 5.0,
    ki: float = 100.0,
    inverter_config: DCBusConfig | None = None,
    model=None,
    integrator=None,
) -> FOCRunner:
    return FOCRunner(
        controller=DQCurrentController(kp=kp, ki=ki),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=2,
            control_time_step_s=0.001,
            use_inverter_limit=inverter_config is not None,
        ),
        inverter_config=inverter_config,
        model=model,
        integrator=integrator,
    )


def _step_input(
    a: float,
    b: float,
    c: float,
    *,
    theta_m_rad: float = 0.0,
) -> FOCStepInput:
    return FOCStepInput(
        phase_current_a=a,
        phase_current_b=b,
        phase_current_c=c,
        theta_m_rad=theta_m_rad,
        omega_m_rad_s=0.0,
        load_torque_nm=0.0,
    )


def test_runner_uses_pole_pairs_to_compute_electrical_angle():
    output = _runner(kp=0.0, ki=0.0).step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=-1.0),
        step_input=_step_input(
            1.0,
            -0.5,
            -0.5,
            theta_m_rad=math.pi / 4.0,
        ),
    )

    assert output.id_measured_a == pytest.approx(0.0, abs=1.0e-12)
    assert output.iq_measured_a == pytest.approx(-1.0, abs=1.0e-12)


def test_runner_transforms_balanced_abc_current_measurement_to_dq():
    output = _runner(kp=0.0, ki=0.0).step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_step_input(
            0.0,
            math.sqrt(3.0) / 2.0,
            -math.sqrt(3.0) / 2.0,
        ),
    )

    assert output.id_measured_a == pytest.approx(0.0, abs=1.0e-12)
    assert output.iq_measured_a == pytest.approx(1.0, abs=1.0e-12)


def test_zero_current_error_produces_zero_voltage_command():
    output = _runner().step(
        reference=FOCReference(id_ref_a=1.0, iq_ref_a=0.0),
        step_input=_step_input(1.0, -0.5, -0.5),
    )

    assert output.vd_command_v == pytest.approx(0.0, abs=1.0e-12)
    assert output.vq_command_v == pytest.approx(0.0, abs=1.0e-12)


def test_positive_iq_reference_produces_positive_q_axis_voltage_command():
    output = _runner().step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_step_input(0.0, 0.0, 0.0),
    )

    assert output.vd_command_v == pytest.approx(0.0)
    assert output.vq_command_v > 0.0
    assert output.voltage_limited is False


def test_inverter_voltage_limit_is_applied_when_configured():
    dc_bus = DCBusConfig(nominal_voltage_v=24.0)
    output = _runner(kp=100.0, ki=0.0, inverter_config=dc_bus).step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_step_input(0.0, 0.0, 0.0),
    )

    voltage_limit = InverterVoltageLimiter.compute_voltage_limit(dc_bus)
    assert output.voltage_limited is True
    assert math.hypot(output.vd_actual_v, output.vq_actual_v) == pytest.approx(
        voltage_limit
    )
    assert abs(output.vq_actual_v) < abs(output.vq_command_v)
    assert output.warning_messages


class _RecordingPlant:
    def __init__(self) -> None:
        self.received_inputs = []

    def compute_derivatives(self, state, input, parameters):
        self.received_inputs.append(input)
        return StateDerivatives(
            did_dt=0.0,
            diq_dt=0.0,
            domega_dt=0.0,
            dtheta_dt=0.0,
        )

    @staticmethod
    def compute_electromagnetic_torque(state, parameters):
        return 0.0


def test_controller_inverter_and_plant_remain_separate_components():
    plant = _RecordingPlant()
    output = _runner(
        kp=100.0,
        ki=0.0,
        inverter_config=DCBusConfig(nominal_voltage_v=24.0),
        model=plant,
        integrator=EulerIntegrator(),
    ).step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_step_input(0.0, 0.0, 0.0),
    )

    assert output.vq_command_v == pytest.approx(100.0)
    assert output.vq_actual_v < output.vq_command_v
    assert len(plant.received_inputs) == 1
    assert plant.received_inputs[0].Vd == pytest.approx(output.vd_actual_v)
    assert plant.received_inputs[0].Vq == pytest.approx(output.vq_actual_v)


def test_minimal_closed_loop_simulation_runs_without_touching_production_model():
    calculations_path = Path(__file__).resolve().parents[1] / "motor_core" / "calculations.py"
    calculations_before = calculations_path.read_bytes()

    result = run_foc_current_control_simulation(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        id_ref_profile=0.0,
        iq_ref_profile=1.0,
        load_torque_profile=0.0,
        simulation_time_s=0.02,
        control_time_step_s=0.0002,
        motor_parameters=_parameters(),
        controller_kp=5.0,
        controller_ki=100.0,
        inverter_config=DCBusConfig(nominal_voltage_v=100.0),
    )

    assert all(len(series) == len(result.time) for series in result.series)
    assert result.time[-1] == pytest.approx(0.02)
    assert result.iq[-1] > 0.0
    assert result.voltage_saturation_count == 0
    assert calculations_path.read_bytes() == calculations_before


def test_minimal_simulation_reports_voltage_saturation_count():
    dc_bus = DCBusConfig(nominal_voltage_v=24.0)
    result = run_foc_current_control_simulation(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        id_ref_profile=0.0,
        iq_ref_profile=10.0,
        load_torque_profile=0.0,
        simulation_time_s=0.001,
        control_time_step_s=0.0001,
        motor_parameters=_parameters(),
        controller_kp=20.0,
        controller_ki=0.0,
        inverter_config=dc_bus,
    )

    voltage_limit = InverterVoltageLimiter.compute_voltage_limit(dc_bus)
    assert result.voltage_saturation_count > 0
    assert result.warning_messages
    max_actual_voltage = max(
        math.hypot(vd, vq)
        for vd, vq in zip(result.vd_actual, result.vq_actual)
    )
    assert max_actual_voltage <= voltage_limit + 1.0e-12
