"""Repeatable prescribed-current experiments for Phase 6O reporting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .losses import CopperLossModel, ResistanceTemperatureConfig
from .thermal import LumpedThermalModel, ThermalConfig, ThermalState


CurrentProfile = float | Callable[[float], float]


@dataclass(frozen=True)
class PrescribedCurrentThermalResult:
    case_name: str
    time_s: tuple[float, ...]
    iq_peak_a: tuple[float, ...]
    winding_temperature_c: tuple[float, ...]
    effective_phase_resistance_ohm: tuple[float, ...]
    copper_loss_w: tuple[float, ...]
    theoretical_fixed_loss_steady_temperature_c: float | None = None

    @property
    def final_temperature_c(self) -> float:
        return self.winding_temperature_c[-1]


@dataclass(frozen=True)
class ThermalExperimentSuite:
    constant_current: PrescribedCurrentThermalResult
    higher_current: PrescribedCurrentThermalResult
    resistance_feedback_disabled: PrescribedCurrentThermalResult
    resistance_feedback_enabled: PrescribedCurrentThermalResult
    cooling: PrescribedCurrentThermalResult


def run_thermal_foundation_experiments() -> ThermalExperimentSuite:
    """Run required heating, I-squared, feedback, and cooling cases."""

    thermal_config = ThermalConfig(
        ambient_temperature_c=25.0,
        thermal_resistance_c_per_w=0.5,
        thermal_capacitance_j_per_c=100.0,
        initial_temperature_c=25.0,
    )
    resistance_config = ResistanceTemperatureConfig(0.5, 25.0, 0.00393)
    constant = _run_prescribed_current_case(
        "A_constant_current_heating",
        5.0,
        300.0,
        1.0,
        thermal_config,
        resistance_config,
        resistance_feedback=False,
    )
    higher = _run_prescribed_current_case(
        "B_higher_current",
        10.0,
        300.0,
        1.0,
        thermal_config,
        resistance_config,
        resistance_feedback=False,
    )
    feedback_disabled = _run_prescribed_current_case(
        "C_resistance_feedback_disabled",
        5.0,
        300.0,
        1.0,
        thermal_config,
        resistance_config,
        resistance_feedback=False,
    )
    feedback_enabled = _run_prescribed_current_case(
        "C_resistance_feedback_enabled",
        5.0,
        300.0,
        1.0,
        thermal_config,
        resistance_config,
        resistance_feedback=True,
    )
    cooling = _run_prescribed_current_case(
        "D_cooling_after_heating",
        lambda time_s: 5.0 if time_s < 150.0 else 0.0,
        450.0,
        1.0,
        thermal_config,
        resistance_config,
        resistance_feedback=False,
    )
    return ThermalExperimentSuite(
        constant_current=constant,
        higher_current=higher,
        resistance_feedback_disabled=feedback_disabled,
        resistance_feedback_enabled=feedback_enabled,
        cooling=cooling,
    )


def _run_prescribed_current_case(
    case_name: str,
    current_profile: CurrentProfile,
    duration_s: float,
    time_step_s: float,
    thermal_config: ThermalConfig,
    resistance_config: ResistanceTemperatureConfig,
    resistance_feedback: bool,
) -> PrescribedCurrentThermalResult:
    model = LumpedThermalModel()
    state = ThermalState(thermal_config.initial_temperature_c)
    fixed_resistance = resistance_config.resistance_ref_ohm
    initial_current = _resolve_current(current_profile, 0.0)
    initial_resistance = (
        resistance_config.resistance_at_temperature(state.winding_temperature_c)
        if resistance_feedback
        else fixed_resistance
    )
    initial_loss = CopperLossModel.compute_from_dq_peak(
        0.0, initial_current, initial_resistance
    )
    time_values = [0.0]
    current_values = [initial_current]
    temperature_values = [state.winding_temperature_c]
    resistance_values = [initial_resistance]
    loss_values = [initial_loss]

    current_time = 0.0
    while current_time < duration_s:
        actual_dt = min(time_step_s, duration_s - current_time)
        current = _resolve_current(current_profile, current_time)
        resistance = (
            resistance_config.resistance_at_temperature(
                state.winding_temperature_c
            )
            if resistance_feedback
            else fixed_resistance
        )
        loss = CopperLossModel.compute_from_dq_peak(0.0, current, resistance)
        state = model.step(state, loss, actual_dt, thermal_config)
        current_time += actual_dt
        sampled_current = _resolve_current(current_profile, current_time)
        sampled_resistance = (
            resistance_config.resistance_at_temperature(
                state.winding_temperature_c
            )
            if resistance_feedback
            else fixed_resistance
        )
        sampled_loss = CopperLossModel.compute_from_dq_peak(
            0.0, sampled_current, sampled_resistance
        )
        time_values.append(current_time)
        current_values.append(sampled_current)
        temperature_values.append(state.winding_temperature_c)
        resistance_values.append(sampled_resistance)
        loss_values.append(sampled_loss)

    steady_temperature = None
    if not callable(current_profile) and not resistance_feedback:
        steady_temperature = thermal_config.steady_state_temperature_c(initial_loss)
    return PrescribedCurrentThermalResult(
        case_name=case_name,
        time_s=tuple(time_values),
        iq_peak_a=tuple(current_values),
        winding_temperature_c=tuple(temperature_values),
        effective_phase_resistance_ohm=tuple(resistance_values),
        copper_loss_w=tuple(loss_values),
        theoretical_fixed_loss_steady_temperature_c=steady_temperature,
    )


def _resolve_current(profile: CurrentProfile, time_s: float) -> float:
    value = profile(time_s) if callable(profile) else profile
    if value < 0.0:
        raise ValueError("prescribed current magnitude must be non-negative")
    return value
