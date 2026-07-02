"""Explicit electrical quantity semantics and centralized conversions."""

from __future__ import annotations

import math
from enum import Enum


class MotorSemanticsError(ValueError):
    """Raised when an electrical quantity conversion is semantically invalid."""


class MotorControlMode(str, Enum):
    """Explicit control-mode semantics for the current legacy-compatible model."""

    PMSM_SINUSOIDAL = "pmsm_sinusoidal"
    BLDC_120_DEGREE = "bldc_120_degree"


LEGACY_CONTROL_MODE_ALIASES = {
    "正弦波": MotorControlMode.PMSM_SINUSOIDAL,
    "PMSM": MotorControlMode.PMSM_SINUSOIDAL,
    "pmsm": MotorControlMode.PMSM_SINUSOIDAL,
    MotorControlMode.PMSM_SINUSOIDAL.value: MotorControlMode.PMSM_SINUSOIDAL,
    "梯形波": MotorControlMode.BLDC_120_DEGREE,
    "BLDC": MotorControlMode.BLDC_120_DEGREE,
    "bldc": MotorControlMode.BLDC_120_DEGREE,
    MotorControlMode.BLDC_120_DEGREE.value: MotorControlMode.BLDC_120_DEGREE,
}


def normalize_motor_control_mode(control_mode: MotorControlMode | str) -> MotorControlMode:
    if isinstance(control_mode, MotorControlMode):
        return control_mode
    try:
        return LEGACY_CONTROL_MODE_ALIASES[str(control_mode)]
    except KeyError as exc:
        raise MotorSemanticsError(f"Unsupported motor control mode: {control_mode!r}") from exc


def control_mode_display_name_zh(control_mode: MotorControlMode | str) -> str:
    normalized_mode = normalize_motor_control_mode(control_mode)
    if normalized_mode is MotorControlMode.PMSM_SINUSOIDAL:
        return "PMSM 正弦模式"
    return "BLDC 120°导通模式"


def legacy_control_model_name_for_mode(control_mode: MotorControlMode | str) -> str:
    normalized_mode = normalize_motor_control_mode(control_mode)
    if normalized_mode is MotorControlMode.PMSM_SINUSOIDAL:
        return "legacy_pmsm_model"
    return "legacy_bldc_model"


def pole_pairs_to_pole_count(pole_pairs: int) -> int:
    return 2 * pole_pairs


def mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm: float) -> float:
    return mechanical_speed_rpm * 2.0 * math.pi / 60.0


def mechanical_angular_speed_rad_s_to_mechanical_speed_rpm(mechanical_angular_speed_rad_s: float) -> float:
    return mechanical_angular_speed_rad_s * 60.0 / (2.0 * math.pi)


def mechanical_speed_rpm_to_electrical_frequency_hz(mechanical_speed_rpm: float, pole_pairs: int) -> float:
    return mechanical_speed_rpm * pole_pairs / 60.0


def mechanical_angular_speed_rad_s_to_electrical_angular_speed_rad_s(
    mechanical_angular_speed_rad_s: float, pole_pairs: int
) -> float:
    return mechanical_angular_speed_rad_s * pole_pairs


def y_connected_phase_current_rms_a_to_line_current_rms_a(phase_current_rms_a: float) -> float:
    return phase_current_rms_a


def require_sinusoidal_control_mode(control_mode: MotorControlMode | str) -> MotorControlMode:
    normalized_mode = normalize_motor_control_mode(control_mode)
    if normalized_mode is not MotorControlMode.PMSM_SINUSOIDAL:
        raise MotorSemanticsError(
            "Sinusoidal RMS/peak conversion is only defined for PMSM_SINUSOIDAL in Phase 3A."
        )
    return normalized_mode


def sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v(
    phase_voltage_rms_v: float, control_mode: MotorControlMode | str
) -> float:
    require_sinusoidal_control_mode(control_mode)
    return math.sqrt(2.0) * phase_voltage_rms_v


def sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v(
    phase_voltage_rms_v: float, control_mode: MotorControlMode | str
) -> float:
    require_sinusoidal_control_mode(control_mode)
    return math.sqrt(3.0) * phase_voltage_rms_v


def sinusoidal_line_voltage_rms_v_to_line_voltage_peak_v(
    line_voltage_rms_v: float, control_mode: MotorControlMode | str
) -> float:
    require_sinusoidal_control_mode(control_mode)
    return math.sqrt(2.0) * line_voltage_rms_v


def sinusoidal_phase_current_rms_a_to_phase_current_peak_a(
    phase_current_rms_a: float, control_mode: MotorControlMode | str
) -> float:
    require_sinusoidal_control_mode(control_mode)
    return math.sqrt(2.0) * phase_current_rms_a


def line_rms_v_per_krpm_to_line_rms_v_per_rad_s(back_emf_constant_line_rms_v_per_krpm: float) -> float:
    mechanical_angular_speed_rad_s_per_krpm = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(1000.0)
    return back_emf_constant_line_rms_v_per_krpm / mechanical_angular_speed_rad_s_per_krpm


def line_rms_v_per_rad_s_to_line_rms_v_per_krpm(back_emf_constant_line_rms_v_per_rad_s: float) -> float:
    mechanical_angular_speed_rad_s_per_krpm = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(1000.0)
    return back_emf_constant_line_rms_v_per_rad_s * mechanical_angular_speed_rad_s_per_krpm
