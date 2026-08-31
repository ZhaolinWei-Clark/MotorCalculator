"""Phase 8H dashboard and plotting API."""

from .adapters import (
    downsample_plot_series,
    dynamic_result_to_plot_data,
    sensitivity_results_to_plot_data,
    uncertainty_result_to_plot_data,
)
from .analysis import render_dynamic_figure, render_sensitivity_figure, render_uncertainty_figure
from .dashboard import build_dashboard_data, format_dashboard_value, mark_dashboard_as_previous
from .export import export_figure, export_speed_sweep_csv
from .font_config import configure_chinese_matplotlib
from .inventory import OUTPUT_INVENTORY, OutputInventoryItem, inventory_by_key
from .models import (
    AvailabilityItem,
    AvailabilityStatus,
    DashboardData,
    DashboardMetric,
    DashboardStatus,
    DesignStatusSummary,
    DynamicPlotData,
    PlotSeries,
    SensitivityPlotData,
    SnapshotAssessment,
    SpeedSweepPoint,
    SpeedSweepResult,
    UncertaintyPlotData,
)
from .performance import (
    build_speed_sweep_series,
    evaluate_speed_points,
    render_speed_sweep_figure,
    run_speed_sweep,
)
from .snapshot import assess_result_snapshot, build_result_snapshot, extract_snapshot_primary_values

__all__ = [
    "AvailabilityItem",
    "AvailabilityStatus",
    "DashboardData",
    "DashboardMetric",
    "DashboardStatus",
    "DesignStatusSummary",
    "DynamicPlotData",
    "OUTPUT_INVENTORY",
    "OutputInventoryItem",
    "PlotSeries",
    "SensitivityPlotData",
    "SnapshotAssessment",
    "SpeedSweepPoint",
    "SpeedSweepResult",
    "UncertaintyPlotData",
    "assess_result_snapshot",
    "build_dashboard_data",
    "build_result_snapshot",
    "build_speed_sweep_series",
    "configure_chinese_matplotlib",
    "downsample_plot_series",
    "dynamic_result_to_plot_data",
    "evaluate_speed_points",
    "export_figure",
    "export_speed_sweep_csv",
    "extract_snapshot_primary_values",
    "format_dashboard_value",
    "inventory_by_key",
    "mark_dashboard_as_previous",
    "render_speed_sweep_figure",
    "render_dynamic_figure",
    "render_sensitivity_figure",
    "render_uncertainty_figure",
    "run_speed_sweep",
    "sensitivity_results_to_plot_data",
    "uncertainty_result_to_plot_data",
]
