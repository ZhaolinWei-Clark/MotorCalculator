from __future__ import annotations

import math
from pathlib import Path

import pytest

from motor_calculator.analysis_service import (
    AnalysisUnavailableError,
    DynamicAnalysisSettings,
    UncertaintyAnalysisSettings,
    dynamic_analysis_availability,
    run_dynamic_analysis,
    run_sensitivity_analysis,
)
from motor_calculator.dynamics import SimulationAccuracy
from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core import MotorAnalysisEngine
from motor_calculator.motor_core.units import legacy_params_to_model_input
from motor_calculator.plots import dynamic_result_to_plot_data
from motor_calculator.version import APPLICATION_VERSION, RELEASE_CHANNEL, windows_version_tuple


ROOT = Path(__file__).resolve().parents[2]


def _pmsm_case():
    inputs = dict(APPLICATION_DEFAULTS)
    model_input = legacy_params_to_model_input(inputs)
    result = MotorAnalysisEngine(model_input).run_full_analysis()
    return inputs, model_input, result


def test_rc_version_uses_one_authoritative_prerelease_value() -> None:
    assert APPLICATION_VERSION == "1.0.0-rc3"
    assert RELEASE_CHANNEL == "release-candidate"
    assert windows_version_tuple() == (1, 0, 0, 3)


def test_dynamic_gui_mapping_is_available_only_after_current_pmsm_calculation() -> None:
    inputs, _model_input, result = _pmsm_case()
    assert dynamic_analysis_availability(inputs, result)[0]
    assert not dynamic_analysis_availability(inputs, None)[0]
    bldc = dict(inputs, waveform="梯形波")
    assert dynamic_analysis_availability(bldc, result) == (
        False,
        "当前动态 GUI 仅支持 PMSM；BLDC 动态模型尚未实现。",
    )


@pytest.mark.parametrize(
    "accuracy",
    (SimulationAccuracy.FAST, SimulationAccuracy.BALANCED, SimulationAccuracy.HIGH_ACCURACY),
)
def test_dynamic_accuracy_presets_run_existing_coupled_engine(accuracy) -> None:
    inputs, _model_input, result = _pmsm_case()
    original_inputs = dict(inputs)
    outcome = run_dynamic_analysis(
        inputs,
        result,
        DynamicAnalysisSettings(
            simulation_time_s=0.02,
            speed_reference_rpm=200.0,
            load_torque_nm=0.0,
            accuracy_level=accuracy,
        ),
    )
    assert inputs == original_inputs
    assert outcome.result.time[-1] == pytest.approx(0.02)
    assert all(math.isfinite(value) for series in outcome.result.numeric_series for value in series)
    assert outcome.mapping_notes and "Ld=Lq" in outcome.mapping_notes[1]


def test_dynamic_plot_adapter_includes_speed_current_torque_and_actual_voltage() -> None:
    inputs, _model_input, result = _pmsm_case()
    outcome = run_dynamic_analysis(
        inputs,
        result,
        DynamicAnalysisSettings(simulation_time_s=0.02, speed_reference_rpm=200.0),
    )
    data = dynamic_result_to_plot_data(outcome.result)
    assert {
        "dynamic_speed",
        "dynamic_speed_reference",
        "dynamic_torque",
        "dynamic_id",
        "dynamic_iq",
        "dynamic_vd",
        "dynamic_vq",
    }.issubset({series.key for series in data.series})


def test_dynamic_invalid_or_unsupported_request_fails_explicitly() -> None:
    inputs, _model_input, result = _pmsm_case()
    with pytest.raises(ValueError):
        DynamicAnalysisSettings(simulation_time_s=0.0)
    with pytest.raises(AnalysisUnavailableError, match="BLDC"):
        run_dynamic_analysis(dict(inputs, waveform="梯形波"), result, DynamicAnalysisSettings())


def test_sensitivity_gui_service_remains_copy_only() -> None:
    inputs, _model_input, _result = _pmsm_case()
    original = dict(inputs)
    summary = run_sensitivity_analysis(inputs, "air_gap_m", "rated_torque_nm")
    assert inputs == original
    assert len(summary.run_results) == 4
    assert summary.boundary_warnings


def test_uncertainty_settings_bound_runtime_without_new_probability_semantics() -> None:
    assert UncertaintyAnalysisSettings(500, 7).sample_count == 500
    with pytest.raises(ValueError):
        UncertaintyAnalysisSettings(1, 7)
    with pytest.raises(ValueError):
        UncertaintyAnalysisSettings(500, True)


def test_packaging_collects_analysis_gui_and_uses_numeric_file_version() -> None:
    spec = (ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "MotorCalculator.iss").read_text(encoding="utf-8")
    build = (ROOT / "work" / "build_windows_release.ps1").read_text(encoding="utf-8")
    assert "motor_calculator.gui.analysis_dialogs" in spec
    assert "motor_calculator.plots.analysis" in spec
    assert "VersionInfoVersion={#AppFileVersion}" in installer
    assert "/DAppFileVersion=$FileVersion" in build


def test_diagnostics_exposes_model_availability_without_project_contents(tmp_path, monkeypatch) -> None:
    from motor_calculator.runtime.diagnostics import build_diagnostics
    from motor_calculator.runtime.paths import resolve_runtime_paths

    monkeypatch.setenv("MOTOR_CALCULATOR_USER_DATA", str(tmp_path / "userdata"))
    diagnostics = build_diagnostics(resolve_runtime_paths())
    assert diagnostics["model_availability"]["pmsm_dynamic_sandbox"] == "EXPERIMENTAL"
    assert diagnostics["model_availability"]["bldc_dynamic"] == "UNAVAILABLE"
    assert "project_inputs" not in diagnostics


def test_production_physics_files_remain_frozen() -> None:
    from motor_calculator.deployment import verify_protected_files

    verified = verify_protected_files(ROOT)
    assert verified["motor_calculator/motor_core/calculations.py"] == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )
    assert verified["motor_calculator/tests/fixtures/legacy_baseline.json"] == (
        "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
    )
