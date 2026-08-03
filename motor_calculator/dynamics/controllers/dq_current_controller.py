"""Independent d- and q-axis PI current controller composition."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .pi_controller import PIController


@dataclass(frozen=True)
class DQVoltageCommand:
    """Controller voltage command before inverter limiting, in volts."""

    vd_command_v: float
    vq_command_v: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.vd_command_v) or not math.isfinite(self.vq_command_v):
            raise ValueError("dq voltage commands must be finite")


@dataclass(frozen=True)
class DQSaturationFeedback:
    """Raw/applied dq voltages and the error fed back to both PI axes."""

    raw_voltage_command: DQVoltageCommand
    saturated_voltage_command: DQVoltageCommand
    saturation_error: DQVoltageCommand
    saturation_active: bool

    def __post_init__(self) -> None:
        if not isinstance(self.raw_voltage_command, DQVoltageCommand):
            raise TypeError("raw_voltage_command must be a DQVoltageCommand")
        if not isinstance(self.saturated_voltage_command, DQVoltageCommand):
            raise TypeError("saturated_voltage_command must be a DQVoltageCommand")
        if not isinstance(self.saturation_error, DQVoltageCommand):
            raise TypeError("saturation_error must be a DQVoltageCommand")
        if not isinstance(self.saturation_active, bool):
            raise TypeError("saturation_active must be a bool")


class DQCurrentController:
    """Two independent PI axes operating directly in the rotating dq frame."""

    def __init__(
        self,
        kp: float,
        ki: float,
        anti_windup_gain: float = 0.0,
    ) -> None:
        self.d_axis_controller = PIController(
            kp=kp,
            ki=ki,
            anti_windup_gain=anti_windup_gain,
        )
        self.q_axis_controller = PIController(
            kp=kp,
            ki=ki,
            anti_windup_gain=anti_windup_gain,
        )

    def compute_voltage_command(
        self,
        id_ref: float,
        iq_ref: float,
        id_actual: float,
        iq_actual: float,
        dt: float,
    ) -> DQVoltageCommand:
        """Compute PI voltage corrections from d- and q-axis current errors."""

        vd_command = self.d_axis_controller.compute(id_ref - id_actual, dt)
        vq_command = self.q_axis_controller.compute(iq_ref - iq_actual, dt)
        return DQVoltageCommand(
            vd_command_v=vd_command,
            vq_command_v=vq_command,
        )

    def update(
        self,
        id_ref: float,
        iq_ref: float,
        id_actual: float,
        iq_actual: float,
        dt: float,
    ) -> DQVoltageCommand:
        """Alias for :meth:`compute_voltage_command`."""

        return self.compute_voltage_command(id_ref, iq_ref, id_actual, iq_actual, dt)

    def reset(self) -> None:
        self.d_axis_controller.reset()
        self.q_axis_controller.reset()

    def track_applied_voltage(
        self,
        command: DQVoltageCommand,
        vd_actual_v: float,
        vq_actual_v: float,
        dt: float,
    ) -> DQSaturationFeedback:
        """Apply inverter tracking and return explicit saturation metadata."""

        self.d_axis_controller.apply_anti_windup(
            command.vd_command_v,
            vd_actual_v,
            dt,
        )
        self.q_axis_controller.apply_anti_windup(
            command.vq_command_v,
            vq_actual_v,
            dt,
        )
        saturated_command = DQVoltageCommand(
            vd_command_v=vd_actual_v,
            vq_command_v=vq_actual_v,
        )
        saturation_error = DQVoltageCommand(
            vd_command_v=vd_actual_v - command.vd_command_v,
            vq_command_v=vq_actual_v - command.vq_command_v,
        )
        return DQSaturationFeedback(
            raw_voltage_command=command,
            saturated_voltage_command=saturated_command,
            saturation_error=saturation_error,
            saturation_active=(
                vd_actual_v != command.vd_command_v
                or vq_actual_v != command.vq_command_v
            ),
        )
