"""Closed-loop orchestration that keeps controller, inverter, and plant separate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from .controllers import DQCurrentController
from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter, VoltageLimitResult
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .simulation_results import SimulationResult, SimulationStatus
from .state import InputState, MotorState, StateDerivatives


@dataclass(frozen=True)
class DQCurrentReference:
    """Current references and mechanical load for one control sample."""

    id_ref: float
    iq_ref: float
    load_torque: float

    def __post_init__(self) -> None:
        for name, value in (
            ("id_ref", self.id_ref),
            ("iq_ref", self.iq_ref),
            ("load_torque", self.load_torque),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")


CurrentReferenceProfile = Callable[[float], DQCurrentReference]


class CurrentControlSimulationRunner:
    """Run one PI update per integration step using zero-order-held voltage."""

    def __init__(
        self,
        controller: DQCurrentController,
        model: PMSMDynamicModel | None = None,
        integrator: EulerIntegrator | RK4Integrator | None = None,
    ) -> None:
        self._controller = controller
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or RK4Integrator()

    def run(
        self,
        initial_state: MotorState,
        motor_parameters: PMSMDynamicParameters,
        reference_profile: DQCurrentReference | CurrentReferenceProfile,
        simulation_time: float,
        time_step: float,
        inverter_config: DCBusConfig | None = None,
    ) -> SimulationResult:
        self._validate_time_settings(simulation_time, time_step)

        state = initial_state
        time_values = [0.0]
        id_values = [state.id]
        iq_values = [state.iq]
        speed_values = [state.omega_m]
        position_values = [state.theta]
        initial_torque = self._model.compute_electromagnetic_torque(state, motor_parameters)
        torque_values = [initial_torque]
        electrical_power_values = [0.0]
        mechanical_power_values = [initial_torque * state.omega_m]
        voltage_limit_results: list[VoltageLimitResult] = []

        sample_count = math.ceil(simulation_time / time_step)
        for step_index in range(sample_count):
            current_time = step_index * time_step
            next_time = min((step_index + 1) * time_step, simulation_time)
            actual_dt = next_time - current_time
            if actual_dt <= 0.0:
                break

            reference = self._resolve_reference(reference_profile, current_time)
            command = self._controller.compute_voltage_command(
                id_ref=reference.id_ref,
                iq_ref=reference.iq_ref,
                id_actual=state.id,
                iq_actual=state.iq,
                dt=actual_dt,
            )
            actual_input, limit_result = self._resolve_voltage(
                command.vd_command_v,
                command.vq_command_v,
                reference.load_torque,
                inverter_config,
            )
            if limit_result is not None:
                voltage_limit_results.append(limit_result)
            self._controller.track_applied_voltage(
                command,
                actual_input.Vd,
                actual_input.Vq,
                actual_dt,
            )

            def derivative_evaluator(candidate_state: MotorState, _: float) -> StateDerivatives:
                return self._model.compute_derivatives(
                    candidate_state,
                    actual_input,
                    motor_parameters,
                )

            state = self._integrator.step(state, derivative_evaluator, actual_dt)
            torque = self._model.compute_electromagnetic_torque(state, motor_parameters)
            time_values.append(next_time)
            id_values.append(state.id)
            iq_values.append(state.iq)
            speed_values.append(state.omega_m)
            position_values.append(state.theta)
            torque_values.append(torque)
            electrical_power_values.append(actual_input.Vd * state.id + actual_input.Vq * state.iq)
            mechanical_power_values.append(torque * state.omega_m)

        inverter_limited_count = sum(item.was_limited for item in voltage_limit_results)
        max_saturation_ratio = max(
            (item.saturation_ratio for item in voltage_limit_results),
            default=0.0,
        )
        voltage_warnings = tuple(
            dict.fromkeys(
                warning
                for item in voltage_limit_results
                for warning in item.warning_messages
            )
        )

        return SimulationResult(
            time=tuple(time_values),
            id=tuple(id_values),
            iq=tuple(iq_values),
            speed=tuple(speed_values),
            position=tuple(position_values),
            torque=tuple(torque_values),
            electrical_power=tuple(electrical_power_values),
            mechanical_power=tuple(mechanical_power_values),
            status=SimulationStatus.WARNING if voltage_warnings else SimulationStatus.SUCCESS,
            warning_messages=voltage_warnings,
            solver_used=type(self._integrator).__name__.removesuffix("Integrator"),
            inverter_limited_count=inverter_limited_count,
            max_voltage_saturation_ratio=max_saturation_ratio,
            voltage_limit_warnings=voltage_warnings,
        )

    @staticmethod
    def _resolve_reference(
        reference_profile: DQCurrentReference | CurrentReferenceProfile,
        time_s: float,
    ) -> DQCurrentReference:
        reference = (
            reference_profile
            if isinstance(reference_profile, DQCurrentReference)
            else reference_profile(time_s)
        )
        if not isinstance(reference, DQCurrentReference):
            raise TypeError("reference_profile must return a DQCurrentReference")
        return reference

    @staticmethod
    def _resolve_voltage(
        vd_command_v: float,
        vq_command_v: float,
        load_torque: float,
        inverter_config: DCBusConfig | None,
    ) -> tuple[InputState, VoltageLimitResult | None]:
        if inverter_config is None:
            return InputState(vd_command_v, vq_command_v, load_torque), None

        result = InverterVoltageLimiter.apply_limit(
            vd_command_v,
            vq_command_v,
            inverter_config,
        )
        return (
            InputState(result.vd_actual_v, result.vq_actual_v, load_torque),
            result,
        )

    @staticmethod
    def _validate_time_settings(simulation_time: float, time_step: float) -> None:
        if not math.isfinite(simulation_time) or simulation_time <= 0.0:
            raise ValueError("simulation_time must be a finite value greater than zero")
        if not math.isfinite(time_step) or time_step <= 0.0:
            raise ValueError("time_step must be a finite value greater than zero")
