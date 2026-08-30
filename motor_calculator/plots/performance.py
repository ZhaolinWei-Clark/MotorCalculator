"""Opt-in one-dimensional sweeps using actual production model evaluations."""

from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Mapping, Sequence

from motor_calculator.motor_core import (
    LegacyGuiMotorModelBridge,
    MotorCalculatorError,
    parse_legacy_gui_params,
)
from motor_calculator.validation.design_feasibility import (
    FeasibilitySeverity,
    evaluate_design_feasibility,
)

from .font_config import configure_chinese_matplotlib
from .models import (
    AvailabilityStatus,
    DashboardStatus,
    PlotSeries,
    SpeedSweepPoint,
    SpeedSweepResult,
)


def _input_hash(parameters: Mapping[str, object]) -> str:
    payload = json.dumps(dict(parameters), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _point_status(issues) -> DashboardStatus:
    if any(issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK for issue in issues):
        return DashboardStatus.SEVERE
    if any(issue.severity is FeasibilitySeverity.WARNING for issue in issues):
        return DashboardStatus.WARNING
    if any(issue.severity is FeasibilitySeverity.INFO for issue in issues):
        return DashboardStatus.INFO
    return DashboardStatus.NORMAL


def evaluate_speed_points(
    baseline_parameters: Mapping[str, object],
    speeds_rpm: Sequence[float],
) -> SpeedSweepResult:
    """Evaluate every speed independently; invalid points remain explicit gaps."""

    baseline = dict(baseline_parameters)
    waveform = str(baseline.get("waveform", ""))
    started = time.perf_counter()
    points: list[SpeedSweepPoint] = []
    for speed in speeds_rpm:
        temporary = dict(baseline)
        temporary["n_rated"] = float(speed)
        try:
            parsed = parse_legacy_gui_params(temporary)
            result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
            assessment = evaluate_design_feasibility(parsed, result)
        except (MotorCalculatorError, ValueError, ZeroDivisionError) as exc:
            points.append(
                SpeedSweepPoint(
                    speed_rpm=float(speed),
                    torque_nm=None,
                    output_power_w=None,
                    required_voltage_line_rms_v=None,
                    available_voltage_line_rms_v=None,
                    voltage_margin_percent=None,
                    efficiency_percent=None,
                    current_density_a_per_mm2=None,
                    availability=AvailabilityStatus.INVALID,
                    feasibility_status=DashboardStatus.UNAVAILABLE,
                    message_zh=f"该采样点输入无效：{exc}",
                )
            )
            continue
        performance = result.performance
        points.append(
            SpeedSweepPoint(
                speed_rpm=float(speed),
                torque_nm=float(performance.rated_torque_nm),
                output_power_w=float(performance.output_power_w),
                required_voltage_line_rms_v=float(performance.required_voltage_v),
                available_voltage_line_rms_v=assessment.available_voltage_line_rms_v,
                voltage_margin_percent=assessment.voltage_margin_percent,
                efficiency_percent=float(performance.efficiency_percent),
                current_density_a_per_mm2=float(assessment.current_density_a_per_mm2),
                availability=AvailabilityStatus.AVAILABLE,
                feasibility_status=_point_status(assessment.issues),
            )
        )
    control_mode = "PMSM" if waveform in {"正弦波", "PMSM", "pmsm"} else "BLDC"
    return SpeedSweepResult(
        points=tuple(points),
        control_mode=control_mode,
        source_label_zh=(
            "基于当前静态模型的速度扫描；每个点均为独立真实计算；"
            "除转速外保持输入不变（包括额定功率），不是能力包络"
        ),
        input_hash=_input_hash(baseline),
        elapsed_seconds=time.perf_counter() - started,
    )


def run_speed_sweep(
    baseline_parameters: Mapping[str, object],
    minimum_speed_rpm: float,
    maximum_speed_rpm: float,
    point_count: int = 21,
) -> SpeedSweepResult:
    if not math.isfinite(minimum_speed_rpm) or not math.isfinite(maximum_speed_rpm):
        raise ValueError("speed bounds must be finite")
    if maximum_speed_rpm <= minimum_speed_rpm:
        raise ValueError("maximum speed must be greater than minimum speed")
    if isinstance(point_count, bool) or not isinstance(point_count, int) or not 2 <= point_count <= 201:
        raise ValueError("point_count must be an integer from 2 to 201")
    step = (maximum_speed_rpm - minimum_speed_rpm) / (point_count - 1)
    speeds = tuple(minimum_speed_rpm + index * step for index in range(point_count))
    return evaluate_speed_points(baseline_parameters, speeds)


def build_speed_sweep_series(result: SpeedSweepResult) -> tuple[PlotSeries, ...]:
    x_values = tuple(point.speed_rpm for point in result.points)

    def series(
        key: str,
        label: str,
        attribute: str,
        y_label: str,
        unit: str,
        *,
        unavailable_reason: str = "",
    ) -> PlotSeries:
        values = tuple(
            getattr(point, attribute)
            if point.availability is AvailabilityStatus.AVAILABLE
            else None
            for point in result.points
        )
        available = any(value is not None for value in values)
        return PlotSeries(
            key=key,
            label_zh=label,
            x_values=x_values,
            y_values=values,
            x_label_zh="机械转速 (rpm)",
            y_label_zh=y_label,
            unit=unit,
            availability=AvailabilityStatus.AVAILABLE if available else AvailabilityStatus.UNAVAILABLE,
            unavailable_reason_zh="" if available else unavailable_reason,
            source_label_zh=result.source_label_zh,
        )

    voltage_reason = "当前 BLDC 模型语义不足，无法生成同基电压裕量曲线。"
    return (
        series("torque_speed", "转矩", "torque_nm", "转矩 (Nm)", "Nm"),
        series("power_speed", "输出功率", "output_power_w", "输出功率 (W)", "W"),
        series("required_voltage", "所需线电压 RMS", "required_voltage_line_rms_v", "线电压 RMS (V)", "V"),
        series("available_voltage", "可用线电压 RMS", "available_voltage_line_rms_v", "线电压 RMS (V)", "V", unavailable_reason=voltage_reason),
        series("voltage_margin", "同基电压裕量", "voltage_margin_percent", "电压裕量 (%)", "%", unavailable_reason=voltage_reason),
        series("efficiency", "当前模型估算效率", "efficiency_percent", "效率 (%)", "%"),
    )


def render_speed_sweep_figure(result: SpeedSweepResult):
    """Render a figure from structured sweep data without evaluating the model."""

    configure_chinese_matplotlib()
    from matplotlib.figure import Figure

    series_by_key = {series.key: series for series in build_speed_sweep_series(result)}
    figure = Figure(figsize=(10.4, 6.5), dpi=100, constrained_layout=True)
    axes = figure.subplots(2, 2)
    panels = (
        (axes[0, 0], ("torque_speed",), "转矩-转速"),
        (axes[1, 0], ("required_voltage", "available_voltage"), "同基线电压 RMS-转速"),
        (axes[1, 1], ("voltage_margin",), "电压裕量-转速"),
    )
    for axis, keys, title in panels:
        plotted = False
        for key in keys:
            item = series_by_key[key]
            if item.availability is not AvailabilityStatus.AVAILABLE:
                continue
            y_values = tuple(float("nan") if value is None else value for value in item.y_values)
            axis.plot(item.x_values, y_values, marker="o", markersize=3.2, linewidth=1.6, label=item.label_zh)
            plotted = True
        axis.set_title(title)
        axis.set_xlabel("机械转速 (rpm)")
        axis.grid(True, alpha=0.25)
        if plotted:
            axis.legend(loc="best", fontsize=8)
        else:
            reason = next(
                (series_by_key[key].unavailable_reason_zh for key in keys if series_by_key[key].unavailable_reason_zh),
                "当前结果不可用。",
            )
            axis.text(0.5, 0.5, reason, transform=axis.transAxes, ha="center", va="center", wrap=True)
    power_axis = axes[0, 1]
    efficiency_axis = power_axis.twinx()
    power = series_by_key["power_speed"]
    efficiency = series_by_key["efficiency"]
    power_axis.plot(power.x_values, power.y_values, marker="o", markersize=3.2, linewidth=1.6, color="#2471a3", label=power.label_zh)
    efficiency_axis.plot(efficiency.x_values, efficiency.y_values, marker="o", markersize=3.2, linewidth=1.6, color="#d35400", label=efficiency.label_zh)
    power_axis.set_title("功率与效率-转速")
    power_axis.set_xlabel("机械转速 (rpm)")
    power_axis.set_ylabel("输出功率 (W)", color="#2471a3")
    efficiency_axis.set_ylabel("效率 (%)", color="#d35400")
    power_axis.grid(True, alpha=0.25)
    handles_left, labels_left = power_axis.get_legend_handles_labels()
    handles_right, labels_right = efficiency_axis.get_legend_handles_labels()
    power_axis.legend(handles_left + handles_right, labels_left + labels_right, loc="best", fontsize=8)

    axes[0, 0].set_ylabel("转矩 (Nm)")
    axes[1, 0].set_ylabel("线电压 RMS (V)")
    axes[1, 1].set_ylabel("裕量 (%)")
    figure.suptitle(
        "基于当前静态模型的速度扫描\n保持其余输入不变（包括额定功率）；不是电驱能力包络",
        fontsize=12,
        fontweight="bold",
    )
    return figure
