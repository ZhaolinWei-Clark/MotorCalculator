"""Deterministic metric-by-metric AFPM external validation campaign."""

from __future__ import annotations

from pathlib import Path

from motor_calculator.motor_core.rated_torque_models import calculate_revised_rated_torque_nm

from .external_metric_comparison import (
    ComparabilityStatus,
    EvidenceType,
    ExternalMetricComparison,
    ExternalMetricEvidence,
    ExternalValidationCampaignResult,
    MetricProvenance,
    compare_external_metric,
)


PARVIAINEN_URL = "https://lutpub.lut.fi/handle/10024/31185"
PRICE_URL = "https://ijme.us/issues/spring2009/ijme_sp_09.pdf"
ABDELLI_URL = "https://doi.org/10.2516/stet/2026004"
BUMBY_URL = "https://durham-repository.worktribe.com/output/1595511/electromagnetic-design-of-axial-flux-permanent-magnet-machines"
HOSSEINI_URL = "https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf"


def _evidence(
    *,
    source_id: str,
    source_title: str,
    source_url: str,
    topology: str,
    metric_name: str,
    value: float | None,
    unit: str,
    operating_point: str,
    quantity_scope: str,
    value_kind: str,
    waveform: str,
    winding_connection: str,
    current_basis: str,
    page: str,
    location: str,
    extraction_note: str,
    evidence_type: EvidenceType,
    uncertainty: str,
    comparability_status: ComparabilityStatus,
    notes: str,
    confidence: str = "medium",
    access_status: str = "full_text_accessed",
) -> ExternalMetricEvidence:
    return ExternalMetricEvidence(
        source_id=source_id,
        source_title=source_title,
        topology=topology,
        metric_name=metric_name,
        value=value,
        unit=unit,
        operating_point=operating_point,
        quantity_scope=quantity_scope,
        value_kind=value_kind,
        waveform=waveform,
        winding_connection=winding_connection,
        current_basis=current_basis,
        provenance=MetricProvenance(
            source_url=source_url,
            page=page,
            location=location,
            extraction_note=extraction_note,
            access_status=access_status,
        ),
        evidence_type=evidence_type,
        uncertainty=uncertainty,
        comparability_status=comparability_status,
        notes=notes,
        confidence=confidence,
    )


def _blocked(evidence: ExternalMetricEvidence, prediction_unit: str) -> ExternalMetricComparison:
    return compare_external_metric(evidence, None, prediction_unit)


def _abdelli_rows() -> list[ExternalMetricComparison]:
    common = dict(
        source_id="abdelli_2026_dssr_afpm",
        source_title="Design and manufacturing of axial flux permanent magnet machines for electric vehicle applications",
        source_url=ABDELLI_URL,
        topology="double-stator/single-rotor slotted AFPM, 18 slots, 12 poles",
        waveform="measured waveform contains even and odd harmonics",
        winding_connection="unavailable",
        current_basis="phase RMS where current is reported",
        evidence_type=EvidenceType.MEASURED,
        uncertainty="No instrument uncertainty reported in the accessible article text.",
        confidence="high for tables; low for untabulated plot values and absent fields",
    )
    return [
        _blocked(_evidence(
            **common, metric_name="back_emf_phase_waveform", value=None, unit="V",
            operating_point="1000 rpm, no load", quantity_scope="measured phase back-EMF waveform",
            value_kind="figure_only", page="article p. 6", location="Figures 10 and 11",
            extraction_note="Measured and FEA curves are visible, but no authoritative numeric ordinate is tabulated.",
            comparability_status=ComparabilityStatus.BLOCKED,
            notes="DSSR topology mismatch and graph-only value prevent a project-model numeric comparison.",
        ), "V"),
        _blocked(_evidence(
            **common, metric_name="torque_nm", value=None, unit="Nm",
            operating_point="1000 rpm, 20-400 A", quantity_scope="measured torque-current sweep",
            value_kind="figure_only", page="article p. 6", location="Figure 12",
            extraction_note="The paper reports maximum FEA/measurement deviation of 3.5%, but no point table.",
            comparability_status=ComparabilityStatus.BLOCKED,
            notes="Graph digitization is not approved evidence and DSSR topology differs from the default model.",
        ), "Nm"),
        _blocked(_evidence(
            **common, metric_name="phase_resistance_ohm", value=None, unit="ohm",
            operating_point="unavailable", quantity_scope="phase resistance",
            value_kind="unavailable", page="entire accessible article", location="not reported",
            extraction_note="No measured or declared phase-resistance value was located.",
            comparability_status=ComparabilityStatus.UNAVAILABLE,
            notes="Missing source value is not represented by zero.",
        ), "ohm"),
        _blocked(_evidence(
            **common, metric_name="phase_inductance_h", value=None, unit="H",
            operating_point="unavailable", quantity_scope="phase or dq inductance",
            value_kind="unavailable", page="entire accessible article", location="not reported",
            extraction_note="No measured or declared phase/Ld/Lq value was located.",
            comparability_status=ComparabilityStatus.UNAVAILABLE,
            notes="Missing source value is not inferred from geometry.",
        ), "H"),
    ]


