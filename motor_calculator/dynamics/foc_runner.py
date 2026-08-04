"""Sandbox-only FOC orchestration with optional measurement non-idealities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from .controllers import (
    DQCurrentController,
    DQVoltageCommand,
    FieldWeakeningController,
    FieldWeakeningResult,
    MTPAController,
    MTPACurrentReference,
    compute_pmsm_dq_decoupling_feedforward,
)
from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .sensors import SensorSuite, SensorSuiteMeasurement
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
    torque_reference_nm: float | None = None

    def __post_init__(self) -> None:
        _require_finite("id_ref_a", self.id_ref_a)
        _require_finite("iq_ref_a", self.iq_ref_a)
        if self.torque_reference_nm is not None:
            _require_finite("torque_reference_nm", self.torque_reference_nm)


@dataclass(frozen=True)
class FOCStepInput:
    """True plant currents and mechanical state entering one FOC step."""

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
    id_reference_a: float | None = None
    iq_reference_a: float | None = None
    mtpa_method: str | None = None
    field_weakening_active: bool = False
    field_weakening_voltage_margin_v: float | None = None
    id_true_a: float | None = None
    iq_true_a: float | None = None
    theta_m_measured_rad: float | None = None
    omega_m_measured_rad_s: float | None = None
    sensor_measurements: SensorSuiteMeasurement | None = None

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
        for name, value in (
            ("id_reference_a", self.id_reference_a),
            ("iq_reference_a", self.iq_reference_a),
            ("field_weakening_voltage_margin_v", self.field_weakening_voltage_margin_v),
            ("id_true_a", self.id_true_a),
            ("iq_true_a", self.iq_true_a),
            ("theta_m_measured_rad", self.theta_m_measured_rad),
            ("omega_m_measured_rad_s", self.omega_m_measured_rad_s),
        ):
            if value is not None:
                _require_finite(name, value)
        if not isinstance(self.field_weakening_active, bool):
            raise TypeError("field_weakening_active must be a bool")
        if self.sensor_measurements is not None and not isinstance(
            self.sensor_measurements, SensorSuiteMeasurement
        ):
            raise TypeError("sensor_measurements must be None or SensorSuiteMeasurement")
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
    enable_mtpa: bool = False
    enable_field_weakening: bool = False
    enable_sensor_nonidealities: bool = False

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
        if not isinstance(self.enable_mtpa, bool):
            raise ValueError("enable_mtpa must be a bool")
        if not isinstance(self.enable_field_weakening, bool):
            raise ValueError("enable_field_weakening must be a bool")
        if not isinstance(self.enable_sensor_nonidealities, bool):
            raise ValueError("enable_sensor_nonidealities must be a bool")


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
    mtpa_active_count: int = 0
    field_weakening_active_count: int = 0
    id_measured: tuple[float, ...] = ()
    iq_measured: tuple[float, ...] = ()
    speed_measured: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))
        for name, value in (
            ("voltage_saturation_count", self.voltage_saturation_count),
            ("mtpa_active_count", self.mtpa_active_count),
            ("field_weakening_active_count", self.field_weakening_active_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        expected_length = len(self.time)
        if expected_length == 0 or any(
            len(series) != expected_length for series in self.series
        ):
            raise ValueError("FOC simulation histories must be non-empty and aligned")
        if any(not math.isfinite(value) for series in self.series for value in series):
            raise ValueError("FOC simulation histories must contain only finite values")
        for series in self.measurement_series:
            if series and len(series) != expected_length:
                raise ValueError("FOC measurement histories must be aligned")
            if any(not math.isfinite(value) for value in series):
                raise ValueError("FOC measurement histories must contain finite values")

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

    @property
    def measurement_series(self) -> tuple[tuple[float, ...], ...]:
        return (self.id_measured, self.iq_measured, self.speed_measured)


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
        mtpa_controller: MTPAController | None = None,
        field_weakening_controller: FieldWeakeningController | None = None,
        sensor_suite: SensorSuite | None = None,
    ) -> None:
        if config.pole_pairs != motor_parameters.pole_pairs:
            raise ValueError("FOC and PMSM pole_pairs must match")
        if config.use_inverter_limit and inverter_config is None:
            raise ValueError("inverter_config is required when use_inverter_limit is true")
        if config.enable_mtpa and mtpa_controller is None:
            raise ValueError("mtpa_controller is required when enable_mtpa is true")
        if config.enable_field_weakening:
            if field_weakening_controller is None:
                raise ValueError(
                    "field_weakening_controller is required when enable_field_weakening is true"
                )
            if not config.use_inverter_limit or inverter_config is None:
                raise ValueError(
                    "field weakening requires an enabled inverter voltage limit"
                )
        if config.enable_sensor_nonidealities and sensor_suite is None:
            raise ValueError(
                "sensor_suite is required when enable_sensor_nonidealities is true"
            )
        self._controller = controller
        self._motor_parameters = motor_parameters
        self._config = config
        self._inverter_config = inverter_config
        self._model = model or PMSMDynamicModel()
        self._integrator = integrator or RK4Integrator()
        self._mtpa_controller = mtpa_controller
        self._field_weakening_controller = field_weakening_controller
        self._sensor_suite = sensor_suite

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

        true_abc_current = ABCPhaseValues(
            a=step_input.phase_current_a,
            b=step_input.phase_current_b,
            c=step_input.phase_current_c,
        )
        true_alpha_beta_current = clarke_transform(true_abc_current)
        true_theta_e_rad = electrical_angle(
            step_input.theta_m_rad,
            self._config.pole_pairs,
        )
        true_dq_current = park_transform(true_alpha_beta_current, true_theta_e_rad)

        sensor_measurements = None
        if (
            self._config.enable_sensor_nonidealities
            and self._sensor_suite is not None
            and self._sensor_suite.enabled
        ):
            sensor_measurements = self._sensor_suite.measure(
                true_phase_currents=true_abc_current,
                true_position_rad=step_input.theta_m_rad,
                true_speed_rad_s=step_input.omega_m_rad_s,
                pole_pairs=self._config.pole_pairs,
            )
            feedback_abc_current = sensor_measurements.measured_phase_currents
            feedback_theta_e_rad = sensor_measurements.position.electrical_angle_rad
            feedback_theta_m_rad = sensor_measurements.position.measured_value
            feedback_speed_rad_s = sensor_measurements.speed.measured_value
            sensor_warnings = sensor_measurements.warning_messages
        else:
            feedback_abc_current = true_abc_current
            feedback_theta_e_rad = true_theta_e_rad
            feedback_theta_m_rad = step_input.theta_m_rad
            feedback_speed_rad_s = step_input.omega_m_rad_s
            sensor_warnings = ()
        feedback_alpha_beta_current = clarke_transform(feedback_abc_current)
        dq_current = park_transform(feedback_alpha_beta_current, feedback_theta_e_rad)

        (
            effective_reference,
            mtpa_result,
            field_weakening_result,
            optimization_warnings,
        ) = self._resolve_effective_reference(reference, feedback_speed_rad_s)

        pi_voltage_command = self._controller.compute_voltage_command(
            id_ref=effective_reference.id_ref_a,
            iq_ref=effective_reference.iq_ref_a,
            id_actual=dq_current.d,
            iq_actual=dq_current.q,
            dt=time_step_s,
        )
        feedforward = compute_pmsm_dq_decoupling_feedforward(
            omega_e_rad_s=self._config.pole_pairs * feedback_speed_rad_s,
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
            warning_messages = (
                sensor_warnings
                + optimization_warnings
                + limit_result.warning_messages
            )
        else:
            vd_actual_v = voltage_command.vd_command_v
            vq_actual_v = voltage_command.vq_command_v
            voltage_limited = False
            warning_messages = sensor_warnings + optimization_warnings

        self._controller.track_applied_voltage(
            voltage_command,
            vd_actual_v,
            vq_actual_v,
            time_step_s,
        )
        current_state = MotorState(
            id=true_dq_current.d,
            iq=true_dq_current.q,
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
                warning_messages=tuple(dict.fromkeys(warning_messages)),
                id_reference_a=effective_reference.id_ref_a,
                iq_reference_a=effective_reference.iq_ref_a,
                mtpa_method=mtpa_result.method if mtpa_result is not None else None,
                field_weakening_active=(
                    field_weakening_result.weakening_active
                    if field_weakening_result is not None
                    else False
                ),
                field_weakening_voltage_margin_v=(
                    field_weakening_result.voltage_margin
                    if field_weakening_result is not None
                    else None
                ),
                id_true_a=true_dq_current.d,
                iq_true_a=true_dq_current.q,
                theta_m_measured_rad=feedback_theta_m_rad,
                omega_m_measured_rad_s=feedback_speed_rad_s,
                sensor_measurements=sensor_measurements,
            ),
            next_state,
        )

    def _resolve_effective_reference(
        self,
        reference: FOCReference,
        feedback_speed_rad_s: float,
    ) -> tuple[
        FOCReference,
        MTPACurrentReference | None,
        FieldWeakeningResult | None,
        tuple[str, ...],
    ]:
        id_reference = reference.id_ref_a
        iq_reference = reference.iq_ref_a
        mtpa_result = None
        weakening_result = None
        warnings: list[str] = []

        if self._config.enable_mtpa:
            torque_reference_nm = reference.torque_reference_nm
            if torque_reference_nm is None:
                torque_reference_nm = self._torque_from_current_reference(
                    id_reference,
                    iq_reference,
                )
            mtpa_result = self._mtpa_controller.compute_current_reference(
                torque_reference_nm,
                self._motor_parameters,
            )
            id_reference = mtpa_result.id_reference
            iq_reference = mtpa_result.iq_reference
            if mtpa_result.current_limited:
                warnings.append(
                    "MTPA current reference reached the configured current magnitude limit."
                )

        if self._config.enable_field_weakening:
            voltage_estimate = self._field_weakening_controller.estimate_steady_state_voltage(
                speed_rad_s=feedback_speed_rad_s,
                id_reference_a=id_reference,
                iq_reference_a=iq_reference,
                motor_parameters=self._motor_parameters,
            )
            weakening_result = self._field_weakening_controller.compute_weakening_command(
                speed_rad_s=feedback_speed_rad_s,
                vd_command_v=voltage_estimate.vd_v,
                vq_command_v=voltage_estimate.vq_v,
                dc_bus_voltage_v=self._inverter_config.nominal_voltage_v,
                motor_parameters=self._motor_parameters,
            )
            if weakening_result.weakening_active:
                id_reference = min(
                    id_reference,
                    weakening_result.id_weakening_command,
                )
                id_reference, iq_reference, was_limited = _limit_current_magnitude(
                    id_reference,
                    iq_reference,
                    self._field_weakening_controller.current_limit_a,
                )
                if was_limited:
                    warnings.append(
                        "Field-weakening current reference was projected onto the current limit."
                    )
            if weakening_result.warning:
                warnings.append(weakening_result.warning)

        return (
            FOCReference(
                id_ref_a=id_reference,
                iq_ref_a=iq_reference,
                torque_reference_nm=reference.torque_reference_nm,
            ),
            mtpa_result,
            weakening_result,
            tuple(warnings),
        )

    def _torque_from_current_reference(self, id_a: float, iq_a: float) -> float:
        parameters = self._motor_parameters
        return 1.5 * parameters.pole_pairs * (
            parameters.psi_f * iq_a
            + (parameters.Ld - parameters.Lq) * id_a * iq_a
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
    enable_mtpa: bool = False,
    enable_field_weakening: bool = False,
    torque_reference_profile: ScalarProfile | None = None,
    mtpa_current_limit_a: float | None = None,
    field_weakening_current_limit_a: float | None = None,
    enable_sensor_nonidealities: bool = False,
    sensor_suite: SensorSuite | None = None,
) -> FOCSimulationResult:
    """Run dq current tracking with optional measurement non-idealities."""

    _require_finite("simulation_time_s", simulation_time_s)
    if simulation_time_s <= 0.0:
        raise ValueError("simulation_time_s must be greater than zero")

    model = PMSMDynamicModel()
    controller = DQCurrentController(
        kp=controller_kp,
        ki=controller_ki,
        anti_windup_gain=anti_windup_gain,
    )
    shared_current_limit = (
        inverter_config.current_limit_a if inverter_config is not None else None
    )
    mtpa_limit = (
        mtpa_current_limit_a
        if mtpa_current_limit_a is not None
        else shared_current_limit
    )
    weakening_limit = (
        field_weakening_current_limit_a
        if field_weakening_current_limit_a is not None
        else shared_current_limit
    )
    if enable_mtpa and mtpa_limit is None:
        raise ValueError("an explicit current limit is required when MTPA is enabled")
    if enable_field_weakening and weakening_limit is None:
        raise ValueError(
            "an explicit current limit is required when field weakening is enabled"
        )
    mtpa_controller = MTPAController(mtpa_limit) if enable_mtpa else None
    field_weakening_controller = (
        FieldWeakeningController(weakening_limit)
        if enable_field_weakening
        else None
    )
    runner = FOCRunner(
        controller=controller,
        motor_parameters=motor_parameters,
        config=FOCRunnerConfig(
            pole_pairs=motor_parameters.pole_pairs,
            control_time_step_s=control_time_step_s,
            use_inverter_limit=inverter_config is not None,
            use_decoupling_feedforward=use_decoupling_feedforward,
            enable_mtpa=enable_mtpa,
            enable_field_weakening=enable_field_weakening,
            enable_sensor_nonidealities=enable_sensor_nonidealities,
        ),
        inverter_config=inverter_config,
        model=model,
        mtpa_controller=mtpa_controller,
        field_weakening_controller=field_weakening_controller,
        sensor_suite=sensor_suite,
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
    id_measured_values = [state.id]
    iq_measured_values = [state.iq]
    speed_measured_values = [state.omega_m]
    saturation_count = 0
    mtpa_active_count = 0
    field_weakening_active_count = 0
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
            torque_reference_nm=(
                _resolve_profile(
                    torque_reference_profile,
                    current_time,
                    "torque_reference_profile",
                )
                if torque_reference_profile is not None
                else None
            ),
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
        id_measured_values.append(output.id_measured_a)
        iq_measured_values.append(output.iq_measured_a)
        speed_measured_values.append(output.omega_m_measured_rad_s)
        saturation_count += int(output.voltage_limited)
        mtpa_active_count += int(output.mtpa_method is not None)
        field_weakening_active_count += int(output.field_weakening_active)
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
        mtpa_active_count=mtpa_active_count,
        field_weakening_active_count=field_weakening_active_count,
        id_measured=tuple(id_measured_values),
        iq_measured=tuple(iq_measured_values),
        speed_measured=tuple(speed_measured_values),
    )


def _resolve_profile(profile: ScalarProfile, time_s: float, name: str) -> float:
    value = profile(time_s) if callable(profile) else profile
    _require_finite(name, value)
    return value


def _limit_current_magnitude(
    id_reference_a: float,
    iq_reference_a: float,
    current_limit_a: float,
) -> tuple[float, float, bool]:
    magnitude = math.hypot(id_reference_a, iq_reference_a)
    if magnitude <= current_limit_a:
        return id_reference_a, iq_reference_a, False
    scale = current_limit_a / magnitude
    return id_reference_a * scale, iq_reference_a * scale, True
