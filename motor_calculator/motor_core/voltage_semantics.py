"""Corrected steady-state required-voltage semantics (Phase 9B Batch C1).

Phase 9 Finding 1 established that the legacy expression

    legacy = sqrt(E_line_rms**2 + (I_ph*R_line)**2 + (I_ph*we*L_s)**2) * k
             |__ sqrt3 x phase   |__ 2 x phase      |__ 1 x phase

mixes three reference bases inside a single root and RSS-combines terms that
are not mutually orthogonal. With `id = 0` the back-EMF and the resistive drop
are in phase, so only the reactive drop is in quadrature.

This module publishes the corrected quantity in ONE explicit basis. It does not
replace the legacy output; promotion is gated separately.

There is deliberately no third formula here: `corrected_required_voltage_...`
and `dq_steady_state_required_voltage_...` are the same expression written two
ways, and a test asserts they agree to 1e-12 relative.
"""

from __future__ import annotations

import math

from .constants import VOLTAGE_REQUIREMENT_MARGIN_FACTOR


# ---------------------------------------------------------------------------
# C1.1 Basis declaration. Every input term is per-phase; only the result is line.
# ---------------------------------------------------------------------------

CORRECTED_VOLTAGE_BASIS: dict[str, str] = {
    "back_emf": "phase_rms_volt",
    "current": "phase_rms_ampere",
    "resistance": "phase_ohm",
    "inductance": "phase_synchronous_henry",
    "result": "line_rms_volt",
}

CORRECTED_VOLTAGE_BASIS_NOTE_ZH = (
    "修正式的每一项均为每相 RMS 量：相反电动势 E_ph(RMS)、相电流 I_ph(RMS)、"
    "相电阻 R_ph、每相同步电感 L_s = L_ph − M；仅在最后统一乘 √3 转为线电压 RMS。"
    "不使用 legacy 的 2×R_ph（端子直流口径）与每相电抗混合基准。"
)

LEGACY_VOLTAGE_STATUS = "legacy_line_rms_requirement_model"
CORRECTED_VOLTAGE_STATUS = "corrected_single_basis_steady_state_phasor"
CORRECTED_VOLTAGE_NOT_APPLICABLE_STATUS = (
    "not_applicable_non_sinusoidal_control_mode"
)


# ---------------------------------------------------------------------------
# Phase 9C promotion. The corrected value is the authoritative engineering
# result for supported PMSM calculations; the legacy value survives only as a
# clearly named compatibility/reference output.
# ---------------------------------------------------------------------------

VOLTAGE_AUTHORITY_CORRECTED = "CORRECTED_SAME_BASIS_PMSM"
VOLTAGE_AUTHORITY_LEGACY_REFERENCE = "LEGACY_MIXED_BASIS_REFERENCE"
VOLTAGE_SEMANTICS_VERSION = "phase9c.voltage.v1"

VOLTAGE_GUIDANCE_ZH = (
    "当前 PMSM 电压裕量使用统一 line-RMS 基准计算，并与现有 dq 稳态模型保持一致。"
    "该结果仍为稳态近似，不代表完整逆变器开关级动态裕量。"
)

LEGACY_VOLTAGE_REFERENCE_NOTE_ZH = (
    "legacy 所需电压与 legacy 直流母线差额仅作为兼容/调试参考保留，"
    "其混合基准（E 线基准、I·R 端子基准、I·X 每相基准）与 RSS 合成已被判定为缺陷，"
    "不再驱动任何工程结论。"
)


class VoltageSemanticsError(ValueError):
    """Raised when a corrected-voltage input is structurally invalid."""


def _require_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise VoltageSemanticsError(f"{name} must be finite, got {value!r}")
    return numeric


def corrected_required_voltage_line_rms_v(
    *,
    back_emf_phase_rms_v: float,
    phase_current_rms_a: float,
    phase_resistance_ohm: float,
    synchronous_inductance_h: float,
    electrical_angular_speed_rad_s: float,
    margin_factor: float = VOLTAGE_REQUIREMENT_MARGIN_FACTOR,
) -> float:
    """Steady-state terminal voltage requirement on a single LINE-RMS basis.

    Balanced three-phase, sinusoidal, surface-PM (`Ld = Lq = L_s`), `id = 0`:

        V_ph = E_ph + I_ph * (R_ph + j * we * L_s)
        |V_ph| = sqrt( (E_ph + I_ph*R_ph)**2 + (I_ph*we*L_s)**2 )
        V_line_rms = sqrt(3) * |V_ph| * margin_factor

    `id = 0` is the model's own assumption: the rated current is obtained as
    `T_rated / Kt`, i.e. every ampere is treated as torque-producing.
    """

    back_emf = _require_finite("back_emf_phase_rms_v", back_emf_phase_rms_v)
    current = _require_finite("phase_current_rms_a", phase_current_rms_a)
    resistance = _require_finite("phase_resistance_ohm", phase_resistance_ohm)
    inductance = _require_finite("synchronous_inductance_h", synchronous_inductance_h)
    omega_e = _require_finite(
        "electrical_angular_speed_rad_s", electrical_angular_speed_rad_s
    )
    margin = _require_finite("margin_factor", margin_factor)

    in_phase = back_emf + current * resistance
    quadrature = current * omega_e * inductance
    return math.sqrt(3.0) * math.hypot(in_phase, quadrature) * margin


