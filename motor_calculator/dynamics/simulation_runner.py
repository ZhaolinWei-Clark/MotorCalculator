"""Time-domain orchestration for the isolated PMSM simulation sandbox."""

from __future__ import annotations

from collections.abc import Callable
import math

from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter, VoltageLimitResult
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .simulation_results import SimulationResult, SimulationStatus
from .state import InputState, MotorState, StateDerivatives

InputProfile = Callable[[float], InputState]


class SimulationRunner:
    """Advance a PMSM model using an injected numerical integrator."""

    def __init__(
        self,
        model: PMSMDynamicModel | None = None,
        integrator: EulerIntegrator | RK4Integrator | None = None,
    ) -> None:
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or EulerIntegrator()

    def run(
        self,
        initial_state: MotorState,
        motor_parameters: PMSMDynamicParameters,
        input_profile: InputState | InputProfile,
        simulation_time: float,
        time_step: float,
        inverter_config: DCBusConfig | None = None,
    ) -> SimulationResult:
        self._validate_time_settings(simulation_time, time_step)

        sample_count = math.ceil(simulation_time / time_step)
        state = initial_state
        time_values = [0.0]
        id_values = [state.id]
        iq_values = [state.iq]
        speed_values = [state.omega_m]
        position_values = [state.theta]
        initial_command = self._resolve_input(input_profile, 0.0)
        initial_input, initial_limit_result = self._apply_voltage_limit(initial_command, inverter_config)
        voltage_limit_results = [initial_limit_result] if initial_limit_result is not None else []
        initial_torque = self._model.compute_electromagnetic_torque(state, motor_parameters)
        torque_values = [initial_torque]
        electrical_power_values = [initial_input.Vd * state.id + initial_input.Vq * state.iq]
        mechanical_power_values = [initial_torque * state.omega_m]

        for step_index in range(sample_count):
            current_time = step_index * time_step
            next_time = min((step_index + 1) * time_step, simulation_time)
            actual_dt = next_time - current_time
            # Floating-point division can make an exact ratio look slightly
            # larger than an integer and cause ceil() to schedule a zero step.
            if actual_dt <= 0.0:
                break

            def derivative_evaluator(candidate_state: MotorState, offset: float) -> StateDerivatives:
                command_input = self._resolve_input(
                    input_profile,
                    min(current_time + offset, simulation_time),
                )
                actual_input, _ = self._apply_voltage_limit(command_input, inverter_config)
                return self._model.compute_derivatives(candidate_state, actual_input, motor_parameters)

            state = self._integrator.step(state, derivative_evaluator, actual_dt)

            sample_command = self._resolve_input(input_profile, next_time)
            sample_input, sample_limit_result = self._apply_voltage_limit(sample_command, inverter_config)
            if sample_limit_result is not None:
                voltage_limit_results.append(sample_limit_result)
            sample_torque = self._model.compute_electromagnetic_torque(state, motor_parameters)
            time_values.append(next_time)
            id_values.append(state.id)
            iq_values.append(state.iq)
            speed_values.append(state.omega_m)
            position_values.append(state.theta)
            torque_values.append(sample_torque)
            electrical_power_values.append(sample_input.Vd * state.id + sample_input.Vq * state.iq)
            mechanical_power_values.append(sample_torque * state.omega_m)

        inverter_limited_count = sum(item.was_limited for item in voltage_limit_results)
        max_voltage_saturation_ratio = max(
            (item.saturation_ratio for item in voltage_limit_results),
            default=0.0,
        )
        voltage_limit_warnings = tuple(
            dict.fromkeys(
                warning
                for item in voltage_limit_results
                for warning in item.warning_messages
            )
        )
        status = SimulationStatus.WARNING if voltage_limit_warnings else SimulationStatus.SUCCESS

        return SimulationResult(
            time=tuple(time_values),
            id=tuple(id_values),
            iq=tuple(iq_values),
            speed=tuple(speed_values),
            position=tuple(position_values),
            torque=tuple(torque_values),
            electrical_power=tuple(electrical_power_values),
            mechanical_power=tuple(mechanical_power_values),
            status=status,
            warning_messages=voltage_limit_warnings,
            solver_used=type(self._integrator).__name__.removesuffix("Integrator"),
            inverter_limited_count=inverter_limited_count,
            max_voltage_saturation_ratio=max_voltage_saturation_ratio,
            voltage_limit_warnings=voltage_limit_warnings,
        )

    @staticmethod
    def _resolve_input(input_profile: InputState | InputProfile, time_s: float) -> InputState:
        resolved = input_profile if isinstance(input_profile, InputState) else input_profile(time_s)
        if not isinstance(resolved, InputState):
            raise TypeError("input_profile must return an InputState")
        return resolved

    @staticmethod
    def _apply_voltage_limit(
        command_input: InputState,
        inverter_config: DCBusConfig | None,
    ) -> tuple[InputState, VoltageLimitResult | None]:
        if inverter_config is None:
            return command_input, None
        limit_result = InverterVoltageLimiter.apply_limit(
            command_input.Vd,
            command_input.Vq,
            inverter_config,
        )
        return (
            InputState(
                Vd=limit_result.vd_actual_v,
                Vq=limit_result.vq_actual_v,
                load_torque=command_input.load_torque,
            ),
            limit_result,
        )

    @staticmethod
    def _validate_time_settings(simulation_time: float, time_step: float) -> None:
        if not math.isfinite(simulation_time) or simulation_time <= 0.0:
            raise ValueError("simulation_time must be a finite value greater than zero")
        if not math.isfinite(time_step) or time_step <= 0.0:
            raise ValueError("time_step must be a finite value greater than zero")
