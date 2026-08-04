"""Repeatable Phase 6M angle and current-sensor sandbox experiments."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
import statistics

from .controllers import DQCurrentController, SpeedController, SpeedControllerConfig
from .inverter import DCBusConfig
from .pmsm_model import PMSMDynamicParameters
from .sensors import (
    CurrentSensorConfig,
    PositionSensorConfig,
    SensorSuite,
    SensorSuiteConfig,
)
from .speed_control_runner import (
    SpeedControlRunnerConfig,
    SpeedControlSimulationResult,
    SpeedControlSimulationRunner,
)
from .state import MotorState


@dataclass(frozen=True)
class RotorAngleErrorExperimentResult:
    electrical_angle_error_deg: float
    final_speed_rad_s: float
    speed_tracking_error_rad_s: float
    mean_true_id_a: float
    mean_true_iq_a: float
    mean_measured_id_a: float
    mean_measured_iq_a: float
    mean_torque_nm: float
    torque_variation_proxy_nm: float
    peak_current_demand_a: float


@dataclass(frozen=True)
class CurrentSensorErrorExperimentResult:
    case_name: str
    final_speed_rad_s: float
    speed_tracking_error_rad_s: float
    id_tracking_error_rms_a: float
    iq_tracking_error_rms_a: float
    voltage_command_variation_v: float
    torque_variation_proxy_nm: float


def run_rotor_angle_error_experiments() -> tuple[RotorAngleErrorExperimentResult, ...]:
    """Run 0, 1, 5, and 10 electrical-degree offset cases."""

    results = []
    for electrical_error_deg in (0.0, 1.0, 5.0, 10.0):
        config = SensorSuiteConfig(
            position_sensor=PositionSensorConfig(
                mechanical_offset_rad=(
                    math.radians(electrical_error_deg) / _parameters().pole_pairs
                ),
                enabled=electrical_error_deg != 0.0,
            )
        )
        simulation = _run_speed_case(config)
        tail = _tail_slice(simulation.time)
        results.append(
            RotorAngleErrorExperimentResult(
                electrical_angle_error_deg=electrical_error_deg,
                final_speed_rad_s=simulation.speed[-1],
                speed_tracking_error_rad_s=30.0 - simulation.speed[-1],
                mean_true_id_a=statistics.fmean(simulation.id[tail]),
                mean_true_iq_a=statistics.fmean(simulation.iq[tail]),
                mean_measured_id_a=statistics.fmean(simulation.id_measured[tail]),
                mean_measured_iq_a=statistics.fmean(simulation.iq_measured[tail]),
                mean_torque_nm=statistics.fmean(simulation.torque[tail]),
                torque_variation_proxy_nm=statistics.pstdev(simulation.torque[tail]),
                peak_current_demand_a=max(
                    math.hypot(id_ref, iq_ref)
                    for id_ref, iq_ref in zip(simulation.id_ref, simulation.iq_ref)
                ),
            )
        )
    return tuple(results)


def run_current_sensor_error_experiments() -> tuple[CurrentSensorErrorExperimentResult, ...]:
    """Run ideal, offset, gain, quantization, and seeded-noise cases."""

    ideal = SensorSuiteConfig()
    offset = SensorSuiteConfig(
        phase_current_a_sensor=CurrentSensorConfig(offset_a=0.2, enabled=True)
    )
    gain_config = CurrentSensorConfig(gain_error_fraction=0.02, enabled=True)
    gain = SensorSuiteConfig(
        phase_current_a_sensor=gain_config,
        phase_current_b_sensor=gain_config,
        phase_current_c_sensor=gain_config,
    )
    quantization_config = CurrentSensorConfig(
        resolution_bits=10,
        full_scale_a=20.0,
        enabled=True,
    )
    quantization = SensorSuiteConfig(
        phase_current_a_sensor=quantization_config,
        phase_current_b_sensor=quantization_config,
        phase_current_c_sensor=quantization_config,
    )
    noise_config = CurrentSensorConfig(noise_std_a=0.02, enabled=True)
    noise = SensorSuiteConfig(
        phase_current_a_sensor=noise_config,
        phase_current_b_sensor=noise_config,
        phase_current_c_sensor=noise_config,
    )

    results = []
    for case_name, config, seed in (
        ("ideal", ideal, None),
        ("phase_a_offset_0.2_a", offset, None),
        ("all_phase_gain_plus_2_percent", gain, None),
        ("10_bit_20_a_full_scale", quantization, None),
        ("gaussian_noise_0.02_a", noise, 20260804),
    ):
        simulation = _run_speed_case(config, seed=seed)
        tail = _tail_slice(simulation.time)
        voltage_magnitudes = tuple(
            math.hypot(vd, vq)
            for vd, vq in zip(
                simulation.vd_command[tail],
                simulation.vq_command[tail],
            )
        )
        results.append(
            CurrentSensorErrorExperimentResult(
                case_name=case_name,
                final_speed_rad_s=simulation.speed[-1],
                speed_tracking_error_rad_s=30.0 - simulation.speed[-1],
                id_tracking_error_rms_a=_rms_tracking_error(
                    simulation.id_ref[tail],
                    simulation.id_measured[tail],
                ),
                iq_tracking_error_rms_a=_rms_tracking_error(
                    simulation.iq_ref[tail],
                    simulation.iq_measured[tail],
                ),
                voltage_command_variation_v=statistics.pstdev(voltage_magnitudes),
                torque_variation_proxy_nm=statistics.pstdev(simulation.torque[tail]),
            )
        )
    return tuple(results)


def _run_speed_case(
    sensor_config: SensorSuiteConfig,
    *,
    seed: int | None = None,
) -> SpeedControlSimulationResult:
    parameters = _parameters()
    sensor_suite = SensorSuite(
        sensor_config,
        random.Random(seed) if seed is not None else None,
    )
    runner = SpeedControlSimulationRunner(
        speed_controller=SpeedController(
            SpeedControllerConfig(
                kp=0.4,
                ki=0.4,
                iq_min_a=-5.0,
                iq_max_a=5.0,
                anti_windup_gain=5.0,
            )
        ),
        current_controller=DQCurrentController(
            kp=2.0,
            ki=200.0,
            anti_windup_gain=5.0,
        ),
        motor_parameters=parameters,
        config=SpeedControlRunnerConfig(
            use_decoupling_feedforward=True,
            enable_sensor_nonidealities=sensor_config.enabled,
        ),
        inverter_config=DCBusConfig(nominal_voltage_v=48.0),
        sensor_suite=sensor_suite if sensor_config.enabled else None,
    )
    return runner.run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        speed_reference_profile=30.0,
        load_torque_profile=0.5,
        simulation_time_s=1.2,
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


def _tail_slice(values: tuple[float, ...]) -> slice:
    return slice(max(0, int(len(values) * 0.75)), None)


def _rms_tracking_error(
    reference: tuple[float, ...],
    measured: tuple[float, ...],
) -> float:
    return math.sqrt(
        statistics.fmean(
            (reference_value - measured_value) ** 2
            for reference_value, measured_value in zip(reference, measured)
        )
    )
