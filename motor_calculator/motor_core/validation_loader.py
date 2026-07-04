"""JSON loader and unit checks for external validation records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .electrical_semantics import line_rms_v_per_krpm_to_line_rms_v_per_rad_s, line_rms_v_per_rad_s_to_line_rms_v_per_krpm
from .validation_records import (
    SUPPORTED_INPUT_PARAMETER_NAMES,
    SUPPORTED_VALIDATION_METRICS,
    ValidationField,
    ValidationMetricExpectation,
    ValidationRecord,
    ValidationRecordError,
)


class ValidationLoaderError(ValidationRecordError):
    """Raised when a validation record cannot be loaded from JSON."""


INPUT_PARAMETER_ALLOWED_UNITS = {
    "pole_pairs": {None},
    "rated_speed_rpm": {"rpm"},
    "rated_power_w": {"W"},
    "dc_bus_voltage_v": {"V"},
    "phase_current_a": {"A"},
    "winding_connection": {None},
    "back_emf_waveform": {None},
    "stator_outer_diameter_m": {"m", "mm"},
    "stator_inner_diameter_m": {"m", "mm"},
    "air_gap_m": {"m", "mm"},
    "magnet_thickness_m": {"m", "mm"},
    "turns_per_phase": {"turn", "turns", None},
    "winding_factor": {"-"},
    "magnet_remanence_t": {"T"},
}

EXPECTED_OUTPUT_ALLOWED_UNITS = {
    "rated_torque_nm": {"Nm"},
    "back_emf_phase_peak_v": {"V"},
    "back_emf_phase_rms_v": {"V"},
    "back_emf_line_rms_v": {"V"},
    "back_emf_constant_line_rms_v_per_krpm": {"V/krpm", "V/(rad/s)"},
    "torque_constant_nm_per_a": {"Nm/A"},
    "phase_resistance_ohm": {"ohm", "Ω"},
    "phase_inductance_h": {"H"},
    "rated_current_a": {"A"},
    "copper_loss_w": {"W"},
    "iron_loss_w": {"W"},
    "mechanical_loss_w": {"W"},
    "efficiency": {"%", "ratio"},
    "required_voltage_v": {"V"},
}


def convert_value_between_units(value: float, source_unit: str, target_unit: str) -> tuple[float, str]:
    """Convert between explicitly supported units and record the step."""

    if source_unit == target_unit:
        return value, f"单位保持不变：{source_unit}"
    if source_unit == "mm" and target_unit == "m":
        return value / 1000.0, "显式单位转换：mm -> m"
    if source_unit == "m" and target_unit == "mm":
        return value * 1000.0, "显式单位转换：m -> mm"
    if source_unit == "V/krpm" and target_unit == "V/(rad/s)":
        return line_rms_v_per_krpm_to_line_rms_v_per_rad_s(value), "显式单位转换：V/krpm -> V/(rad/s)"
    if source_unit == "V/(rad/s)" and target_unit == "V/krpm":
        return line_rms_v_per_rad_s_to_line_rms_v_per_krpm(value), "显式单位转换：V/(rad/s) -> V/krpm"
    if source_unit == "ratio" and target_unit == "%":
        return value * 100.0, "显式单位转换：ratio -> %"
    if source_unit == "%" and target_unit == "ratio":
        return value / 100.0, "显式单位转换：% -> ratio"
    raise ValidationLoaderError(f"当前不支持从“{source_unit}”到“{target_unit}”的显式单位转换。")


def load_validation_record(record_path: str | Path) -> ValidationRecord:
    path = Path(record_path)
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationLoaderError(f"验证记录文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationLoaderError(f"验证记录 JSON 解析失败：{path}，第 {exc.lineno} 行第 {exc.colno} 列。") from exc

    record = load_validation_record_from_dict(raw_data)
    validate_record_units(record)
    return record


def load_validation_record_from_dict(raw_data: Mapping[str, Any]) -> ValidationRecord:
    record = ValidationRecord.from_dict(raw_data)
    validate_record_units(record)
    return record


def validate_record_units(record: ValidationRecord) -> None:
    for field_name, field_value in record.input_parameters.items():
        _validate_input_parameter_unit(field_name, field_value)

    for metric_name, metric in record.expected_outputs.items():
        _validate_expected_output_unit(metric_name, metric)


def _validate_input_parameter_unit(field_name: str, field_value: ValidationField) -> None:
    if field_name not in SUPPORTED_INPUT_PARAMETER_NAMES:
        raise ValidationLoaderError(f"未注册的输入参数字段：{field_name}")

    allowed_units = INPUT_PARAMETER_ALLOWED_UNITS[field_name]
    if field_value.unit not in allowed_units:
        allowed = ", ".join("null" if unit is None else unit for unit in allowed_units)
        raise ValidationLoaderError(
            f"字段“input_parameters.{field_name}.unit”当前值“{field_value.unit}”无效；允许单位：{allowed}。"
        )


def _validate_expected_output_unit(metric_name: str, metric: ValidationMetricExpectation) -> None:
    if metric_name not in SUPPORTED_VALIDATION_METRICS:
        supported = ", ".join(sorted(SUPPORTED_VALIDATION_METRICS))
        raise ValidationLoaderError(f"未注册的 expected output metric：{metric_name}；当前支持：{supported}。")

    allowed_units = EXPECTED_OUTPUT_ALLOWED_UNITS[metric_name]
    if metric.unit not in allowed_units:
        allowed = ", ".join(sorted(allowed_units))
        raise ValidationLoaderError(
            f"字段“expected_outputs.{metric_name}.unit”当前值“{metric.unit}”无效；允许单位：{allowed}。"
        )
