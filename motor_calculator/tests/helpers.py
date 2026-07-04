"""Shared test helpers for the motor calculator suite."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


def build_sample_legacy_params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "V_dc": 48.0,
        "P_rated": 800.0,
        "n_rated": 2500.0,
        "Temp_coil": 80.0,
        "D_out": 140.0,
        "D_in": 70.0,
        "g_side": 1.0,
        "D_stator_out": 138.0,
        "D_stator_in": 72.0,
        "h_stator": 20.0,
        "h_coil": 5.0,
        "h_yoke": 5.0,
        "slots": 24,
        "slot_type": "无槽",
        "h_slot": 15.0,
        "w_slot_top": 8.0,
        "w_slot_bottom": 6.0,
        "h_slot_opening": 1.0,
        "w_slot_opening": 3.0,
        "h_wedge": 2.0,
        "h_mag": 5.0,
        "w_magnet": 20.0,
        "L_magnet": 30.0,
        "magnet_type": "表贴式",
        "magnetization": "径向充磁",
        "p": 8,
        "magnet_grade": "N42",
        "Br": 1.28,
        "alpha_p": 0.70,
        "sigma_m": 1.15,
        "mu_r_mag": 1.05,
        "N_ph_turns": 50,
        "d_wire": 0.9,
        "n_parallel": 2,
        "k_w": 0.93,
        "fill_limit": 0.65,
        "waveform": "正弦波",
        "k_cogging": 0.02,
        "k_ripple_6": 0.05,
        "k_ripple_12": 0.02,
        "coreless": True,
    }
    params.update(overrides)
    return params


def build_sample_validation_record_dict(**overrides: Any) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "validation_id": "sample_validation_record",
        "source_type": "analytical_reference",
        "evidence_level": "LEVEL_1_ANALYTICAL",
        "motor_type": "AFPM PMSM/BLDC",
        "control_mode": "pmsm_sinusoidal",
        "topology": "双转子、单定子、双气隙",
        "source_title": "Sample analytical record",
        "source_author_or_organization": "Test Suite",
        "source_year": 2026,
        "source_identifier": "test-record",
        "source_file": "validation_data/templates/example_synthetic_record.json",
        "source_page_or_section": "unit-test",
        "license_or_usage_note": "For test use only.",
        "data_quality_notes": "Synthetic analytical data for tests.",
        "model_assumptions": [
            "只用于自动化测试。",
            "不得用于准确度声明。"
        ],
        "input_parameters": {
            "pole_pairs": {"status": "provided", "value": 8, "unit": None, "notes": "测试输入。"},
            "rated_speed_rpm": {"status": "provided", "value": 2500.0, "unit": "rpm", "notes": "测试输入。"},
            "rated_power_w": {"status": "provided", "value": 800.0, "unit": "W", "notes": "测试输入。"},
            "dc_bus_voltage_v": {"status": "provided", "value": 48.0, "unit": "V", "notes": "测试输入。"},
            "phase_current_a": {"status": "provided", "value": 10.0, "unit": "A", "notes": "phase_rms 测试输入。"},
            "winding_connection": {"status": "provided", "value": "Y", "unit": None, "notes": "默认 Y 接。"},
            "back_emf_waveform": {"status": "provided", "value": "sinusoidal", "unit": None, "notes": "PMSM 正弦波。"},
            "stator_outer_diameter_m": {"status": "provided", "value": 0.138, "unit": "m", "notes": "测试输入。"},
            "stator_inner_diameter_m": {"status": "provided", "value": 0.072, "unit": "m", "notes": "测试输入。"},
            "air_gap_m": {"status": "provided", "value": 0.001, "unit": "m", "notes": "测试输入。"},
            "magnet_thickness_m": {"status": "provided", "value": 0.005, "unit": "m", "notes": "测试输入。"},
            "turns_per_phase": {"status": "provided", "value": 50, "unit": "turn", "notes": "测试输入。"},
            "winding_factor": {"status": "provided", "value": 0.93, "unit": "-", "notes": "测试输入。"},
            "magnet_remanence_t": {"status": "provided", "value": 1.28, "unit": "T", "notes": "测试输入。"}
        },
        "expected_outputs": {
            "rated_torque_nm": {
                "metric_name": "rated_torque_nm",
                "status": "provided",
                "value": 3.056,
                "unit": "Nm",
                "quantity_scope": "shaft",
                "value_kind": "average",
                "current_basis": None,
                "notes": "测试 expected。"
            }
        },
        "uncertainty": {
            "rated_torque_nm": {"absolute": 0.05, "relative": 0.02, "coverage_factor": 2.0, "notes": "测试 uncertainty。"}
        },
        "tolerances": {
            "rated_torque_nm": {"absolute": 0.2, "relative": 0.1, "notes": "测试 tolerance。"}
        },
        "excluded_comparisons": {},
        "created_at": "2026-07-04T00:00:00",
        "synthetic": True,
        "not_for_accuracy_claims": True,
        "conversion_log": []
    }
    merged = deepcopy(record)
    for key, value in overrides.items():
        merged[key] = value
    return merged


def validation_data_root() -> Path:
    return Path(__file__).resolve().parents[2] / "validation_data"
