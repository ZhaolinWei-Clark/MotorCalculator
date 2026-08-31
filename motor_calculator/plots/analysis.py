"""Matplotlib renderers for explicitly executed sandbox analyses."""

from __future__ import annotations

from .font_config import configure_chinese_matplotlib
from .models import AvailabilityStatus, DynamicPlotData, SensitivityPlotData, UncertaintyPlotData


def render_dynamic_figure(data: DynamicPlotData):
    from matplotlib.figure import Figure

    configure_chinese_matplotlib()
    figure = Figure(figsize=(7.8, 4.6))
    figure.subplots_adjust(left=0.15, right=0.98, bottom=0.20, top=0.83, wspace=0.38, hspace=0.88)
    axes = figure.subplots(2, 2)
    groups = (
        (axes[0][0], {"dynamic_speed", "dynamic_speed_reference"}, "转速响应"),
        (axes[0][1], {"dynamic_torque"}, "电磁转矩"),
        (axes[1][0], {"dynamic_id", "dynamic_iq"}, "dq 电流"),
        (axes[1][1], {"dynamic_vd", "dynamic_vq"}, "实际 dq 电压"),
    )
    for axis, keys, title in groups:
        plotted = False
        for series in data.series:
            if series.key not in keys or series.availability is not AvailabilityStatus.AVAILABLE:
                continue
            axis.plot(series.x_values, series.y_values, label=series.label_zh, linewidth=1.3)
            axis.set_xlabel(series.x_label_zh, fontsize=8)
            axis.set_ylabel(series.y_label_zh, fontsize=8)
            plotted = True
        axis.set_title(title, fontsize=9, pad=2)
        axis.tick_params(labelsize=7)
        axis.grid(True, alpha=0.25)
        if plotted:
            axis.legend(loc="best", fontsize=7)
        else:
            axis.text(0.5, 0.5, "当前结果不可用", ha="center", va="center", transform=axis.transAxes)
    return figure


def render_uncertainty_figure(data: UncertaintyPlotData):
    from matplotlib.figure import Figure

    configure_chinese_matplotlib()
    figure = Figure(figsize=(7.2, 3.6))
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.22, top=0.78)
    axis = figure.subplots()
    if data.availability is not AvailabilityStatus.AVAILABLE:
        axis.text(0.5, 0.5, data.reason_zh, ha="center", va="center", transform=axis.transAxes)
        axis.set_axis_off()
        return figure
    axis.hlines(0.0, data.lower_value, data.upper_value, linewidth=8, color="#8ab6a7", label="参数边界")
    axis.scatter([data.nominal_value], [0.0], s=80, color="#183a37", zorder=3, label="标称值")
    if None not in (data.p10, data.p50, data.p90):
        axis.hlines(0.18, data.p10, data.p90, linewidth=6, color="#d6a84b", label="Monte Carlo P10-P90")
        axis.scatter([data.p50], [0.18], s=65, color="#8a541f", zorder=3, label="P50")
    axis.set_yticks([])
    axis.set_ylim(-0.12, 0.30)
    metric_label = {
        "back_emf_phase_fundamental_rms_v": "相基波反电动势 RMS",
        "back_emf_phase_rms_v": "相反电动势 RMS",
        "back_emf_line_rms_v": "线反电动势 RMS",
        "rated_torque_nm": "额定转矩",
    }.get(data.metric_name, data.metric_name)
    axis.set_title(f"受控参考参数不确定性：{metric_label} ({data.unit})", fontsize=10)
    axis.tick_params(labelsize=8)
    axis.grid(True, axis="x", alpha=0.25)
    axis.legend(loc="upper right", fontsize=7, ncol=2)
    return figure


def render_sensitivity_figure(data: SensitivityPlotData):
    from matplotlib.figure import Figure

    configure_chinese_matplotlib()
    figure = Figure(figsize=(7.2, 3.6))
    figure.subplots_adjust(left=0.14, right=0.98, bottom=0.24, top=0.82)
    axis = figure.subplots()
    if data.availability is not AvailabilityStatus.AVAILABLE:
        axis.text(0.5, 0.5, data.reason_zh, ha="center", va="center", transform=axis.transAxes)
        axis.set_axis_off()
        return figure
    pairs = [
        (percent, value)
        for percent, value in zip(data.perturbation_percent, data.output_values)
        if value is not None
    ]
    axis.plot([item[0] for item in pairs], [item[1] for item in pairs], marker="o", color="#276678")
    axis.axvline(0.0, color="#777777", linewidth=1.0, linestyle="--")
    parameter_label = {
        "magnet_remanence_t": "磁体剩磁 Br",
        "air_gap_m": "气隙",
        "magnet_thickness_m": "磁体厚度",
        "turns_per_phase": "每相匝数",
        "rated_speed_rpm": "额定转速",
    }.get(data.parameter_name, data.parameter_name)
    output_label = {
        "rated_torque_nm": "额定转矩",
        "back_emf_phase_peak_v": "相反电动势峰值",
        "back_emf_line_rms_v": "线反电动势 RMS",
        "torque_constant_nm_per_a": "转矩常数",
        "required_voltage_v": "所需电压",
        "copper_loss_w": "铜耗",
        "iron_loss_w": "铁耗",
        "efficiency_percent": "效率",
    }.get(data.output_name, data.output_name)
    axis.set_xlabel(f"{parameter_label} 临时扰动 (%)", fontsize=8)
    axis.set_ylabel(f"{output_label} ({data.unit})" if data.unit else output_label, fontsize=8)
    axis.set_title("只读局部参数敏感性", fontsize=10)
    axis.tick_params(labelsize=8)
    axis.grid(True, alpha=0.25)
    return figure
