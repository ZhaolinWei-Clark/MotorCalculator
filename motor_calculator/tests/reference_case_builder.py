"""Independent analytical builders for PMSM sinusoidal reference cases.

This module intentionally uses only fixture primitives plus ``math`` so that
reference values stay independent from production calculation functions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "pmsm_reference_cases.json"

DERIVED_FIELDS = (
    "mechanical_angular_speed_rad_s",
    "back_emf_phase_rms_v",
    "back_emf_line_rms_v",
    "phase_current_rms_a",
)

EXPECTED_FIELDS = (
    "expected_ke_phase_peak_v_per_rad_s",
    "expected_ke_phase_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_krpm",
    "expected_kt_phase_peak_nm_per_a",
    "expected_kt_phase_rms_nm_per_a",
    "expected_electromagnetic_power_w",
    "expected_torque_nm",
)

SUPPORTED_SOURCE_TYPES = {
    "analytical_reference",
    "published_reference",
    "user_supplied_measurement",
    "fea_reference",
}


def load_pmsm_reference_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["cases"]


def build_independent_reference_values(case: dict[str, Any]) -> dict[str, float]:
    mechanical_speed_rpm = float(case["mechanical_speed_rpm"])
    back_emf_phase_peak_v = float(case["back_emf_phase_peak_v"])
    phase_current_peak_a = float(case["phase_current_peak_a"])

    mechanical_angular_speed_rad_s = mechanical_speed_rpm * 2.0 * math.pi / 60.0
    back_emf_phase_rms_v = back_emf_phase_peak_v / math.sqrt(2.0)
    back_emf_line_rms_v = math.sqrt(3.0) * back_emf_phase_rms_v
    phase_current_rms_a = phase_current_peak_a / math.sqrt(2.0)

    expected_ke_phase_peak_v_per_rad_s = back_emf_phase_peak_v / mechanical_angular_speed_rad_s
    expected_ke_phase_rms_v_per_rad_s = back_emf_phase_rms_v / mechanical_angular_speed_rad_s
    expected_ke_line_rms_v_per_rad_s = back_emf_line_rms_v / mechanical_angular_speed_rad_s
    expected_ke_line_rms_v_per_krpm = back_emf_line_rms_v / (mechanical_speed_rpm / 1000.0)
    expected_kt_phase_peak_nm_per_a = 1.5 * expected_ke_phase_peak_v_per_rad_s
    expected_kt_phase_rms_nm_per_a = math.sqrt(2.0) * expected_kt_phase_peak_nm_per_a
    expected_electromagnetic_power_w = 1.5 * back_emf_phase_peak_v * phase_current_peak_a
    expected_torque_nm = expected_electromagnetic_power_w / mechanical_angular_speed_rad_s

    return {
        "mechanical_angular_speed_rad_s": mechanical_angular_speed_rad_s,
        "back_emf_phase_rms_v": back_emf_phase_rms_v,
        "back_emf_line_rms_v": back_emf_line_rms_v,
        "phase_current_rms_a": phase_current_rms_a,
        "expected_ke_phase_peak_v_per_rad_s": expected_ke_phase_peak_v_per_rad_s,
        "expected_ke_phase_rms_v_per_rad_s": expected_ke_phase_rms_v_per_rad_s,
        "expected_ke_line_rms_v_per_rad_s": expected_ke_line_rms_v_per_rad_s,
        "expected_ke_line_rms_v_per_krpm": expected_ke_line_rms_v_per_krpm,
        "expected_kt_phase_peak_nm_per_a": expected_kt_phase_peak_nm_per_a,
        "expected_kt_phase_rms_nm_per_a": expected_kt_phase_rms_nm_per_a,
        "expected_electromagnetic_power_w": expected_electromagnetic_power_w,
        "expected_torque_nm": expected_torque_nm,
    }
