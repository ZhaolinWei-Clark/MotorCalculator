"""Traceable dashboard data generation from existing model results."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

from motor_calculator.motor_core.loss_semantics import (
    CORE_LOSS_LABEL_ZH,
    CORE_LOSS_LIMITATION_ZH,
    EDDY_LOSS_LABEL_ZH,
    EDDY_LOSS_LIMITATION_ZH,
)
from motor_calculator.motor_core.models import AnalysisResult
from motor_calculator.validation.design_feasibility import (
    DesignFeasibilityAssessment,
    FeasibilitySeverity,
)

from .models import (
    AvailabilityItem,
    AvailabilityStatus,
    DashboardData,
    DashboardMetric,
    DashboardStatus,
    DesignStatusSummary,
)


_PRECISION = {
    "rated_torque_nm": 3,
    "output_power_w": 1,
    "efficiency_percent": 2,
    "mechanical_speed_rpm": 0,
    "current_density_a_per_mm2": 2,
    "voltage_margin_percent": 2,
    "slot_fill_factor": 3,
    "ke_line_rms": 4,
    "kt_phase_rms": 4,
    "phase_current_rms_a": 3,
    "required_voltage_v": 2,
    "required_voltage_line_rms_corrected_v": 2,
    "corrected_voltage_margin_percent": 2,
    "back_emf_line_rms_v": 2,
    "copper_loss_w": 2,
    "eddy_loss_w": 2,
    "mechanical_loss_w": 2,
    "core_loss_w": 2,
}


def format_dashboard_value(key: str, value: float | None) -> str:
    if value is None:
        return "不可用"
    precision = _PRECISION.get(key, 3)
    return f"{value:.{precision}f}"


def _severity_status(
    assessment: DesignFeasibilityAssessment,
    code_prefix: str,
) -> DashboardStatus:
    relevant = tuple(
        issue for issue in assessment.issues if issue.code.startswith(code_prefix)
    )
    if any(issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK for issue in relevant):
        return DashboardStatus.SEVERE
    if any(issue.severity is FeasibilitySeverity.WARNING for issue in relevant):
        return DashboardStatus.WARNING
    if any(issue.severity is FeasibilitySeverity.INFO for issue in relevant):
        return DashboardStatus.INFO
    return DashboardStatus.NORMAL


def _metric(
    key: str,
    label: str,
    value: float | None,
    unit: str,
    status: DashboardStatus,
    interpretation: str,
    source: str,
    *,
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
) -> DashboardMetric:
    return DashboardMetric(
        key=key,
        label_zh=label,
        value=value,
        display_value=format_dashboard_value(key, value),
        unit=unit,
        status=status,
        interpretation_zh=interpretation,
        availability=availability,
        source=source,
    )


def _optional_metric(
    key: str,
    label: str,
    value: float | None,
    unit: str,
    interpretation: str,
    source: str,
    unavailable_reason: str,
) -> DashboardMetric:
    if value is None:
        return _metric(
            key,
            label,
            None,
            unit,
            DashboardStatus.UNAVAILABLE,
            unavailable_reason,
            source,
            availability=AvailabilityStatus.UNAVAILABLE,
        )
    return _metric(
        key,
        label,
        float(value),
        unit,
        DashboardStatus.INFO,
        interpretation,
        source,
    )


def _design_summary(
    assessment: DesignFeasibilityAssessment,
    availability_items: Iterable[AvailabilityItem],
) -> DesignStatusSummary:
    issues = tuple(
        issue for issue in assessment.issues if issue.code != "FEASIBILITY_SUMMARY"
    )
    severe = sum(
        issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK for issue in issues
    )
    warnings = sum(issue.severity is FeasibilitySeverity.WARNING for issue in issues)
    reviews = sum(issue.severity is FeasibilitySeverity.INFO for issue in issues)
    insufficient = sum(
        item.status in {AvailabilityStatus.UNAVAILABLE, AvailabilityStatus.NOT_RUN}
        for item in availability_items
    )
    if severe:
        headline = f"有 {severe} 项严重设计风险"
    elif warnings:
        headline = f"无严重风险；有 {warnings} 项警告"
    elif reviews:
        headline = f"无严重风险；有 {reviews} 项建议检查"
    else:
        headline = "无严重可行性风险"
    return DesignStatusSummary(
        headline_zh=headline,
        severe_count=severe,
        warning_count=warnings,
        review_count=reviews,
        insufficient_count=insufficient,
        contributors_zh=tuple(issue.message_zh for issue in issues[:5]),
    )


def build_dashboard_data(
    parameters: Mapping[str, object],
    result: AnalysisResult,
    assessment: DesignFeasibilityAssessment,
    *,
    uncertainty_available: bool = False,
    dynamic_available: bool = False,
    sensitivity_available: bool = False,
    result_label_zh: str = "当前成功计算",
) -> DashboardData:
    """Build dashboard values without mutating or reinterpreting model outputs."""

    del parameters
    performance = result.performance
    electrical = result.electrical
    primary = (
        _metric("rated_torque_nm", "转矩", performance.rated_torque_nm, "Nm", DashboardStatus.INFO, "当前生产路径的额定转矩。", "AnalysisResult.performance"),
        _metric("output_power_w", "输出功率", performance.output_power_w, "W", DashboardStatus.INFO, "当前输入工作点的轴端输出功率。", "AnalysisResult.performance"),
        _metric("efficiency_percent", "当前模型估算效率", performance.efficiency_percent, "%", DashboardStatus.INFO, "来自现有损耗定义，不代表完整铁耗、机械损耗和风阻模型。", "AnalysisResult.performance"),
        _metric("mechanical_speed_rpm", "转速", performance.mechanical_speed_rpm, "rpm", DashboardStatus.INFO, "机械转速工作点。", "AnalysisResult.performance"),
    )

    current_status = _severity_status(assessment, "CURRENT_DENSITY")
    current_text = (
        "当前处于 Phase 8G 保守连续运行起始参考范围。"
        if current_status is DashboardStatus.NORMAL
        else "请结合导体截面、并联路径、占空比和冷却能力复核。"
    )
    current = _metric(
        "current_density_a_per_mm2",
        "电流密度",
        assessment.current_density_a_per_mm2,
        "A/mm2",
        current_status,
        current_text,
        "validation.design_feasibility",
    )

    if assessment.slot_fill_factor is None:
        slot = _metric(
            "slot_fill_factor",
            "近似裸铜槽占比",
            None,
            "",
            DashboardStatus.INSUFFICIENT,
            "当前项目缺少可用槽几何；legacy 线性绕组占比不能代替制造槽满率。",
            "validation.design_feasibility",
            availability=AvailabilityStatus.UNAVAILABLE,
        )
    else:
        slot = _metric(
            "slot_fill_factor",
            "近似裸铜槽占比",
            assessment.slot_fill_factor,
            "",
            _severity_status(assessment, "SLOT_FILL"),
            "当前槽几何下的近似裸铜面积占比，未包含绝缘、排布和制造工艺。",
            "validation.design_feasibility",
        )

    if assessment.voltage_margin_percent is None:
        voltage_margin = _metric(
            "voltage_margin_percent",
            "同基电压裕量",
            None,
            "%",
            DashboardStatus.INSUFFICIENT,
            "当前 BLDC 模型语义不足，不能生成正弦 line-RMS 同基裕量。",
            "validation.design_feasibility",
            availability=AvailabilityStatus.UNAVAILABLE,
        )
    else:
        voltage_margin = _metric(
            "voltage_margin_percent",
            "同基电压裕量",
            assessment.voltage_margin_percent,
            "%",
            _severity_status(assessment, "VOLTAGE_MARGIN"),
            "使用同基 line-RMS 电压比较，并非完整逆变器动态裕量。",
            "validation.design_feasibility",
        )

    availability_items = (
        AvailabilityItem("static_thermal", "静态温升", AvailabilityStatus.UNAVAILABLE, "当前静态模式无可信温升预测。"),
        AvailabilityItem("dynamic", "动态响应", AvailabilityStatus.AVAILABLE if dynamic_available else AvailabilityStatus.NOT_RUN, "已提供显式动态结果。" if dynamic_available else "尚未运行动态仿真。"),
        AvailabilityItem("uncertainty", "不确定性", AvailabilityStatus.AVAILABLE if uncertainty_available else AvailabilityStatus.NOT_RUN, "已执行不确定性分析。" if uncertainty_available else "尚未执行不确定性分析。"),
        AvailabilityItem("sensitivity", "敏感性", AvailabilityStatus.AVAILABLE if sensitivity_available else AvailabilityStatus.NOT_RUN, "已执行单参数敏感性分析。" if sensitivity_available else "尚未运行单参数敏感性分析。"),
    )
    design_summary = _design_summary(assessment, availability_items)
    design_status = DashboardStatus.SEVERE if design_summary.severe_count else (
        DashboardStatus.WARNING if design_summary.warning_count else DashboardStatus.NORMAL
    )
    feasibility = (
        current,
        voltage_margin,
        slot,
        DashboardMetric(
            key="design_status",
            label_zh="设计状态",
            value=None,
            display_value=design_summary.headline_zh,
            unit="",
            status=design_status,
            interpretation_zh="按 Phase 8G 各项状态汇总，不是综合评分。",
            source="validation.design_feasibility",
        ),
    )

    electromagnetic = (
        _optional_metric("ke_line_rms", "Ke 线电压 RMS", electrical.back_emf_constant_line_rms_v_per_krpm, "V/krpm", "按当前控制模式的显式 Ke 语义。", "AnalysisResult.electrical", "当前模式没有可用 Ke 语义。"),
        _optional_metric("kt_phase_rms", "Kt 相电流 RMS", electrical.torque_constant_nm_per_phase_rms_a, "Nm/A", "按当前控制模式的显式 Kt 语义。", "AnalysisResult.electrical", "当前模式没有可用 Kt 语义。"),
        _metric("phase_current_rms_a", "相电流 RMS", performance.phase_current_rms_a, "A", DashboardStatus.INFO, "当前工作点相电流有效值。", "AnalysisResult.performance"),
        _metric("required_voltage_v", "所需线电压 RMS（legacy）", performance.required_voltage_v, "V", DashboardStatus.INFO, "legacy 混合基准 RSS 估计，保留为兼容值。", "AnalysisResult.performance"),
        _optional_metric(
            "required_voltage_line_rms_corrected_v",
            "所需线电压 RMS（修正同基）",
            performance.required_voltage_line_rms_corrected_v,
            "V",
            "单一线电压 RMS 基准的稳态相量结果，与 Phase 6 dq 稳态解一致；尚未成为默认口径。",
            "AnalysisResult.performance",
            "当前控制模式缺少正弦相量基准，无法给出修正所需电压。",
        ),
        _optional_metric(
            "corrected_voltage_margin_percent",
            "同基电压裕量（修正）",
            assessment.corrected_voltage_margin_percent,
            "%",
            "使用修正所需电压与同一 SVPWM 包络比较；严重度判据仍由 legacy 值驱动。",
            "validation.design_feasibility",
            "当前控制模式缺少正弦相量基准，无法给出修正裕量。",
        ),
    )

    loss_metrics = tuple(
        _metric(key, label, float(value), "W", DashboardStatus.INFO, limitation, "AnalysisResult.performance")
        for key, label, value, limitation in (
            ("copper_loss_w", "铜耗", performance.copper_loss_w, "当前模型计算的三相铜耗。"),
            ("eddy_loss_w", EDDY_LOSS_LABEL_ZH, performance.eddy_loss_w, EDDY_LOSS_LIMITATION_ZH),
            ("mechanical_loss_w", "legacy 机械损耗", performance.mechanical_loss_w, "经验/模型受限损耗项。"),
            ("core_loss_w", CORE_LOSS_LABEL_ZH, performance.core_loss_w, CORE_LOSS_LIMITATION_ZH),
        )
    )
    return DashboardData(
        primary_metrics=primary,
        feasibility_metrics=feasibility,
        electromagnetic_metrics=electromagnetic,
        loss_metrics=loss_metrics,
        availability_items=availability_items,
        design_status=design_summary,
        result_label_zh=result_label_zh,
    )


def mark_dashboard_as_previous(data: DashboardData) -> DashboardData:
    return replace(data, result_label_zh="上一次成功计算；本次计算失败")
