"""Phase 11A: exporting a validation comparison without overclaiming in print.

An exported report outlives the screen it came from. It gets pasted into a
design review, attached to an email, or read a year later by somebody who was
not there. Everything the UI conveys through layout and colour has to survive as
text, or the export becomes the place where the careful distinctions are lost.

So the export is built around one prohibition: the word ``VALIDATED`` is never
written for anything except an experimental measurement of *this* machine. The
guard is :func:`_claim_text`, every path goes through it, and a test asserts a
different-machine dataset cannot produce that word anywhere in the output.

Limitations are not a footnote here. They are a required section, and a report
with no limitations section is treated as a defect rather than as a clean bill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .comparison import (
    AFFIRMATIVE_CLAIMS,
    OverallClaim,
    QuantityComparison,
    ValidationOverview,
)
from .compatibility import MachineCompatibility
from .schema import UNKNOWN, DatasetMetadata, metadata_to_payload
from .sources import SOURCE_TYPE_CAVEATS_ZH, SOURCE_TYPE_LABELS_ZH, is_experimental

REPORT_SCHEMA_VERSION = "phase11a.experiment.report.v1"

#: The word that may only ever accompany an experimental measurement of this
#: machine. Held as a constant so the guard and its test refer to one string.
VALIDATED_WORD = "VALIDATED"

#: What a non-affirmative claim is written as instead.
CLAIM_TEXT = {
    OverallClaim.EXPERIMENTALLY_SUPPORTED: "EXPERIMENTALLY_SUPPORTED",
    OverallClaim.METHODOLOGY_REFERENCE_ONLY: "NOT_VALIDATED / METHODOLOGY_REFERENCE_ONLY",
    OverallClaim.SIMULATION_CROSS_CHECK_ONLY: "NOT_VALIDATED / SIMULATION_CROSS_CHECK_ONLY",
    OverallClaim.NO_EXPERIMENTAL_DATA: "NOT_VALIDATED / NO_EXPERIMENTAL_DATA",
    OverallClaim.INSUFFICIENT_METADATA: "NOT_VALIDATED / INSUFFICIENT_METADATA",
}


def _claim_text(comparison: QuantityComparison) -> str:
    """The claim string. The single place ``VALIDATED`` can be emitted."""

    if comparison.overall_claim in AFFIRMATIVE_CLAIMS:
        return CLAIM_TEXT[comparison.overall_claim]
    text = CLAIM_TEXT[comparison.overall_claim]
    # Defensive: the mapping above already avoids it, but a future edit must not
    # be able to slip the word into a non-affirmative claim.
    if VALIDATED_WORD in text.replace("NOT_VALIDATED", ""):
        raise AssertionError("a non-affirmative claim may not contain VALIDATED")
    return text


def _plain(value: Any) -> Any:
    return "UNKNOWN" if value == UNKNOWN else value


def _dataset_block(dataset: DatasetMetadata | None) -> dict[str, Any]:
    if dataset is None:
        return {"present": False, "note_zh": "该量没有关联的数据集。"}
    citation = dataset.citation
    return {
        "present": True,
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "source_type": dataset.source_type.value,
        "source_type_label_zh": SOURCE_TYPE_LABELS_ZH[dataset.source_type],
        "source_type_caveat_zh": SOURCE_TYPE_CAVEATS_ZH[dataset.source_type],
        "is_experimental": is_experimental(dataset.source_type),
        "test_type": dataset.test_type.value,
        "data_provenance": dataset.data_provenance,
        "test_fixture_only": dataset.test_fixture_only,
        "raw_file_hash": _plain(dataset.raw_file_hash),
        "import_timestamp_utc": _plain(dataset.import_timestamp_utc),
        "measurement_date": _plain(dataset.measurement_date),
        "operator": _plain(dataset.operator),
        "citation": {
            "title": _plain(citation.title),
            "authors": _plain(citation.authors),
            "publication": _plain(citation.publication),
            "year": _plain(citation.year),
            "doi": _plain(citation.doi),
            "url": _plain(citation.url),
            "page": _plain(citation.page),
            "table_or_figure": _plain(citation.table_or_figure),
            "license": _plain(citation.license),
            "redistribution": citation.redistribution.value,
        },
    }


def build_report_payload(
    overview: ValidationOverview,
    *,
    application_version: str,
    generated_at_utc: str,
) -> dict[str, Any]:
    """The machine-readable validation report."""

    quantities = []
    for comparison in overview.comparisons:
        compatibility = comparison.compatibility
        entry: dict[str, Any] = {
            "quantity": comparison.quantity,
            "quantity_label_zh": comparison.quantity_label_zh,
            "unit": comparison.unit,
            "basis_zh": comparison.basis_zh,
            "claim": _claim_text(comparison),
            "claim_label_zh": comparison.claim_label_zh,
            "claim_reason_zh": comparison.claim_reason_zh,
            "calibration_status": comparison.calibration_status,
            "analytical_value": None if comparison.analytical is None else comparison.analytical.value,
            "fea_value": None if comparison.fea is None else comparison.fea.value,
            "measured_value": None if comparison.measured is None else comparison.measured.value,
            "measured_evidence_label": (
                None if comparison.measured is None else comparison.measured.evidence_label
            ),
            "sample_count": (
                None if comparison.measured is None else comparison.measured.sample_count
            ),
            "residuals": [
                {
                    "subject": residual.subject,
                    "reference": residual.reference,
                    "absolute": residual.absolute,
                    "relative_percent": residual.relative_percent,
                }
                for residual in comparison.residuals
            ],
            "machine_compatibility": (
                None if compatibility is None else compatibility.status.value
            ),
            "machine_compatibility_reason_zh": (
                None if compatibility is None else compatibility.reason_zh
            ),
            "permitted_use_zh": (
                None if compatibility is None else compatibility.permitted_use_zh
            ),
            "limitations_zh": list(comparison.limitations_zh),
            "dataset": _dataset_block(comparison.dataset),
        }
        quantities.append(entry)

    return {
        "schema": REPORT_SCHEMA_VERSION,
        "application_version": application_version,
        "generated_at_utc": generated_at_utc,
        "state": overview.state,
        "state_message_zh": overview.message_zh,
        "dataset_count": overview.dataset_count,
        "experimental_dataset_count": overview.experimental_dataset_count,
        "has_any_validated_quantity": overview.has_any_affirmative_claim,
        "calibration_status": "NONE",
        "calibration_note_zh": (
            "本项目不进行任何标定：没有经验系数拟合，也没有为了贴合测量而修改解析输出。"
        ),
        "quantities": quantities,
        "global_limitations_zh": _global_limitations(overview),
    }


def _global_limitations(overview: ValidationOverview) -> list[str]:
    limitations = [
        "解析模型、数值有限元与实测数据是三类独立证据，本报告不将任何一类"
        "当作另一类使用。",
        "残差是数值差异，不是结论；证据类别由数据来源与机器一致性决定，"
        "与残差大小无关。",
    ]
    if not overview.has_experimental_data:
        limitations.append(
            "当前没有任何实验测量数据，因此本项目的任何量都不能称为已实验验证。"
        )
    for comparison in overview.comparisons:
        compatibility = comparison.compatibility
        if compatibility is None:
            continue
        if compatibility.status is MachineCompatibility.DIFFERENT_MACHINE:
            limitations.append(
                f"{comparison.quantity_label_zh}：所用数据集测的是另一台机器，"
                "只能检验方法学，不能验证当前设计。"
            )
        elif compatibility.status is MachineCompatibility.COMPATIBLE_REFERENCE:
            limitations.append(
                f"{comparison.quantity_label_zh}：所用数据集为可比参考机器，"
                "并非当前设计本身。"
            )
    return limitations


def render_report_zh(payload: dict[str, Any]) -> str:
    """The human-readable form of the same report."""

    lines = [
        "实验 / 参考数据验证报告",
        "=" * 60,
        f"报告版本：{payload['schema']}",
        f"应用版本：{payload['application_version']}",
        f"生成时间（UTC）：{payload['generated_at_utc']}",
        f"标定状态：{payload['calibration_status']} —— {payload['calibration_note_zh']}",
        "",
        f"总体状态：{payload['state']}",
        payload["state_message_zh"],
        "",
    ]
    if not payload["quantities"]:
        lines.append("没有可比较的量。")
    for entry in payload["quantities"]:
        lines.extend(
            [
                "-" * 60,
                f"{entry['quantity_label_zh']}（{entry['quantity']}，单位 {entry['unit']}）",
                f"  比较基准：{entry['basis_zh']}",
                f"  结论：{entry['claim']} —— {entry['claim_label_zh']}",
                f"  理由：{entry['claim_reason_zh']}",
                f"  解析模型：{_number(entry['analytical_value'])}",
                f"  数值有限元：{_number(entry['fea_value'])}",
                f"  实验/参考：{_number(entry['measured_value'])}"
                + (
                    f"（证据类别 {entry['measured_evidence_label']}，"
                    f"样本数 {entry['sample_count']}）"
                    if entry["measured_evidence_label"]
                    else ""
                ),
            ]
        )
        for residual in entry["residuals"]:
            relative = (
                "不适用"
                if residual["relative_percent"] is None
                else f"{residual['relative_percent']:+.3f} %"
            )
            lines.append(
                f"    残差 {residual['subject']} vs {residual['reference']}："
                f"{residual['absolute']:+.6g}（{relative}）"
            )
        dataset = entry["dataset"]
        if dataset["present"]:
            lines.extend(
                [
                    f"  数据集：{dataset['title']}（{dataset['dataset_id']}）",
                    f"  来源类别：{dataset['source_type']} —— {dataset['source_type_label_zh']}",
                    f"    {dataset['source_type_caveat_zh']}",
                    f"  测试类型：{dataset['test_type']}",
                    f"  文件哈希：{dataset['raw_file_hash']}",
                    f"  引用：{dataset['citation']['title']}"
                    f"（{dataset['citation']['year']}）"
                    f" DOI {dataset['citation']['doi']}"
                    f" URL {dataset['citation']['url']}",
                    f"  再分发许可：{dataset['citation']['redistribution']}",
                ]
            )
        if entry["machine_compatibility"]:
            lines.extend(
                [
                    f"  机器一致性：{entry['machine_compatibility']}",
                    f"    {entry['machine_compatibility_reason_zh']}",
                    f"    允许的用途：{entry['permitted_use_zh']}",
                ]
            )
        if entry["limitations_zh"]:
            lines.append("  局限：")
            lines.extend(f"    · {item}" for item in entry["limitations_zh"])
    lines.extend(["", "=" * 60, "全局局限："])
    lines.extend(f"  · {item}" for item in payload["global_limitations_zh"])
    return "\n".join(lines) + "\n"


def _number(value: Any) -> str:
    return "不可用" if value is None else f"{float(value):.6g}"


@dataclass(frozen=True)
class ExportedReport:
    json_path: Path
    text_path: Path


def export_validation_report(
    overview: ValidationOverview,
    destination_dir: str | Path,
    *,
    application_version: str,
    generated_at_utc: str,
    stem: str = "phase11a_validation_report",
) -> ExportedReport:
    """Write both forms of the report and return where they went."""

    directory = Path(destination_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(
        overview,
        application_version=application_version,
        generated_at_utc=generated_at_utc,
    )
    json_path = directory / f"{stem}.json"
    text_path = directory / f"{stem}.txt"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_report_zh(payload), encoding="utf-8")
    return ExportedReport(json_path=json_path, text_path=text_path)


def export_dataset_metadata(
    datasets: Sequence[DatasetMetadata], destination: str | Path
) -> Path:
    """Metadata only, for a source whose raw numbers may not be redistributed."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": REPORT_SCHEMA_VERSION,
                "note_zh": (
                    "本文件只包含数据集元数据与引用信息，不包含原始测量数值。"
                    "当再分发许可未知或不允许时，这是可以安全共享的形式。"
                ),
                "datasets": [metadata_to_payload(dataset) for dataset in datasets],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
