"""Input parsing and validation with explicit Chinese error messages."""

from __future__ import annotations

import math
from dataclasses import fields
from typing import Any, Dict, Mapping

from .constants import SLOT_TYPES
from .electrical_semantics import MotorControlMode
from .models import MotorAnalysisInput


class MotorCalculatorError(Exception):
    """Base error for the refactored motor calculator."""


class MotorValidationError(MotorCalculatorError):
    """Raised when user input is invalid or physically inconsistent."""


class MotorCalculationError(MotorCalculatorError):
    """Raised when the calculation layer produces invalid outputs."""


NUMERIC_FIELD_SPECS = {
    "V_dc": {"label": "直流母线电压", "kind": "float", "min": 0.0, "unit": "V", "suggestion": "请输入大于 0 的电压，例如 48.0。"},
    "P_rated": {"label": "额定输出功率", "kind": "float", "min": 0.0, "unit": "W", "suggestion": "请输入大于 0 的功率，例如 800。"},
    "n_rated": {"label": "额定转速", "kind": "float", "min": 0.0, "unit": "rpm", "suggestion": "请输入大于 0 的转速，例如 2500。"},
    "Temp_coil": {"label": "绕组温度", "kind": "float", "unit": "°C", "suggestion": "请输入数值温度，例如 80。"},
    "D_out": {"label": "电机外径", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的外径，例如 140。"},
    "D_in": {"label": "电机内径", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的内径，例如 70。"},
    "g_side": {"label": "单侧机械气隙", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的单侧气隙，例如 1.0。"},
    "D_stator_out": {"label": "定子外径", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的定子外径。"},
    "D_stator_in": {"label": "定子内径", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的定子内径。"},
    "h_stator": {"label": "定子叠厚", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的定子叠厚。"},
    "h_coil": {"label": "线圈高度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的线圈高度。"},
    "h_yoke": {"label": "轭部高度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负轭部高度。"},
    "slots": {"label": "槽数", "kind": "int", "min": 0, "unit": "个", "suggestion": "请输入正整数槽数，例如 24。"},
    "h_slot": {"label": "槽深", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽深。"},
    "w_slot_top": {"label": "槽口宽度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽口宽度。"},
    "w_slot_bottom": {"label": "槽底宽度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽底宽度。"},
    "h_slot_opening": {"label": "槽口高度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽口高度。"},
    "w_slot_opening": {"label": "槽口开口宽度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽口开口宽度。"},
    "h_wedge": {"label": "槽楔高度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入非负槽楔高度。"},
    "h_mag": {"label": "磁钢厚度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的磁钢厚度。"},
    "w_magnet": {"label": "磁钢周向宽度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的磁钢宽度。"},
    "L_magnet": {"label": "磁钢长度", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的磁钢长度。"},
    "p": {"label": "极对数", "kind": "int", "min": 0, "unit": "对", "suggestion": "请输入正整数极对数，例如 8。"},
    "Br": {"label": "剩磁", "kind": "float", "min": 0.0, "unit": "T", "suggestion": "请输入大于 0 的剩磁。"},
    "alpha_p": {"label": "极弧系数", "kind": "float", "min": 0.0, "max": 1.0, "unit": "-", "suggestion": "请输入 0 到 1 之间的极弧系数，例如 0.7。"},
    "sigma_m": {"label": "漏磁系数", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入大于 0 的漏磁系数，例如 1.15。"},
    "mu_r_mag": {"label": "磁钢相对磁导率", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入大于 0 的相对磁导率，例如 1.05。"},
    "N_ph_turns": {"label": "每相匝数", "kind": "int", "min": 0, "unit": "匝", "suggestion": "请输入正整数匝数，例如 50。"},
    "d_wire": {"label": "导线直径", "kind": "float", "min": 0.0, "unit": "mm", "suggestion": "请输入大于 0 的导线直径，例如 0.9。"},
    "n_parallel": {"label": "并联支路数", "kind": "int", "min": 0, "unit": "路", "suggestion": "请输入正整数并联支路数，例如 2。"},
    "k_w": {"label": "绕组系数", "kind": "float", "min": 0.0, "max": 1.0, "unit": "-", "suggestion": "请输入 0 到 1 之间的绕组系数，例如 0.93。"},
    "fill_limit": {"label": "填充系数限制", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入正数填充系数限制，例如 0.65。"},
    "k_cogging": {"label": "齿槽转矩系数", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入非负齿槽转矩系数。"},
    "k_ripple_6": {"label": "6 次谐波转矩系数", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入非负 6 次谐波系数。"},
    "k_ripple_12": {"label": "12 次谐波转矩系数", "kind": "float", "min": 0.0, "unit": "-", "suggestion": "请输入非负 12 次谐波系数。"},
}

TEXT_FIELD_DEFAULTS = {
    "slot_type": "无槽",
    "magnet_type": "表贴式",
    "magnetization": "径向充磁",
    "magnet_grade": "N42",
    "waveform": "正弦波",
}


def _format_range(spec: Mapping[str, Any]) -> str:
    lower = spec.get("min")
    upper = spec.get("max")
    if lower is not None and upper is not None:
        return f"({lower}, {upper}]"
    if lower is not None:
        return f"> {lower}"
    if upper is not None:
        return f"<= {upper}"
    return "有效数值"


def _raise_invalid_value(spec: Mapping[str, Any], raw_value: Any, reason: str) -> None:
    label = spec["label"]
    allowed_range = _format_range(spec)
    suggestion = spec["suggestion"]
    raise MotorValidationError(
        f"参数“{label}”当前输入为“{raw_value}”，{reason}；合法范围为 {allowed_range} {spec.get('unit', '')}。建议：{suggestion}"
    )


def _parse_numeric_field(key: str, raw_value: Any) -> Any:
    spec = NUMERIC_FIELD_SPECS[key]
    if raw_value is None or str(raw_value).strip() == "":
        _raise_invalid_value(spec, raw_value, "不能为空")

    try:
        parsed = int(str(raw_value).strip()) if spec["kind"] == "int" else float(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise MotorValidationError(
            f"参数“{spec['label']}”当前输入为“{raw_value}”，不是可识别的数值；"
            f"合法范围为 {_format_range(spec)} {spec.get('unit', '')}。建议：{spec['suggestion']}"
        ) from exc

    if isinstance(parsed, float) and (math.isnan(parsed) or math.isinf(parsed)):
        _raise_invalid_value(spec, raw_value, "不能是 NaN 或无穷大")

    lower = spec.get("min")
    upper = spec.get("max")
    if lower is not None and parsed <= lower:
        _raise_invalid_value(spec, raw_value, "超出下限")
    if upper is not None and parsed > upper:
        _raise_invalid_value(spec, raw_value, "超出上限")

    return parsed


def parse_legacy_gui_params(raw_values: Mapping[str, Any]) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for key in NUMERIC_FIELD_SPECS:
        if key in raw_values:
            parsed[key] = _parse_numeric_field(key, raw_values[key])

    for key, default_value in TEXT_FIELD_DEFAULTS.items():
        raw_value = raw_values.get(key, default_value)
        parsed[key] = default_value if raw_value is None or str(raw_value).strip() == "" else str(raw_value).strip()

    parsed["coreless"] = bool(raw_values.get("coreless", True))
    return parsed


def validate_motor_input(motor_input: MotorAnalysisInput) -> None:
    if not isinstance(motor_input.control_mode, MotorControlMode):
        raise MotorValidationError(
            f"控制模式当前输入为“{motor_input.control_mode}”，无法识别；建议：使用 PMSM_SINUSOIDAL 或 BLDC_120_DEGREE。"
        )

    if motor_input.outer_diameter_m <= motor_input.inner_diameter_m:
        raise MotorValidationError(
            f"参数“电机外径/内径”当前输入为“{motor_input.outer_diameter_m} m / {motor_input.inner_diameter_m} m”，"
            "外径必须大于内径；合法范围为 外径 > 内径。建议：增大外径或减小内径。"
        )

    positive_fields = {
        "单侧气隙": motor_input.air_gap_per_side_m,
        "磁钢厚度": motor_input.magnet_thickness_m,
        "导线直径": motor_input.wire_diameter_m,
        "线圈高度": motor_input.coil_height_m,
        "额定转速": motor_input.rated_speed_rpm,
        "额定功率": motor_input.rated_output_power_w,
        "直流母线电压": motor_input.dc_bus_voltage_v,
        "磁钢剩磁": motor_input.remanence_t,
        "漏磁系数": motor_input.leakage_factor,
        "卡特/槽型等效系数": SLOT_TYPES.get(motor_input.slot_type, {"carter_factor": 1.0})["carter_factor"],
        "磁钢相对磁导率": motor_input.magnet_relative_permeability,
    }
    for label, value in positive_fields.items():
        if value <= 0.0:
            raise MotorValidationError(
                f"参数“{label}”当前输入为“{value}”，必须大于 0；合法范围为 > 0。建议：请输入正数。"
            )

    integer_fields = {
        "极对数": motor_input.pole_pairs,
        "槽数": motor_input.slot_count,
        "每相匝数": motor_input.turns_per_phase,
        "并联支路数": motor_input.parallel_paths,
    }
    for label, value in integer_fields.items():
        if int(value) != value or value < 1:
            raise MotorValidationError(
                f"参数“{label}”当前输入为“{value}”，必须为正整数；合法范围为 1, 2, 3 ...。建议：输入正整数。"
            )

    if not (0.0 < motor_input.pole_arc_coefficient <= 1.0):
        raise MotorValidationError(
            f"参数“极弧系数”当前输入为“{motor_input.pole_arc_coefficient}”，必须满足 0 < alpha_p <= 1。建议：例如输入 0.7。"
        )
    if not (0.0 < motor_input.winding_factor <= 1.0):
        raise MotorValidationError(
            f"参数“绕组系数”当前输入为“{motor_input.winding_factor}”，必须满足 0 < kw <= 1。建议：例如输入 0.93。"
        )


def validate_finite_result(name: str, value: float) -> None:
    if math.isnan(value) or math.isinf(value):
        raise MotorCalculationError(
            f"计算结果“{name}”出现了 NaN 或无穷大，通常表示输入触发了除零、负面积或无效磁阻。建议：检查尺寸、极对数、匝数和气隙。"
        )


def validate_result_object_finite(result_object: Any) -> None:
    for field in fields(result_object):
        value = getattr(result_object, field.name)
        if isinstance(value, (float, int)):
            validate_finite_result(field.name, float(value))
