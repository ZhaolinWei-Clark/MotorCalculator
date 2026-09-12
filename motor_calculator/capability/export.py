"""Phase 12: exporting the capability result with its provenance attached.

Every number here is a steady-state model output. None of it is measured, and
the export says so in its own body rather than relying on the reader to
remember: this project's AFPM design remains not experimentally validated, and
a torque-speed envelope does not change that.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .conventions import CONVENTION_SCHEMA_VERSION, CURRENT_BASIS, VOLTAGE_BASIS
from .envelope import REGION_LABELS_ZH
from .feasibility import capability_issues
from .parameters import MACHINE_TYPE_LABELS_ZH
from .solver import CapabilityResult

CAPABILITY_EXPORT_SCHEMA_VERSION = "phase12.capability_export.v1"

#: Stated in every export. A capability envelope is a model result.
EVIDENCE_STATEMENT = "ANALYTICAL_MODEL_NOT_EXPERIMENTALLY_VALIDATED"
EVIDENCE_NOTE_ZH = (
    "本能力包络为**稳态解析模型输出**，不是测量结果，也未经实验验证。"
    "它由 dq 稳态方程、电流圆与电压椭圆约束求解得到；"
    "其准确度受限于 Ld/Lq、ψ_pm 与 Rs 的来源精度，"
    "以及「忽略铁耗、磁饱和与逆变器开关动态」这一稳态假设。"
)
CALIBRATION_STATUS = "NONE"


def build_export_payload(
    result: CapabilityResult,
    *,
    required_speed_rpm: float | None = None,
    required_torque_nm: float | None = None,
) -> dict[str, Any]:
    """The machine-readable capability section."""

    parameters = result.parameters
    base = result.base_speed
    maximum = result.maximum_speed
    constant_power = result.constant_power
    issues = capability_issues(
        result,
        required_speed_rpm=required_speed_rpm,
        required_torque_nm=required_torque_nm,
    )

    return {
        "schema": CAPABILITY_EXPORT_SCHEMA_VERSION,
        "convention": CONVENTION_SCHEMA_VERSION,
        "evidence": EVIDENCE_STATEMENT,
        "evidence_note_zh": EVIDENCE_NOTE_ZH,
        "calibration_status": CALIBRATION_STATUS,
        "bases": {
            "current": CURRENT_BASIS,
            "voltage": VOLTAGE_BASIS,
            "torque": "ELECTROMAGNETIC",
            "power": "ELECTROMAGNETIC_T_TIMES_OMEGA_M",
        },
        "machine": {
            "type": parameters.machine_type.value,
            "type_label_zh": MACHINE_TYPE_LABELS_ZH[parameters.machine_type],
            "pole_pairs": parameters.pole_pairs,
            "saliency_ratio": parameters.saliency_ratio,
            "characteristic_current_peak_a": parameters.characteristic_current_a,
        },
        "parameters": [
            {
                "name": item.name,
                "value": item.value,
                "unit": item.unit,
                "source": item.source,
                "basis": item.basis,
                "conversion": item.conversion,
                "provenance": item.provenance,
            }
            for item in parameters.provenance
        ],
        "inverter": {
            "dc_bus_voltage_v": result.voltage_limit.dc_bus_voltage_v,
            "modulation": result.voltage_limit.modulation.value,
            "voltage_utilization": result.voltage_limit.utilization,
            "voltage_utilization_classification": (
                result.voltage_limit.utilization_classification
            ),
            "voltage_limit_phase_peak_v": result.voltage_limit.phase_peak_v,
            "voltage_limit_phase_rms_v": result.voltage_limit.phase_rms_v,
            "voltage_limit_line_rms_v": result.voltage_limit.line_rms_v,
            "current_limit_peak_a": result.current_limit.peak_a,
            "current_limit_rms_a": result.current_limit.rms_a,
        },
        "mtpa": {
            "method": result.mtpa_at_limit.method,
            "id_a": result.mtpa_at_limit.id_a,
            "iq_a": result.mtpa_at_limit.iq_a,
            "torque_nm": result.mtpa_at_limit.torque_nm,
            "condition_residual": result.mtpa_at_limit.condition_residual,
        },
        "base_speed": {
            "resolved": base.resolved,
            "speed_rpm": base.speed_rpm,
            "omega_e_rad_s": base.omega_e_rad_s,
            "voltage_utilization": base.voltage_utilization,
            "current_utilization": base.current_utilization,
            "note_zh": base.note_zh,
        },
        "maximum_speed": {
            "bounded": maximum.bounded,
            "speed_rpm": maximum.speed_rpm,
            "torque_nm": maximum.torque_nm,
            "mechanical_power_w": maximum.mechanical_power_w,
            "active_constraints": list(maximum.active_constraints),
            "note_zh": maximum.note_zh,
        },
        "peak_torque_nm": result.peak_torque_nm,
        "peak_power_w": result.peak_power_w,
        "peak_power_speed_rpm": result.peak_power_speed_rpm,
        "field_weakening_active": result.field_weakening_active,
        "constant_power": {
            "exists": constant_power.exists,
            "start_rpm": constant_power.start_rpm,
            "end_rpm": constant_power.end_rpm,
            "mean_power_w": constant_power.mean_power_w,
            "power_spread_percent": constant_power.power_spread_percent,
            "speed_ratio": constant_power.ratio_to_base_speed,
            "tolerance": constant_power.tolerance,
            "classification": constant_power.classification,
            "note_zh": constant_power.note_zh,
        },
        "regions_present": [region.value for region in result.regions_present()],
        "issues": [
            {"code": issue.code, "severity": issue.severity, "message_zh": issue.message_zh}
            for issue in issues
        ],
        "warnings_zh": list(result.warnings_zh),
        "envelope_point_count": len(result.envelope),
    }


ENVELOPE_CSV_HEADER = (
    "speed_rpm",
    "omega_m_rad_s",
    "omega_e_rad_s",
    "id_peak_a",
    "iq_peak_a",
    "vd_peak_v",
    "vq_peak_v",
    "current_magnitude_peak_a",
    "voltage_magnitude_peak_v",
    "torque_nm",
    "mechanical_power_w",
    "current_utilization",
    "voltage_utilization",
    "region",
    "feasible",
    "active_constraints",
)


def write_envelope_csv(result: CapabilityResult, destination: str | Path) -> Path:
    """The full torque-speed curve. Column names carry their basis."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([f"# {EVIDENCE_STATEMENT}: {EVIDENCE_NOTE_ZH}"])
        writer.writerow(
            [f"# current/voltage basis: {CURRENT_BASIS} / {VOLTAGE_BASIS}"]
        )
        writer.writerow(ENVELOPE_CSV_HEADER)
        for point in result.envelope:
            writer.writerow(
                [
                    f"{point.speed_rpm:.6f}",
                    f"{point.omega_m_rad_s:.6f}",
                    f"{point.omega_e_rad_s:.6f}",
                    f"{point.id_a:.6f}",
                    f"{point.iq_a:.6f}",
                    f"{point.vd_v:.6f}",
                    f"{point.vq_v:.6f}",
                    f"{point.current_magnitude_a:.6f}",
                    f"{point.voltage_magnitude_v:.6f}",
                    f"{point.torque_nm:.6f}",
                    f"{point.mechanical_power_w:.6f}",
                    f"{point.current_utilization:.6f}",
                    f"{point.voltage_utilization:.6f}",
                    point.region.value,
                    "1" if point.feasible else "0",
                    "|".join(point.active_constraints),
                ]
            )
    return path