def _price_rows() -> list[ExternalMetricComparison]:
    common = dict(
        source_id="price_2009_coreless_afpm_generator",
        source_title="Design and Testing of a Permanent Magnet Axial Flux Wind Power Generator",
        source_url=PRICE_URL,
        topology="dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection",
        waveform="sinusoidal measurement; source analytical model also evaluates coil-shape variants",
        winding_connection="Y",
        current_basis="rated load current basis not fully normalized to project current semantics",
        evidence_type=EvidenceType.MEASURED,
        uncertainty="No instrument uncertainty reported; displayed values are rounded.",
        confidence="high for explicitly stated measured values; low for absent fields",
    )
    return [
        _blocked(_evidence(
            **common, metric_name="back_emf_phase_peak_v", value=37.0, unit="V phase peak",
            operating_point="600 rpm, no load", quantity_scope="single-phase measured back-EMF peak",
            value_kind="measured", page="article p. 65 (issue PDF p. 67)", location="Figure 12 and adjacent text",
            extraction_note="Text states a measured peak of 37 V; source analytical prediction is 35.5 V.",
            comparability_status=ComparabilityStatus.BLOCKED,
            notes="Magnet remanence, leakage factor, winding factor, and project winding semantics are incomplete.",
        ), "V phase peak"),
        _blocked(_evidence(
            **common, metric_name="torque_nm", value=12.6, unit="Nm",
            operating_point="500 rpm, rated load current", quantity_scope="measured average shaft torque",
            value_kind="measured", page="article p. 65 (issue PDF p. 67)", location="torque paragraph and Figure 14",
            extraction_note="Text reports 12.6 Nm measured and 12.8 Nm from the source analytical model.",
            comparability_status=ComparabilityStatus.BLOCKED,
            notes="Rated-current semantics and missing project magnetic inputs prevent a model-to-measurement comparison.",
        ), "Nm"),
        _blocked(_evidence(
            **common, metric_name="phase_resistance_ohm", value=None, unit="ohm",
            operating_point="unavailable", quantity_scope="phase resistance", value_kind="unavailable",
            page="article pp. 59-66", location="not reported",
            extraction_note="The accessible article does not tabulate phase resistance.",
            comparability_status=ComparabilityStatus.UNAVAILABLE,
            notes="No resistance value is inferred from wire dimensions.",
        ), "ohm"),
        _blocked(_evidence(
            **common, metric_name="phase_inductance_h", value=None, unit="H",
            operating_point="unavailable", quantity_scope="phase inductance", value_kind="unavailable",
            page="article pp. 59-66", location="not reported",
            extraction_note="The accessible article does not tabulate phase inductance.",
            comparability_status=ComparabilityStatus.UNAVAILABLE,
            notes="No inductance value is inferred from geometry.",
        ), "H"),
    ]


