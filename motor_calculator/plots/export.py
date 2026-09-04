"""Explicit user-selected exports for structured plot data and figures."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import SpeedSweepResult


def export_speed_sweep_csv(result: SpeedSweepResult, destination: Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Phase 9C: authoritative corrected columns first, legacy explicitly named.
    fields = (
        "speed_rpm",
        "torque_nm",
        "power_w",
        "voltage_required_line_rms_v",
        "voltage_available_line_rms_v",
        "voltage_margin_line_rms_percent",
        "legacy_required_voltage_v",
        "legacy_voltage_margin_percent",
        "efficiency_percent",
        "current_density_a_per_mm2",
        "validity_status",
        "feasibility_status",
        "message",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for point in result.points:
            writer.writerow(
                {
                    "speed_rpm": point.speed_rpm,
                    "torque_nm": point.torque_nm,
                    "power_w": point.output_power_w,
                    "voltage_required_line_rms_v": point.required_voltage_line_rms_v,
                    "voltage_available_line_rms_v": point.available_voltage_line_rms_v,
                    "voltage_margin_line_rms_percent": point.voltage_margin_percent,
                    "legacy_required_voltage_v": point.legacy_required_voltage_line_rms_v,
                    "legacy_voltage_margin_percent": point.legacy_voltage_margin_percent,
                    "efficiency_percent": point.efficiency_percent,
                    "current_density_a_per_mm2": point.current_density_a_per_mm2,
                    "validity_status": point.availability.value,
                    "feasibility_status": point.feasibility_status.value,
                    "message": point.message_zh,
                }
            )
    return path


def export_figure(figure, destination: Path) -> Path:
    path = Path(destination)
    suffix = path.suffix.lower()
    if suffix not in {".png", ".svg"}:
        raise ValueError("plot export supports PNG or SVG")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160 if suffix == ".png" else None, bbox_inches="tight")
    return path
