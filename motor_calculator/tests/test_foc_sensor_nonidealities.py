"""FOC integration checks for measurement-only sensor non-idealities."""

from __future__ import annotations

import math
import random

import pytest

from dynamics import (
    ABCPhaseValues,
    CurrentSensorConfig,
    DQCurrentController,
    DQValues,
    EulerIntegrator,
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCStepInput,
    PMSMDynamicParameters,
    PositionSensorConfig,
    SensorSuite,
    SensorSuiteConfig,
    SpeedSensorConfig,
    StateDerivatives,
    inverse_clarke_transform,
    inverse_park_transform,
    run_current_sensor_error_experiments,
    run_rotor_angle_error_experiments,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )


def _abc_from_dq(id_a: float, iq_a: float, theta_m_rad: float = 0.0) -> ABCPhaseValues:
    alpha_beta = inverse_park_transform(
        DQValues(d=id_a, q=iq_a),
        _parameters().pole_pairs * theta_m_rad,
    )
    return inverse_clarke_transform(alpha_beta)


def _step_input(
    *,
    id_a: float = 0.0,
    iq_a: float = 1.0,
    theta_m_rad: float = 0.0,
    speed_rad_s: float = 10.0,
) -> FOCStepInput:
    abc = _abc_from_dq(id_a, iq_a, theta_m_rad)
    return FOCStepInput(
        phase_current_a=abc.a,
        phase_current_b=abc.b,
        phase_current_c=abc.c,
        theta_m_rad=theta_m_rad,
        omega_m_rad_s=speed_rad_s,
        load_torque_nm=0.0,
    )


def _runner(
    *,
    sensor_suite: SensorSuite | None = None,
    enable_sensors: bool = False,
    model=None,
) -> FOCRunner:
    return FOCRunner(
        controller=DQCurrentController(kp=0.0, ki=0.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.0001,
            use_inverter_limit=False,
            enable_sensor_nonidealities=enable_sensors,
        ),
        model=model,
        integrator=EulerIntegrator(),
        sensor_suite=sensor_suite,
    )


def test_disabled_sensor_suite_preserves_exact_existing_foc_output():
    reference = FOCReference(id_ref_a=0.0, iq_ref_a=1.0)
    step_input = _step_input()
    ideal = _runner().step(reference, step_input)
    explicitly_disabled = _runner(
        sensor_suite=SensorSuite(SensorSuiteConfig()),
        enable_sensors=True,
    ).step(reference, step_input)

    assert explicitly_disabled == ideal
    assert ideal.sensor_measurements is None


class _RecordingPlant:
    def __init__(self) -> None:
        self.received_states = []

    def compute_derivatives(self, state, input, parameters):
        self.received_states.append(state)
        return StateDerivatives(0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def compute_electromagnetic_torque(state, parameters):
        return 1.5 * parameters.pole_pairs * parameters.psi_f * state.iq


def test_foc_uses_measured_feedback_while_plant_keeps_true_state():
    plant = _RecordingPlant()
    suite = SensorSuite(
        SensorSuiteConfig(
            phase_current_a_sensor=CurrentSensorConfig(offset_a=0.5, enabled=True),
            position_sensor=PositionSensorConfig(
                mechanical_offset_rad=math.radians(5.0) / 4.0,
                enabled=True,
            ),
            speed_sensor=SpeedSensorConfig(offset_rad_s=2.0, enabled=True),
        )
    )
    output = _runner(
        sensor_suite=suite,
        enable_sensors=True,
        model=plant,
    ).step(
        FOCReference(id_ref_a=0.0, iq_ref_a=2.0),
        _step_input(id_a=0.0, iq_a=2.0, speed_rad_s=10.0),
    )

    assert output.sensor_measurements is not None
    assert output.id_measured_a != pytest.approx(output.id_true_a)
    assert output.omega_m_measured_rad_s == pytest.approx(12.0)
    assert len(plant.received_states) == 1
    assert plant.received_states[0].id == pytest.approx(0.0, abs=1.0e-12)
    assert plant.received_states[0].iq == pytest.approx(2.0, abs=1.0e-12)
    assert plant.received_states[0].omega_m == pytest.approx(10.0)


def test_increasing_electrical_angle_error_degrades_dq_alignment():
    measured_d = []
    measured_q = []
    for electrical_error_deg in (0.0, 1.0, 5.0, 10.0):
        suite = SensorSuite(
            SensorSuiteConfig(
                position_sensor=PositionSensorConfig(
                    mechanical_offset_rad=math.radians(electrical_error_deg) / 4.0,
                    enabled=electrical_error_deg != 0.0,
                )
            )
        )
        output = _runner(
            sensor_suite=suite,
            enable_sensors=True,
        ).step(
            FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
            _step_input(id_a=0.0, iq_a=1.0),
        )
        measured_d.append(abs(output.id_measured_a))
        measured_q.append(output.iq_measured_a)

    assert measured_d == sorted(measured_d)
    assert measured_q == sorted(measured_q, reverse=True)
    assert measured_d[-1] == pytest.approx(math.sin(math.radians(10.0)))
    assert measured_q[-1] == pytest.approx(math.cos(math.radians(10.0)))


def test_seeded_sensor_suite_produces_repeatable_foc_feedback():
    config = SensorSuiteConfig(
        phase_current_a_sensor=CurrentSensorConfig(noise_std_a=0.02, enabled=True),
        phase_current_b_sensor=CurrentSensorConfig(noise_std_a=0.02, enabled=True),
        phase_current_c_sensor=CurrentSensorConfig(noise_std_a=0.02, enabled=True),
    )
    first = _runner(
        sensor_suite=SensorSuite(config, random.Random(99)),
        enable_sensors=True,
    ).step(FOCReference(0.0, 1.0), _step_input())
    second = _runner(
        sensor_suite=SensorSuite(config, random.Random(99)),
        enable_sensors=True,
    ).step(FOCReference(0.0, 1.0), _step_input())

    assert first == second


def test_required_rotor_angle_experiment_cases_run_with_finite_metrics():
    results = run_rotor_angle_error_experiments()

    assert tuple(result.electrical_angle_error_deg for result in results) == (
        0.0,
        1.0,
        5.0,
        10.0,
    )
    assert all(
        math.isfinite(value)
        for result in results
        for value in (
            result.final_speed_rad_s,
            result.mean_true_id_a,
            result.mean_true_iq_a,
            result.mean_measured_id_a,
            result.mean_measured_iq_a,
            result.mean_torque_nm,
            result.torque_variation_proxy_nm,
        )
    )


def test_required_current_sensor_experiment_cases_run_with_finite_metrics():
    results = run_current_sensor_error_experiments()

    assert tuple(result.case_name for result in results) == (
        "ideal",
        "phase_a_offset_0.2_a",
        "all_phase_gain_plus_2_percent",
        "10_bit_20_a_full_scale",
        "gaussian_noise_0.02_a",
    )
    assert all(
        math.isfinite(result.torque_variation_proxy_nm) for result in results
    )
