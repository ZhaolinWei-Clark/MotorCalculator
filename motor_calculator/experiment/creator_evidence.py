"""Phase 11B: assembling the CREATOR evidence for display, including its absence.

The repository ships no raw data, so the normal state of this view is *"the
source is registered, the data is not here"*. That has to be a first-class,
informative state rather than an error, because it is what every user sees until
they fetch the dataset themselves.

When the data is present, the report carries what was extracted **and** what the
extraction is not entitled to claim. The second part is the reason this module
exists: a successful reproduction of a published number is evidence about this
software's processing chain, and it is evidence about nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import creator_adapter as adapter
from . import creator_source as src
from .compatibility import (
    CompatibilityAssessment,
    MachineCompatibility,
    assess_compatibility,
    project_machine_identity,
)
from .origins import ParameterSet, render_parameter_table_zh
from .sources import SOURCE_TYPE_CAVEATS_ZH, DatasetSourceType
from .topology import (
    AFPM_NOT_VALIDATED,
    PIPELINE_VALIDATED,
    PIPELINE_VALIDATED_NOTE_ZH,
    MachineTopology,
)

CREATOR_EVIDENCE_SCHEMA_VERSION = "phase11b.creator_evidence.v1"

#: The state when no dataset root is configured. Not an error.
DATA_NOT_CONFIGURED = "PUBLIC_REFERENCE_DATA_NOT_CONFIGURED"
DATA_AVAILABLE = "PUBLIC_REFERENCE_DATA_AVAILABLE"
DATA_UNREADABLE = "PUBLIC_REFERENCE_DATA_UNREADABLE"

NOT_CONFIGURED_MESSAGE_ZH = (
    f"{DATA_NOT_CONFIGURED} —— 已登记 CREATOR 公开参考源，但本机尚未配置其数据目录。\n"
    "本仓库**不分发原始测量数据**：只保存引用、DOI、许可、文件哈希与适配器。\n"
    f"如需运行分析，请自行从 https://doi.org/{src.DATASET_DOI} 获取数据集"
    f"（{src.LICENSE_NAME}），再在此处指向你自己的副本。\n"
    "在此之前，此处不显示任何数值，也不显示零。"
)


@dataclass(frozen=True)
class CreatorEvidenceReport:
    """Everything the public-reference view shows, present or absent."""

    schema_version: str
    state: str
    message_zh: str
    summary: src.SourceSummary
    parameters: ParameterSet
    compatibility: CompatibilityAssessment
    #: Present only when the data is configured and readable.
    back_emf: adapter.BackEmfWaveformResult | None = None
    publication_check: adapter.PublicationCheck | None = None
    single_speed_ke: adapter.SingleSpeedKe | None = None
    cogging: adapter.CoggingResult | None = None
    no_load: adapter.NoLoadLossResult | None = None
    drive_cycle: adapter.DriveCycleResult | None = None
    errors_zh: tuple[str, ...] = ()

    @property
    def has_data(self) -> bool:
        return self.state == DATA_AVAILABLE

    @property
    def is_different_machine(self) -> bool:
        return self.compatibility.status is MachineCompatibility.DIFFERENT_MACHINE

    @property
    def pipeline_claim(self) -> str:
        """What a successful run is entitled to claim. Never the AFPM design."""

        if not self.has_data or self.publication_check is None:
            return DATA_NOT_CONFIGURED if not self.has_data else DATA_UNREADABLE
        return PIPELINE_VALIDATED if self.publication_check.reproduced else DATA_UNREADABLE

    @property
    def afpm_claim(self) -> str:
        """Constant. No CREATOR result can ever change this."""

        return AFPM_NOT_VALIDATED


def build_report(
    dataset_root: str | Path | None,
    project_parameters: dict[str, Any] | None = None,
    *,
    verify: bool = True,
) -> CreatorEvidenceReport:
    """Assemble the CREATOR evidence report for the current project.

    ``dataset_root`` of ``None`` produces the not-configured state with the
    source record and compatibility verdict still fully populated -- those are
    metadata and need no data file.
    """

    summary = src.source_summary()
    parameters = src.published_parameters()
    compatibility = assess_compatibility(
        src.CREATOR_MACHINE,
        project_machine_identity(project_parameters or {}, connection="WYE"),
    )

    if not dataset_root:
        return CreatorEvidenceReport(
            schema_version=CREATOR_EVIDENCE_SCHEMA_VERSION,
            state=DATA_NOT_CONFIGURED,
            message_zh=NOT_CONFIGURED_MESSAGE_ZH,
            summary=summary,
            parameters=parameters,
            compatibility=compatibility,
        )

    errors: list[str] = []
    back_emf = check = ke = cogging = no_load = drive_cycle = None

    try:
        back_emf = adapter.read_back_emf(dataset_root, verify=verify)
        check = adapter.check_against_publication(back_emf)
        ke = adapter.single_speed_ke(back_emf)
    except (adapter.CreatorAdapterError, OSError, ValueError) as error:
        errors.append(f"反电动势波形：{error}")
    try:
        cogging = adapter.read_cogging(dataset_root, verify=verify)
    except (adapter.CreatorAdapterError, OSError, ValueError) as error:
        errors.append(f"齿槽转矩：{error}")
    try:
        no_load = adapter.read_no_load_loss(dataset_root, verify=verify)
    except (adapter.CreatorAdapterError, OSError, ValueError) as error:
        errors.append(f"空载损耗：{error}")
    try:
        drive_cycle = adapter.read_drive_cycle(dataset_root)
    except (adapter.CreatorAdapterError, OSError, ValueError) as error:
        errors.append(f"行驶工况：{error}")

    if back_emf is None and cogging is None and no_load is None:
        return CreatorEvidenceReport(
            schema_version=CREATOR_EVIDENCE_SCHEMA_VERSION,
            state=DATA_UNREADABLE,
            message_zh=(
                f"{DATA_UNREADABLE} —— 已配置数据目录，但其中没有可读的 CREATOR 文件。\n"
                + "\n".join(errors)
            ),
            summary=summary,
            parameters=parameters,
            compatibility=compatibility,
            errors_zh=tuple(errors),
        )

    return CreatorEvidenceReport(
        schema_version=CREATOR_EVIDENCE_SCHEMA_VERSION,
        state=DATA_AVAILABLE,
        message_zh=(
            f"{DATA_AVAILABLE} —— 已从本机副本读取 CREATOR 公开实测数据。"
            "所有数值均来自使用者自己的数据集副本，本仓库未分发任何原始数据。"
        ),
        summary=summary,
        parameters=parameters,
        compatibility=compatibility,
        back_emf=back_emf,
        publication_check=check,
        single_speed_ke=ke,
        cogging=cogging,
        no_load=no_load,
        drive_cycle=drive_cycle,
        errors_zh=tuple(errors),
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_header_zh(report: CreatorEvidenceReport) -> str:
    summary = report.summary
    return "\n".join(
        [
            f"来源：{summary.title}",
            f"DOI：{summary.doi}",
            f"证据类别：{summary.evidence_class}",
            f"    {SOURCE_TYPE_CAVEATS_ZH[DatasetSourceType(summary.evidence_class)]}",
            f"机器拓扑：{summary.topology}（{summary.topology_label_zh}）",
            f"机器一致性：{report.compatibility.status.value}"
            f"（{report.compatibility.status_label_zh}）",
            f"    {report.compatibility.reason_zh}",
            f"    {report.compatibility.permitted_use_zh}",
            f"许可：{summary.license_name}    仓库策略：{summary.commit_policy}",
            f"    {src.COMMIT_POLICY_NOTE_ZH}",
            "",
            "可用证据：",
            *(f"  · {item}" for item in summary.available_evidence_zh),
        ]
    )


def render_back_emf_zh(report: CreatorEvidenceReport) -> str:
    if report.back_emf is None:
        return report.message_zh
    emf = report.back_emf
    analysis = emf.analysis(emf.reference_phase)
    check = report.publication_check
    ke = report.single_speed_ke
    lines = [
        f"文件：{emf.binding.path.name}",
        f"文件完整性：{emf.binding.integrity}"
        + ("（SHA-256 与审计记录一致）" if emf.binding.is_verified else ""),
        f"样本数：{emf.sample_count}    角度跨度：{analysis.angle_span_deg:.4f}° 机械",
        f"转速：{emf.speed_rpm:.0f} rpm（来自来源文档）    极对数：{emf.pole_pairs}",
        f"角度基准：{emf.angle_basis}",
        f"电压基准：{emf.voltage_basis}",
        f"三相之和：max|Eu+Ev+Ew| = {emf.phase_sum_max_abs:.4f} V"
        f"（原始峰值的 {emf.phase_sum_residual_ratio * 100.0:.2f} %）"
        f" → 平衡性检查 {'通过' if emf.balanced else '未通过'}",
        "",
        f"基波峰值（相）：{emf.fundamental_peak_v:.6f} V",
        f"基波有效值（相）：{emf.fundamental_rms_v:.6f} V",
        f"原始波形峰值：{emf.raw_peak_v:.4f} V",
        f"原始峰值 / 基波峰值：{analysis.crest_ratio:.4f}"
        f"　← 直接取原始峰值会高估 {(analysis.crest_ratio - 1.0) * 100.0:.1f} %",
        f"THD：{analysis.thd * 100.0:.3f} %",
        f"三相基波离散度：{emf.phase_spread_percent:.4f} %",
        "",
        "谐波（电气次数，峰值）：",
    ]
    for harmonic in analysis.harmonics:
        if harmonic.percent_of_fundamental is None:
            continue
        lines.append(
            f"  h{harmonic.order:<3} {harmonic.amplitude:10.6f} V "
            f"({harmonic.percent_of_fundamental:7.3f} % 基波)"
        )
    if check is not None:
        lines.extend(
            [
                "",
                "— 与公开值比对 —",
                f"  提取值：{check.extracted:.6f} V",
                f"  公开值：{check.published:.4f} V",
                f"  偏差：{check.difference_percent:+.5f} %（容差 ±{check.tolerance_percent} %）",
                f"  复现：{'是' if check.reproduced else '否'}",
                f"  {check.note_zh}",
            ]
        )
    if ke is not None:
        lines.extend(
            [
                "",
                "— 单转速 Ke —",
                f"  Ke = {ke.value_v_per_rad_s:.8f} V/(rad/s)",
                f"  来源标记：{ke.provenance}",
                f"  电压基准：{ke.voltage_basis}    转速基准：{ke.speed_basis}",
                f"  转速：{ke.speed_rpm:.0f} rpm（ω = {ke.angular_speed_rad_s:.4f} rad/s）",
                f"  公式：{ke.formula}",
                f"  R²：不适用（单转速点不是回归，不给 R²）",
                f"  不确定度：{ke.uncertainty_status} —— {ke.uncertainty_note_zh}",
                "  局限：",
                *(f"    · {item}" for item in ke.limitations_zh),
            ]
        )
    lines.extend(["", "说明：", *(f"  · {item}" for item in emf.notes_zh)])
    lines.extend(
        [
            "",
            f"结论：{report.pipeline_claim}",
            f"  {PIPELINE_VALIDATED_NOTE_ZH}",
            f"  {report.afpm_claim}",
        ]
    )
    return "\n".join(lines)


def render_cogging_zh(report: CreatorEvidenceReport) -> str:
    if report.cogging is None:
        return report.message_zh
    cog = report.cogging
    lines = [
        f"文件：{cog.binding.path.name}    完整性：{cog.binding.integrity}",
        f"样本数：{cog.sample_count}（全量统计，未降采样）"
        f"    角度跨度：{cog.angle_span_deg:.3f}°",
        f"电流条件：{cog.current_condition}    转速：{cog.speed_rpm} rpm（准静态）",
        f"转矩基准：{cog.torque_basis}",
        "",
        f"最大正峰：{cog.max_positive_nm:+.6f} Nm",
        f"最大负峰：{cog.min_negative_nm:+.6f} Nm",
        f"最大绝对值 max|T|：{cog.max_abs_nm:.6f} Nm",
        f"峰峰值：{cog.peak_to_peak_nm:.6f} Nm",
        f"均值：{cog.mean_nm:.3e} Nm    有效值：{cog.rms_nm:.6f} Nm",
        "",
        f"公开参考标量：{cog.published_scalar_nm} Nm",
        f"⚠ {cog.published_scalar_flag}",
        f"  最接近的原始统计量：{cog.published_scalar_matches}",
        f"  {cog.published_scalar_note_zh}",
    ]
    if cog.harmonics is not None:
        lines.extend(["", "齿槽谐波（机械次数，峰值）："])
        for harmonic in cog.harmonics.harmonics:
            lines.append(f"  h{harmonic.order:<3} {harmonic.amplitude:.6f} Nm")
    lines.extend(["", "说明：", *(f"  · {item}" for item in cog.notes_zh)])
    return "\n".join(lines)


def render_no_load_zh(report: CreatorEvidenceReport) -> str:
    if report.no_load is None:
        return report.message_zh
    result = report.no_load
    lines = ["各次空载测量："]
    for run in result.runs:
        lines.append(
            f"  {run.measurement_date}  {run.configuration:22} "
            f"{len(run.speeds_rpm)} 个转速点    {run.binding.path.name}"
            f"（{run.binding.integrity}）"
        )
    lines.extend(
        [
            "",
            f"来源公开的铁耗数据：{len(result.published_iron_loss)} 点，"
            f"来源标记 {result.published_iron_loss_origin.value}",
            f"重建参照：{result.reconstruction_reference}",
            "",
            f"{'频率 Hz':>9}{'转速 rpm':>10}{'公开 W':>10}{'重建 W':>11}{'残差 %':>10}",
        ]
    )
    for item in result.reconstruction:
        lines.append(
            f"{item.frequency_hz:9.3f}{item.speed_rpm:10.1f}{item.published_w:10.5f}"
            f"{item.reconstructed_w:11.5f}{item.residual_percent:+10.3f}"
        )
    lines.extend(
        [
            "",
            f"平均 |残差|：{result.mean_abs_residual_percent:.3f} %"
            f"    最大 |残差|：{result.max_abs_residual_percent:.3f} %",
            f"重建是否收敛到报告阈值内：{'是' if result.closes else '否'}"
            f"（阈值 {adapter.RECONSTRUCTION_TOLERANCE_PERCENT} %）",
            "",
            "说明：",
            *(f"  · {item}" for item in result.notes_zh),
        ]
    )
    return "\n".join(lines)


def render_parameters_zh(report: CreatorEvidenceReport) -> str:
    return render_parameter_table_zh(report.parameters)


def render_drive_cycle_zh(report: CreatorEvidenceReport) -> str:
    if report.drive_cycle is None:
        return report.message_zh
    cycle = report.drive_cycle
    lines = [
        f"车型：{cycle.vehicle}    工况：{cycle.cycle}",
        f"各信号时间基准一致：{'是' if cycle.shared_time_base else '否'}",
        "",
        f"{'信号':<16}{'规范字段':<18}{'语义':<20}{'点数':>7}{'表头':>7}",
    ]
    for signal in cycle.signals:
        lines.append(
            f"{signal.name:<16}{signal.canonical:<18}{signal.semantics:<20}"
            f"{len(signal.values):>7}{'有' if signal.has_header else '无':>7}"
        )
        lines.append(
            f"    范围 {signal.min_value:.4f} … {signal.max_value:.4f} {signal.unit}"
            + ("    含负值（回馈）" if signal.has_negative else "")
        )
    lines.extend(
        [
            "",
            f"输入能量：{cycle.input_energy_j:.2f} J",
            f"输出能量：{cycle.output_energy_j:.2f} J",
            f"循环效率（能量比）：{cycle.cycle_efficiency:.4f}",
            f"回馈样本数：{cycle.regenerative_samples}",
            "",
            "说明：",
            *(f"  · {item}" for item in cycle.notes_zh),
        ]
    )
    return "\n".join(lines)