def _parviainen_rows() -> list[ExternalMetricComparison]:
    common = dict(
        source_id="parviainen_2005_afpm_prototype",
        source_title="Design of Axial-Flux Permanent-Magnet Low-Speed Machines and Performance Comparison Between Radial-Flux and Axial-Flux Machines",
        source_url=PARVIAINEN_URL,
        topology="one-rotor/two-stators AFPM; stators electrically parallel; 12 poles",
        waveform="approximately sinusoidal where back-EMF is reported",
        winding_connection="star per stator; two stators electrically parallel",
        current_basis="phase RMS",
        uncertainty="Formal measurement uncertainty is not reported; table values are rounded.",
        confidence="high for tabulated values and topology metadata",
    )
    rated_torque_evidence = _evidence(
        **common, metric_name="rated_torque_nm", value=159.0, unit="Nm",
        operating_point="5 kW rated shaft output, 300 rpm", quantity_scope="rated shaft torque from published power-speed operating point",
        value_kind="published prototype rating", page="dissertation p. 73", location="Table 3.1",
        extraction_note="The same table states 5 kW output, 300 rpm, and 159 Nm rated torque.",
        evidence_type=EvidenceType.PUBLISHED_PROTOTYPE_SPECIFICATION,
        comparability_status=ComparabilityStatus.DIRECT,
        notes="Strict-SI P/omega consistency is topology-independent; this is not electromagnetic torque-current validation.",
    )
    rows = [compare_external_metric(
        rated_torque_evidence,
        calculate_revised_rated_torque_nm(5000.0, 300.0),
        "Nm",
    )]
    blocked_specs = (
        ("back_emf_phase_rms_v", 211.0, "V phase RMS", "rated point, PM temperature approximately 95-100 C", "PM-induced phase voltage", "dissertation pp. 73 and 78", "Table 3.1 and Figure 3.6", "DSSR/parallel-stator topology cannot be routed through the SSDR production magnetic model."),
        ("phase_resistance_ohm", 3.7, "ohm", "prototype DC test", "per-stator phase DC resistance", "dissertation p. 77", "Table 3.3", "Source quantity is per stator while the machine stators operate electrically in parallel."),
        ("Ld_h", 0.055, "H", "inverter estimate", "measured/estimated d-axis inductance", "dissertation p. 77", "Table 3.3", "Production exposes scalar phase inductance; collapsing Ld to that field is not approved."),
        ("Lq_h", 0.060, "H", "inverter estimate", "measured/estimated q-axis inductance", "dissertation p. 77", "Table 3.3", "Production exposes scalar phase inductance; collapsing Lq to that field is not approved."),
        ("efficiency_percent", 89.2, "%", "rated steady state, natural cooling", "measured efficiency", "dissertation p. 79", "prototype test discussion", "Loss/cooling operating-point mapping is incomplete and production loss formulas remain frozen."),
    )
    for metric, value, unit, point, scope, page, location, notes in blocked_specs:
        rows.append(_blocked(_evidence(
            **common, metric_name=metric, value=value, unit=unit,
            operating_point=point, quantity_scope=scope, value_kind="measured or inverter-estimated",
            page=page, location=location, extraction_note=f"Published source value retained exactly as {value:g} {unit}.",
            evidence_type=EvidenceType.MEASURED,
            comparability_status=ComparabilityStatus.BLOCKED, notes=notes,
        ), unit))
    return rows


