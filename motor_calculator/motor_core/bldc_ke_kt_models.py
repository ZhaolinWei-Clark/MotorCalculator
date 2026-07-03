"""Explicit ideal BLDC 120-degree waveform semantics and Ke/Kt helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .electrical_semantics import (
    MotorControlMode,
    line_rms_v_per_rad_s_to_line_rms_v_per_krpm,
    mechanical_speed_rpm_to_mechanical_angular_speed_rad_s,
    normalize_motor_control_mode,
)
from .validation import MotorCalculationError

REL_TOL = 1e-8
ABS_TOL = 1e-10
NUMERIC_REL_TOL = 1e-6
NUMERIC_ABS_TOL = 1e-8
DEFAULT_NUMERIC_SAMPLE_COUNT = 36000
TWO_PI = 2.0 * math.pi
ONE_THIRD_PI = math.pi / 3.0
ONE_SIXTH_PI = math.pi / 6.0
FIVE_SIXTHS_PI = 5.0 * math.pi / 6.0
SEVEN_SIXTHS_PI = 7.0 * math.pi / 6.0
ELEVEN_SIXTHS_PI = 11.0 * math.pi / 6.0
TWO_THIRDS_PI = 2.0 * math.pi / 3.0


@dataclass(frozen=True)
class RevisedBldcKeKtSemantics:
    revised_bldc_phase_flat_top_back_emf_v: float
    revised_bldc_phase_peak_back_emf_v: float
    revised_bldc_phase_rms_back_emf_v: float
    revised_bldc_line_to_line_peak_back_emf_v: float
    revised_bldc_line_to_line_rms_back_emf_v: float
    revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s: float
    revised_bldc_back_emf_constant_phase_peak_v_per_rad_s: float
    revised_bldc_back_emf_constant_phase_rms_v_per_rad_s: float
    revised_bldc_back_emf_constant_line_rms_v_per_rad_s: float
    revised_bldc_back_emf_constant_line_rms_v_per_krpm: float
    revised_bldc_torque_constant_nm_per_conduction_a: float
    revised_bldc_torque_constant_nm_per_phase_rms_a: float
    bldc_waveform_semantics_status: str
    bldc_power_balance_status: str
    bldc_ke_semantics_status: str
    bldc_kt_semantics_status: str


def _require_positive_finite(name: str, value: float, unit: str) -> None:
    if math.isnan(value) or math.isinf(value):
        raise MotorCalculationError(f"{name} must be finite, got {value!r} {unit}.")
    if value <= 0.0:
        raise MotorCalculationError(f"{name} must be greater than 0, got {value!r} {unit}.")


def require_bldc_control_mode(control_mode: MotorControlMode | str) -> MotorControlMode:
    normalized_mode = normalize_motor_control_mode(control_mode)
    if normalized_mode is not MotorControlMode.BLDC_120_DEGREE:
        raise MotorCalculationError("Ideal BLDC 120-degree waveform helpers only apply to BLDC_120_DEGREE.")
    return normalized_mode


def _normalize_electrical_angle(electrical_angle_rad: float) -> float:
    return electrical_angle_rad % TWO_PI


def normalized_bldc_phase_back_emf(electrical_angle_rad: float) -> float:
    """Return normalized ideal trapezoidal phase back EMF over one electrical cycle.

    The idealized waveform is:
    - 0 -> +1 over 30 degrees
    - +1 flat for 120 degrees
    - +1 -> -1 over 60 degrees
    - -1 flat for 120 degrees
    - -1 -> 0 over 30 degrees
    """

    theta = _normalize_electrical_angle(electrical_angle_rad)
    if theta < ONE_SIXTH_PI:
        return 6.0 * theta / math.pi
    if theta < FIVE_SIXTHS_PI:
        return 1.0
    if theta < SEVEN_SIXTHS_PI:
        return 1.0 - 6.0 * (theta - FIVE_SIXTHS_PI) / math.pi
    if theta < ELEVEN_SIXTHS_PI:
        return -1.0
    return -1.0 + 6.0 * (theta - ELEVEN_SIXTHS_PI) / math.pi


def normalized_bldc_phase_current(electrical_angle_rad: float) -> float:
    """Return normalized ideal 120-degree phase current for six-step BLDC."""

    theta = _normalize_electrical_angle(electrical_angle_rad)
    if theta < ONE_SIXTH_PI:
        return 0.0
    if theta < FIVE_SIXTHS_PI:
        return 1.0
    if theta < SEVEN_SIXTHS_PI:
        return 0.0
    if theta < ELEVEN_SIXTHS_PI:
        return -1.0
    return 0.0


def normalized_bldc_line_to_line_back_emf(electrical_angle_rad: float) -> float:
    phase_a = normalized_bldc_phase_back_emf(electrical_angle_rad)
    phase_b = normalized_bldc_phase_back_emf(electrical_angle_rad - TWO_THIRDS_PI)
    return phase_a - phase_b


def _average_over_cycle(function, sample_count: int = DEFAULT_NUMERIC_SAMPLE_COUNT) -> float:
    total = 0.0
    for index in range(sample_count):
        theta = TWO_PI * (index + 0.5) / sample_count
        total += function(theta)
    return total / sample_count


def _rms_over_cycle(function, sample_count: int = DEFAULT_NUMERIC_SAMPLE_COUNT) -> float:
    return math.sqrt(_average_over_cycle(lambda theta: function(theta) ** 2, sample_count=sample_count))


def normalized_bldc_phase_back_emf_rms() -> float:
    return math.sqrt(7.0) / 3.0


def normalized_bldc_line_to_line_back_emf_rms() -> float:
    return 2.0 * math.sqrt(5.0) / 3.0


def normalized_bldc_phase_current_rms() -> float:
    return math.sqrt(2.0 / 3.0)


def normalized_bldc_average_electromagnetic_power() -> float:
    return 2.0


def calculate_bldc_phase_back_emf_rms_from_flat_top_v(
    phase_flat_top_back_emf_v: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase flat-top back EMF", phase_flat_top_back_emf_v, "V")
    return normalized_bldc_phase_back_emf_rms() * phase_flat_top_back_emf_v


def calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v(
    phase_flat_top_back_emf_v: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase flat-top back EMF", phase_flat_top_back_emf_v, "V")
    return 2.0 * phase_flat_top_back_emf_v


def calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v(
    phase_flat_top_back_emf_v: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase flat-top back EMF", phase_flat_top_back_emf_v, "V")
    return normalized_bldc_line_to_line_back_emf_rms() * phase_flat_top_back_emf_v


def calculate_bldc_phase_current_rms_from_conduction_current(
    phase_current_conduction_a: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC conduction current", phase_current_conduction_a, "A")
    return normalized_bldc_phase_current_rms() * phase_current_conduction_a


def calculate_bldc_line_current_rms_from_conduction_current(
    phase_current_conduction_a: float,
    control_mode: MotorControlMode | str,
) -> float:
    return calculate_bldc_phase_current_rms_from_conduction_current(
        phase_current_conduction_a=phase_current_conduction_a,
        control_mode=control_mode,
    )


def calculate_bldc_conduction_current_from_phase_rms_current(
    phase_current_rms_a: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase RMS current", phase_current_rms_a, "A")
    return phase_current_rms_a / normalized_bldc_phase_current_rms()


def calculate_bldc_average_electromagnetic_power_w(
    phase_flat_top_back_emf_v: float,
    conduction_current_a: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase flat-top back EMF", phase_flat_top_back_emf_v, "V")
    _require_positive_finite("BLDC conduction current", conduction_current_a, "A")
    return normalized_bldc_average_electromagnetic_power() * phase_flat_top_back_emf_v * conduction_current_a


def calculate_bldc_average_electromagnetic_power_from_numeric_integration_w(
    phase_flat_top_back_emf_v: float,
    conduction_current_a: float,
    control_mode: MotorControlMode | str,
    sample_count: int = DEFAULT_NUMERIC_SAMPLE_COUNT,
) -> float:
    require_bldc_control_mode(control_mode)
    _require_positive_finite("BLDC phase flat-top back EMF", phase_flat_top_back_emf_v, "V")
    _require_positive_finite("BLDC conduction current", conduction_current_a, "A")

    def phase_emf(theta: float, phase_shift: float) -> float:
        return phase_flat_top_back_emf_v * normalized_bldc_phase_back_emf(theta + phase_shift)

    def phase_current(theta: float, phase_shift: float) -> float:
        return conduction_current_a * normalized_bldc_phase_current(theta + phase_shift)

    return _average_over_cycle(
        lambda theta: (
            phase_emf(theta, 0.0) * phase_current(theta, 0.0)
            + phase_emf(theta, -TWO_THIRDS_PI) * phase_current(theta, -TWO_THIRDS_PI)
            + phase_emf(theta, TWO_THIRDS_PI) * phase_current(theta, TWO_THIRDS_PI)
        ),
        sample_count=sample_count,
    )


def compare_legacy_and_revised_bldc_ke_kt(
    control_mode: MotorControlMode | str,
    legacy_back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
    legacy_back_emf_constant_line_rms_v_per_krpm: float,
) -> RevisedBldcKeKtSemantics:
    normalized_mode = require_bldc_control_mode(control_mode)
    _require_positive_finite("Legacy BLDC phase RMS back EMF", legacy_back_emf_phase_rms_v, "V")
    _require_positive_finite("Mechanical speed", mechanical_speed_rpm, "rpm")
    _require_positive_finite("Legacy BLDC line RMS back EMF constant", legacy_back_emf_constant_line_rms_v_per_krpm, "V/krpm")

    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    phase_flat_top_back_emf_v = legacy_back_emf_phase_rms_v / normalized_bldc_phase_back_emf_rms()
    phase_peak_back_emf_v = phase_flat_top_back_emf_v
    phase_rms_back_emf_v = calculate_bldc_phase_back_emf_rms_from_flat_top_v(
        phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        control_mode=normalized_mode,
    )
    line_to_line_peak_back_emf_v = calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v(
        phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        control_mode=normalized_mode,
    )
    line_to_line_rms_back_emf_v = calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v(
        phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        control_mode=normalized_mode,
    )

    revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s = phase_flat_top_back_emf_v / mechanical_angular_speed_rad_s
    revised_bldc_back_emf_constant_phase_peak_v_per_rad_s = phase_peak_back_emf_v / mechanical_angular_speed_rad_s
    revised_bldc_back_emf_constant_phase_rms_v_per_rad_s = phase_rms_back_emf_v / mechanical_angular_speed_rad_s
    revised_bldc_back_emf_constant_line_rms_v_per_rad_s = line_to_line_rms_back_emf_v / mechanical_angular_speed_rad_s
    revised_bldc_back_emf_constant_line_rms_v_per_krpm = line_to_line_rms_back_emf_v / (mechanical_speed_rpm / 1000.0)

    revised_bldc_torque_constant_nm_per_conduction_a = (
        normalized_bldc_average_electromagnetic_power() * revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s
    )
    revised_bldc_torque_constant_nm_per_phase_rms_a = (
        revised_bldc_torque_constant_nm_per_conduction_a / normalized_bldc_phase_current_rms()
    )

    numeric_phase_rms = _rms_over_cycle(normalized_bldc_phase_back_emf)
    numeric_line_rms = _rms_over_cycle(normalized_bldc_line_to_line_back_emf)
    numeric_phase_current_rms = _rms_over_cycle(normalized_bldc_phase_current)
    numeric_average_power = calculate_bldc_average_electromagnetic_power_from_numeric_integration_w(
        phase_flat_top_back_emf_v=1.0,
        conduction_current_a=1.0,
        control_mode=normalized_mode,
        sample_count=DEFAULT_NUMERIC_SAMPLE_COUNT,
    )

    for actual_value, expected_value, label in (
        (numeric_phase_rms, normalized_bldc_phase_back_emf_rms(), "BLDC phase back EMF RMS"),
        (numeric_line_rms, normalized_bldc_line_to_line_back_emf_rms(), "BLDC line-to-line back EMF RMS"),
        (numeric_phase_current_rms, normalized_bldc_phase_current_rms(), "BLDC phase current RMS"),
        (numeric_average_power, normalized_bldc_average_electromagnetic_power(), "BLDC average electromagnetic power"),
    ):
        if not math.isclose(actual_value, expected_value, rel_tol=NUMERIC_REL_TOL, abs_tol=NUMERIC_ABS_TOL):
            raise MotorCalculationError(
                f"{label} analytic and numeric validation mismatch: {actual_value!r} vs {expected_value!r}."
            )

    converted_line_rms_v_per_krpm = line_rms_v_per_rad_s_to_line_rms_v_per_krpm(
        revised_bldc_back_emf_constant_line_rms_v_per_rad_s
    )
    if not math.isclose(
        converted_line_rms_v_per_krpm,
        revised_bldc_back_emf_constant_line_rms_v_per_krpm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    ):
        raise MotorCalculationError("BLDC revised line RMS Ke unit conversion mismatch.")

    return RevisedBldcKeKtSemantics(
        revised_bldc_phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        revised_bldc_phase_peak_back_emf_v=phase_peak_back_emf_v,
        revised_bldc_phase_rms_back_emf_v=phase_rms_back_emf_v,
        revised_bldc_line_to_line_peak_back_emf_v=line_to_line_peak_back_emf_v,
        revised_bldc_line_to_line_rms_back_emf_v=line_to_line_rms_back_emf_v,
        revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s=revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s,
        revised_bldc_back_emf_constant_phase_peak_v_per_rad_s=revised_bldc_back_emf_constant_phase_peak_v_per_rad_s,
        revised_bldc_back_emf_constant_phase_rms_v_per_rad_s=revised_bldc_back_emf_constant_phase_rms_v_per_rad_s,
        revised_bldc_back_emf_constant_line_rms_v_per_rad_s=revised_bldc_back_emf_constant_line_rms_v_per_rad_s,
        revised_bldc_back_emf_constant_line_rms_v_per_krpm=revised_bldc_back_emf_constant_line_rms_v_per_krpm,
        revised_bldc_torque_constant_nm_per_conduction_a=revised_bldc_torque_constant_nm_per_conduction_a,
        revised_bldc_torque_constant_nm_per_phase_rms_a=revised_bldc_torque_constant_nm_per_phase_rms_a,
        bldc_waveform_semantics_status="ideal_bldc_three_phase_y_120_degree_defined",
        bldc_power_balance_status="validated_from_piecewise_and_numeric_integration",
        bldc_ke_semantics_status="bldc_revised_ke_mechanical_speed_basis",
        bldc_kt_semantics_status="bldc_revised_kt_120_degree_power_balance",
    )
