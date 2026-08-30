"""Phase 8H dashboard-domain, sweep, adapter, export, and snapshot tests."""

from __future__ import annotations

import csv
import os
from pathlib import Path
import subprocess
import sys

import pytest

from motor_calculator.calibration_sandbox.perturbation import PerturbationSpec
from motor_calculator.calibration_sandbox.sensitivity import (
    SensitivityOutputChange,
    SensitivityRunResult,
)
from motor_calculator.dynamics import SimulationResult
from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.plots import (
    AvailabilityStatus,
    DashboardStatus,
    OUTPUT_INVENTORY,
    assess_result_snapshot,
    build_dashboard_data,
    build_result_snapshot,
    build_speed_sweep_series,
    configure_chinese_matplotlib,
    downsample_plot_series,
    dynamic_result_to_plot_data,
    evaluate_speed_points,
    export_figure,
    export_speed_sweep_csv,
    inventory_by_key,
    render_speed_sweep_figure,
    run_speed_sweep,
    sensitivity_results_to_plot_data,
    uncertainty_result_to_plot_data,
)
from motor_calculator.plots.models import PlotSeries
from motor_calculator.presets import apply_preset, default_preset_registry
from motor_calculator.project import build_project_inputs
from motor_calculator.project import create_project_document, load_project, save_project
from motor_calculator.validation.design_feasibility import evaluate_design_feasibility
from motor_calculator.validation.uncertainty_models import (
    AccuracyEnvelopeResult,
    ModelFormUncertaintyStatus,
    ResultConfidence,
)
from motor_calculator.version import APPLICATION_VERSION
from motor_calculator.gui.main_window import _smoke_tk_scaling_argument


ROOT = Path(__file__).resolve().parents[2]


def _feasible_inputs() -> dict[str, object]:
    preset = default_preset_registry().get("design.manufacturability_start.v1")
    return apply_preset(APPLICATION_DEFAULTS, preset)


def _run(parameters):
    parsed = parse_legacy_gui_params(parameters)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return result, evaluate_design_feasibility(parsed, result)


