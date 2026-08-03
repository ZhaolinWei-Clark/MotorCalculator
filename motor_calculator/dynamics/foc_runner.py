"""Sandbox-only FOC signal-chain orchestration without sensors or PWM."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from .controllers import (
    DQCurrentController,
    DQVoltageCommand,
    compute_pmsm_dq_decoupling_feedforward,
)
from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .state import InputState, MotorState, StateDerivatives
from .transforms import (
    ABCPhaseValues,
    DQValues,
    clarke_transform,
    electrical_angle,
    inverse_clarke_transform,
    inverse_park_transform,
    park_transform,
)


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class FOCReference:
    """Direct dq current references for one FOC control sample."""

    id_ref_a: float
    iq_ref_a: float

    def __post_init__(self) -> None:
        _require_finite("id_ref_a", self.id_ref_a)
        _require_finite("iq_ref_a", self.iq_ref_a)


@dataclass(frozen=True)
class FOCStepInput:
    """Ideal current feedback and mechanical state for one FOC step."""

    phase_current_a: float
    phase_current_b: float
    phase_current_c: float
    theta_m_rad: float
    omega_m_rad_s: float
    load_torque_nm: float

    def __post_init__(self) -> None:
        for name, value in (
            ("phase_current_a", self.phase_current_a),
            ("phase_current_b", self.phase_current_b),
            ("phase_current_c", self.phase_current_c),
            ("theta_m_rad", self.theta_m_rad),
            ("omega_m_rad_s", self.omega_m_rad_s),
            ("load_torque_nm", self.load_torque_nm),
        ):
            _require_finite(name, value)


@dataclass(frozen=True)
class FOCStepOutput:
    """Measured currents, voltage path, and post-step mechanical outputs."""

    id_measured_a: float
    iq_measured_a: float
    vd_command_v: float
    vq_command_v: float
    vd_actual_v: float
    vq_actual_v: float
    voltage_limited: bool
    torque_nm: float
    omega_m_rad_s: float
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("id_measured_a", self.id_measured_a),
            ("iq_measured_a", self.iq_measured_a),
            ("vd_command_v", self.vd_command_v),
            ("vq_command_v", self.vq_command_v),
            ("vd_actual_v", self.vd_actual_v),
            ("vq_actual_v", self.vq_actual_v),
            ("torque_nm", self.torque_nm),
            ("omega_m_rad_s", self.omega_m_rad_s),
        ):
            _require_finite(name, value)
        if not isinstance(self.voltage_limited, bool):
            raise ValueError("voltage_limited must be a bool")
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))

    @property
    def raw_voltage_command(self) -> DQVoltageCommand:
        return DQVoltageCommand(self.vd_command_v, self.vq_command_v)

    @property
    def saturated_voltage_command(self) -> DQVoltageCommand:
        return DQVoltageCommand(self.vd_actual_v, self.vq_actual_v)

    @property
    def saturation_error(self) -> DQVoltageCommand:
        return DQVoltageCommand(
            self.vd_actual_v - self.vd_command_v,
            self.vq_actual_v - self.vq_command_v,
        )

    @property
    def saturation_active(self) -> bool:
        return self.voltage_limited


@dataclass(frozen=True)
class FOCRunnerConfig:
    """Fixed-rate settings for the Phase 6I FOC skeleton."""

    pole_pairs: int
    control_time_step_s: float
    use_inverter_limit: bool
    use_decoupling_feedforward: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.pole_pairs, bool) or not isinstance(self.pole_pairs, int):
            raise ValueError("pole_pairs must be a positive integer")
        if self.pole_pairs <= 0:
            raise ValueError("pole_pairs must be a positive integer")
        _require_finite("control_time_step_s", self.control_time_step_s)
        if self.control_time_step_s <= 0.0:
            raise ValueError("control_time_step_s must be greater than zero")
        if not isinstance(self.use_inverter_limit, bool):
            raise ValueError("use_inverter_limit must be a bool")
        if not isinstance(self.use_decoupling_feedforward, bool):
            raise ValueError("use_decoupling_feedforward must be a bool")


@dataclass(frozen=True)
class FOCSimulationResult:
    """Minimal closed-loop FOC current-tracking histories."""

    time: tuple[float, ...]
    id: tuple[float, ...]
    iq: tuple[float, ...]
    vd_command: tuple[float, ...]
    vq_command: tuple[float, ...]
    vd_actual: tuple[float, ...]
    vq_actual: tuple[float, ...]
    torque: tuple[float, ...]
    speed: tuple[float, ...]
    voltage_saturation_count: int
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))
        if (
            isinstance(self.voltage_saturation_count, bool)
            or not isinstance(self.voltage_saturation_count, int)
            or self.voltage_saturation_count < 0
        ):
            raise ValueError("voltage_saturation_count must be a non-negative integer")
        expected_length = len(self.time)
        if expected_length == 0 or any(
            len(series) != expected_length for series in self.series
        ):
            raise ValueError("FOC simulation histories must be non-empty and aligned")
        if any(not math.isfinite(value) for series in self.series for value in series):
            raise ValueError("FOC simulation histories must contain only finite values")

    @property
    def series(self) -> tuple[tuple[float, ...], ...]:
        return (
            self.time,
            self.id,
            self.iq,
            self.vd_command,
            self.vq_command,
            self.vd_actual,
            self.vq_actual,
            self.torque,
            self.speed,
        )


class FOCRunner:
    """Connect transforms, dq PI control, voltage limiting, and PMSM plant."""

    def __init__(
        self,
        controller: DQCurrentController,
        motor_parameters: PMSMDynamicParameters,
        config: FOCRunnerConfig,
        inverter_config: DCBusConfig | None = None,
        model: PMSMDynamicModel | None = None,
        integrator: EulerIntegrator | RK4Integrator | None = None,
    ) -> None:
        if config.pole_pairs != motor_parameters.pole_pairs:
            raise ValueError("FOC and PMSM pole_pairs must match")
        if config.use_inverter_limit and inverter_config is None:
            raise ValueError("inverter_config is required when use_inverter_limit is true")
        self._controller = controller
        self._motor_parameters = motor_parameters
        self._config = config
        self._inverter_config = inverter_config
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or RK4Integrator()

    def step(
        self,
        reference: FOCReference,
        step_input: FOCStepInput,
    ) -> FOCStepOutput:
        """Execute one control and plant integration step."""

        output, _ = self._execute_step(
            reference,
            step_input,
            self._config.control_time_step_s,
        )
        return output

    def _execute_step(
        self,
        reference: FOCReference,
        step_input: FOCStepInput,
        time_step_s: float,
    ) -> tuple[FOCStepOutput, MotorState]:
        _require_finite("time_step_s", time_step_s)
        if time_step_s <= 0.0:
            raise ValueError("time_step_s must be greater than zero")

        abc_current = ABCPhaseValues(
            a=step_input.phase_current_a,
            b=step_input.phase_current_b,
            c=step_input.phase_current_c,
        )
        alpha_beta_current = clarke_transform(abc_current)
        theta_e_rad = electrical_angle(step_input.theta_m_rad, self._config.pole_pairs)
        dq_current = park_transform(alpha_beta_current, theta_e_rad)

        pi_voltage_command = self._controller.compute_voltage_command(
            id_ref=reference.id_ref_a,
            iq_ref=reference.iq_ref_a,
            id_actual=dq_current.d,
            iq_actual=dq_current.q,
            dt=time_step_s,
        )
        feedforward = compute_pmsm_dq_decoupling_feedforward(
            omega_e_rad_s=self._config.pole_pairs * step_input.omega_m_rad_s,
            id_a=dq_current.d,
            iq_a=dq_current.q,
            motor_parameters=self._motor_parameters,
            enabled=self._config.use_decoupling_feedforward,
        )
        voltage_command = DQVoltageCommand(
            vd_command_v=pi_voltage_command.vd_command_v + feedforward.vd_ff_v,
            vq_command_v=pi_voltage_command.vq_command_v + feedforward.vq_ff_v,
        )
        if self._config.use_inverter_limit:
            limit_result = InverterVoltageLimiter.apply_limit(
                voltage_command.vd_command_v,
                voltage_command.vq_command_v,
                self._inverter_config,
            )
            vd_actual_v = limit_result.vd_actual_v
            vq_actual_v = limit_result.vq_actual_v
            voltage_limited = limit_result.was_limited
            warning_messages = limit_result.warning_messages
        else:
            vd_actual_v = voltage_command.vd_command_v
            vq_actual_v = voltage_command.vq_command_v
            voltage_limited = False
            warning_messages = ()

        self._controller.track_applied_voltage(
            voltage_command,
            vd_actual_v,
            vq_actual_v,
            time_step_s,
        )
        current_state = MotorState(
            id=dq_current.d,
            iq=dq_current.q,
            omega_m=step_input.omega_m_rad_s,
            theta=step_input.theta_m_rad,
        )
        plant_input = InputState(
            Vd=vd_actual_v,
            Vq=vq_actual_v,
            load_torque=step_input.load_torque_nm,
        )

        def derivative_evaluator(candidate_state: MotorState, _: float) -> StateDerivatives:
            return self._model.compute_derivatives(
                candidate_state,
                plant_input,
                self._motor_parameters,
            )

        next_state = self._integrator.step(
            current_state,
            derivative_evaluator,
            time_step_s,
        )
        torque_nm = self._model.compute_electromagnetic_torque(
            next_state,
            self._motor_parameters,
        )
        return (
            FOCStepOutput(
                id_measured_a=dq_current.d,
                iq_measured_a=dq_current.q,
                vd_command_v=voltage_command.vd_command_v,
                vq_command_v=voltage_command.vq_command_v,
                vd_actual_v=vd_actual_v,
                vq_actual_v=vq_actual_v,
                voltage_limited=voltage_limited,
                torque_nm=torque_nm,
                omega_m_rad_s=next_state.omega_m,
                warning_messages=warning_messages,
            ),
            next_state,
        )


ScalarProfile = float | Callable[[float], float]


def run_foc_current_control_simulation(
    initial_state: MotorState,
    id_ref_profile: ScalarProfile,
    iq_ref_profile: ScalarProfile,
    load_torque_profile: ScalarProfile,
    simulation_time_s: float,
    control_time_step_s: float,
    motor_parameters: PMSMDynamicParameters,
    controller_kp: float,
    controller_ki: float,
    inverter_config: DCBusConfig | None = None,
    anti_windup_gain: float = 0.0,
    use_decoupling_feedforward: bool = False,
) -> FOCSimulationResult:
    """Run minimal ideal-feedback dq current tracking through the FOC chain."""

    _require_finite("simulation_time_s", simulation_time_s)
    if simulation_time_s <= 0.0:
        raise ValueError("simulation_time_s must be greater than zero")

    model = PMSMDynamicModel()
    controller = DQCurrentController(
        kp=controller_kp,
        ki=controller_ki,
        anti_windup_gain=anti_windup_gain,
    )
    runner = FOCRunner(
        controller=controller,
        motor_parameters=motor_parameters,
        config=FOCRunnerConfig(
            pole_pairs=motor_parameters.pole_pairs,
            control_time_step_s=control_time_step_s,
            use_inverter_limit=inverter_config is not None,
            use_decoupling_feedforward=use_decoupling_feedforward,
        ),
        inverter_config=inverter_config,
        model=model,
    )

    state = initial_state
    initial_torque = model.compute_electromagnetic_torque(state, motor_parameters)
    time_values = [0.0]
    id_values = [state.id]
    iq_values = [state.iq]
    vd_command_values = [0.0]
    vq_command_values = [0.0]
    vd_actual_values = [0.0]
    vq_actual_values = [0.0]
    torque_values = [initial_torque]
    speed_values = [state.omega_m]
    saturation_count = 0
    warning_messages: list[str] = []

    current_time = 0.0
    while current_time < simulation_time_s:
        actual_dt = min(control_time_step_s, simulation_time_s - current_time)
        theta_e_rad = electrical_angle(state.theta, motor_parameters.pole_pairs)
        alpha_beta_current = inverse_park_transform(
            DQValues(d=state.id, q=state.iq),
            theta_e_rad,
        )
        abc_current = inverse_clarke_transform(alpha_beta_current)
        reference = FOCReference(
            id_ref_a=_resolve_profile(id_ref_profile, current_time, "id_ref_profile"),
            iq_ref_a=_resolve_profile(iq_ref_profile, current_time, "iq_ref_profile"),
        )
        step_input = FOCStepInput(
            phase_current_a=abc_current.a,
            phase_current_b=abc_current.b,
            phase_current_c=abc_current.c,
            theta_m_rad=state.theta,
            omega_m_rad_s=state.omega_m,
            load_torque_nm=_resolve_profile(
                load_torque_profile,
                current_time,
                "load_torque_profile",
            ),
        )
        output, state = runner._execute_step(reference, step_input, actual_dt)
        current_time = min(current_time + actual_dt, simulation_time_s)

        time_values.append(current_time)
        id_values.append(state.id)
        iq_values.append(state.iq)
        vd_command_values.append(output.vd_command_v)
        vq_command_values.append(output.vq_command_v)
        vd_actual_values.append(output.vd_actual_v)
        vq_actual_values.append(output.vq_actual_v)
        torque_values.append(output.torque_nm)
        speed_values.append(output.omega_m_rad_s)
        saturation_count += int(output.voltage_limited)
        warning_messages.extend(output.warning_messages)

    return FOCSimulationResult(
        time=tuple(time_values),
        id=tuple(id_values),
        iq=tuple(iq_values),
        vd_command=tuple(vd_command_values),
        vq_command=tuple(vq_command_values),
        vd_actual=tuple(vd_actual_values),
        vq_actual=tuple(vq_actual_values),
        torque=tuple(torque_values),
        speed=tuple(speed_values),
        voltage_saturation_count=saturation_count,
        warning_messages=tuple(dict.fromkeys(warning_messages)),
    )


def _resolve_profile(profile: ScalarProfile, time_s: float, name: str) -> float:
    value = profile(time_s) if callable(profile) else profile
    _require_finite(name, value)
    return value
