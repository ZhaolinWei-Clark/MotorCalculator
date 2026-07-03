"""Revised PMSM sinusoidal Ke/Kt semantics derived from explicit units and power balance."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .electrical_semantics import (
    MotorControlMode,
    line_rms_v_per_rad_s_to_line_rms_v_per_krpm,
    mechanical_speed_rpm_to_mechanical_angular_speed_rad_s,
    require_sinusoidal_control_mode,
    sinusoidal_phase_current_peak_a_to_phase_current_rms_a,
    sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v,
    sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v,
)
from .validation import MotorCalculationError

REL_TOL = 1e-8
ABS_TOL = 1e-10


@dataclass(frozen=True)
class RevisedPmsmKeKtSemantics:
    revised_back_emf_constant_phase_peak_v_per_rad_s: float
    revised_back_emf_constant_phase_rms_v_per_rad_s: float
    revised_back_emf_constant_line_rms_v_per_rad_s: float
    revised_back_emf_constant_line_rms_v_per_krpm: float
    revised_torque_constant_nm_per_phase_peak_a: float
    revised_torque_constant_nm_per_phase_rms_a: float
    ke_model_status: str
    kt_model_status: str
    pmsm_power_consistency_status: str
    ke_legacy_revised_relative_difference: float
    kt_legacy_revised_relative_difference: float


def _require_positive_finite(name_zh: str, value: float, unit: str) -> None:
    if math.isnan(value) or math.isinf(value):
        raise MotorCalculationError(f"{name_zh}当前输入为“{value} {unit}”，不能是 NaN 或 inf；建议：输入有限正数。")
    if value <= 0.0:
        raise MotorCalculationError(f"{name_zh}当前输入为“{value} {unit}”，必须大于 0；建议：输入大于 0 的{ name_zh }。")


def calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed(
    back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
    control_mode: MotorControlMode | str,
) -> tuple[float, float, float, float, float]:
    require_sinusoidal_control_mode(control_mode)
    _require_positive_finite("相反电势 RMS 值", back_emf_phase_rms_v, "V")
    _require_positive_finite("机械转速", mechanical_speed_rpm, "rpm")

    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    return calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
        back_emf_phase_rms_v=back_emf_phase_rms_v,
        mechanical_speed_rpm=mechanical_speed_rpm,
        mechanical_angular_speed_rad_s=mechanical_angular_speed_rad_s,
        control_mode=control_mode,
    )


def calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
    back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
    mechanical_angular_speed_rad_s: float,
    control_mode: MotorControlMode | str,
) -> tuple[float, float, float, float, float]:
    require_sinusoidal_control_mode(control_mode)
    _require_positive_finite("相反电势 RMS 值", back_emf_phase_rms_v, "V")
    _require_positive_finite("机械转速", mechanical_speed_rpm, "rpm")
    _require_positive_finite("机械角速度", mechanical_angular_speed_rad_s, "rad/s")

    back_emf_phase_peak_v = sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v(back_emf_phase_rms_v, control_mode)
    back_emf_line_rms_v = sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v(back_emf_phase_rms_v, control_mode)

    revised_back_emf_constant_phase_peak_v_per_rad_s = back_emf_phase_peak_v / mechanical_angular_speed_rad_s
    revised_back_emf_constant_phase_rms_v_per_rad_s = back_emf_phase_rms_v / mechanical_angular_speed_rad_s
    revised_back_emf_constant_line_rms_v_per_rad_s = back_emf_line_rms_v / mechanical_angular_speed_rad_s
    revised_back_emf_constant_line_rms_v_per_krpm = back_emf_line_rms_v / (mechanical_speed_rpm / 1000.0)

    for name_zh, value, unit in (
        ("revised 相峰值反电势常数", revised_back_emf_constant_phase_peak_v_per_rad_s, "V/(rad/s)"),
        ("revised 相 RMS 反电势常数", revised_back_emf_constant_phase_rms_v_per_rad_s, "V/(rad/s)"),
        ("revised 线 RMS 反电势常数", revised_back_emf_constant_line_rms_v_per_rad_s, "V/(rad/s)"),
        ("revised 线 RMS 反电势常数", revised_back_emf_constant_line_rms_v_per_krpm, "V/krpm"),
    ):
        _require_positive_finite(name_zh, value, unit)

    return (
        revised_back_emf_constant_phase_peak_v_per_rad_s,
        revised_back_emf_constant_phase_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_krpm,
        back_emf_phase_peak_v,
    )


def calculate_pmsm_three_phase_electromagnetic_power_w(
    back_emf_phase_peak_v: float,
    phase_current_peak_a: float,
    control_mode: MotorControlMode | str,
) -> float:
    require_sinusoidal_control_mode(control_mode)
    _require_positive_finite("相反电势峰值", back_emf_phase_peak_v, "V")
    _require_positive_finite("相电流峰值", phase_current_peak_a, "A")
    return 1.5 * back_emf_phase_peak_v * phase_current_peak_a


def calculate_mechanical_power_from_torque_and_speed_w(torque_nm: float, mechanical_angular_speed_rad_s: float) -> float:
    _require_positive_finite("转矩", torque_nm, "N·m")
    _require_positive_finite("机械角速度", mechanical_angular_speed_rad_s, "rad/s")
    return torque_nm * mechanical_angular_speed_rad_s


def derive_revised_pmsm_torque_constants_from_power_balance(
    revised_back_emf_constant_phase_peak_v_per_rad_s: float,
    revised_back_emf_constant_phase_rms_v_per_rad_s: float,
    control_mode: MotorControlMode | str,
) -> tuple[float, float]:
    require_sinusoidal_control_mode(control_mode)
    _require_positive_finite("revised 相峰值反电势常数", revised_back_emf_constant_phase_peak_v_per_rad_s, "V/(rad/s)")
    _require_positive_finite("revised 相 RMS 反电势常数", revised_back_emf_constant_phase_rms_v_per_rad_s, "V/(rad/s)")

    revised_torque_constant_nm_per_phase_peak_a = 1.5 * revised_back_emf_constant_phase_peak_v_per_rad_s
    revised_torque_constant_nm_per_phase_rms_a = math.sqrt(2.0) * revised_torque_constant_nm_per_phase_peak_a
    equivalent_revised_torque_constant_nm_per_phase_rms_a = 3.0 * revised_back_emf_constant_phase_rms_v_per_rad_s

    if not math.isclose(
        revised_torque_constant_nm_per_phase_rms_a,
        equivalent_revised_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    ):
        raise MotorCalculationError("PMSM revised Kt 推导未通过代数一致性检查，请检查 RMS/峰值转换和 Ke 定义。")

    return revised_torque_constant_nm_per_phase_peak_a, revised_torque_constant_nm_per_phase_rms_a


def compare_legacy_and_revised_pmsm_ke_kt(
    control_mode: MotorControlMode | str,
    back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
    legacy_back_emf_constant_line_rms_v_per_krpm: float,
    legacy_torque_constant_nm_per_phase_rms_a: float,
) -> RevisedPmsmKeKtSemantics:
    normalized_mode = require_sinusoidal_control_mode(control_mode)
    _require_positive_finite("legacy 线 RMS 反电势常数", legacy_back_emf_constant_line_rms_v_per_krpm, "V/krpm")
    _require_positive_finite("legacy 转矩常数", legacy_torque_constant_nm_per_phase_rms_a, "N·m/A")

    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    (
        revised_back_emf_constant_phase_peak_v_per_rad_s,
        revised_back_emf_constant_phase_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_krpm,
        back_emf_phase_peak_v,
    ) = calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
        back_emf_phase_rms_v=back_emf_phase_rms_v,
        mechanical_speed_rpm=mechanical_speed_rpm,
        mechanical_angular_speed_rad_s=mechanical_angular_speed_rad_s,
        control_mode=normalized_mode,
    )
    revised_torque_constant_nm_per_phase_peak_a, revised_torque_constant_nm_per_phase_rms_a = (
        derive_revised_pmsm_torque_constants_from_power_balance(
            revised_back_emf_constant_phase_peak_v_per_rad_s=revised_back_emf_constant_phase_peak_v_per_rad_s,
            revised_back_emf_constant_phase_rms_v_per_rad_s=revised_back_emf_constant_phase_rms_v_per_rad_s,
            control_mode=normalized_mode,
        )
    )

    sample_phase_current_peak_a = math.sqrt(2.0)
    sample_electromagnetic_power_w = calculate_pmsm_three_phase_electromagnetic_power_w(
        back_emf_phase_peak_v=back_emf_phase_peak_v,
        phase_current_peak_a=sample_phase_current_peak_a,
        control_mode=normalized_mode,
    )
    sample_phase_current_rms_a = sinusoidal_phase_current_peak_a_to_phase_current_rms_a(
        sample_phase_current_peak_a,
        normalized_mode,
    )
    sample_torque_nm = revised_torque_constant_nm_per_phase_rms_a * sample_phase_current_rms_a
    sample_mechanical_power_w = calculate_mechanical_power_from_torque_and_speed_w(
        torque_nm=sample_torque_nm,
        mechanical_angular_speed_rad_s=mechanical_angular_speed_rad_s,
    )
    if not math.isclose(sample_electromagnetic_power_w, sample_mechanical_power_w, rel_tol=REL_TOL, abs_tol=ABS_TOL):
        raise MotorCalculationError("PMSM revised Ke/Kt 未通过功率一致性检查，请检查三相功率推导和机械功率关系。")

    converted_line_rms_v_per_krpm = line_rms_v_per_rad_s_to_line_rms_v_per_krpm(
        revised_back_emf_constant_line_rms_v_per_rad_s
    )
    if not math.isclose(
        converted_line_rms_v_per_krpm,
        revised_back_emf_constant_line_rms_v_per_krpm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    ):
        raise MotorCalculationError("PMSM revised Ke 单位换算不一致，请检查 V/krpm 与 V/(rad/s) 的转换。")

    ke_legacy_revised_relative_difference = abs(
        legacy_back_emf_constant_line_rms_v_per_krpm - revised_back_emf_constant_line_rms_v_per_krpm
    ) / revised_back_emf_constant_line_rms_v_per_krpm
    kt_legacy_revised_relative_difference = abs(
        legacy_torque_constant_nm_per_phase_rms_a - revised_torque_constant_nm_per_phase_rms_a
    ) / revised_torque_constant_nm_per_phase_rms_a

    return RevisedPmsmKeKtSemantics(
        revised_back_emf_constant_phase_peak_v_per_rad_s=revised_back_emf_constant_phase_peak_v_per_rad_s,
        revised_back_emf_constant_phase_rms_v_per_rad_s=revised_back_emf_constant_phase_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_rad_s=revised_back_emf_constant_line_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_krpm=revised_back_emf_constant_line_rms_v_per_krpm,
        revised_torque_constant_nm_per_phase_peak_a=revised_torque_constant_nm_per_phase_peak_a,
        revised_torque_constant_nm_per_phase_rms_a=revised_torque_constant_nm_per_phase_rms_a,
        ke_model_status="pmsm_sinusoidal_mechanical_speed_basis",
        kt_model_status="pmsm_sinusoidal_power_balance_derived",
        pmsm_power_consistency_status="validated_from_three_phase_power_balance",
        ke_legacy_revised_relative_difference=ke_legacy_revised_relative_difference,
        kt_legacy_revised_relative_difference=kt_legacy_revised_relative_difference,
    )
