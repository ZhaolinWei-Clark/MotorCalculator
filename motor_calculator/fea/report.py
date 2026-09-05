"""Chinese-first runtime report rendering for the FEA validation bridge."""

from __future__ import annotations

from .comparison import PROVISIONAL_BAND_STATEMENT, FEAComparisonReport
from .evidence import CONFIDENCE_POLICY_STATEMENT
from .models import FEAComparisonStatus, FEASupportability, FEAValidationCase
from .service import SOLVER_UNAVAILABLE_DETAIL_ZH, SOLVER_UNAVAILABLE_MESSAGE_ZH, FEAValidationRun

STATUS_LABELS_ZH = {
    FEAComparisonStatus.CLOSE_AGREEMENT: "接近一致",
    FEAComparisonStatus.MODERATE_DEVIATION: "中等偏差",
    FEAComparisonStatus.LARGE_DEVIATION: "显著偏差",
    FEAComparisonStatus.NOT_COMPARABLE: "不可比",
    FEAComparisonStatus.INSUFFICIENT_DATA: "数据不足",
}

SUPPORTABILITY_LABELS_ZH = {
    FEASupportability.SUPPORTED: "支持",
    FEASupportability.PARTIALLY_SUPPORTED: "部分支持",
    FEASupportability.UNSUPPORTED: "不支持",
    FEASupportability.NOT_ENOUGH_GEOMETRY: "几何信息不足",
}

TARGET_LABELS_ZH = {
    "NO_LOAD_BACK_EMF": "空载反电动势 / Ke",
    "AVERAGE_TORQUE": "平均电磁转矩",
    "COGGING_TORQUE": "齿槽转矩",
}


def _format_optional(value: float | None, digits: int = 6) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_case_review_zh(case: FEAValidationCase) -> str:
    """The review screen text shown before the user starts a solve."""

    geometry = case.geometry
    winding = case.winding
    point = case.operating_point
    lines = [
        "# FEA 验证案例复核",
        "",
        f"验证目标：{TARGET_LABELS_ZH.get(case.target.value, case.target.value)}",
        f"案例哈希 case_id：{case.case_id}",
        f"案例 schema：{case.schema_version}",
        f"应用版本：{case.application_version}",
        "",
        "## 拓扑与可支持性",
        f"拓扑：{case.supportability.topology}",
        f"可支持性：{SUPPORTABILITY_LABELS_ZH[case.supportability.state]}",
        f"维度：{case.supportability.dimensionality_note}",
        f"保真度等级：{case.supportability.fidelity_tier}",
        "",
        "## 几何映射（中径展开平面切片）",
        f"中径半径 r_mean：{geometry.mean_radius_m:.6f} m",
        f"径向有效长度（求解深度）：{geometry.radial_active_length_m:.6f} m",
        f"中径周长：{geometry.circumference_m:.6f} m",
        f"极对数 p：{geometry.pole_pairs}；槽数 Q：{geometry.slot_count}",
        f"极距 tau_p：{geometry.pole_pitch_m:.6f} m；槽距：{geometry.slot_pitch_m:.6f} m",
        f"磁钢厚度：{geometry.magnet_thickness_m:.6f} m；弧长：{geometry.magnet_arc_length_m:.6f} m",
        f"单侧机械气隙：{geometry.mechanical_air_gap_per_side_m:.6f} m",
        f"磁钢面间总气隙：{geometry.magnetic_gap_between_magnet_faces_m:.6f} m",
        f"是否无铁芯：{'是' if geometry.is_coreless else '否'}",
        "",
        "## 材料映射",
        f"磁钢剩磁 Br：{case.materials.magnet_remanence_t:.6f} T",
        f"磁钢相对磁导率：{case.materials.magnet_relative_permeability:.6f}",
        f"磁钢矫顽力 Hc：{case.materials.magnet_coercivity_a_per_m:.1f} A/m",
        f"导体：{case.materials.conductor_name}，"
        f"{case.materials.conductor_conductivity_ms_per_m:.6f} MS/m",
        f"铁芯模型：{case.materials.core_model_policy.value}",
        "",
        "## 绕组映射",
        f"相数：{winding.phases}；每相串联匝数：{winding.turns_per_phase}；"
        f"并联支路：{winding.parallel_paths}",
        f"每线圈匝数：{winding.turns_per_coil:.6f}；线圈节距：{winding.coil_span_slots} 槽",
        "线圈相位分配：" + " ".join(
            f"{phase}{'+' if sign > 0 else '-'}"
            for phase, sign in zip(winding.coil_phase_assignment, winding.coil_polarity)
        ),
        f"层布置：{winding.layer_arrangement}",
        f"绕组系数（解析侧）：{winding.winding_factor_analytical:.6f}"
        f"（{winding.winding_factor_provenance}）",
        "",
        "## 工况",
        f"机械转速：{point.mechanical_speed_rpm:.4f} rpm",
        f"相电流 RMS：{point.phase_current_rms_a:.6f} A",
        f"电流角（电角度）：{point.current_angle_electrical_deg:.4f}°",
        f"温度：{point.temperature_c:.2f} ℃",
        f"转子角扫描：{point.rotor_angle_start_mech_deg:.6f}° 起，"
        f"跨度 {point.rotor_angle_span_mech_deg:.6f}° 机械角，"
        f"{point.rotor_angle_sample_count} 个采样点",
        f"采样依据：{point.sampling_rationale}",
        "",
        "## 网格策略",
        f"名称：{case.mesh_policy.name}",
        f"全局：{case.mesh_policy.global_size_m:.6e} m；"
        f"气隙：{case.mesh_policy.air_gap_size_m:.6e} m；"
        f"磁钢边缘：{case.mesh_policy.magnet_edge_size_m:.6e} m",
        f"收敛声明：{case.mesh_policy.convergence_claim}（单一网格，不作收敛声明）",
        "",
        "## 对称性",
        f"机器周期数 gcd(Q, 2p)：{case.symmetry.machine_periodicity}",
        f"是否启用扇区：{'是' if case.symmetry.applied else '否（求解完整圆周）'}",
        f"说明：{case.symmetry.rationale}",
        "",
        "## 近似与已知遗漏",
    ]
    lines.extend(f"- {label}" for label in case.supportability.approximation_labels)
    lines.extend(f"- {item}" for item in geometry.omitted_three_dimensional_effects)
    if case.notes:
        lines.append("")
        lines.append("## 案例备注")
        lines.extend(f"- {note}" for note in case.notes)
    return "\n".join(lines)


