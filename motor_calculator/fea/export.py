"""Export of FEA cases, raw solver results and comparisons.

Everything is written as plain JSON or CSV. No FEMM-internal binary is copied
out: the ``.fem`` model and its solution stay in the solver workspace, and only
the numbers this application actually consumed are exported.
"""

from __future__ import annotations

import csv
import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .comparison import FEAComparisonReport
from .models import FEAValidationCase
from .results import FEARawResult
from .serialization import case_to_dict

FEA_EXPORT_SCHEMA_VERSION = "phase10a.fea.export.v1"

#: Columns of the raw sample CSV, in order.
RAW_SAMPLE_BASE_COLUMNS = ("rotor_angle_mech_deg",)
RAW_SAMPLE_TAIL_COLUMNS = ("circumferential_force_n", "torque_nm", "element_count")

#: Columns of the comparison CSV, in order.
COMPARISON_COLUMNS = (
    "quantity",
    "unit",
    "basis",
    "analytical_value",
    "fea_value",
    "absolute_error",
    "relative_error_percent",
    "reference_scale_name",
    "reference_scale_value",
    "error_relative_to_reference_scale_percent",
    "status",
    "is_mock",
    "evidence_admissible",
    "stale",
    "fidelity_tier",
)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def export_case_json(case: FEAValidationCase, path: Path) -> Path:
    """Write the full validation case definition."""

    payload = {
        "export_schema_version": FEA_EXPORT_SCHEMA_VERSION,
        "case": case_to_dict(case),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def export_raw_result_json(result: FEARawResult, path: Path) -> Path:
    """Write the raw solver result with its full provenance."""

    payload = {
        "export_schema_version": FEA_EXPORT_SCHEMA_VERSION,
        "result": _plain(result),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def export_raw_samples_csv(result: FEARawResult, path: Path) -> Path:
    """Write the solved position sweep as a flat CSV."""

    phase_names = result.phase_names()
    torque = result.torque_series_nm()
    columns = (
        list(RAW_SAMPLE_BASE_COLUMNS)
        + [f"flux_linkage_{name}_wb_turn" for name in phase_names]
        + list(RAW_SAMPLE_TAIL_COLUMNS)
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for index, sample in enumerate(result.samples):
            row = [sample.rotor_angle_mech_deg]
            row.extend(sample.phase_flux_linkage_wb_turn[name] for name in phase_names)
            row.append(sample.circumferential_force_n)
            row.append(None if torque is None else float(torque[index]))
            row.append(sample.element_count)
            writer.writerow(["" if value is None else value for value in row])
    return path


def export_comparison_csv(report: FEAComparisonReport, path: Path) -> Path:
    """Write one row per compared quantity."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COMPARISON_COLUMNS)
        for metric in report.metrics:
            writer.writerow(
                [
                    metric.quantity,
                    metric.unit,
                    metric.basis,
                    "" if metric.analytical_value is None else metric.analytical_value,
                    "" if metric.fea_value is None else metric.fea_value,
                    "" if metric.absolute_error is None else metric.absolute_error,
                    ""
                    if metric.relative_error_percent is None
                    else metric.relative_error_percent,
                    metric.reference_scale_name or "",
                    ""
                    if metric.reference_scale_value is None
                    else metric.reference_scale_value,
                    ""
                    if metric.error_relative_to_reference_scale_percent is None
                    else metric.error_relative_to_reference_scale_percent,
                    metric.status.value,
                    report.is_mock,
                    report.evidence_admissible,
                    report.stale,
                    report.fidelity_tier,
                ]
            )
    return path


def export_comparison_json(report: FEAComparisonReport, path: Path) -> Path:
    """Write the full comparison, including provisional band wording."""

    payload = {
        "export_schema_version": FEA_EXPORT_SCHEMA_VERSION,
        "comparison": _plain(report),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def export_bundle(
    case: FEAValidationCase,
    directory: Path,
    *,
    result: FEARawResult | None = None,
    report: FEAComparisonReport | None = None,
) -> tuple[Path, ...]:
    """Export everything that exists for a case; skip what does not."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = [export_case_json(case, directory / "fea_case.json")]
    if result is not None:
        written.append(export_raw_result_json(result, directory / "fea_raw_result.json"))
        written.append(export_raw_samples_csv(result, directory / "fea_raw_samples.csv"))
    if report is not None:
        written.append(export_comparison_csv(report, directory / "fea_comparison.csv"))
        written.append(export_comparison_json(report, directory / "fea_comparison.json"))
    return tuple(written)


def plot_series(result: FEARawResult) -> dict[str, Sequence[float]]:
    """Series a plot layer may draw. Empty when the solver has not run."""

    angles = [sample.rotor_angle_mech_deg for sample in result.samples]
    series: dict[str, Sequence[float]] = {"rotor_angle_mech_deg": angles}
    for name in result.phase_names():
        series[f"flux_linkage_{name}_wb_turn"] = list(result.flux_linkage_series(name))
    torque = result.torque_series_nm()
    if torque is not None:
        series["torque_nm"] = [float(value) for value in torque]
    return series
