"""Read-only adapters for existing dynamic, uncertainty, and sensitivity results."""

from __future__ import annotations

from typing import Any

from .models import (
    AvailabilityStatus,
    DynamicPlotData,
    PlotSeries,
    SensitivityPlotData,
    UncertaintyPlotData,
)


def dynamic_result_to_plot_data(result: Any | None) -> DynamicPlotData:
    if result is None:
        return DynamicPlotData((), "NOT_RUN", ("尚未运行动态仿真。",))
    electrical = getattr(result, "electrical_result", result)
    transient_available = getattr(
        electrical,
        "transient_response_available",
        bool(getattr(electrical, "time", ())),
    )
    if not transient_available:
        reason = getattr(electrical, "fallback_reason", None) or "动态瞬态结果不可用。"
        return DynamicPlotData((), str(getattr(electrical, "status", "UNAVAILABLE")), (reason,))
    time_values = tuple(float(value) for value in electrical.time)
    definitions = (
        ("dynamic_speed", "转速", tuple(electrical.speed), "机械角速度 (rad/s)", "rad/s"),
        ("dynamic_torque", "转矩", tuple(electrical.torque), "转矩 (Nm)", "Nm"),
        ("dynamic_id", "id", tuple(electrical.id), "电流 (A)", "A"),
        ("dynamic_iq", "iq", tuple(electrical.iq), "电流 (A)", "A"),
    )
    series = [
        PlotSeries(key, label, time_values, values, "时间 (s)", y_label, unit, AvailabilityStatus.AVAILABLE, source_label_zh="Phase 6 动态仿真结果")
        for key, label, values, y_label, unit in definitions
    ]
    optional_definitions = (
        ("dynamic_speed_reference", "目标转速", "speed_reference", "机械角速度 (rad/s)", "rad/s"),
        ("dynamic_vd", "Vd 实际", "vd_actual", "电压 (V)", "V"),
        ("dynamic_vq", "Vq 实际", "vq_actual", "电压 (V)", "V"),
    )
    for key, label, attribute, y_label, unit in optional_definitions:
        values = getattr(electrical, attribute, None)
        if values is not None and len(values) == len(time_values):
            series.append(
                PlotSeries(
                    key,
                    label,
                    time_values,
                    tuple(float(value) for value in values),
                    "时间 (s)",
                    y_label,
                    unit,
                    AvailabilityStatus.AVAILABLE,
                    source_label_zh="Phase 6 动态控制沙盒结果",
                )
            )
    temperature = getattr(result, "winding_temperature_c", None)
    if temperature is not None:
        series.append(
            PlotSeries("dynamic_temperature", "绕组温度", time_values, tuple(temperature), "时间 (s)", "温度 (degC)", "degC", AvailabilityStatus.AVAILABLE, source_label_zh="一阶集中参数热模型")
        )
    return DynamicPlotData(
        tuple(series),
        str(getattr(getattr(electrical, "status", "success"), "value", getattr(electrical, "status", "success"))),
        tuple(getattr(electrical, "warning_messages", ())),
    )


def uncertainty_result_to_plot_data(result: Any | None) -> UncertaintyPlotData:
    if result is None:
        return UncertaintyPlotData(AvailabilityStatus.NOT_RUN, "", "", None, None, None, None, None, None, (), "尚未执行不确定性分析。")
    return UncertaintyPlotData(
        availability=AvailabilityStatus.AVAILABLE,
        metric_name=str(result.metric_name),
        unit=str(result.unit),
        nominal_value=float(result.nominal_value),
        lower_value=float(result.parameter_bound_min),
        upper_value=float(result.parameter_bound_max),
        p10=None if result.p10 is None else float(result.p10),
        p50=None if result.p50 is None else float(result.p50),
        p90=None if result.p90 is None else float(result.p90),
        dominant_parameters=tuple(result.dominant_uncertainty_parameters),
        reason_zh="来自已显式执行的 Phase 7I 分析；不是自动置信概率。",
    )


def sensitivity_results_to_plot_data(
    run_results,
    parameter_name: str,
    output_name: str,
) -> SensitivityPlotData:
    matching = [
        result for result in run_results if result.perturbation.parameter_name == parameter_name
    ]
    percents: list[float] = []
    values: list[float | None] = []
    unit = ""
    for result in sorted(matching, key=lambda item: item.perturbation.perturbation_percent):
        change = next(
            (item for item in result.affected_outputs if item.output_name == output_name),
            None,
        )
        percents.append(float(result.perturbation.perturbation_percent))
        values.append(None if change is None else change.temporary_value)
        if change is not None and change.unit:
            unit = change.unit
    available = bool(percents) and any(value is not None for value in values)
    return SensitivityPlotData(
        parameter_name=parameter_name,
        output_name=output_name,
        perturbation_percent=tuple(percents),
        output_values=tuple(values),
        unit=unit,
        availability=AvailabilityStatus.AVAILABLE if available else AvailabilityStatus.UNAVAILABLE,
        reason_zh="" if available else "当前参数/输出组合没有可绘制的敏感性结果。",
    )


def downsample_plot_series(series: PlotSeries, maximum_points: int = 2000) -> PlotSeries:
    if maximum_points < 2:
        raise ValueError("maximum_points must be at least two")
    count = len(series.x_values)
    if count <= maximum_points:
        return series
    indexes = tuple(round(index * (count - 1) / (maximum_points - 1)) for index in range(maximum_points))
    return PlotSeries(
        key=series.key,
        label_zh=series.label_zh,
        x_values=tuple(series.x_values[index] for index in indexes),
        y_values=tuple(series.y_values[index] for index in indexes),
        x_label_zh=series.x_label_zh,
        y_label_zh=series.y_label_zh,
        unit=series.unit,
        availability=series.availability,
        unavailable_reason_zh=series.unavailable_reason_zh,
        source_label_zh=series.source_label_zh,
    )