def _bumby_rows() -> list[ExternalMetricComparison]:
    common = dict(
        source_id="bumby_2004_afpm_validation",
        source_title="Electromagnetic Design of Axial-Flux Permanent Magnet Machines",
        source_url=BUMBY_URL,
        topology="slotless axial-flux permanent-magnet generators; details require full article",
        operating_point="unavailable from repository abstract",
        value_kind="unavailable",
        waveform="unavailable",
        winding_connection="unavailable",
        current_basis="unavailable",
        page="repository abstract", location="abstract only",
        evidence_type=EvidenceType.MEASURED,
        uncertainty="Full numeric tables and measurement uncertainty were not accessible.",
        confidence="low because only metadata and abstract were accessible",
        comparability_status=ComparabilityStatus.UNAVAILABLE,
        access_status="metadata_and_abstract_only",
    )
    return [
        _blocked(_evidence(
            **common, metric_name="back_emf", value=None, unit="V", quantity_scope="measured generator EMF",
            extraction_note="Abstract says the analytical model predicts EMF within 5%, but provides no machine-level values.",
            notes="Full-text numeric evidence is access-blocked; the abstract percentage is not a substitute for source values.",
        ), "V"),
        _blocked(_evidence(
            **common, metric_name="inductance", value=None, unit="H", quantity_scope="measured generator inductance",
            extraction_note="Abstract says the analytical model predicts inductance within 10%, but provides no machine-level values.",
            notes="Full-text numeric evidence is access-blocked; no inductance is inferred.",
        ), "H"),
    ]


def _hosseini_rows() -> list[ExternalMetricComparison]:
    common = dict(
        source_id="hosseini_2008_coreless_afpm_generator",
        source_title="Design, Prototyping and Analysis of a Low-Cost Disk Permanent Magnet Generator with Rectangular Flat-Shaped Magnets",
        source_url=HOSSEINI_URL,
        topology="dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils",
        winding_connection="unavailable",
        current_basis="phase current where reported; RMS/peak basis not explicit",
        evidence_type=EvidenceType.MEASURED,
        uncertainty="No instrument uncertainty reported; tabulated values are retained at source precision.",
        confidence="high for tabulated source values; low for missing winding semantics",
    )
    specs = (
        ("back_emf_no_load_peak_to_peak_v", 160.0, "V phase peak-to-peak", "3000 rpm, no load", "no-load output phase voltage peak-to-peak", "harmonic waveform", "article p. 201", "Table 3", "Unknown connection/waveform semantics and incomplete production winding/leakage inputs block conversion and prediction."),
        ("output_voltage_fundamental_peak_to_peak_v", 102.0, "V phase peak-to-peak", "3000 rpm, 10 ohm load", "fundamental component of loaded output phase voltage", "fundamental extracted from harmonic waveform", "article p. 201", "Table 3", "Peak-to-peak loaded generator output is not the production back-EMF semantic; no unapproved conversion is made."),
        ("efficiency_percent", 78.1, "%", "3000 rpm nominal load", "measured generator efficiency", "not applicable", "article pp. 201-202", "Figure 14 and Table 4", "Matched loss and load semantics are unavailable while production loss formulas remain frozen."),
        ("Xsd_ohm", 2.1, "ohm", "3000 rpm, 300 Hz nominal operation", "measured d-axis synchronous reactance", "not applicable", "article p. 202", "Table 4", "Reactance is not converted to the production scalar inductance without an approved dq/scalar model bridge."),
        ("Xsq_ohm", 2.1, "ohm", "3000 rpm, 300 Hz nominal operation", "measured q-axis synchronous reactance", "not applicable", "article p. 202", "Table 4", "Reactance is not converted to the production scalar inductance without an approved dq/scalar model bridge."),
    )
    rows: list[ExternalMetricComparison] = []
    for metric, value, unit, point, scope, waveform, page, location, notes in specs:
        rows.append(_blocked(_evidence(
            **common, metric_name=metric, value=value, unit=unit,
            operating_point=point, quantity_scope=scope, value_kind="measured",
            waveform=waveform, page=page, location=location,
            extraction_note=f"Source table value retained exactly as {value:g} {unit}.",
            comparability_status=ComparabilityStatus.BLOCKED, notes=notes,
        ), unit))
    return rows


