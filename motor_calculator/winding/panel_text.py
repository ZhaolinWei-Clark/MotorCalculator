"""Phase 10G: the winding engineering panel's content, as data then text.

Kept out of the GUI module so it can be tested without a display, and so the
same rows can be exported or rendered elsewhere without duplicating the
formatting rules.

Every row carries a provenance tag. That is the point of the panel: a user
looking at a winding factor needs to know whether it is something they typed,
something the slot star computed, or something measured off the meshed
geometry, because in this project those have differed by more than 10 %.
"""

from __future__ import annotations

from dataclasses import dataclass

from .slot_fill import ManufacturabilityStatus, Provenance

PANEL_SCHEMA_VERSION = "phase10g.winding_panel.v1"

STATUS_LABELS_ZH = {
    ManufacturabilityStatus.COMFORTABLE: "宽裕",
    ManufacturabilityStatus.FEASIBLE: "可行",
    ManufacturabilityStatus.TIGHT: "偏紧",
    ManufacturabilityStatus.OVERFILLED: "超填充（绕不进）",
    ManufacturabilityStatus.NOT_CALCULABLE: "无法计算",
}

PROVENANCE_LABELS_ZH = {
    Provenance.GEOMETRY_DERIVED: "几何推导",
    Provenance.USER_INPUT: "用户输入",
    Provenance.MANUAL_OVERRIDE: "手动覆盖",
    Provenance.ENGINEERING_ASSUMPTION: "工程假设",
    Provenance.NUMERICAL_FEA: "数值有限元",
}


@dataclass(frozen=True)
class PanelRow:
    label_zh: str
    value: str
    provenance: str | None = None
    note_zh: str | None = None


def _num(value, digits: int = 4, suffix: str = "") -> str:
    if value is None:
        return "不可用"
    return f"{value:.{digits}f}{suffix}"


def _pct(value) -> str:
    if value is None:
        return "不可用"
    return f"{value * 100.0:.2f} %"


