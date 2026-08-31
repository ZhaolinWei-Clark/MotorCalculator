"""Sandbox-only orchestration for explicitly requested GUI analyses."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Mapping

from motor_calculator.calibration_sandbox import SensitivitySummary, run_sensitivity_sweep
from motor_calculator.dynamics import (
    DCBusConfig,
    DQCurrentController,
    EulerIntegrator,
    MotorState,
    PMSMDynamicParameters,
    RK4Integrator,
    SimulationAccuracy,
    SpeedControlRunnerConfig,
    SpeedControlSimulationResult,
    SpeedControlSimulationRunner,
    SpeedController,
    SpeedControllerConfig,
)
from motor_calculator.motor_core import MotorAnalysisEngine
from motor_calculator.motor_core.electrical_semantics import MotorControlMode
from motor_calculator.motor_core.models import AnalysisResult, MotorAnalysisInput
from motor_calculator.motor_core.units import legacy_params_to_model_input
from motor_calculator.validation.phase7i_uncertainty_report import (
    Phase7IUncertaintyDemonstration,
    run_phase7i_demonstration,
)
from motor_calculator.validation.uncertainty_models import UncertaintySpecification


class AnalysisUnavailableError(ValueError):
    """Raised when an existing sandbox cannot represent the current request."""


@dataclass(frozen=True)
class DynamicAnalysisSettings:
    """Visible sandbox settings; plant timesteps remain accuracy-preset details."""

    simulation_time_s: float = 0.5
    accuracy_level: SimulationAccuracy = SimulationAccuracy.BALANCED
    speed_reference_rpm: float = 1000.0
    load_torque_nm: float = 0.2
    initial_speed_rpm: float = 0.0
    inertia_kg_m2: float = 0.02
    viscous_friction_nm_per_rad_s: float = 0.001
    speed_kp: float = 0.2
    speed_ki: float = 1.0
    current_kp: float = 2.0
    current_ki: float = 200.0

    def __post_init__(self) -> None:
        finite = (
            self.simulation_time_s,
            self.speed_reference_rpm,
            self.load_torque_nm,
            self.initial_speed_rpm,
            self.inertia_kg_m2,
            self.viscous_friction_nm_per_rad_s,
            self.speed_kp,
            self.speed_ki,
            self.current_kp,
            self.current_ki,
        )
        if any(not math.isfinite(value) for value in finite):
            raise ValueError("dynamic analysis settings must be finite")
        if self.simulation_time_s <= 0.0 or self.inertia_kg_m2 <= 0.0:
            raise ValueError("simulation time and inertia must be greater than zero")
        if self.viscous_friction_nm_per_rad_s < 0.0:
            raise ValueError("viscous friction must be non-negative")
        if min(self.speed_kp, self.speed_ki, self.current_kp, self.current_ki) < 0.0:
            raise ValueError("controller gains must be non-negative")


@dataclass(frozen=True)
class DynamicAnalysisOutcome:
    result: SpeedControlSimulationResult
    elapsed_seconds: float
    mapping_notes: tuple[str, ...]
    accuracy_level: SimulationAccuracy


@dataclass(frozen=True)
class UncertaintyAnalysisSettings:
    sample_count: int = 500
    random_seed: int = 20260701

    def __post_init__(self) -> None:
        if isinstance(self.sample_count, bool) or not 10 <= self.sample_count <= 50_000:
            raise ValueError("sample_count must be an integer from 10 to 50000")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise ValueError("random_seed must be an integer")


def _coerce_model_input(inputs: MotorAnalysisInput | Mapping[str, object]) -> MotorAnalysisInput:
    if isinstance(inputs, MotorAnalysisInput):
        return inputs
    return legacy_params_to_model_input(inputs)


def dynamic_analysis_availability(
    inputs: MotorAnalysisInput | Mapping[str, object],
    analysis_result: AnalysisResult | None,
) -> tuple[bool, str]:
    model_input = _coerce_model_input(inputs)
    if model_input.control_mode is not MotorControlMode.PMSM_SINUSOIDAL:
        return False, "当前动态 GUI 仅支持 PMSM；BLDC 动态模型尚未实现。"
    if analysis_result is None:
        return False, "请先完成一次当前项目静态计算，以取得显式 R、L 与 Kt 映射。"
    electrical = analysis_result.electrical
    if electrical.phase_inductance_h <= 0.0 or electrical.phase_resistance_ohm < 0.0:
        return False, "当前静态结果没有可用的正相电感或非负相电阻。"
    if electrical.torque_constant_nm_per_phase_peak_a is None:
        return False, "当前结果没有 PMSM 相峰值电流口径的 Kt，无法安全映射磁链。"
    return True, "可用：PMSM 沙盒将显式映射当前 R、标量 L 与 Kt；不会写回生产模型。"


def _runner_settings(accuracy: SimulationAccuracy) -> tuple[SpeedControlRunnerConfig, object]:
    if accuracy is SimulationAccuracy.FAST:
        return (
            SpeedControlRunnerConfig(
                plant_time_step_s=5.0e-4,
                current_control_period_s=1.0e-3,
                speed_control_period_s=1.0e-2,
                use_decoupling_feedforward=True,
            ),
            EulerIntegrator(),
        )
    if accuracy is SimulationAccuracy.HIGH_ACCURACY:
        return (
            SpeedControlRunnerConfig(
                plant_time_step_s=5.0e-5,
                current_control_period_s=2.5e-4,
                speed_control_period_s=2.5e-3,
                use_decoupling_feedforward=True,
            ),
            RK4Integrator(),
        )
    return SpeedControlRunnerConfig(use_decoupling_feedforward=True), RK4Integrator()


def run_dynamic_analysis(
    inputs: MotorAnalysisInput | Mapping[str, object],
    analysis_result: AnalysisResult,
    settings: DynamicAnalysisSettings,
) -> DynamicAnalysisOutcome:
    """Run the existing PMSM speed/current sandbox from explicit GUI settings."""

    model_input = _coerce_model_input(inputs)
    available, reason = dynamic_analysis_availability(model_input, analysis_result)
    if not available:
        raise AnalysisUnavailableError(reason)

    peak_current = analysis_result.performance.phase_current_peak_a
    if peak_current is None or peak_current <= 0.0:
        raise AnalysisUnavailableError("当前结果没有可用的 PMSM 相峰值电流限制。")
    torque_constant = analysis_result.electrical.torque_constant_nm_per_phase_peak_a
    assert torque_constant is not None
    flux_linkage = torque_constant / (1.5 * model_input.pole_pairs)
    scalar_inductance = analysis_result.electrical.phase_inductance_h
    parameters = PMSMDynamicParameters(
        Rs=analysis_result.electrical.phase_resistance_ohm,
        Ld=scalar_inductance,
        Lq=scalar_inductance,
        psi_f=flux_linkage,
        pole_pairs=model_input.pole_pairs,
        J=settings.inertia_kg_m2,
        B=settings.viscous_friction_nm_per_rad_s,
    )
    speed_controller = SpeedController(
        SpeedControllerConfig(
            kp=settings.speed_kp,
            ki=settings.speed_ki,
            iq_min_a=-peak_current,
            iq_max_a=peak_current,
            anti_windup_gain=5.0,
        )
    )
    current_controller = DQCurrentController(
        kp=settings.current_kp,
        ki=settings.current_ki,
        anti_windup_gain=5.0,
    )
    runner_config, integrator = _runner_settings(settings.accuracy_level)
    runner = SpeedControlSimulationRunner(
        speed_controller=speed_controller,
        current_controller=current_controller,
        motor_parameters=parameters,
        config=runner_config,
        inverter_config=DCBusConfig(model_input.dc_bus_voltage_v),
        integrator=integrator,
    )
    initial_state = MotorState(
        id=0.0,
        iq=0.0,
        omega_m=settings.initial_speed_rpm * 2.0 * math.pi / 60.0,
        theta=0.0,
    )
    started = time.perf_counter()
    result = runner.run(
        initial_state=initial_state,
        speed_reference_profile=settings.speed_reference_rpm * 2.0 * math.pi / 60.0,
        load_torque_profile=settings.load_torque_nm,
        simulation_time_s=settings.simulation_time_s,
    )
    return DynamicAnalysisOutcome(
        result=result,
        elapsed_seconds=time.perf_counter() - started,
        mapping_notes=(
            "Rs 使用当前静态 AnalysisResult 的相电阻。",
            "Ld=Lq 使用当前标量相电感，仅作为表贴式 PMSM 沙盒近似。",
            "psi_f 由显式 PMSM 相峰值电流 Kt / (1.5*p) 换算。",
            "J、B 与 PI 增益来自本次用户设置，不写回项目默认值。",
        ),
        accuracy_level=settings.accuracy_level,
    )


def run_uncertainty_analysis(
    repository_root,
    settings: UncertaintyAnalysisSettings,
    specification_override: UncertaintySpecification | None = None,
) -> Phase7IUncertaintyDemonstration:
    return run_phase7i_demonstration(
        repository_root,
        monte_carlo_sample_count=settings.sample_count,
        random_seed=settings.random_seed,
        specification_override=specification_override,
    )


def run_sensitivity_analysis(
    inputs: MotorAnalysisInput | Mapping[str, object],
    parameter_name: str,
    output_name: str,
) -> SensitivitySummary:
    # The Phase 6A runner copies the normalized input before every perturbation.
    return run_sensitivity_sweep(
        inputs,
        parameter_names=(parameter_name,),
        output_names=(output_name,),
    )