def build_phase7b1_campaign() -> ExternalValidationCampaignResult:
    rows = _abdelli_rows() + _price_rows() + _parviainen_rows() + _bumby_rows() + _hosseini_rows()
    return ExternalValidationCampaignResult(rows=tuple(rows))


def _number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def render_phase7b1_report(result: ExternalValidationCampaignResult) -> str:
    lines = [
        "# Phase 7B.1 外部 AFPM 逐指标比较报告",
        "",
        "## 冻结边界",
        "",
        "本报告只读取公开来源并调用既有 strict-SI 额定转矩关系。它不修改生产公式、默认参数、动态模型、GUI 或 legacy baseline，也不执行校准。",
        "有来源数值但拓扑、波形、绕组或 operating-point 语义不兼容时，该行保持 `BLOCKED`，不计算误差。`APPROXIMATE` 证据即使有数值也不得形成 accuracy PASS 声明。",
        "",
        "## 汇总",
        "",
        *(f"- comparability {key}: {value}" for key, value in result.comparability_counts.items()),
        *(f"- outcome {key}: {value}" for key, value in result.outcome_counts.items()),
        "",
        "当前唯一外部直接可比较行是 Parviainen 原型机 5 kW / 300 rpm / 159 Nm 的额定轴端功率-转速-转矩关系。它验证 strict-SI `T=P/omega` 一致性，不验证 AFPM 电磁转矩模型。",
    ]
    source_ids = tuple(dict.fromkeys(row.evidence.source_id for row in result.rows))
    for source_id in source_ids:
        source_rows = [row for row in result.rows if row.evidence.source_id == source_id]
        lines.extend((
            "",
            f"## 来源：{source_rows[0].evidence.source_title}",
            "",
            f"- topology: {source_rows[0].evidence.topology}",
            f"- source: {source_rows[0].evidence.provenance.source_url}",
            "",
            "| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |",
            "|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|",
        ))
        for row in source_rows:
            evidence = row.evidence
            provenance = f"{evidence.provenance.page}, {evidence.provenance.location}"
            notes = evidence.notes.replace("|", "/")
            lines.append(
                f"| {evidence.source_id} | {evidence.topology} | {evidence.metric_name} | {evidence.operating_point} | {_number(row.model_prediction)} | "
                f"{_number(row.normalized_reference)} | {row.normalized_unit} | "
                f"{evidence.evidence_type.value} | "
                f"{_number(row.metrics.absolute_error_magnitude)} | {_number(row.metrics.absolute_percentage_error)} | "
                f"{evidence.comparability_status.value} | {row.outcome.value} | "
                f"{evidence.uncertainty}; confidence: {evidence.confidence} | {provenance} | {notes} |"
            )
    lines.extend((
        "",
        "## 结论",
        "",
        "- 已从完全外部的 AFPM 原型来源建立 1 行直接可比较结果；相对误差约 0.0974%，在 Phase 7A torque tolerance 下为 PASS。",
        "- 该 PASS 只覆盖额定轴功率、转速和转矩的 SI 一致性，不能扩展为 back-EMF、Ke、Kt、磁路、损耗或整体 AFPM accuracy 声明。",
        "- 其余指标继续因拓扑、绕组、波形、参数完整性或全文访问问题阻塞；没有通过调参、图像数字化或推断缺失值来减少 blocker 数量。",
        "- 当前证据适合继续进行逐指标 Phase 7C 前置工作，但不足以开始生产参数校准。",
        "",
    ))
    return "\n".join(lines)


def run_phase7b1_campaign(repo_root: Path | None = None) -> ExternalValidationCampaignResult:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    result = build_phase7b1_campaign()
    output = root / "validation_data" / "reports" / "phase7b1_external_afpm_metric_comparison_zh.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_phase7b1_report(result), encoding="utf-8")
    return result
