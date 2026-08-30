"""Audited output inventory used by the dashboard and Phase 8H documentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputInventoryItem:
    key: str
    label_zh: str
    unit: str
    source: str
    mode: str
    applicability: str
    derivation: str
    confidence: str
    suitable_for: tuple[str, ...]
    unavailable_reason: str = ""


OUTPUT_INVENTORY: tuple[OutputInventoryItem, ...] = (
    OutputInventoryItem("rated_torque_nm", "额定转矩", "Nm", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct model output", "legacy production path", ("KPI", "curve", "table")),
    OutputInventoryItem("output_power_w", "输出功率", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct model output", "input operating point", ("KPI", "curve", "table")),
    OutputInventoryItem("input_power_w", "输入功率", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "derived from current loss model", "legacy/model-limited", ("table", "loss")),
    OutputInventoryItem("efficiency_percent", "当前模型估算效率", "%", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "derived from modeled input/output power", "legacy/model-limited", ("KPI", "curve", "table")),
    OutputInventoryItem("mechanical_speed_rpm", "机械转速", "rpm", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct operating point", "input-backed", ("KPI", "curve", "table")),
    OutputInventoryItem("phase_current_rms_a", "相电流 RMS", "A", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct model output", "waveform semantics explicit", ("KPI", "table")),
    OutputInventoryItem("required_voltage_v", "所需线电压 RMS", "V", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "legacy voltage model", "model-limited", ("KPI", "curve", "table")),
    OutputInventoryItem("voltage_margin_percent", "同基电压裕量", "%", "validation.design_feasibility", "static", "PMSM only", "derived from repeated model output and SVPWM-compatible line-RMS envelope", "approximate", ("KPI", "gauge", "curve"), "BLDC switching semantics are insufficient"),
    OutputInventoryItem("current_density_a_per_mm2", "电流密度", "A/mm2", "validation.design_feasibility", "static", "PMSM/BLDC/AFPM", "phase RMS current per equal parallel conductor path", "calculable with equal-sharing assumption", ("KPI", "gauge", "curve")),
    OutputInventoryItem("slot_fill_factor", "近似裸铜槽占比", "ratio", "validation.design_feasibility", "static", "slotted AFPM", "derived from available slot and bare-copper area", "approximate", ("KPI", "gauge", "table"), "slotless/coreless inputs lack slot geometry"),
    OutputInventoryItem("ke_line_rms", "Ke 线电压 RMS", "V/krpm", "AnalysisResult.electrical", "static", "mode-dependent", "explicit electrical semantic output", "parallel revised/legacy semantics", ("KPI", "table", "sensitivity")),
    OutputInventoryItem("kt_phase_rms", "Kt 相电流 RMS", "Nm/A", "AnalysisResult.electrical", "static", "mode-dependent", "explicit electrical semantic output", "parallel revised/legacy semantics", ("KPI", "table", "sensitivity")),
    OutputInventoryItem("back_emf_line_rms_v", "线反电动势 RMS", "V", "AnalysisResult.electrical", "static", "PMSM/BLDC/AFPM", "direct model output", "waveform semantics explicit", ("KPI", "table", "curve")),
    OutputInventoryItem("copper_loss_w", "铜耗", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct legacy loss output", "model-limited", ("loss", "table")),
    OutputInventoryItem("eddy_loss_w", "涡流损耗", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct legacy loss output", "empirical/model-limited", ("loss", "table")),
    OutputInventoryItem("mechanical_loss_w", "机械损耗", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct legacy loss output", "empirical/model-limited", ("loss", "table")),
    OutputInventoryItem("core_loss_w", "铁芯损耗", "W", "AnalysisResult.performance", "static", "PMSM/BLDC/AFPM", "direct legacy loss output", "empirical/model-limited", ("loss", "table")),
    OutputInventoryItem("static_temperature_rise", "静态温升", "degC", "not implemented", "static", "none", "unavailable", "not supported", ("unavailable",), "current static mode has no credible temperature-rise prediction"),
    OutputInventoryItem("dynamic_temperature_c", "绕组温度", "degC", "dynamics.ThermalSimulationResult", "dynamic sandbox", "PMSM", "first-order lumped thermal model", "sandbox only", ("dynamic curve",), "available only after an explicit thermal simulation"),
    OutputInventoryItem("dynamic_speed", "动态转速", "rad/s", "dynamics.SimulationResult", "dynamic sandbox", "PMSM", "time-domain state", "sandbox only", ("dynamic curve",), "available only after an explicit simulation"),
    OutputInventoryItem("dynamic_torque", "动态转矩", "Nm", "dynamics.SimulationResult", "dynamic sandbox", "PMSM", "time-domain plant output", "sandbox only", ("dynamic curve",), "available only after an explicit simulation"),
    OutputInventoryItem("dynamic_id_iq", "id / iq", "A", "dynamics.SimulationResult", "dynamic sandbox", "PMSM", "time-domain electrical states", "sandbox only", ("dynamic curve",), "available only after an explicit simulation"),
    OutputInventoryItem("uncertainty_envelope", "不确定性包络", "metric-specific", "validation.AccuracyEnvelopeResult", "controlled analysis", "controlled AFPM reference", "explicit sweep/Monte Carlo output", "low/incomplete external evidence", ("range bar", "table"), "available only after explicit uncertainty analysis"),
    OutputInventoryItem("confidence_evidence", "工程置信度与证据", "categorical", "validation.confidence_summary", "static/validation", "AFPM", "evidence aggregation", "not a probability", ("status", "table")),
    OutputInventoryItem("sensitivity", "单参数敏感性", "metric-specific", "calibration_sandbox", "sandbox", "supported production inputs", "actual copied-input model evaluations", "sandbox only; not calibration", ("sensitivity", "table"), "available only after explicit sensitivity run"),
)


def inventory_by_key() -> dict[str, OutputInventoryItem]:
    return {item.key: item for item in OUTPUT_INVENTORY}