def dq_steady_state_required_voltage_line_rms_v(
    *,
    magnet_flux_linkage_wb: float,
    phase_current_rms_a: float,
    phase_resistance_ohm: float,
    synchronous_inductance_h: float,
    electrical_angular_speed_rad_s: float,
    margin_factor: float = VOLTAGE_REQUIREMENT_MARGIN_FACTOR,
) -> float:
    """The same requirement expressed through the Phase 6 dq equations.

    Setting `did/dt = diq/dt = 0` and `id = 0` in
    `dynamics.pmsm_model.PMSMDynamicModel.compute_electrical_derivatives` gives

        vd = -we * Lq * iq
        vq =  Rs * iq + we * psi_f

    The Park transform used by the project is amplitude-invariant (the inverter
    envelope in `dynamics.inverter` is `Vdc/sqrt(3)` applied to `hypot(vd, vq)`),
    so `|V_dq|` is the phase PEAK and

        V_line_rms = |V_dq| / sqrt(2) * sqrt(3)

    with `iq = sqrt(2) * I_phase_rms`.
    """

    psi_f = _require_finite("magnet_flux_linkage_wb", magnet_flux_linkage_wb)
    current = _require_finite("phase_current_rms_a", phase_current_rms_a)
    resistance = _require_finite("phase_resistance_ohm", phase_resistance_ohm)
    inductance = _require_finite("synchronous_inductance_h", synchronous_inductance_h)
    omega_e = _require_finite(
        "electrical_angular_speed_rad_s", electrical_angular_speed_rad_s
    )
    margin = _require_finite("margin_factor", margin_factor)

    iq = math.sqrt(2.0) * current
    vd = -omega_e * inductance * iq
    vq = resistance * iq + omega_e * psi_f
    phase_peak = math.hypot(vd, vq)
    return phase_peak / math.sqrt(2.0) * math.sqrt(3.0) * margin


def legacy_corrected_relative_difference(
    legacy_v: float, corrected_v: float
) -> float | None:
    """`corrected / legacy - 1`, or None when the legacy value is unusable."""

    legacy = float(legacy_v)
    if not math.isfinite(legacy) or legacy == 0.0:
        return None
    return float(corrected_v) / legacy - 1.0


# ---------------------------------------------------------------------------
# C1.6 Downstream consumer inventory.
#
# Nothing may carry MIGRATE_TO_CORRECTED until the promotion gates pass; a test
# enforces that. DUAL_DISPLAY means the surface shows both values side by side.
# ---------------------------------------------------------------------------

VOLTAGE_CONSUMER_CLASSIFICATION: dict[str, dict[str, str]] = {
    "feasibility": {
        "classification": "DUAL_DISPLAY",
        "surface": "validation.design_feasibility.evaluate_design_feasibility",
        "rationale_zh": (
            "同时给出 legacy 同基裕量与修正同基裕量；严重度判据仍由 legacy 值驱动，"
            "待推广门禁通过后再切换。"
        ),
    },
    "optimizer": {
        "classification": "NEEDS_REVIEW",
        "surface": "PMDC_Calculator_claude204.run_optimization",
        "rationale_zh": (
            "RC2 已将其电压约束改为同基包络，但仍以 legacy 所需电压为输入。"
            "Batch C2 以对比模式评估，不在 C1 中改动。"
        ),
    },
    "dashboard": {
        "classification": "DUAL_DISPLAY",
        "surface": "plots.dashboard.build_dashboard_data",
        "rationale_zh": "所需电压与电压裕量均并列展示 legacy 与修正值，并标注基准差异。",
    },
    "plots": {
        "classification": "NEEDS_REVIEW",
        "surface": "plots.performance speed sweep",
        "rationale_zh": (
            "速度扫描电压曲线目前仍绘制 legacy 所需电压；修正曲线在推广后加入，"
            "以免同一张图出现两条含义相近但基准不同的线。"
        ),
    },
    "exports": {
        "classification": "DUAL_DISPLAY",
        "surface": "gui.main_window.rc2_export_payload, legacy TXT/JSON/CSV",
        "rationale_zh": "两个值以显式不同的键名导出，legacy 键保持原语义不变。",
    },
    "reports": {
        "classification": "DUAL_DISPLAY",
        "surface": "gui.main_window._inject_rc2_engineering_summary",
        "rationale_zh": "详细结果摘要同时列出两者与相对差，并说明 legacy 为兼容值。",
    },
    "presets": {
        "classification": "NEEDS_REVIEW",
        "surface": "presets/data/presets.json",
        "rationale_zh": (
            "design.manufacturability_start.v1 在修正基准下裕量为负；"
            "Batch C3 准备并行候选 v2，v1 保持不变。"
        ),
    },
    "project_snapshots": {
        "classification": "LEGACY_KEEP",
        "surface": "plots.snapshot / project.schema result_snapshot",
        "rationale_zh": (
            "快照保存的是 AnalysisResult.to_dict()，新增字段自动包含；"
            "输入哈希与 schema 版本不变，历史项目不受影响。"
        ),
    },
    "uncertainty": {
        "classification": "LEGACY_KEEP",
        "surface": "validation.uncertainty_sweep",
        "rationale_zh": "受控参考参数不确定性分析不消费所需电压，无需改动。",
    },
    "sensitivity": {
        "classification": "LEGACY_KEEP",
        "surface": "calibration_sandbox.sensitivity",
        "rationale_zh": "只读局部扰动复用完整结果对象，新增字段随之可用，无需改动。",
    },
}
