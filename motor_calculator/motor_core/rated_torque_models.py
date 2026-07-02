"""Legacy and strict-SI rated torque comparison helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import LEGACY_POWER_SPEED_TO_TORQUE_FACTOR
from .electrical_semantics import mechanical_speed_rpm_to_mechanical_angular_speed_rad_s
from .validation import MotorCalculationError


def _validate_rated_torque_inputs(rated_power_w: float, mechanical_speed_rpm: float) -> None:
    if rated_power_w <= 0:
        raise MotorCalculationError(
            f"额定输出功率当前输入为“{rated_power_w} W”，必须大于 0；建议：输入大于 0 的额定输出功率。"
        )
    if mechanical_speed_rpm <= 0:
        raise MotorCalculationError(
            f"机械转速当前输入为“{mechanical_speed_rpm} rpm”，必须大于 0；建议：输入大于 0 的机械转速。"
        )


def calculate_legacy_rated_torque_nm(rated_power_w: float, mechanical_speed_rpm: float) -> float:
    _validate_rated_torque_inputs(rated_power_w, mechanical_speed_rpm)
    legacy_rated_torque_nm = LEGACY_POWER_SPEED_TO_TORQUE_FACTOR * rated_power_w / mechanical_speed_rpm
    if math.isnan(legacy_rated_torque_nm) or math.isinf(legacy_rated_torque_nm):
        raise MotorCalculationError("legacy 额定转矩计算结果出现 NaN 或 inf，请检查额定输出功率和机械转速输入。")
    return legacy_rated_torque_nm


def calculate_revised_rated_torque_nm(rated_power_w: float, mechanical_speed_rpm: float) -> float:
    _validate_rated_torque_inputs(rated_power_w, mechanical_speed_rpm)
    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    revised_rated_torque_nm = rated_power_w / mechanical_angular_speed_rad_s
    if math.isnan(revised_rated_torque_nm) or math.isinf(revised_rated_torque_nm):
        raise MotorCalculationError("严格 SI 额定转矩计算结果出现 NaN 或 inf，请检查额定输出功率和机械转速输入。")
    return revised_rated_torque_nm


@dataclass(frozen=True)
class RatedTorqueComparison:
    legacy_rated_torque_nm: float
    revised_rated_torque_nm: float
    rated_torque_absolute_difference_nm: float
    rated_torque_relative_difference: float
    rated_torque_model_status: str


def compare_rated_torque_models(rated_power_w: float, mechanical_speed_rpm: float) -> RatedTorqueComparison:
    legacy_rated_torque_nm = calculate_legacy_rated_torque_nm(rated_power_w, mechanical_speed_rpm)
    revised_rated_torque_nm = calculate_revised_rated_torque_nm(rated_power_w, mechanical_speed_rpm)
    rated_torque_absolute_difference_nm = abs(legacy_rated_torque_nm - revised_rated_torque_nm)
    rated_torque_relative_difference = rated_torque_absolute_difference_nm / revised_rated_torque_nm
    if math.isnan(rated_torque_relative_difference) or math.isinf(rated_torque_relative_difference):
        raise MotorCalculationError("额定转矩相对差值计算结果出现 NaN 或 inf，请检查输入。")
    return RatedTorqueComparison(
        legacy_rated_torque_nm=legacy_rated_torque_nm,
        revised_rated_torque_nm=revised_rated_torque_nm,
        rated_torque_absolute_difference_nm=rated_torque_absolute_difference_nm,
        rated_torque_relative_difference=rated_torque_relative_difference,
        rated_torque_model_status="strict_si_comparison_available",
    )
