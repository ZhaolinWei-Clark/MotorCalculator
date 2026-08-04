"""Optional multi-rate loss/thermal wrapper around the validated PMSM plant."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter, VoltageLimitResult
from .losses import (
    DynamicLossModel,
    LossBreakdown,
    ResistanceTemperatureConfig,
)
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .simulation_results import SimulationResult, SimulationStatus
from .simulation_runner import InputProfile, SimulationRunner
from .state import InputState, MotorState, StateDerivatives
from .thermal import (
    LumpedThermalModel,
    ThermalConfig,
    ThermalElectricalCouplingConfig,
    ThermalState,
)


@dataclass(frozen=True)
class ThermalSimulationResult:
    """Electrical result plus aligned loss and winding-temperature metadata."""

    electrical_result: SimulationResult
    winding_temperature_c: tuple[float, ...]
    effective_phase_resistance_ohm: tuple[float, ...]
    copper_loss_w: tuple[float, ...]
    iron_loss_w: tuple[float | None, ...]
    mechanical_loss_w: tuple[float, ...]
    total_loss_w: tuple[float, ...]
    thermal_warning_messages: tuple[str, ...] = ()
    thermal_update_count: int = 0

    def __post_init__(self) -> None:
        expected_length = len(self.electrical_result.time)
        if expected_length == 0 or any(
            len(series) != expected_length for series in self.histories
        ):
            raise ValueError("thermal and electrical histories must be non-empty and aligned")
        for series in (
            self.winding_temperature_c,
            self.effective_phase_resistance_ohm,
            self.copper_loss_w,
            self.mechanical_loss_w,
            self.total_loss_w,
        ):
            if any(not math.isfinite(value) for value in series):
                raise ValueError("thermal histories must contain finite values")
        if any(
            value is not None and not math.isfinite(value)
            for value in self.iron_loss_w
        ):
            raise ValueError("available iron-loss values must be finite")
        if (
            isinstance(self.thermal_update_count, bool)
            or not isinstance(self.thermal_update_count, int)
            or self.thermal_update_count < 0
        ):
            raise ValueError("thermal_update_count must be a non-negative integer")
        object.__setattr__(
            self, "thermal_warning_messages", tuple(self.thermal_warning_messages)
        )

    @property
    def histories(self) -> tuple[tuple, ...]:
        return (
            self.winding_temperature_c,
            self.effective_phase_resistance_ohm,
            self.copper_loss_w,
            self.iron_loss_w,
            self.mechanical_loss_w,
            self.total_loss_w,
        )

    @property
    def time(self) -> tuple[float, ...]:
        return self.electrical_result.time

    @property
    def final_temperature_c(self) -> float:
        return self.winding_temperature_c[-1]


class ThermalElectricalSimulationRunner:
    """Add optional thermal feedback without modifying existing runner behavior."""

    def __init__(
        self,
        model: PMSMDynamicModel | None = None,
        integrator: EulerIntegrator | RK4Integrator | None = None,
        loss_model: DynamicLossModel | None = None,
        thermal_model: LumpedThermalModel | None = None,
    ) -> None:
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or EulerIntegrator()
        self._loss_model = loss_model or DynamicLossModel()
        self._thermal_model = thermal_model or LumpedThermalModel()
        self._base_runner = SimulationRunner(self._model, self._integrator)

    def run(
        self,
        initial_state: MotorState,
        motor_parameters: PMSMDynamicParameters,
        input_profile: InputState | InputProfile,
        simulation_time: float,
        time_step: float,
        coupling_config: ThermalElectricalCouplingConfig | None = None,
        thermal_config: ThermalConfig | None = None,
        resistance_config: ResistanceTemperatureConfig | None = None,
        inverter_config: DCBusConfig | None = None,
    ) -> SimulationResult | ThermalSimulationResult:
        coupling = coupling_config or ThermalElectricalCouplingConfig()
        if not coupling.enabled:
            return self._base_runner.run(
                initial_state,
                motor_parameters,
                input_profile,
                simulation_time,
                time_step,
                inverter_config,
            )
        if thermal_config is None:
            raise ValueError("thermal_config is required when thermal coupling is enabled")
        if resistance_config is None:
            raise ValueError(
                "resistance_config is required when thermal coupling is enabled"
            )
        SimulationRunner._validate_time_settings(simulation_time, time_step)
        if coupling.thermal_update_period_s + 1.0e-15 < time_step:
            raise ValueError(
                "thermal_update_period_s must not be faster than the plant time_step"
            )

        state = initial_state
        thermal_state = ThermalState(thermal_config.initial_temperature_c)
        initial_input, initial_limit = self._resolve_limited_input(
            input_profile, 0.0, inverter_config
        )
        limit_results = [initial_limit] if initial_limit is not None else []
        initial_resistance = self._effective_resistance(
            thermal_state, motor_parameters, resistance_config, coupling
        )
        initial_parameters = replace(motor_parameters, Rs=initial_resistance)
        initial_loss = self._loss_model.compute(
            state,
            initial_parameters,
            thermal_state.winding_temperature_c,
            initial_resistance,
            coupling.flux_density_proxy,
        )

        time_values = [0.0]
        id_values = [state.id]
        iq_values = [state.iq]
        speed_values = [state.omega_m]
        position_values = [state.theta]
        torque_values = [self._model.compute_electromagnetic_torque(state, initial_parameters)]
        electrical_power_values = [initial_input.Vd * state.id + initial_input.Vq * state.iq]
        mechanical_power_values = [torque_values[0] * state.omega_m]
        temperature_values = [thermal_state.winding_temperature_c]
        resistance_values = [initial_resistance]
        copper_loss_values = [initial_loss.copper_loss_w]
        iron_loss_values = [initial_loss.iron_loss_w]
        mechanical_loss_values = [initial_loss.mechanical_loss_w]
        total_loss_values = [initial_loss.total_loss_w]
        warnings = list(initial_loss.warning_messages)
        thermal_update_count = 0
        accumulated_loss_energy_j = 0.0
        accumulated_thermal_time_s = 0.0

        sample_count = math.ceil(simulation_time / time_step)
        for step_index in range(sample_count):
            current_time = step_index * time_step
            next_time = min((step_index + 1) * time_step, simulation_time)
            actual_dt = next_time - current_time
            if actual_dt <= 0.0:
                break

            effective_resistance = self._effective_resistance(
                thermal_state, motor_parameters, resistance_config, coupling
            )
            effective_parameters = replace(motor_parameters, Rs=effective_resistance)

            def derivative_evaluator(
                candidate_state: MotorState, offset: float
            ) -> StateDerivatives:
                actual_input, _ = self._resolve_limited_input(
                    input_profile,
                    min(current_time + offset, simulation_time),
                    inverter_config,
                )
                return self._model.compute_derivatives(
                    candidate_state, actual_input, effective_parameters
                )

            state = self._integrator.step(state, derivative_evaluator, actual_dt)
            pre_update_loss = self._loss_model.compute(
                state,
                effective_parameters,
                thermal_state.winding_temperature_c,
                effective_resistance,
                coupling.flux_density_proxy,
            )
            accumulated_loss_energy_j += pre_update_loss.total_loss_w * actual_dt
            accumulated_thermal_time_s += actual_dt

            thermal_update_due = (
                accumulated_thermal_time_s + 1.0e-15
                >= coupling.thermal_update_period_s
                or math.isclose(next_time, simulation_time, rel_tol=0.0, abs_tol=1.0e-15)
            )
            if thermal_update_due:
                average_loss_w = (
                    accumulated_loss_energy_j / accumulated_thermal_time_s
                )
                thermal_state = self._thermal_model.step(
                    thermal_state,
                    average_loss_w,
                    accumulated_thermal_time_s,
                    thermal_config,
                    coupling.integration_method,
                )
                accumulated_loss_energy_j = 0.0
                accumulated_thermal_time_s = 0.0
                thermal_update_count += 1

            sample_resistance = self._effective_resistance(
                thermal_state, motor_parameters, resistance_config, coupling
            )
            sample_parameters = replace(motor_parameters, Rs=sample_resistance)
            sample_loss = self._loss_model.compute(
                state,
                sample_parameters,
                thermal_state.winding_temperature_c,
                sample_resistance,
                coupling.flux_density_proxy,
            )
            sample_input, sample_limit = self._resolve_limited_input(
                input_profile, next_time, inverter_config
            )
            if sample_limit is not None:
                limit_results.append(sample_limit)
                warnings.extend(sample_limit.warning_messages)
            warnings.extend(sample_loss.warning_messages)
            if (
                thermal_config.warning_temperature_c is not None
                and thermal_state.winding_temperature_c
                >= thermal_config.warning_temperature_c
            ):
                warnings.append(
                    "Winding temperature reached the configured warning threshold; automatic shutdown is not implemented."
                )

            sample_torque = self._model.compute_electromagnetic_torque(
                state, sample_parameters
            )
            time_values.append(next_time)
            id_values.append(state.id)
            iq_values.append(state.iq)
            speed_values.append(state.omega_m)
            position_values.append(state.theta)
            torque_values.append(sample_torque)
            electrical_power_values.append(sample_input.Vd * state.id + sample_input.Vq * state.iq)
            mechanical_power_values.append(sample_torque * state.omega_m)
            temperature_values.append(thermal_state.winding_temperature_c)
            resistance_values.append(sample_resistance)
            copper_loss_values.append(sample_loss.copper_loss_w)
            iron_loss_values.append(sample_loss.iron_loss_w)
            mechanical_loss_values.append(sample_loss.mechanical_loss_w)
            total_loss_values.append(sample_loss.total_loss_w)

        unique_warnings = tuple(dict.fromkeys(warnings))
        electrical_result = SimulationResult(
            time=tuple(time_values),
            id=tuple(id_values),
            iq=tuple(iq_values),
            speed=tuple(speed_values),
            position=tuple(position_values),
            torque=tuple(torque_values),
            electrical_power=tuple(electrical_power_values),
            mechanical_power=tuple(mechanical_power_values),
            status=(SimulationStatus.WARNING if unique_warnings else SimulationStatus.SUCCESS),
            warning_messages=unique_warnings,
            solver_used=type(self._integrator).__name__.removesuffix("Integrator"),
            inverter_limited_count=sum(item.was_limited for item in limit_results),
            max_voltage_saturation_ratio=max(
                (item.saturation_ratio for item in limit_results), default=0.0
            ),
            voltage_limit_warnings=tuple(
                dict.fromkeys(
                    warning
                    for item in limit_results
                    for warning in item.warning_messages
                )
            ),
        )
        return ThermalSimulationResult(
            electrical_result=electrical_result,
            winding_temperature_c=tuple(temperature_values),
            effective_phase_resistance_ohm=tuple(resistance_values),
            copper_loss_w=tuple(copper_loss_values),
            iron_loss_w=tuple(iron_loss_values),
            mechanical_loss_w=tuple(mechanical_loss_values),
            total_loss_w=tuple(total_loss_values),
            thermal_warning_messages=unique_warnings,
            thermal_update_count=thermal_update_count,
        )

    @staticmethod
    def _effective_resistance(
        thermal_state: ThermalState,
        motor_parameters: PMSMDynamicParameters,
        resistance_config: ResistanceTemperatureConfig,
        coupling: ThermalElectricalCouplingConfig,
    ) -> float:
        if not coupling.enable_resistance_feedback:
            return motor_parameters.Rs
        return resistance_config.resistance_at_temperature(
            thermal_state.winding_temperature_c
        )

    @staticmethod
    def _resolve_limited_input(
        input_profile: InputState | InputProfile,
        time_s: float,
        inverter_config: DCBusConfig | None,
    ) -> tuple[InputState, VoltageLimitResult | None]:
        command = SimulationRunner._resolve_input(input_profile, time_s)
        if inverter_config is None:
            return command, None
        limit = InverterVoltageLimiter.apply_limit(
            command.Vd, command.Vq, inverter_config
        )
        return (
            InputState(limit.vd_actual_v, limit.vq_actual_v, command.load_torque),
            limit,
        )
