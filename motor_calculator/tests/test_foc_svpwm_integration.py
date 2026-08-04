"""Integration checks for the optional average-SVPWM voltage path."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from dynamics import (
    CurrentSensorConfig,
    DCBusConfig,
    DQCurrentController,
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCStepInput,
    FieldWeakeningController,
    MTPAController,
    MotorState,
    PMSMDynamicParameters,
    SVPWMConfig,
    SensorSuite,
    SensorSuiteConfig,
    SpeedControlRunnerConfig,
    SpeedControlSimulationRunner,
    SpeedController,
    SpeedControllerConfig,
    StateDerivatives,
    VoltageApplicationMode,
    run_foc_current_control_simulation,
    run_direct_modulation_examples,
    run_speed_mode_comparison,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.007,
        psi_f=0.1,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )


def _step_input(speed_rad_s: float = 0.0) -> FOCStepInput:
    return FOCStepInput(0.0, 0.0, 0.0, 0.1, speed_rad_s, 0.0)


def test_default_mode_and_explicit_simple_mode_are_identical():
    kwargs = dict(
        initial_state=MotorState(0.0, 0.0, 0.0, 0.0),
        id_ref_profile=0.0,
        iq_ref_profile=2.0,
        load_torque_profile=0.0,
        simulation_time_s=0.002,
        control_time_step_s=0.0001,
        motor_parameters=_parameters(),
        controller_kp=2.0,
        controller_ki=50.0,
        inverter_config=DCBusConfig(48.0),
    )

    default_result = run_foc_current_control_simulation(**kwargs)
    explicit_result = run_foc_current_control_simulation(
        **kwargs,
        voltage_application_mode=VoltageApplicationMode.SIMPLE_DQ_LIMIT,
    )

    assert explicit_result == default_result
    assert default_result.minimum_duty is None


def test_foc_step_exposes_svpwm_duties_and_reconstructed_voltage():
    runner = FOCRunner(
        controller=DQCurrentController(kp=4.0, ki=0.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.0001,
            use_inverter_limit=True,
            voltage_application_mode=VoltageApplicationMode.SVPWM_AVERAGE,
        ),
        inverter_config=DCBusConfig(48.0),
        svpwm_config=SVPWMConfig(True, 48.0),
    )

    output = runner.step(FOCReference(0.0, 2.0), _step_input())

    assert output.svpwm_result is not None
    assert output.svpwm_result.duties != (0.5, 0.5, 0.5)
    assert output.vd_actual_v == pytest.approx(output.svpwm_result.vd_actual_v)
    assert output.vq_actual_v == pytest.approx(output.svpwm_result.vq_actual_v)


class _RecordingController(DQCurrentController):
    def __init__(self) -> None:
        super().__init__(kp=100.0, ki=0.0, anti_windup_gain=2.0)
        self.feedback = None

    def track_applied_voltage(self, command, vd_actual_v, vq_actual_v, dt):
        self.feedback = super().track_applied_voltage(
            command, vd_actual_v, vq_actual_v, dt
        )
        return self.feedback


class _RecordingPlant:
    def __init__(self) -> None:
        self.inputs = []

    def compute_derivatives(self, state, input, parameters):
        self.inputs.append(input)
        return StateDerivatives(0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def compute_electromagnetic_torque(state, parameters):
        return 0.0


def test_svpwm_saturation_feedback_and_actual_voltage_reach_separate_layers():
    controller = _RecordingController()
    plant = _RecordingPlant()
    runner = FOCRunner(
        controller=controller,
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.001,
            use_inverter_limit=True,
            voltage_application_mode=VoltageApplicationMode.SVPWM_AVERAGE,
        ),
        inverter_config=DCBusConfig(24.0),
        svpwm_config=SVPWMConfig(True, 24.0),
        model=plant,
    )

    output = runner.step(FOCReference(0.0, 2.0), _step_input())

    assert output.voltage_limited is True
    assert controller.feedback.saturation_active is True
    assert plant.inputs
    assert plant.inputs[0].Vd == pytest.approx(output.vd_actual_v)
    assert plant.inputs[0].Vq == pytest.approx(output.vq_actual_v)


def test_svpwm_is_compatible_with_mtpa_field_weakening_and_sensor_layer():
    parameters = _parameters()
    dc_bus = DCBusConfig(48.0, current_limit_a=20.0)
    suite = SensorSuite(
        SensorSuiteConfig(
            phase_current_a_sensor=CurrentSensorConfig(offset_a=0.01, enabled=True)
        )
    )
    runner = FOCRunner(
        controller=DQCurrentController(kp=2.0, ki=20.0),
        motor_parameters=parameters,
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.0001,
            use_inverter_limit=True,
            enable_mtpa=True,
            enable_field_weakening=True,
            enable_sensor_nonidealities=True,
            voltage_application_mode=VoltageApplicationMode.SVPWM_AVERAGE,
        ),
        inverter_config=dc_bus,
        mtpa_controller=MTPAController(20.0),
        field_weakening_controller=FieldWeakeningController(20.0),
        sensor_suite=suite,
        svpwm_config=SVPWMConfig(True, 48.0),
    )

    output = runner.step(
        FOCReference(0.0, 0.0, torque_reference_nm=3.0),
        _step_input(speed_rad_s=200.0),
    )

    assert output.svpwm_result is not None
    assert output.sensor_measurements is not None
    assert output.mtpa_method is not None
    assert output.field_weakening_active is True
    assert all(
        math.isfinite(value)
        for value in (output.vd_actual_v, output.vq_actual_v, output.torque_nm)
    )


def test_speed_runner_operates_stably_with_average_svpwm():
    parameters = _parameters()
    runner = SpeedControlSimulationRunner(
        speed_controller=SpeedController(
            SpeedControllerConfig(0.4, 0.4, -5.0, 5.0, 5.0)
        ),
        current_controller=DQCurrentController(2.0, 200.0, 5.0),
        motor_parameters=parameters,
        config=SpeedControlRunnerConfig(
            use_decoupling_feedforward=True,
            voltage_application_mode=VoltageApplicationMode.SVPWM_AVERAGE,
        ),
        inverter_config=DCBusConfig(48.0),
        svpwm_config=SVPWMConfig(True, 48.0),
    )

    result = runner.run(MotorState(0.0, 0.0, 0.0, 0.0), 30.0, 0.2, 0.2)

    assert all(math.isfinite(value) for series in result.numeric_series for value in series)
    assert result.maximum_modulation_index > 0.0
    assert 0.0 <= result.minimum_duty <= result.maximum_duty <= 1.0


def test_svpwm_simulation_does_not_modify_production_calculator():
    calculations = Path(__file__).resolve().parents[1] / "motor_core" / "calculations.py"
    before = calculations.read_bytes()

    result = run_foc_current_control_simulation(
        MotorState(0.0, 0.0, 0.0, 0.0),
        0.0,
        2.0,
        0.0,
        0.001,
        0.0001,
        _parameters(),
        2.0,
        50.0,
        DCBusConfig(48.0),
        voltage_application_mode=VoltageApplicationMode.SVPWM_AVERAGE,
        svpwm_config=SVPWMConfig(True, 48.0),
    )

    assert result.maximum_modulation_index > 0.0
    assert calculations.read_bytes() == before


def test_required_direct_modulation_examples_cover_low_near_and_overcommand():
    low, near_limit, over_command = run_direct_modulation_examples()

    assert low.result.voltage_saturated is False
    assert low.dq_round_trip_error_v < 1.0e-12
    assert near_limit.result.modulation_index == pytest.approx(0.98)
    assert near_limit.result.voltage_saturated is False
    assert over_command.result.modulation_index == pytest.approx(1.5)
    assert over_command.result.voltage_saturated is True
    assert all(math.isfinite(value) for value in over_command.result.duties)


def test_required_speed_mode_comparison_returns_finite_tracking_metrics():
    comparison = run_speed_mode_comparison()

    assert comparison.simple_dq_limit.minimum_modulation_index is None
    assert comparison.svpwm_average.minimum_modulation_index is not None
    assert comparison.svpwm_average.maximum_modulation_index > 0.0
    assert all(
        math.isfinite(value)
        for metrics in (comparison.simple_dq_limit, comparison.svpwm_average)
        for value in (
            metrics.final_speed_rad_s,
            metrics.rms_speed_tracking_error_rad_s,
            metrics.rms_iq_tracking_error_a,
        )
    )
