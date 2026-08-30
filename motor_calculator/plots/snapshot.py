"""Compatibility checks for optional project result snapshots."""

from __future__ import annotations

from typing import Any, Mapping

from motor_calculator.project.schema import (
    ResultSnapshot,
    build_project_inputs,
    project_inputs_hash,
    utc_now_iso,
)

from .models import AvailabilityStatus, SnapshotAssessment


def build_result_snapshot(
    flat_inputs: Mapping[str, Any],
    result: Mapping[str, Any],
    model_version: str,
) -> ResultSnapshot:
    return ResultSnapshot(
        result=dict(result),
        result_model_version=model_version,
        result_timestamp=utc_now_iso(),
        input_hash=project_inputs_hash(build_project_inputs(flat_inputs)),
    )


def assess_result_snapshot(
    snapshot: ResultSnapshot | None,
    project_inputs,
    current_model_version: str,
) -> SnapshotAssessment:
    if snapshot is None:
        return SnapshotAssessment(AvailabilityStatus.NOT_RUN, False, "项目未保存结果快照。", None)
    current_hash = project_inputs_hash(project_inputs)
    if snapshot.input_hash != current_hash:
        return SnapshotAssessment(AvailabilityStatus.INVALID, False, "历史结果与当前输入不匹配，需要重新计算。", snapshot.result)
    if snapshot.result_model_version != current_model_version:
        return SnapshotAssessment(AvailabilityStatus.UNAVAILABLE, False, "历史结果的模型/应用版本不同，需要重新计算。", snapshot.result)
    return SnapshotAssessment(AvailabilityStatus.AVAILABLE, True, "结果快照的输入哈希与模型版本匹配。", snapshot.result)


def extract_snapshot_primary_values(snapshot_result: Mapping[str, Any]) -> dict[str, float]:
    performance = snapshot_result.get("性能指标", {})
    if not isinstance(performance, Mapping):
        return {}
    mapping = {
        "rated_torque_nm": "rated_torque_nm",
        "output_power_w": "output_power_w",
        "efficiency_percent": "efficiency_percent",
        "mechanical_speed_rpm": "mechanical_speed_rpm",
    }
    values: dict[str, float] = {}
    for target, source in mapping.items():
        value = performance.get(source)
        if isinstance(value, (int, float)):
            values[target] = float(value)
    return values
