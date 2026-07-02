"""Output schema tests for explicit electrical semantics."""

from __future__ import annotations

from motor_core import calculate_from_legacy_params

from helpers import build_sample_legacy_params


def test_analysis_result_contains_explicit_speed_and_electrical_semantic_fields():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="正弦波"))

    assert hasattr(result.electrical, "back_emf_constant_line_rms_v_per_rad_s")
    assert hasattr(result.electrical, "back_emf_constant_line_rms_v_per_krpm")
    assert hasattr(result.electrical, "torque_constant_nm_per_phase_rms_a")
    assert hasattr(result.performance, "mechanical_speed_rpm")
    assert hasattr(result.performance, "mechanical_angular_speed_rad_s")
    assert hasattr(result.performance, "electrical_frequency_hz")
    assert hasattr(result.performance, "electrical_angular_speed_rad_s")
    assert hasattr(result.performance, "legacy_rated_torque_nm")
    assert hasattr(result.performance, "revised_rated_torque_nm")
    assert hasattr(result.performance, "rated_torque_absolute_difference_nm")
    assert hasattr(result.performance, "rated_torque_relative_difference")
    assert hasattr(result.performance, "rated_torque_model_status")
    assert hasattr(result.performance, "dc_bus_current_a")


def test_to_dict_includes_control_mode_metadata():
    result_dict = calculate_from_legacy_params(build_sample_legacy_params(waveform="正弦波")).to_dict()
    metadata = result_dict["元数据"]
    assert "控制模式" in metadata
    assert "legacy控制模型" in metadata
    assert "机械转速_rpm" in metadata
    assert "电频率_Hz" in metadata