@dataclass(frozen=True)
class ExportedCapability:
    json_path: Path
    csv_path: Path | None


def export_capability(
    result: CapabilityResult,
    destination_dir: str | Path,
    *,
    stem: str = "phase12_capability",
    include_envelope_csv: bool = True,
    **payload_kwargs: Any,
) -> ExportedCapability:
    directory = Path(destination_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    json_path.write_text(
        json.dumps(
            build_export_payload(result, **payload_kwargs),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    csv_path = None
    if include_envelope_csv:
        csv_path = write_envelope_csv(result, directory / f"{stem}_envelope.csv")
    return ExportedCapability(json_path=json_path, csv_path=csv_path)


def render_summary_zh(result: CapabilityResult) -> str:
    """The headline capability block, for the report and the GUI."""

    base = result.base_speed
    maximum = result.maximum_speed
    voltage = result.voltage_limit
    current = result.current_limit
    lines = [
        "转矩-转速能力（稳态模型）",
        "=" * 52,
        f"机器类型      ：{MACHINE_TYPE_LABELS_ZH[result.parameters.machine_type]}",
        f"直流母线电压  ：{voltage.dc_bus_voltage_v:.3f} V",
        f"调制方式      ：{voltage.modulation.value}",
        f"电压上限      ：{voltage.phase_peak_v:.4f} V 相峰值"
        f"（= {voltage.line_rms_v:.4f} V 线有效值，利用率 {voltage.utilization:.3f}）",
        f"电流上限      ：{current.peak_a:.4f} A 相峰值"
        f"（= {current.rms_a:.4f} A 相有效值）",
        "",
        f"基速          ：{base.speed_rpm:.1f} rpm" + ("" if base.resolved else "（无解）"),
        f"最高转速      ：{maximum.speed_rpm:.1f} rpm"
        + ("" if maximum.bounded else "（搜索上限，非外推；本模型下无有限电磁转速极限）"),
        f"峰值转矩      ：{result.peak_torque_nm:.4f} N·m",
        f"峰值功率      ：{result.peak_power_w:.1f} W @ {result.peak_power_speed_rpm:.0f} rpm",
        "",
        f"MTPA          ：{result.mtpa_at_limit.method}"
        f"  id = {result.mtpa_at_limit.id_a:.6f} A，iq = {result.mtpa_at_limit.iq_a:.4f} A",
        f"弱磁          ：{'已进入（存在负 id）' if result.field_weakening_active else '未进入'}",
        f"恒功率区      ：{'存在' if result.constant_power.exists else '不存在'}",
        f"  {result.constant_power.note_zh}",
        "",
        "出现的运行区间：",
    ]
    for region in result.regions_present():
        lines.append(f"  · {region.value} —— {REGION_LABELS_ZH[region]}")
    lines.extend(["", f"证据类别：{EVIDENCE_STATEMENT}", f"  {EVIDENCE_NOTE_ZH}",
                  f"标定状态：{CALIBRATION_STATUS}"])
    if result.warnings_zh:
        lines.append("")
        lines.append("提示：")
        lines.extend(f"  · {item}" for item in result.warnings_zh)
    return "\n".join(lines)
