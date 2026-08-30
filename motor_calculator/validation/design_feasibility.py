"""Audited design-feasibility guidance outside the production calculator."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from motor_calculator.motor_core.models import AnalysisResult


class FeasibilitySeverity(str, Enum):
    ERROR = "ERROR"
    SEVERE_DESIGN_RISK = "SEVERE_DESIGN_RISK"
    WARNING = "WARNING"
    INFO = "INFO"


class FeasibilityCalculability(str, Enum):
    CALCULABLE = "CALCULABLE"
    APPROXIMATE = "APPROXIMATE"
    NOT_ENOUGH_GEOMETRY = "NOT_ENOUGH_GEOMETRY"
    NOT_ENOUGH_SEMANTICS = "NOT_ENOUGH_SEMANTICS"


@dataclass(frozen=True)
class FeasibilityIssue:
    code: str
    severity: FeasibilitySeverity
    message_zh: str


@dataclass(frozen=True)
class DesignFeasibilityAssessment:
    current_density_a_per_mm2: float
    phase_current_rms_a: float
    conductor_current_rms_a: float
    conductor_copper_area_mm2: float
    current_density_status: FeasibilityCalculability
    slot_fill_factor: float | None
    slot_fill_status: FeasibilityCalculability
    total_slot_copper_area_mm2: float | None
    total_available_slot_area_mm2: float | None
    legacy_fill_proxy: float
    required_voltage_line_rms_v: float
    available_voltage_line_rms_v: float | None
    voltage_margin_percent: float | None
    voltage_status: FeasibilityCalculability
    issues: tuple[FeasibilityIssue, ...]

    @property
    def has_error(self) -> bool:
        return any(issue.severity is FeasibilitySeverity.ERROR for issue in self.issues)

    @property
    def has_severe_design_risk(self) -> bool:
        return any(
            issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK
            for issue in self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["current_density_status"] = self.current_density_status.value
        payload["slot_fill_status"] = self.slot_fill_status.value
        payload["voltage_status"] = self.voltage_status.value
        payload["issues"] = [
            {"code": issue.code, "severity": issue.severity.value, "message_zh": issue.message_zh}
            for issue in self.issues
        ]
        return payload


FEASIBLE_STARTING_OVERRIDES: dict[str, str | int | float | bool] = {
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 2200.0,
    "d_wire": 1.2,
    "slot_type": "半闭口槽",
    "coreless": False,
}


def feasible_starting_inputs(base: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(base)
    values.update(FEASIBLE_STARTING_OVERRIDES)
    return values


def _current_density(
    parameters: Mapping[str, Any], result: AnalysisResult
) -> tuple[float, float, float]:
    phase_current_rms_a = float(result.performance.phase_current_rms_a)
    parallel_paths = int(parameters["n_parallel"])
    conductor_area_mm2 = math.pi * (float(parameters["d_wire"]) / 2.0) ** 2
    conductor_current_rms_a = phase_current_rms_a / parallel_paths
    return (
        conductor_current_rms_a / conductor_area_mm2,
        conductor_current_rms_a,
        conductor_area_mm2,
    )


def _slot_fill(
    parameters: Mapping[str, Any], conductor_area_mm2: float
) -> tuple[float | None, FeasibilityCalculability, float | None, float | None]:
    if bool(parameters.get("coreless", False)) or str(parameters.get("slot_type")) == "无槽":
        return None, FeasibilityCalculability.NOT_ENOUGH_GEOMETRY, None, None

    slot_count = int(parameters["slots"])
    slot_top_width_mm = float(parameters["w_slot_top"])
    slot_bottom_width_mm = float(parameters["w_slot_bottom"])
    slot_depth_mm = float(parameters["h_slot"])
    wedge_height_mm = float(parameters["h_wedge"])
    gross_slot_area_mm2 = (
        (slot_top_width_mm + slot_bottom_width_mm) / 2.0 * slot_depth_mm
    )
    # The wedge is represented explicitly; insulation, liners and detailed coil placement are not.
    available_slot_area_mm2 = gross_slot_area_mm2 - slot_top_width_mm * wedge_height_mm
    if slot_count <= 0 or available_slot_area_mm2 <= 0.0:
        return None, FeasibilityCalculability.NOT_ENOUGH_GEOMETRY, None, None

    conductor_sides = (
        3
        * 2
        * int(parameters["N_ph_turns"])
        * int(parameters["n_parallel"])
    )
    total_copper_area_mm2 = conductor_sides * conductor_area_mm2
    total_available_slot_area_mm2 = slot_count * available_slot_area_mm2
    return (
        total_copper_area_mm2 / total_available_slot_area_mm2,
        FeasibilityCalculability.APPROXIMATE,
        total_copper_area_mm2,
        total_available_slot_area_mm2,
    )


def _voltage_margin(
    parameters: Mapping[str, Any], result: AnalysisResult
) -> tuple[float | None, float | None, FeasibilityCalculability]:
    waveform = str(parameters.get("waveform", ""))
    if waveform not in {"正弦波", "PMSM", "pmsm"}:
        return None, None, FeasibilityCalculability.NOT_ENOUGH_SEMANTICS

    # Phase 6F uses the linear SVPWM-compatible dq phase-peak envelope Vdc/sqrt(3).
    # Its balanced sinusoidal line-line RMS equivalent is Vdc/sqrt(2).
    available_line_rms_v = float(parameters["V_dc"]) / math.sqrt(2.0)
    required_line_rms_v = float(result.performance.required_voltage_v)
    margin_percent = (
        (available_line_rms_v - required_line_rms_v) / available_line_rms_v * 100.0
    )
    return available_line_rms_v, margin_percent, FeasibilityCalculability.APPROXIMATE


def evaluate_design_feasibility(
    parameters: Mapping[str, Any], result: AnalysisResult
) -> DesignFeasibilityAssessment:
    """Evaluate warning semantics without changing any production calculation."""

    current_density, conductor_current, conductor_area = _current_density(parameters, result)
    slot_fill, slot_status, total_copper, total_available = _slot_fill(
        parameters, conductor_area
    )
    available_voltage, voltage_margin, voltage_status = _voltage_margin(parameters, result)
    issues: list[FeasibilityIssue] = []

    fill_summary = (
        f"近似裸铜槽占比 {slot_fill:.3f}"
        if slot_fill is not None
        else f"槽满率 {slot_status.value}"
    )
    voltage_summary = (
        f"可用/所需线电压 RMS {available_voltage:.2f}/{float(result.performance.required_voltage_v):.2f} V，"
        f"同基裕量 {voltage_margin:.1f}%"
        if available_voltage is not None and voltage_margin is not None
        else f"电压裕量 {voltage_status.value}"
    )
    issues.append(
        FeasibilityIssue(
            "FEASIBILITY_SUMMARY",
            FeasibilitySeverity.INFO,
            f"当前电流密度 {current_density:.2f} A/mm²；{fill_summary}；{voltage_summary}。",
        )
    )

    if current_density > 10.0:
        issues.append(
            FeasibilityIssue(
                "CURRENT_DENSITY_SEVERE",
                FeasibilitySeverity.SEVERE_DESIGN_RISK,
                f"电流密度为 {current_density:.2f} A/mm²，超过 10 A/mm²，连续运行热风险很高。"
                "可尝试增大导体截面积、增加并联路径或降低相电流，并进行专门热验证。",
            )
        )
    elif current_density > 6.0:
        issues.append(
            FeasibilityIssue(
                "CURRENT_DENSITY_HIGH",
                FeasibilitySeverity.WARNING,
                f"电流密度为 {current_density:.2f} A/mm²，高于当前连续运行建议范围。"
                "可尝试增大导体截面积、增加并联路径或降低相电流；冷却能力需另行验证。",
            )
        )
    elif current_density > 5.0:
        issues.append(
            FeasibilityIssue(
                "CURRENT_DENSITY_GUIDANCE",
                FeasibilitySeverity.INFO,
                f"电流密度为 {current_density:.2f} A/mm²，略高于保守起始目标 5 A/mm²。"
                "建议结合占空比、冷却和温升模型复核。",
            )
        )

    if slot_status is FeasibilityCalculability.NOT_ENOUGH_GEOMETRY:
        issues.append(
            FeasibilityIssue(
                "SLOT_FILL_GEOMETRY_UNAVAILABLE",
                FeasibilitySeverity.INFO,
                "当前无槽/无铁芯输入缺少可用槽面积与线圈排布，物理槽满率为 NOT_ENOUGH_GEOMETRY；"
                f"legacy 线性绕组占比 {result.performance.fill_factor:.3f} 不得用于宣称无法制造。",
            )
        )
    elif slot_fill is not None:
        if slot_fill > 0.80:
            issues.append(
                FeasibilityIssue(
                    "SLOT_FILL_SEVERE",
                    FeasibilitySeverity.SEVERE_DESIGN_RISK,
                    f"近似裸铜槽占比为 {slot_fill:.3f}，超过 0.80，属于严重设计风险。"
                    "请减少导体总面积、增加槽面积或重新分配绕组；本值仍未包含绝缘和工艺细节。",
                )
            )
        elif slot_fill > 0.60:
            issues.append(
                FeasibilityIssue(
                    "SLOT_FILL_HIGH",
                    FeasibilitySeverity.WARNING,
                    f"近似裸铜槽占比为 {slot_fill:.3f}，高于 0.60 制造指导区。"
                    "请复核槽衬、漆包线绝缘、绕线工艺和实际可用槽面积。",
                )
            )
        elif slot_fill > 0.50:
            issues.append(
                FeasibilityIssue(
                    "SLOT_FILL_GUIDANCE",
                    FeasibilitySeverity.INFO,
                    f"近似裸铜槽占比为 {slot_fill:.3f}，处于 0.50–0.60 的审慎复核区。"
                    "实际可制造性取决于绝缘、导体类型、槽形和绕线工艺。",
                )
            )

    required_voltage = float(result.performance.required_voltage_v)
    if voltage_status is FeasibilityCalculability.NOT_ENOUGH_SEMANTICS:
        issues.append(
            FeasibilityIssue(
                "VOLTAGE_BASIS_UNAVAILABLE",
                FeasibilitySeverity.INFO,
                "BLDC 梯形波缺少受控的 PWM/换相电压基准，不能把 DC 母线与 legacy RMS 需求直接比较。",
            )
        )
    elif available_voltage is not None and voltage_margin is not None:
        detail = (
            f"可用线电压 RMS 约 {available_voltage:.2f} V，legacy 所需线电压 RMS "
            f"{required_voltage:.2f} V，同基裕量 {voltage_margin:.1f}%。"
        )
        if voltage_margin < 0.0:
            issues.append(
                FeasibilityIssue(
                    "VOLTAGE_MARGIN_SEVERE",
                    FeasibilitySeverity.SEVERE_DESIGN_RISK,
                    detail + "当前线性 SVPWM-compatible 电压包络不足以维持该静态工作点。",
                )
            )
        elif voltage_margin < 10.0:
            issues.append(
                FeasibilityIssue(
                    "VOLTAGE_MARGIN_LOW",
                    FeasibilitySeverity.WARNING,
                    detail + "裕量低于 10%，动态调节与参数偏差余量有限。",
                )
            )
        elif voltage_margin < 15.0:
            issues.append(
                FeasibilityIssue(
                    "VOLTAGE_MARGIN_GUIDANCE",
                    FeasibilitySeverity.INFO,
                    detail + "处于 10–15% 的保守起始复核区。",
                )
            )

    if result.performance.efficiency_percent < 85.0:
        issues.append(
            FeasibilityIssue(
                "EFFICIENCY_REVIEW",
                FeasibilitySeverity.INFO,
                f"当前 legacy 效率估计为 {result.performance.efficiency_percent:.1f}%，建议复核损耗假设。",
            )
        )
    if result.magnetic.air_gap_flux_density_peak_t > 1.0:
        issues.append(
            FeasibilityIssue(
                "AIR_GAP_FLUX_REVIEW",
                FeasibilitySeverity.WARNING,
                f"峰值气隙磁密为 {result.magnetic.air_gap_flux_density_peak_t:.2f} T，"
                "请验证永磁体工作点和饱和假设。",
            )
        )

    return DesignFeasibilityAssessment(
        current_density_a_per_mm2=current_density,
        phase_current_rms_a=float(result.performance.phase_current_rms_a),
        conductor_current_rms_a=conductor_current,
        conductor_copper_area_mm2=conductor_area,
        current_density_status=FeasibilityCalculability.CALCULABLE,
        slot_fill_factor=slot_fill,
        slot_fill_status=slot_status,
        total_slot_copper_area_mm2=total_copper,
        total_available_slot_area_mm2=total_available,
        legacy_fill_proxy=float(result.performance.fill_factor),
        required_voltage_line_rms_v=required_voltage,
        available_voltage_line_rms_v=available_voltage,
        voltage_margin_percent=voltage_margin,
        voltage_status=voltage_status,
        issues=tuple(issues),
    )


def format_feasibility_messages_zh(
    assessment: DesignFeasibilityAssessment,
) -> tuple[str, ...]:
    labels = {
        FeasibilitySeverity.ERROR: "错误",
        FeasibilitySeverity.SEVERE_DESIGN_RISK: "严重设计风险",
        FeasibilitySeverity.WARNING: "警告",
        FeasibilitySeverity.INFO: "提示",
    }
    return tuple(
        f"[{labels[issue.severity]}] {issue.message_zh}" for issue in assessment.issues
    )
