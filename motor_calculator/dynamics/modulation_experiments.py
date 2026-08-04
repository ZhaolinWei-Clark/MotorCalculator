"""Repeatable Phase 6N examples for average-modulation reporting."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .controllers import DQCurrentController, SpeedController, SpeedControllerConfig
from .inverter import DCBusConfig
from .modulation import (
    SVPWMConfig,
    SVPWMModulator,
    SVPWMResult,
    VoltageApplicationMode,
)
from .pmsm_model import PMSMDynamicParameters
from .speed_control_runner import (
    SpeedControlRunnerConfig,
    SpeedControlSimulationRunner,
)
from .state import MotorState


@dataclass(frozen=True)
class ModulationExampleResult:
    """One direct dq modulation case and its round-trip error."""

    case_name: str
    vd_command_v: float
    vq_command_v: float
    theta_e_rad: float
    result: SVPWMResult
    dq_round_trip_error_v: float


@dataclass(frozen=True)
class SpeedModeMetrics:
    """Compact metrics for one speed-control voltage application mode."""

    mode: VoltageApplicationMode
    final_speed_rad_s: float
    rms_speed_tracking_error_rad_s: float
    rms_iq_tracking_error_a: float
    voltage_saturation_count: int
    minimum_modulation_index: float | None
    maximum_modulation_index: float | None


@dataclass(frozen=True)
class SpeedModeComparison:
    """Case D comparison using identical plant and controller settings."""

    simple_dq_limit: SpeedModeMetrics
    svpwm_average: SpeedModeMetrics


def run_direct_modulation_examples() -> tuple[ModulationExampleResult, ...]:
    """Run required Cases A-C at a fixed 48 V DC bus."""

    config = SVPWMConfig(enabled=True, dc_bus_voltage_v=48.0)
    limit = config.linear_voltage_limit_v
    cases = (
        ("A_low_modulation", 5.0, 8.0, 0.7),
        ("B_near_voltage_limit", 0.98 * limit, 0.0, math.radians(20.0)),
        ("C_over_command", 1.5 * limit, 0.0, math.radians(20.0)),
    )
    modulator = SVPWMModulator()
    outputs = []
    for name, vd_command, vq_command, theta_e in cases:
        result = modulator.modulate_dq(
            vd_command,
            vq_command,
            theta_e,
            config,
        )
        outputs.append(
            ModulationExampleResult(
                case_name=name,
                vd_command_v=vd_command,
                vq_command_v=vq_command,
                theta_e_rad=theta_e,
                result=result,
                dq_round_trip_error_v=math.hypot(
                    result.vd_actual_v - vd_command,
                    result.vq_actual_v - vq_command,
                ),
            )
        )
    return tuple(outputs)


def run_speed_mode_comparison() -> SpeedModeComparison:
    """Run Case D with identical settings in simple and average-SVPWM modes."""

    simple_result = _build_speed_runner(
        VoltageApplicationMode.SIMPLE_DQ_LIMIT
    ).run(
        initial_state=MotorState(0.0, 0.0, 0.0, 0.0),
        speed_reference_profile=30.0,
        load_torque_profile=0.2,
        simulation_time_s=0.75,
    )
    svpwm_result = _build_speed_runner(VoltageApplicationMode.SVPWM_AVERAGE).run(
        initial_state=MotorState(0.0, 0.0, 0.0, 0.0),
        speed_reference_profile=30.0,
        load_torque_profile=0.2,
        simulation_time_s=0.75,
    )
    return SpeedModeComparison(
        simple_dq_limit=_speed_metrics(
            VoltageApplicationMode.SIMPLE_DQ_LIMIT, simple_result
        ),
        svpwm_average=_speed_metrics(
            VoltageApplicationMode.SVPWM_AVERAGE, svpwm_result
        ),
    )


def _build_speed_runner(mode: VoltageApplicationMode) -> SpeedControlSimulationRunner:
    parameters = PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )
    return SpeedControlSimulationRunner(
        speed_controller=SpeedController(
            SpeedControllerConfig(0.4, 0.4, -5.0, 5.0, 5.0)
        ),
        current_controller=DQCurrentController(2.0, 200.0, 5.0),
        motor_parameters=parameters,
        config=SpeedControlRunnerConfig(
            use_decoupling_feedforward=True,
            voltage_application_mode=mode,
        ),
        inverter_config=DCBusConfig(48.0),
        svpwm_config=(
            SVPWMConfig(enabled=True, dc_bus_voltage_v=48.0)
            if mode is VoltageApplicationMode.SVPWM_AVERAGE
            else None
        ),
    )


def _speed_metrics(mode, result) -> SpeedModeMetrics:
    sample_count = len(result.time)
    rms_speed_error = math.sqrt(
        sum(
            (reference - actual) ** 2
            for reference, actual in zip(result.speed_reference, result.speed)
        )
        / sample_count
    )
    rms_iq_error = math.sqrt(
        sum(
            (reference - actual) ** 2
            for reference, actual in zip(result.iq_ref, result.iq)
        )
        / sample_count
    )
    return SpeedModeMetrics(
        mode=mode,
        final_speed_rad_s=result.speed[-1],
        rms_speed_tracking_error_rad_s=rms_speed_error,
        rms_iq_tracking_error_a=rms_iq_error,
        voltage_saturation_count=result.voltage_saturation_count,
        minimum_modulation_index=result.minimum_modulation_index,
        maximum_modulation_index=(
            result.maximum_modulation_index
            if result.minimum_modulation_index is not None
            else None
        ),
    )
