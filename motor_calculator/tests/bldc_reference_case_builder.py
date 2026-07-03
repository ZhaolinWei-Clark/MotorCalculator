"""Independent analytical builders for ideal BLDC 120-degree reference cases."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "bldc_reference_cases.json"
DEFAULT_NUMERIC_SAMPLE_COUNT = 36000
TWO_PI = 2.0 * math.pi
ONE_SIXTH_PI = math.pi / 6.0
FIVE_SIXTHS_PI = 5.0 * math.pi / 6.0
SEVEN_SIXTHS_PI = 7.0 * math.pi / 6.0
ELEVEN_SIXTHS_PI = 11.0 * math.pi / 6.0
TWO_THIRDS_PI = 2.0 * math.pi / 3.0

DERIVED_FIELDS = (
    "mechanical_angular_speed_rad_s",
    "phase_peak_back_emf_v",
    "expected_phase_back_emf_rms_v",
    "expected_line_to_line_peak_back_emf_v",
    "expected_line_back_emf_rms_v",
    "expected_phase_current_rms_a",
    "numeric_phase_back_emf_rms_v",
    "numeric_line_back_emf_rms_v",
    "numeric_phase_current_rms_a",
    "numeric_average_electromagnetic_power_w",
)

EXPECTED_FIELDS = (
    "expected_ke_phase_flat_top_v_per_rad_s",
    "expected_ke_phase_peak_v_per_rad_s",
    "expected_ke_phase_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_krpm",
    "expected_kt_conduction_nm_per_a",
    "expected_kt_phase_rms_nm_per_a",
    "expected_average_electromagnetic_power_w",
    "expected_torque_nm",
)

SUPPORTED_SOURCE_TYPES = {
    "analytical_reference",
    "published_reference",
    "user_supplied_measurement",
    "fea_reference",
}


def load_bldc_reference_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["cases"]


def _normalized_bldc_phase_back_emf(electrical_angle_rad: float) -> float:
    theta = electrical_angle_rad % TWO_PI
    if theta < ONE_SIXTH_PI:
        return 6.0 * theta / math.pi
    if theta < FIVE_SIXTHS_PI:
        return 1.0
    if theta < SEVEN_SIXTHS_PI:
        return 1.0 - 6.0 * (theta - FIVE_SIXTHS_PI) / math.pi
    if theta < ELEVEN_SIXTHS_PI:
        return -1.0
    return -1.0 + 6.0 * (theta - ELEVEN_SIXTHS_PI) / math.pi


def _normalized_bldc_phase_current(electrical_angle_rad: float) -> float:
    theta = electrical_angle_rad % TWO_PI
    if theta < ONE_SIXTH_PI:
        return 0.0
    if theta < FIVE_SIXTHS_PI:
        return 1.0
    if theta < SEVEN_SIXTHS_PI:
        return 0.0
    if theta < ELEVEN_SIXTHS_PI:
        return -1.0
    return 0.0


def _average_over_cycle(function, sample_count: int = DEFAULT_NUMERIC_SAMPLE_COUNT) -> float:
    total = 0.0
    for index in range(sample_count):
        theta = TWO_PI * (index + 0.5) / sample_count
        total += function(theta)
    return total / sample_count


def _rms_over_cycle(function, sample_count: int = DEFAULT_NUMERIC_SAMPLE_COUNT) -> float:
    return math.sqrt(_average_over_cycle(lambda theta: function(theta) ** 2, sample_count=sample_count))


def build_independent_bldc_reference_values(case: dict[str, Any]) -> dict[str, float]:
    mechanical_speed_rpm = float(case["mechanical_speed_rpm"])
    phase_flat_top_back_emf_v = float(case["phase_flat_top_back_emf_v"])
    conduction_current_a = float(case["conduction_current_a"])

    mechanical_angular_speed_rad_s = mechanical_speed_rpm * 2.0 * math.pi / 60.0
    phase_peak_back_emf_v = phase_flat_top_back_emf_v
    expected_phase_back_emf_rms_v = phase_flat_top_back_emf_v * math.sqrt(7.0) / 3.0
    expected_line_to_line_peak_back_emf_v = 2.0 * phase_flat_top_back_emf_v
    expected_line_back_emf_rms_v = phase_flat_top_back_emf_v * 2.0 * math.sqrt(5.0) / 3.0
    expected_phase_current_rms_a = conduction_current_a * math.sqrt(2.0 / 3.0)

    expected_ke_phase_flat_top_v_per_rad_s = phase_flat_top_back_emf_v / mechanical_angular_speed_rad_s
    expected_ke_phase_peak_v_per_rad_s = phase_peak_back_emf_v / mechanical_angular_speed_rad_s
    expected_ke_phase_rms_v_per_rad_s = expected_phase_back_emf_rms_v / mechanical_angular_speed_rad_s
    expected_ke_line_rms_v_per_rad_s = expected_line_back_emf_rms_v / mechanical_angular_speed_rad_s
    expected_ke_line_rms_v_per_krpm = expected_line_back_emf_rms_v / (mechanical_speed_rpm / 1000.0)

    expected_kt_conduction_nm_per_a = 2.0 * expected_ke_phase_flat_top_v_per_rad_s
    expected_kt_phase_rms_nm_per_a = expected_kt_conduction_nm_per_a / math.sqrt(2.0 / 3.0)
    expected_average_electromagnetic_power_w = 2.0 * phase_flat_top_back_emf_v * conduction_current_a
    expected_torque_nm = expected_average_electromagnetic_power_w / mechanical_angular_speed_rad_s

    numeric_phase_back_emf_rms_v = phase_flat_top_back_emf_v * _rms_over_cycle(_normalized_bldc_phase_back_emf)
    numeric_line_back_emf_rms_v = phase_flat_top_back_emf_v * _rms_over_cycle(
        lambda theta: _normalized_bldc_phase_back_emf(theta) - _normalized_bldc_phase_back_emf(theta - TWO_THIRDS_PI)
    )
    numeric_phase_current_rms_a = conduction_current_a * _rms_over_cycle(_normalized_bldc_phase_current)
    numeric_average_electromagnetic_power_w = phase_flat_top_back_emf_v * conduction_current_a * _average_over_cycle(
        lambda theta: (
            _normalized_bldc_phase_back_emf(theta) * _normalized_bldc_phase_current(theta)
            + _normalized_bldc_phase_back_emf(theta - TWO_THIRDS_PI) * _normalized_bldc_phase_current(theta - TWO_THIRDS_PI)
            + _normalized_bldc_phase_back_emf(theta + TWO_THIRDS_PI) * _normalized_bldc_phase_current(theta + TWO_THIRDS_PI)
        )
    )

    return {
        "mechanical_angular_speed_rad_s": mechanical_angular_speed_rad_s,
        "phase_peak_back_emf_v": phase_peak_back_emf_v,
        "expected_phase_back_emf_rms_v": expected_phase_back_emf_rms_v,
        "expected_line_to_line_peak_back_emf_v": expected_line_to_line_peak_back_emf_v,
        "expected_line_back_emf_rms_v": expected_line_back_emf_rms_v,
        "expected_phase_current_rms_a": expected_phase_current_rms_a,
        "expected_ke_phase_flat_top_v_per_rad_s": expected_ke_phase_flat_top_v_per_rad_s,
        "expected_ke_phase_peak_v_per_rad_s": expected_ke_phase_peak_v_per_rad_s,
        "expected_ke_phase_rms_v_per_rad_s": expected_ke_phase_rms_v_per_rad_s,
        "expected_ke_line_rms_v_per_rad_s": expected_ke_line_rms_v_per_rad_s,
        "expected_ke_line_rms_v_per_krpm": expected_ke_line_rms_v_per_krpm,
        "expected_kt_conduction_nm_per_a": expected_kt_conduction_nm_per_a,
        "expected_kt_phase_rms_nm_per_a": expected_kt_phase_rms_nm_per_a,
        "expected_average_electromagnetic_power_w": expected_average_electromagnetic_power_w,
        "expected_torque_nm": expected_torque_nm,
        "numeric_phase_back_emf_rms_v": numeric_phase_back_emf_rms_v,
        "numeric_line_back_emf_rms_v": numeric_line_back_emf_rms_v,
        "numeric_phase_current_rms_a": numeric_phase_current_rms_a,
        "numeric_average_electromagnetic_power_w": numeric_average_electromagnetic_power_w,
    }
