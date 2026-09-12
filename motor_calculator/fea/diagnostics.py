"""Phase 10E: the engineering diagnostics a validation comparison should show.

A single "analytical vs FEMM: +7.15 %" line is not useful to an engineer, and it
is actively misleading if it is read as a model error. Phase 10D showed that
number was a product of a winding-geometry mismatch, a flux-convention
mismatch, a waveform effect and a rounding constant, two of which pull in
opposite directions.

This module assembles what the user needs to see in order to understand *why*
two models differ, without changing either of them. It computes nothing new: it
collects values other layers produced and labels each with its evidence class.

Three rules are enforced by construction:

* a numerical comparison is never labelled as experimental validation;
* no "corrected analytical" value is produced anywhere;
* the calibration status is never anything but ``NONE``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DIAGNOSTICS_SCHEMA_VERSION = "phase10e.fea.diagnostics.v1"

#: Calibration is not a setting. It is a property of this project.
CALIBRATION_STATUS = "NONE"


class EvidenceLabel:
    """Evidence classes the UI must render distinctly.

    ``VALIDATED`` is reserved for a quantity backed by physical measurement.
    A numerical comparison, however close, earns ``NUMERICAL_FEA`` and nothing
    stronger; conflating the two is the failure mode this project exists to
    avoid.
    """

    VALIDATED = "VALIDATED"
    NOT_YET_VALIDATED = "NOT_YET_VALIDATED"
    NUMERICAL_FEA = "NUMERICAL_FEA"
    EXPERIMENTAL_MEASUREMENT = "EXPERIMENTAL_MEASUREMENT"
    MODEL_LIMITATION = "MODEL_LIMITATION"
    DEFINITION_CONVENTION_MISMATCH = "DEFINITION_CONVENTION_MISMATCH"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    HISTORICAL_INTERPRETATION_SUPERSEDED = "HISTORICAL_INTERPRETATION_SUPERSEDED"
    # Phase 10F. A quantity whose analytical value is a user-supplied ratio is
    # not a model output, and one with no first-principles model at all cannot
    # be said to agree with anything.
    NOT_EXPERIMENTALLY_VALIDATED = "NOT_EXPERIMENTALLY_VALIDATED"
    EMPIRICAL_INPUT = "EMPIRICAL_INPUT"
    NO_ANALYTICAL_MODEL = "NO_ANALYTICAL_MODEL"
    MORE_VALIDATION_REQUIRED = "MORE_VALIDATION_REQUIRED"
    NOT_AN_INDEPENDENT_PREDICTION = "NOT_AN_INDEPENDENT_PREDICTION"

    #: Labels that may be rendered with an affirmative (green) style. Only a
    #: physically measured result qualifies.
    AFFIRMATIVE = frozenset({VALIDATED, EXPERIMENTAL_MEASUREMENT})

    ALL = frozenset(
        {
            VALIDATED,
            NOT_YET_VALIDATED,
            NUMERICAL_FEA,
            EXPERIMENTAL_MEASUREMENT,
            MODEL_LIMITATION,
            DEFINITION_CONVENTION_MISMATCH,
            DIAGNOSTIC_ONLY,
            HISTORICAL_INTERPRETATION_SUPERSEDED,
            NOT_EXPERIMENTALLY_VALIDATED,
            EMPIRICAL_INPUT,
            NO_ANALYTICAL_MODEL,
            MORE_VALIDATION_REQUIRED,
            NOT_AN_INDEPENDENT_PREDICTION,
        }
    )


def is_affirmative(label: str) -> bool:
    """Whether a label may be styled as a positive validation outcome."""

    return label in EvidenceLabel.AFFIRMATIVE


@dataclass(frozen=True)
class DiagnosticRow:
    """One labelled line of the diagnostics panel."""

    label_zh: str
    value: str
    evidence: str | None = None
    note_zh: str | None = None


@dataclass(frozen=True)
class ValidationDiagnostics:
    """Everything the diagnostics panel renders, already labelled."""

    schema_version: str
    available: bool
    unavailable_reason_zh: str | None
    fidelity_tier: str | None
    evidence_type: str
    calibration_status: str  # always NONE: never fitted, never applied
    comparison: tuple[DiagnosticRow, ...] = ()
    winding: tuple[DiagnosticRow, ...] = ()
    flux: tuple[DiagnosticRow, ...] = ()
    residual: tuple[DiagnosticRow, ...] = ()
    torque: tuple[DiagnosticRow, ...] = ()
    cogging: tuple[DiagnosticRow, ...] = ()
    limitations_zh: tuple[str, ...] = ()

    @property
    def sections(self) -> tuple[tuple[str, tuple[DiagnosticRow, ...]], ...]:
        return (
            ("对比", self.comparison),
            ("绕组语义", self.winding),
            ("磁通诊断", self.flux),
            ("残差分解", self.residual),
            ("转矩验证", self.torque),
            ("齿槽转矩", self.cogging),
        )


def _fmt(value: float | None, digits: int = 6, suffix: str = "") -> str:
    if value is None or not math.isfinite(value):
        return "未测量"
    return f"{value:.{digits}f}{suffix}"


def _pct(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "未测量"
    return f"{value:+.3f} %"


def unavailable_diagnostics(reason_zh: str) -> ValidationDiagnostics:
    """The panel state when there is no evidence to show.

    Missing evidence is rendered as missing, never as agreement.
    """

    return ValidationDiagnostics(
        schema_version=DIAGNOSTICS_SCHEMA_VERSION,
        available=False,
        unavailable_reason_zh=reason_zh,
        fidelity_tier=None,
        evidence_type=EvidenceLabel.NOT_YET_VALIDATED,
        calibration_status=CALIBRATION_STATUS,  # never fitted, never applied
    )


def build_validation_diagnostics(
    *,
    fidelity_tier: str | None,
    ke_analytical: float | None,
    ke_fea: float | None,
    winding_factor_analytical: float | None,
    winding_factor_meshed: float | None,
    winding_factor_ideal_star: float | None = None,
    analytical_flat_top_flux_wb: float | None = None,
    fea_direct_fundamental_flux_wb: float | None = None,
    fea_linkage_derived_flux_wb: float | None = None,
    budget=None,
    is_mock: bool = False,
) -> ValidationDiagnostics:
    """Assemble the diagnostics for one comparison.

    ``budget`` is an optional
    :class:`~motor_calculator.fea.flux_budget.FluxResidualBudget`; when absent
    the residual section says so rather than showing a partial decomposition.
    """

    if is_mock:
        return unavailable_diagnostics(
            "当前结果来自模拟求解器，不能作为验证证据，因此不展示诊断分解。"
        )
    if ke_analytical is None or ke_fea is None:
        return unavailable_diagnostics(
            "尚无真实求解结果。可生成验证案例与求解脚本，但在实际求解之前不展示任何对比数字。"
        )

    residual_percent = (ke_fea / ke_analytical - 1.0) * 100.0 if ke_analytical else None

    comparison = (
        DiagnosticRow("解析 Ke", _fmt(ke_analytical, 8, " V·s/rad"), EvidenceLabel.DIAGNOSTIC_ONLY,
                      "生产解析模型的输出，未被本面板修改"),
        DiagnosticRow("FEMM Ke", _fmt(ke_fea, 8, " V·s/rad"), EvidenceLabel.NUMERICAL_FEA,
                      "数值有限元结果，不是实测值"),
        DiagnosticRow("残差 (FEMM 相对解析)", _pct(residual_percent), EvidenceLabel.NUMERICAL_FEA),
        DiagnosticRow("物理台架验证", "尚未进行", EvidenceLabel.NOT_YET_VALIDATED,
                      "NUMERICAL_FEA 不等于 EXPERIMENTAL_MEASUREMENT"),
    )

    winding_rows = [
        DiagnosticRow("解析输入 k_w", _fmt(winding_factor_analytical, 9),
                      EvidenceLabel.DIAGNOSTIC_ONLY, "用户或预设在解析模型中输入的值"),
        DiagnosticRow("剖分几何 k_w", _fmt(winding_factor_meshed, 9),
                      EvidenceLabel.DIAGNOSTIC_ONLY,
                      "由求解器实际剖分的导体分布投影到基波得到"),
    ]
    if winding_factor_ideal_star is not None:
        winding_rows.append(
            DiagnosticRow(
                "理想槽电势星形图 k_w", _fmt(winding_factor_ideal_star, 9),
                EvidenceLabel.HISTORICAL_INTERPRETATION_SUPERSEDED,
                "Phase 10B/10C 使用该值解释求解结果；它描述的是理想细丝绕组，不是被剖分的绕组",
            )
        )
    if winding_factor_meshed and winding_factor_analytical:
        winding_rows.append(
            DiagnosticRow(
                "剖分 / 解析输入",
                _pct((winding_factor_meshed / winding_factor_analytical - 1.0) * 100.0),
                EvidenceLabel.DEFINITION_CONVENTION_MISMATCH,
                "两者描述不同的绕组；差异本身不代表任何一方有误",
            )
        )

    flux_rows = (
        DiagnosticRow("解析平顶每极磁通", _fmt(analytical_flat_top_flux_wb, 9, " Wb"),
                      EvidenceLabel.DIAGNOSTIC_ONLY, "集总磁路在磁钢极弧上的平顶磁通"),
        DiagnosticRow("FEMM 直接基波磁通", _fmt(fea_direct_fundamental_flux_wb, 9, " Wb"),
                      EvidenceLabel.NUMERICAL_FEA, "沿气隙直接采样并做空间傅里叶分解得到"),
        DiagnosticRow("FEMM 磁链反推等效磁通", _fmt(fea_linkage_derived_flux_wb, 9, " Wb"),
                      EvidenceLabel.NUMERICAL_FEA,
                      "由磁链除以匝数与剖分 k_w 得到；不是独立的磁通测量"),
    )

    if budget is None:
        residual_rows: tuple[DiagnosticRow, ...] = (
            DiagnosticRow("残差分解", "尚未计算", EvidenceLabel.NOT_YET_VALIDATED,
                          "需要直接气隙场诊断证据才能分解残差"),
        )
    else:
        rows = []
        for label, _factor, percent in budget.as_rows():
            rows.append(
                DiagnosticRow(_BUDGET_LABELS_ZH.get(label, label), _pct(percent),
                              EvidenceLabel.DIAGNOSTIC_ONLY)
            )
        rows.append(
            DiagnosticRow(
                "未解释余量", _pct(budget.unresolved_remainder * 100.0),
                EvidenceLabel.DIAGNOSTIC_ONLY,
                "各分量按乘积合成；余量接近零表示残差已被完整分解",
            )
        )
        residual_rows = tuple(rows)

    return ValidationDiagnostics(
        schema_version=DIAGNOSTICS_SCHEMA_VERSION,
        available=True,
        unavailable_reason_zh=None,
        fidelity_tier=fidelity_tier,
        evidence_type=EvidenceLabel.NUMERICAL_FEA,
        calibration_status=CALIBRATION_STATUS,  # never fitted, never applied
        comparison=comparison,
        winding=tuple(winding_rows),
        flux=flux_rows,
        residual=residual_rows,
        limitations_zh=(
            "对比为数值有限元，非实验测量；物理台架验证尚未完成。",
            "FEA_TIER_3 为平均半径展开的二维 AFPM 近似，不是三维等效声明。",
            "解析平顶磁通与 FEMM 基波磁通是不同的物理量，二者之差包含约定差异。",
            "本面板不修改任何生产计算结果，也不应用任何修正系数。",
        ),
    )


def torque_diagnostic_rows(
    *,
    analytical_electromagnetic_torque_nm: float | None,
    production_shaft_torque_nm: float | None,
    femm_mean_torque_nm: float | None,
    femm_ripple_percent: float | None,
    residual_percent: float | None,
    current_is_back_solved_from_rated_torque: bool,
    mesh_sensitivity_percent: float | None = None,
) -> tuple[DiagnosticRow, ...]:
    """Phase 10F torque rows, on one stated basis.

    ``production_shaft_torque_nm`` is shown next to the electromagnetic value
    precisely so a reader can see that they are different quantities. It is
    never the thing compared against FEMM.
    """

    rows = [
        DiagnosticRow(
            "解析电磁转矩（同基准）",
            _fmt(analytical_electromagnetic_torque_nm, 6, " N·m"),
            EvidenceLabel.DIAGNOSTIC_ONLY,
            "T_em = 3·E_phase_rms·I_phase_rms/ω_mech，与 FEMM 同为气隙电磁基准",
        ),
        DiagnosticRow(
            "生产额定转矩（轴端）",
            _fmt(production_shaft_torque_nm, 6, " N·m"),
            EvidenceLabel.DEFINITION_CONVENTION_MISMATCH,
            "P_rated/ω_mech，是输入派生的轴端量，**不**与 FEMM 同基准，仅供对照",
        ),
        DiagnosticRow(
            "FEMM 电磁转矩（平均）",
            _fmt(femm_mean_torque_nm, 6, " N·m"),
            EvidenceLabel.NUMERICAL_FEA,
            "转子块加权 Maxwell 应力积分 × 平均半径",
        ),
        DiagnosticRow("残差 (FEMM 相对解析)", _pct(residual_percent), EvidenceLabel.NUMERICAL_FEA),
        DiagnosticRow(
            "FEMM 转矩脉动", _pct(femm_ripple_percent), EvidenceLabel.NUMERICAL_FEA,
            "峰峰值除以平均值；生产模型的脉动是用户输入系数，不可与此直接比较",
        ),
    ]
    if current_is_back_solved_from_rated_torque:
        rows.append(
            DiagnosticRow(
                "解析转矩的独立性", "非独立预测",
                EvidenceLabel.NOT_AN_INDEPENDENT_PREDICTION,
                "相电流由额定转矩反解得到（I = T_rated/Kt），因此 T_em ≡ T_rated 恒成立；"
                "该对比实际检验的是 Kt，即 k_w·Φ，而不是一个独立的转矩预测",
            )
        )
    if mesh_sensitivity_percent is not None:
        rows.append(
            DiagnosticRow("网格敏感性", _pct(mesh_sensitivity_percent), EvidenceLabel.NUMERICAL_FEA)
        )
    rows.append(
        DiagnosticRow("物理台架验证", "尚未进行", EvidenceLabel.NOT_EXPERIMENTALLY_VALIDATED)
    )
    return tuple(rows)


def cogging_diagnostic_rows(
    *,
    femm_peak_to_peak_nm: float | None,
    mesh_sensitivity_percent: float | None,
    analytical_status: str,
    analytical_value_nm: float | None = None,
    is_coreless: bool = False,
    signal_above_numerical_floor: bool | None = None,
) -> tuple[DiagnosticRow, ...]:
    """Phase 10F cogging rows.

    ``analytical_status`` is one of :attr:`EvidenceLabel.EMPIRICAL_INPUT` or
    :attr:`EvidenceLabel.NO_ANALYTICAL_MODEL`. There is no path that reports
    agreement between FEMM and a quantity that has no model behind it.
    """

    rows = [
        DiagnosticRow(
            "FEMM 齿槽转矩峰峰值", _fmt(femm_peak_to_peak_nm, 8, " N·m"),
            EvidenceLabel.NUMERICAL_FEA, "零定子电流，仅永磁励磁",
        ),
        DiagnosticRow("网格敏感性", _pct(mesh_sensitivity_percent), EvidenceLabel.NUMERICAL_FEA),
    ]
    if signal_above_numerical_floor is False:
        rows.append(
            DiagnosticRow(
                "信号是否高于数值噪声", "否",
                EvidenceLabel.MORE_VALIDATION_REQUIRED,
                "网格敏感性与齿槽幅值同量级，无法将该信号与离散化误差区分开",
            )
        )
    elif signal_above_numerical_floor is True:
        rows.append(
            DiagnosticRow("信号是否高于数值噪声", "是", EvidenceLabel.NUMERICAL_FEA)
        )
    if is_coreless:
        rows.append(
            DiagnosticRow(
                "解析齿槽转矩", _fmt(analytical_value_nm, 8, " N·m"),
                EvidenceLabel.NO_ANALYTICAL_MODEL,
                "无槽定子按构造无齿槽转矩，解析值恒为零；这是一个假设，不是模型预测，"
                "因此不存在可与 FEMM 比较的解析量",
            )
        )
    else:
        rows.append(
            DiagnosticRow(
                "解析齿槽转矩", _fmt(analytical_value_nm, 8, " N·m"),
                analytical_status,
                "由用户输入的齿槽系数乘以额定转矩得到，是经验输入而非首要原理模型",
            )
        )
    rows.append(
        DiagnosticRow("物理台架验证", "尚未进行", EvidenceLabel.NOT_EXPERIMENTALLY_VALIDATED)
    )
    return tuple(rows)


_BUDGET_LABELS_ZH = {
    "winding factor: meshed vs assumed": "绕组几何贡献",
    "convention: flat-top flux vs fundamental": "磁通约定贡献",
    "waveform and axial averaging": "波形与轴向平均贡献",
    "sine EMF rounding": "4.44 舍入贡献",
}


def render_diagnostics_zh(diagnostics: ValidationDiagnostics) -> str:
    """Plain-text rendering for the dialog's diagnostics tab."""

    if not diagnostics.available:
        return "\n".join(
            (
                "工程诊断",
                "=" * 48,
                "",
                diagnostics.unavailable_reason_zh or "暂无可用证据。",
                "",
                f"标定状态：{diagnostics.calibration_status}",
            )
        )

    lines = [
        "工程诊断",
        "=" * 48,
        "",
        f"证据类型：{diagnostics.evidence_type}",
        f"保真度等级：{diagnostics.fidelity_tier or '未声明'}",
        f"标定状态：{diagnostics.calibration_status}",
        "",
    ]
    for title, rows in diagnostics.sections:
        if not rows:
            continue
        lines.append(f"【{title}】")
        for row in rows:
            tag = f"  [{row.evidence}]" if row.evidence else ""
            lines.append(f"  {row.label_zh}：{row.value}{tag}")
            if row.note_zh:
                lines.append(f"      · {row.note_zh}")
        lines.append("")
    lines.append("【已知局限】")
    for item in diagnostics.limitations_zh:
        lines.append(f"  · {item}")
    lines.append("")
    lines.append("本面板只展示差异及其成因，不提供任何经过修正的解析值。")
    return "\n".join(lines)
