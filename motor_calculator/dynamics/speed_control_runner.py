"""Multi-rate cascaded PMSM speed/current control sandbox."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from .controllers import (
    DQCurrentController,
    DQVoltageCommand,
    SpeedController,
    SpeedControllerConfig,
    compute_pmsm_dq_decoupling_feedforward,
)
from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .state import InputState, MotorState, StateDerivatives


ScalarProfile = float | Callable[[float], float]


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class SpeedControlRunnerConfig:
    """Internal sandbox rates; normal user APIs do not expose these values."""

    plant_time_step_s: float = 1.0e-4
    current_control_period_s: float = 5.0e-4
    speed_control_period_s: float = 5.0e-3
    use_inverter_limit: bool = True
    use_decoupling_feedforward: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("plant_time_step_s", self.plant_time_step_s),
            ("current_control_period_s", self.current_control_period_s),
            ("speed_control_period_s", self.speed_control_period_s),
        ):
            _require_finite(name, value)
            if value <= 0.0:
                raise ValueError(f"{name} must be greater than zero")
        if self.current_control_period_s >= self.speed_control_period_s:
            raise ValueError("current loop must run faster than the speed loop")
        self._require_integer_ratio(
            self.current_control_period_s,
            self.plant_time_step_s,
            "current_control_period_s",
        )
        self._require_integer_ratio(
            self.speed_control_period_s,
            self.plant_time_step_s,
            "speed_control_period_s",
        )
        if not isinstance(self.use_inverter_limit, bool):
            raise TypeError("use_inverter_limit must be a bool")
        if not isinstance(self.use_decoupling_feedforward, bool):
            raise TypeError("use_decoupling_feedforward must be a bool")

    @staticmethod
    def _require_integer_ratio(period: float, base: float, name: str) -> None:
        ratio = period / base
        if not math.isclose(ratio, round(ratio), rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(f"{name} must be an integer multiple of plant_time_step_s")

    @property
    def current_steps(self) -> int:
        return round(self.current_control_period_s / self.plant_time_step_s)

    @property
    def speed_steps(self) -> int:
        return round(self.speed_control_period_s / self.plant_time_step_s)


@dataclass(frozen=True)
class SpeedControlSimulationResult:
    """Aligned multi-rate speed/current-loop histories and saturation metadata."""

    time: tuple[float, ...]
    speed_reference: tuple[float, ...]
    speed: tuple[float, ...]
    id_ref: tuple[float, ...]
    iq_ref: tuple[float, ...]
    id: tuple[float, ...]
    iq: tuple[float, ...]
    vd_command: tuple[float, ...]
    vq_command: tuple[float, ...]
    vd_actual: tuple[float, ...]
    vq_actual: tuple[float, ...]
    torque: tuple[float, ...]
    load_torque: tuple[float, ...]
    current_limit_active: tuple[bool, ...]
    voltage_saturation_active: tuple[bool, ...]
    current_limit_count: int
    voltage_saturation_count: int
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))
        expected_length = len(self.time)
        if expected_length == 0:
            raise ValueError("speed-control histories must not be empty")
        if any(len(series) != expected_length for series in self.all_series):
            raise ValueError("speed-control histories must be aligned")
        if any(not math.isfinite(value) for series in self.numeric_series for value in series):
            raise ValueError("speed-control histories must contain finite values")
        for name, value in (
            ("current_limit_count", self.current_limit_count),
            ("voltage_saturation_count", self.voltage_saturation_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def numeric_series(self) -> tuple[tuple[float, ...], ...]:
        return (
            self.time,
            self.speed_reference,
            self.speed,
            self.id_ref,
            self.iq_ref,
            self.id,
            self.iq,
            self.vd_command,
            self.vq_command,
            self.vd_actual,
            self.vq_actual,
            self.torque,
            self.load_torque,
        )

    @property
    def all_series(self) -> tuple[tuple, ...]:
        return (
            *self.numeric_series,
            self.current_limit_active,
            self.voltage_saturation_active,
        )


class SpeedControlSimulationRunner:
    """Coordinate a slower speed PI around the existing fast dq current PI."""

    def __init__(
        self,
        speed_controller: SpeedController,
        current_controller: DQCurrentController,
        motor_parameters: PMSMDynamicParameters,
        config: SpeedControlRunnerConfig | None = None,
        inverter_config: DCBusConfig | None = None,
        model: PMSMDynamicModel | None = None,
        integrator: EulerIntegrator | RK4Integrator | None = None,
    ) -> None:
        self._speed_controller = speed_controller
        self._current_controller = current_controller
        self._motor_parameters = motor_parameters
        self._config = config or SpeedControlRunnerConfig()
        if self._config.use_inverter_limit and inverter_config is None:
            raise ValueError("inverter_config is required when use_inverter_limit is true")
        self._inverter_config = inverter_config
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or RK4Integrator()

    def run(
        self,
        initial_state: MotorState,
        speed_reference_profile: ScalarProfile,
        load_torque_profile: ScalarProfile,
        simulation_time_s: float,
    ) -> SpeedControlSimulationResult:
        _require_finite("simulation_time_s", simulation_time_s)
        if simulation_time_s <= 0.0:
            raise ValueError("simulation_time_s must be greater than zero")

        state = initial_state
        initial_speed_ref = _resolve_profile(
            speed_reference_profile, 0.0, "speed_reference_profile"
        )
        initial_load = _resolve_profile(load_torque_profile, 0.0, "load_torque_profile")
        initial_torque = self._model.compute_electromagnetic_torque(
            state, self._motor_parameters
        )
        time_values = [0.0]
        speed_reference_values = [initial_speed_ref]
        speed_values = [state.omega_m]
        id_ref_values = [self._speed_controller.config.default_id_ref_a]
        iq_ref_values = [0.0]
        id_values = [state.id]
        iq_values = [state.iq]
        vd_command_values = [0.0]
        vq_command_values = [0.0]
        vd_actual_values = [0.0]
        vq_actual_values = [0.0]
        torque_values = [initial_torque]
        load_torque_values = [initial_load]
        current_limit_flags = [False]
        voltage_saturation_flags = [False]
        current_limit_count = 0
        voltage_saturation_count = 0
        warnings: list[str] = []

        held_id_ref = self._speed_controller.config.default_id_ref_a
        held_iq_ref = 0.0
        held_current_limit = False
        held_voltage_saturation = False
        held_voltage_command = DQVoltageCommand(0.0, 0.0)
        held_plant_input = InputState(Vd=0.0, Vq=0.0, load_torque=initial_load)

        plant_step_count = math.ceil(
            simulation_time_s / self._config.plant_time_step_s
        )
        for step_index in range(plant_step_count):
            current_time = step_index * self._config.plant_time_step_s
            next_time = min(
                (step_index + 1) * self._config.plant_time_step_s,
                simulation_time_s,
            )
            actual_dt = next_time - current_time
            if actual_dt <= 0.0:
                break

            speed_reference = _resolve_profile(
                speed_reference_profile, current_time, "speed_reference_profile"
            )
            load_torque = _resolve_profile(
                load_torque_profile, current_time, "load_torque_profile"
            )
            if step_index % self._config.speed_steps == 0:
                speed_output = self._speed_controller.update(
                    omega_ref_rad_s=speed_reference,
                    omega_measured_rad_s=state.omega_m,
                    dt=self._config.speed_control_period_s,
                )
                held_id_ref = speed_output.id_ref_a
                held_iq_ref = speed_output.iq_ref_actual_a
                held_current_limit = speed_output.current_limit_active
                if held_current_limit:
                    current_limit_count += 1
                    warnings.append(
                        "Speed controller q-current reference reached its configured limit."
                    )

            if step_index % self._config.current_steps == 0:
                pi_command = self._current_controller.compute_voltage_command(
                    id_ref=held_id_ref,
                    iq_ref=held_iq_ref,
                    id_actual=state.id,
                    iq_actual=state.iq,
                    dt=self._config.current_control_period_s,
                )
                feedforward = compute_pmsm_dq_decoupling_feedforward(
                    omega_e_rad_s=self._motor_parameters.pole_pairs * state.omega_m,
                    id_a=state.id,
                    iq_a=state.iq,
                    motor_parameters=self._motor_parameters,
                    enabled=self._config.use_decoupling_feedforward,
                )
                held_voltage_command = DQVoltageCommand(
                    vd_command_v=pi_command.vd_command_v + feedforward.vd_ff_v,
                    vq_command_v=pi_command.vq_command_v + feedforward.vq_ff_v,
                )
                if self._config.use_inverter_limit:
                    limit_result = InverterVoltageLimiter.apply_limit(
                        held_voltage_command.vd_command_v,
                        held_voltage_command.vq_command_v,
                        self._inverter_config,
                    )
                    vd_actual = limit_result.vd_actual_v
                    vq_actual = limit_result.vq_actual_v
                    held_voltage_saturation = limit_result.was_limited
                    if held_voltage_saturation:
                        voltage_saturation_count += 1
                        warnings.extend(limit_result.warning_messages)
                else:
                    vd_actual = held_voltage_command.vd_command_v
                    vq_actual = held_voltage_command.vq_command_v
                    held_voltage_saturation = False
                self._current_controller.track_applied_voltage(
                    held_voltage_command,
                    vd_actual,
                    vq_actual,
                    self._config.current_control_period_s,
                )
                held_plant_input = InputState(
                    Vd=vd_actual,
                    Vq=vq_actual,
                    load_torque=load_torque,
                )
            else:
                held_plant_input = InputState(
                    Vd=held_plant_input.Vd,
                    Vq=held_plant_input.Vq,
                    load_torque=load_torque,
                )

            def derivative_evaluator(candidate_state: MotorState, _: float) -> StateDerivatives:
                return self._model.compute_derivatives(
                    candidate_state, held_plant_input, self._motor_parameters
                )

            state = self._integrator.step(state, derivative_evaluator, actual_dt)
            torque = self._model.compute_electromagnetic_torque(
                state, self._motor_parameters
            )
            time_values.append(next_time)
            speed_reference_values.append(speed_reference)
            speed_values.append(state.omega_m)
            id_ref_values.append(held_id_ref)
            iq_ref_values.append(held_iq_ref)
            id_values.append(state.id)
            iq_values.append(state.iq)
            vd_command_values.append(held_voltage_command.vd_command_v)
            vq_command_values.append(held_voltage_command.vq_command_v)
            vd_actual_values.append(held_plant_input.Vd)
            vq_actual_values.append(held_plant_input.Vq)
            torque_values.append(torque)
            load_torque_values.append(load_torque)
            current_limit_flags.append(held_current_limit)
            voltage_saturation_flags.append(held_voltage_saturation)

        return SpeedControlSimulationResult(
            time=tuple(time_values),
            speed_reference=tuple(speed_reference_values),
            speed=tuple(speed_values),
            id_ref=tuple(id_ref_values),
            iq_ref=tuple(iq_ref_values),
            id=tuple(id_values),
            iq=tuple(iq_values),
            vd_command=tuple(vd_command_values),
            vq_command=tuple(vq_command_values),
            vd_actual=tuple(vd_actual_values),
            vq_actual=tuple(vq_actual_values),
            torque=tuple(torque_values),
            load_torque=tuple(load_torque_values),
            current_limit_active=tuple(current_limit_flags),
            voltage_saturation_active=tuple(voltage_saturation_flags),
            current_limit_count=current_limit_count,
            voltage_saturation_count=voltage_saturation_count,
            warning_messages=tuple(dict.fromkeys(warnings)),
        )


def run_speed_startup_example() -> SpeedControlSimulationResult:
    """Case A: accelerate from zero to a reachable constant target speed."""

    runner, initial_state = _build_example_runner(dc_bus_voltage_v=48.0)
    return runner.run(
        initial_state=initial_state,
        speed_reference_profile=lambda time_s: 0.0 if time_s < 0.02 else 40.0,
        load_torque_profile=0.0,
        simulation_time_s=1.5,
    )


def run_speed_load_step_example() -> SpeedControlSimulationResult:
    """Case B: reject a mechanical load step at constant speed reference."""

    runner, initial_state = _build_example_runner(dc_bus_voltage_v=48.0)
    return runner.run(
        initial_state=initial_state,
        speed_reference_profile=30.0,
        load_torque_profile=lambda time_s: 0.0 if time_s < 1.0 else 1.0,
        simulation_time_s=2.5,
    )


def run_unreachable_speed_example() -> SpeedControlSimulationResult:
    """Case C: remain bounded under current and voltage constrained demand."""

    runner, initial_state = _build_example_runner(
        dc_bus_voltage_v=24.0, iq_limit_a=3.0
    )
    return runner.run(
        initial_state=initial_state,
        speed_reference_profile=300.0,
        load_torque_profile=0.5,
        simulation_time_s=0.5,
    )


def _build_example_runner(
    dc_bus_voltage_v: float,
    iq_limit_a: float = 5.0,
) -> tuple[SpeedControlSimulationRunner, MotorState]:
    parameters = PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )
    speed_controller = SpeedController(
        SpeedControllerConfig(
            kp=0.4,
            ki=0.4,
            iq_min_a=-iq_limit_a,
            iq_max_a=iq_limit_a,
            anti_windup_gain=5.0,
        )
    )
    current_controller = DQCurrentController(
        kp=2.0, ki=200.0, anti_windup_gain=5.0
    )
    runner = SpeedControlSimulationRunner(
        speed_controller=speed_controller,
        current_controller=current_controller,
        motor_parameters=parameters,
        config=SpeedControlRunnerConfig(use_decoupling_feedforward=True),
        inverter_config=DCBusConfig(nominal_voltage_v=dc_bus_voltage_v),
    )
    return runner, MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def _resolve_profile(profile: ScalarProfile, time_s: float, name: str) -> float:
    value = profile(time_s) if callable(profile) else profile
    _require_finite(name, value)
    return value