def build_winding_panel_rows(
    *, report=None, fill=None, axes=None
) -> tuple[tuple[str, tuple[PanelRow, ...]], ...]:
    """Assemble the panel sections from whichever pieces are available.

    Missing pieces are reported as missing rather than filled with defaults.
    """

    sections: list[tuple[str, tuple[PanelRow, ...]]] = []

    if report is not None:
        sections.append(
            (
                "绕组配置",
                (
                    PanelRow("槽数 Q", str(report.slots), Provenance.USER_INPUT),
                    PanelRow("极数 2p", str(report.pole_count), Provenance.USER_INPUT),
                    PanelRow("相数 m", str(report.phases), Provenance.USER_INPUT),
                    PanelRow("每极每相槽数 q", _num(report.slots_per_pole_per_phase, 4),
                             Provenance.GEOMETRY_DERIVED, "q = Q / (2p·m)"),
                    PanelRow("绕组类型", report.topology_label_zh, Provenance.GEOMETRY_DERIVED),
                    PanelRow("层数", str(report.layers), Provenance.USER_INPUT),
                    PanelRow("线圈节距", f"{report.coil_span_slots} / {report.full_pitch_slots} 槽（整距）",
                             Provenance.USER_INPUT),
                    PanelRow("并联支路数", str(report.parallel_paths), Provenance.USER_INPUT),
                ),
            )
        )
        factors = report.factors
        rows = [
            PanelRow("分布系数 kd", _num(report.distribution_factor, 6), Provenance.GEOMETRY_DERIVED),
            PanelRow("节距系数 kp", _num(report.pitch_factor, 6), Provenance.GEOMETRY_DERIVED),
            PanelRow("斜槽系数 ks", _num(report.skew_factor, 6), Provenance.GEOMETRY_DERIVED),
            PanelRow("理想绕组系数 kw（槽电势星形图）", _num(factors.ideal_slot_star, 6),
                     Provenance.GEOMETRY_DERIVED,
                     "假设线圈边为位于槽中心的细丝，间隔整数个槽距"),
            PanelRow("剖分几何绕组系数 kw", _num(factors.meshed_geometry, 6),
                     Provenance.GEOMETRY_DERIVED,
                     "对求解器实际剖分的导体分布做基波投影，含层位移与有限边宽"),
            PanelRow("有限边宽系数", _num(factors.finite_width_factor, 6),
                     Provenance.GEOMETRY_DERIVED),
        ]
        if factors.entered is not None:
            rows.append(
                PanelRow(
                    "输入的绕组系数 kw", _num(factors.entered, 6),
                    factors.entered_provenance,
                    "仅在显式覆盖时使用；不会静默优先于几何推导值",
                )
            )
        if factors.meshed_over_ideal is not None:
            rows.append(
                PanelRow("剖分 / 理想", f"{(factors.meshed_over_ideal - 1.0) * 100.0:+.3f} %",
                         Provenance.GEOMETRY_DERIVED,
                         "两者描述不同的绕组；差异本身不代表任何一方有误"))
        sections.append(("绕组系数", tuple(rows)))

    if fill is not None:
        sections.append(
            (
                "导体",
                (
                    PanelRow("每线圈边匝数", _num(fill.turns_per_coil_side, 3), Provenance.USER_INPUT),
                    PanelRow("每槽线圈边数", str(fill.coil_sides_per_slot), Provenance.USER_INPUT),
                    PanelRow("每槽导体数", _num(fill.conductors_per_slot, 3), Provenance.GEOMETRY_DERIVED),
                ),
            )
        )
        sections.append(
            (
                "槽利用率",
                (
                    PanelRow("槽毛面积", _num(fill.gross_slot_area_mm2, 3, " mm²"),
                             Provenance.GEOMETRY_DERIVED),
                    PanelRow("可用槽面积", _num(fill.usable_slot_area_mm2, 3, " mm²"),
                             Provenance.GEOMETRY_DERIVED, "已扣除楔块、槽绝缘与间隙"),
                    PanelRow("每槽裸铜面积", _num(fill.bare_copper_area_per_slot_mm2, 3, " mm²"),
                             Provenance.GEOMETRY_DERIVED),
                    PanelRow("每槽绝缘包络面积", _num(fill.envelope_area_per_slot_mm2, 3, " mm²"),
                             Provenance.GEOMETRY_DERIVED, "占据槽空间的是包络，不是裸铜"),
                    PanelRow("裸铜占比（毛面积）", _pct(fill.gross_copper_fill),
                             Provenance.GEOMETRY_DERIVED, "分母：槽毛面积"),
                    PanelRow("裸铜占比（可用面积）", _pct(fill.usable_copper_fill),
                             Provenance.GEOMETRY_DERIVED, "分母：可用槽面积"),
                    PanelRow("包络占比（毛面积）", _pct(fill.gross_envelope_fill),
                             Provenance.GEOMETRY_DERIVED, "分母：槽毛面积"),
                    PanelRow("包络占比（可用面积）", _pct(fill.usable_envelope_fill),
                             Provenance.GEOMETRY_DERIVED, "分母：可用槽面积"),
                    PanelRow("装填系数", _num(fill.packing_factor, 3),
                             fill.packing_factor_provenance,
                             "圆线无法完美铺满槽；该值是工程假设，不是物理常数"),
                    PanelRow("可达包络面积", _num(fill.achievable_envelope_area_mm2, 3, " mm²"),
                             Provenance.ENGINEERING_ASSUMPTION),
                    PanelRow("制造可行性", STATUS_LABELS_ZH.get(fill.status, fill.status),
                             fill.status_provenance,
                             "阈值带为工程假设；计算结果与该建议相互独立"),
                ),
            )
        )

    if axes is not None:
        sections.append(
            (
                "电角度基准",
                (
                    PanelRow("A 相磁轴", _num(axes.phase_a_axis_elec_deg, 3, "°电"),
                             Provenance.GEOMETRY_DERIVED),
                    PanelRow("转子 d 轴（相对 A 相）", _num(axes.d_axis_from_phase_a_elec_deg, 3, "°电"),
                             Provenance.GEOMETRY_DERIVED, "由磁钢极性分布与 A 相导体分布的基波相位之差导出"),
                    PanelRow("转子 q 轴（相对 A 相）", _num(axes.q_axis_from_phase_a_elec_deg, 3, "°电"),
                             Provenance.GEOMETRY_DERIVED, "d 轴 + 90°电"),
                    PanelRow("转子机械角", _num(axes.rotor_angle_mech_deg, 3, "°机"),
                             Provenance.USER_INPUT),
                ),
            )
        )

    return tuple(sections)


def render_winding_panel_zh(sections, warnings: tuple[str, ...] = (), notes: tuple[str, ...] = ()) -> str:
    """Plain-text rendering for the winding engineering tab."""

    if not sections:
        return "\n".join(
            ("绕组工程", "=" * 48, "", "当前设计不足以计算绕组与槽利用率。")
        )
    lines = ["绕组工程", "=" * 48, ""]
    for title, rows in sections:
        lines.append(f"【{title}】")
        for row in rows:
            tag = ""
            if row.provenance:
                tag = f"  [{PROVENANCE_LABELS_ZH.get(row.provenance, row.provenance)}]"
            lines.append(f"  {row.label_zh}：{row.value}{tag}")
            if row.note_zh:
                lines.append(f"      · {row.note_zh}")
        lines.append("")
    if warnings:
        lines.append("【警告】")
        for item in warnings:
            lines.append(f"  ! {item}")
        lines.append("")
    if notes:
        lines.append("【说明】")
        for item in notes:
            lines.append(f"  · {item}")
        lines.append("")
    lines.append("本面板不修改任何生产计算结果；标注为工程假设的数值可由用户自行调整。")
    return "\n".join(lines)