def render_comparison_zh(report: FEAComparisonReport) -> str:
    """The results screen text, shown only when real data exists."""

    lines = [
        "# 解析 vs FEA 对比",
        "",
        f"验证目标：{TARGET_LABELS_ZH.get(report.target.value, report.target.value)}",
        f"案例哈希：{report.case_id}",
        f"保真度等级：{report.fidelity_tier}",
        f"数据来源：{'模拟管线数据（非验证证据）' if report.is_mock else '真实求解器'}",
        f"是否可作为证据：{'是' if report.evidence_admissible else '否'}",
    ]
    if report.stale_reasons:
        lines.append("")
        lines.append("## 结果已过期")
        lines.extend(f"- {reason}" for reason in report.stale_reasons)
    lines.extend(["", "## 对比结果", ""])
    lines.append("| 量 | 单位 | 解析值 | FEA 值 | 绝对差 | 相对差 % | 判定 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for metric in report.metrics:
        lines.append(
            "| {quantity} | {unit} | {analytical} | {fea} | {absolute} | {relative} | {status} |".format(
                quantity=metric.quantity,
                unit=metric.unit,
                analytical=_format_optional(metric.analytical_value),
                fea=_format_optional(metric.fea_value),
                absolute=_format_optional(metric.absolute_error),
                relative=_format_optional(metric.relative_error_percent, 4),
                status=STATUS_LABELS_ZH[metric.status],
            )
        )
    lines.extend(["", f"判定带说明：{PROVISIONAL_BAND_STATEMENT}", ""])
    for metric in report.metrics:
        if metric.notes:
            lines.append(f"### {metric.quantity} 备注")
            lines.extend(f"- {note}" for note in metric.notes)
            lines.append("")
    lines.append("## 差异的可能来源（候选，未经证实的归因）")
    lines.extend(f"- {candidate}" for candidate in report.discrepancy_candidates)
    lines.extend(
        [
            "",
            "## 校准政策",
            f"自动校准是否启用：{'是' if report.auto_calibration_enabled else '否'}",
            "FEA 结果不会自动修改任何解析参数；任何校准都只能作为提案由人工审批。",
            "",
            "## 置信度政策",
            CONFIDENCE_POLICY_STATEMENT,
        ]
    )
    return "\n".join(lines)


def render_run_zh(run: FEAValidationRun) -> str:
    """Render a complete run, including the solver-unavailable state."""

    sections = [render_case_review_zh(run.case)]
    if run.comparison is None:
        sections.extend(
            [
                "",
                "# 求解状态",
                "",
                SOLVER_UNAVAILABLE_MESSAGE_ZH
                if run.outcome.status == "BLOCKED_BY_ENVIRONMENT"
                else f"求解未产生结果：{run.outcome.status}",
                "",
                run.outcome.detail or SOLVER_UNAVAILABLE_DETAIL_ZH,
                "",
                "本次未产生任何 FEA 数值，因此不展示任何对比数字，也不绘制任何 FEA 曲线。",
            ]
        )
    else:
        sections.extend(["", render_comparison_zh(run.comparison)])
    return "\n".join(sections)