def test_plots_package_imports_directly_without_duplicate_motor_core_state() -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    command = (
        "import sys; import motor_calculator.plots as plots; "
        "assert 'motor_calculator.motor_core' in sys.modules; "
        "assert 'motor_core' not in sys.modules; print(len(plots.OUTPUT_INVENTORY))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(len(OUTPUT_INVENTORY))


def test_output_inventory_is_unique_and_explains_unavailable_metrics() -> None:
    indexed = inventory_by_key()
    assert len(indexed) == len(OUTPUT_INVENTORY)
    assert {"rated_torque_nm", "voltage_margin_percent", "static_temperature_rise"} <= set(indexed)
    assert indexed["static_temperature_rise"].unavailable_reason
    assert indexed["dynamic_speed"].mode == "dynamic sandbox"


def test_feasible_baseline_dashboard_preserves_phase8g_values() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    dashboard = build_dashboard_data(parameters, result, assessment)
    metrics = dashboard.metric_by_key
    assert metrics["rated_torque_nm"].value == pytest.approx(2.6045454545)
    assert metrics["output_power_w"].value == pytest.approx(600.0)
    assert metrics["efficiency_percent"].value == pytest.approx(89.5909, rel=1e-4)
    assert metrics["current_density_a_per_mm2"].value == pytest.approx(4.3399, rel=1e-4)
    assert metrics["slot_fill_factor"].value == pytest.approx(0.3176891447)
    assert metrics["voltage_margin_percent"].value == pytest.approx(15.62548387)
    assert dashboard.design_status.severe_count == 0
    assert dashboard.design_status.warning_count == 0
    assert all(metric.status not in {DashboardStatus.WARNING, DashboardStatus.SEVERE} for metric in dashboard.feasibility_metrics)


def test_bad_design_exposes_severe_contributors_without_a_fake_score() -> None:
    parameters = dict(_feasible_inputs(), V_dc=48.0, P_rated=10000.0, N_ph_turns=200)
    result, assessment = _run(parameters)
    dashboard = build_dashboard_data(parameters, result, assessment)
    assert dashboard.design_status.severe_count >= 3
    assert dashboard.metric_by_key["design_status"].status is DashboardStatus.SEVERE
    assert "评分" not in dashboard.metric_by_key["design_status"].display_value


def test_loss_metrics_map_one_to_one_to_existing_outputs() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    metrics = build_dashboard_data(parameters, result, assessment).metric_by_key
    assert metrics["copper_loss_w"].value == result.performance.copper_loss_w
    assert metrics["eddy_loss_w"].value == result.performance.eddy_loss_w
    assert metrics["mechanical_loss_w"].value == result.performance.mechanical_loss_w
    assert metrics["core_loss_w"].value == result.performance.core_loss_w


def test_speed_sweep_uses_real_model_points_and_does_not_mutate_inputs() -> None:
    parameters = _feasible_inputs()
    original = dict(parameters)
    speeds = (1200.0, float(parameters["n_rated"]), 3000.0)
    sweep = evaluate_speed_points(parameters, speeds)
    expected, _ = _run(parameters)
    assert parameters == original
    assert sweep.points[1].torque_nm == pytest.approx(expected.performance.rated_torque_nm)
    assert sweep.points[1].output_power_w == pytest.approx(expected.performance.output_power_w)
    assert sweep.points[1].required_voltage_line_rms_v == pytest.approx(expected.performance.required_voltage_v)
    assert all(point.availability is AvailabilityStatus.AVAILABLE for point in sweep.points)


def test_speed_sweep_invalid_point_remains_an_explicit_gap() -> None:
    sweep = evaluate_speed_points(_feasible_inputs(), (0.0, 2200.0))
    assert sweep.points[0].availability is AvailabilityStatus.INVALID
    assert sweep.points[0].torque_nm is None
    assert sweep.points[0].message_zh
    torque = {series.key: series for series in build_speed_sweep_series(sweep)}["torque_speed"]
    assert torque.y_values[0] is None


def test_speed_sweep_bounds_and_count_are_validated() -> None:
    with pytest.raises(ValueError):
        run_speed_sweep(_feasible_inputs(), 2000.0, 1000.0)
    with pytest.raises(ValueError):
        run_speed_sweep(_feasible_inputs(), 1000.0, 2000.0, 1)


def test_bldc_sweep_keeps_voltage_margin_explicitly_unavailable() -> None:
    sweep = evaluate_speed_points(dict(_feasible_inputs(), waveform="梯形波"), (1500.0, 2200.0))
    series = {item.key: item for item in build_speed_sweep_series(sweep)}
    assert sweep.control_mode == "BLDC"
    assert series["voltage_margin"].availability is AvailabilityStatus.UNAVAILABLE
    assert "BLDC" in series["voltage_margin"].unavailable_reason_zh
    assert series["torque_speed"].availability is AvailabilityStatus.AVAILABLE


def test_dynamic_adapter_preserves_source_samples() -> None:
    result = SimulationResult(
        time=(0.0, 0.1, 0.2), id=(0.0, 1.0, 2.0), iq=(0.0, 2.0, 3.0),
        speed=(0.0, 4.0, 8.0), position=(0.0, 0.2, 0.8), torque=(0.0, 0.5, 0.7),
        electrical_power=(0.0, 3.0, 8.0), mechanical_power=(0.0, 2.0, 5.6),
    )
    data = dynamic_result_to_plot_data(result)
    assert data.source_status == "success"
    assert data.series[0].x_values == result.time
    assert {series.key for series in data.series} == {"dynamic_speed", "dynamic_torque", "dynamic_id", "dynamic_iq"}


def test_dynamic_and_uncertainty_not_run_are_not_fabricated() -> None:
    assert dynamic_result_to_plot_data(None).series == ()
    assert uncertainty_result_to_plot_data(None).availability is AvailabilityStatus.NOT_RUN


def test_uncertainty_adapter_uses_an_explicit_result_only() -> None:
    result = AccuracyEnvelopeResult(
        metric_name="back_emf_line_rms_v", nominal_value=50.0, unit="V",
        parameter_bound_min=45.0, parameter_bound_max=56.0, monte_carlo_available=True,
        p10=47.0, p50=50.5, p90=54.0, standard_deviation=2.0,
        dominant_uncertainty_parameters=("magnet_remanence_t",), numerical_uncertainty=None,
        model_form_uncertainty_status=ModelFormUncertaintyStatus.UNQUANTIFIED,
        external_validation_status="BLOCKED", confidence_level=ResultConfidence.LOW,
        warnings=(), assumptions=(),
    )
    data = uncertainty_result_to_plot_data(result)
    assert data.availability is AvailabilityStatus.AVAILABLE
    assert (data.lower_value, data.nominal_value, data.upper_value) == (45.0, 50.0, 56.0)
    assert data.dominant_parameters == ("magnet_remanence_t",)


def test_sensitivity_adapter_preserves_actual_perturbation_values() -> None:
    runs = tuple(
        SensitivityRunResult(
            perturbation=PerturbationSpec("air_gap_m", 0.001, percent, 0.001 * (1 + percent / 100.0)),
            affected_outputs=(SensitivityOutputChange("rated_torque_nm", 2.0, value, value - 2.0, (value / 2.0 - 1) * 100.0, "Nm"),),
            status="success",
        )
        for percent, value in ((-1.0, 2.1), (1.0, 1.9))
    )
    data = sensitivity_results_to_plot_data(runs, "air_gap_m", "rated_torque_nm")
    assert data.availability is AvailabilityStatus.AVAILABLE
    assert data.perturbation_percent == (-1.0, 1.0)
    assert data.output_values == (2.1, 1.9)


def test_downsampling_changes_plot_view_only_and_retains_endpoints() -> None:
    series = PlotSeries("x", "测试", tuple(float(i) for i in range(100)), tuple(float(i * i) for i in range(100)), "x", "y", "", AvailabilityStatus.AVAILABLE)
    reduced = downsample_plot_series(series, 10)
    assert len(reduced.x_values) == 10
    assert reduced.x_values[0] == series.x_values[0]
    assert reduced.x_values[-1] == series.x_values[-1]
    assert len(series.x_values) == 100


def test_speed_sweep_csv_contains_exact_calculated_rows(tmp_path: Path) -> None:
    sweep = run_speed_sweep(_feasible_inputs(), 1800.0, 2200.0, 3)
    path = export_speed_sweep_csv(sweep, tmp_path / "速度扫描.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert float(rows[1]["torque_nm"]) == pytest.approx(sweep.points[1].torque_nm)
    assert rows[1]["validity_status"] == "AVAILABLE"


def test_plot_exports_png_and_svg_with_chinese_labels(tmp_path: Path) -> None:
    sweep = run_speed_sweep(_feasible_inputs(), 1800.0, 2600.0, 5)
    figure = render_speed_sweep_figure(sweep)
    png = export_figure(figure, tmp_path / "性能扫描.png")
    svg = export_figure(figure, tmp_path / "性能扫描.svg")
    assert png.stat().st_size > 1000
    assert "基于当前静态模型的速度扫描" in svg.read_text(encoding="utf-8")
    assert configure_chinese_matplotlib()


def test_power_and_efficiency_use_separate_engineering_axes() -> None:
    figure = render_speed_sweep_figure(
        run_speed_sweep(_feasible_inputs(), 1800.0, 2600.0, 5)
    )
    labels = {axis.get_ylabel() for axis in figure.axes}
    assert "输出功率 (W)" in labels
    assert "效率 (%)" in labels
    assert "W / %" not in labels


def test_every_available_sweep_series_retains_model_source_label() -> None:
    series = build_speed_sweep_series(
        run_speed_sweep(_feasible_inputs(), 1800.0, 2600.0, 5)
    )
    assert all(item.source_label_zh for item in series)
    assert all("不是能力包络" in item.source_label_zh for item in series)


def test_figure_export_rejects_unsupported_format(tmp_path: Path) -> None:
    figure = render_speed_sweep_figure(
        run_speed_sweep(_feasible_inputs(), 1800.0, 2600.0, 3)
    )
    with pytest.raises(ValueError):
        export_figure(figure, tmp_path / "performance.pdf")


def test_result_snapshot_current_and_stale_states_are_explicit() -> None:
    parameters = _feasible_inputs()
    result, _ = _run(parameters)
    snapshot = build_result_snapshot(parameters, result.to_dict(), APPLICATION_VERSION)
    project_inputs = build_project_inputs(parameters)
    current = assess_result_snapshot(snapshot, project_inputs, APPLICATION_VERSION)
    version_stale = assess_result_snapshot(snapshot, project_inputs, "99.0.0")
    changed_inputs = build_project_inputs(dict(parameters, P_rated=650.0))
    input_stale = assess_result_snapshot(snapshot, changed_inputs, APPLICATION_VERSION)
    assert current.is_current and current.status is AvailabilityStatus.AVAILABLE
    assert not version_stale.is_current and "版本" in version_stale.message_zh
    assert not input_stale.is_current and "输入不匹配" in input_stale.message_zh


def test_result_snapshot_serializes_and_loads_with_project(tmp_path: Path) -> None:
    parameters = _feasible_inputs()
    result, _ = _run(parameters)
    snapshot = build_result_snapshot(parameters, result.to_dict(), APPLICATION_VERSION)
    document = create_project_document("Phase 8H snapshot", parameters, result_snapshot=snapshot)
    restored = load_project(save_project(document, tmp_path / "dashboard.motorproj"))
    assert restored.result_snapshot == snapshot
    assert assess_result_snapshot(restored.result_snapshot, restored.inputs, APPLICATION_VERSION).is_current


def test_pyinstaller_spec_collects_dashboard_and_plot_modules() -> None:
    source = (ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    assert '"motor_calculator.gui.results_dashboard"' in source
    assert '"motor_calculator.plots.performance"' in source
    assert '"matplotlib.backends.backend_tkagg"' in source


def test_smoke_scaling_override_is_explicit_and_validated() -> None:
    assert _smoke_tk_scaling_argument([]) is None
    assert _smoke_tk_scaling_argument(["--smoke-tk-scaling", "2.6666667"]) == pytest.approx(2.6666667)
    with pytest.raises(SystemExit):
        _smoke_tk_scaling_argument(["--smoke-tk-scaling", "0"])
    with pytest.raises(SystemExit):
        _smoke_tk_scaling_argument(["--smoke-tk-scaling", "nan"])
