"""Phase 12: capability findings, in the feasibility layer's own shape.

Reports what the capability solver found. Changes nothing about the design: a
machine that cannot reach its required speed is told so, and is not quietly
given a bigger inverter to make the warning go away.
"""

from __future__ import annotations

from dataclasses import dataclass

from .envelope import Region
from .solver import CapabilityResult

CAPABILITY_FEASIBILITY_SCHEMA_VERSION = "phase12.capability_feasibility.v1"


@dataclass(frozen=True)
class CapabilityIssue:
    code: str
    severity: str
    message_zh: str


def capability_issues(
    result: CapabilityResult,
    *,
    required_speed_rpm: float | None = None,
    required_torque_nm: float | None = None,
) -> tuple[CapabilityIssue, ...]:
    """Capability findings, or an empty tuple when there is nothing to say."""

    issues: list[CapabilityIssue] = []
    base = result.base_speed
    maximum = result.maximum_speed

    if not base.resolved and base.speed_rpm == 0.0:
        issues.append(
            CapabilityIssue(
                "VOLTAGE_LIMIT_EXCEEDED",
                "ERROR",
                "在零转速下，满电流 MTPA 工作点所需电压已超过逆变器可用电压："
                "该电流上限在此母线电压下根本无法建立。"
                "请提高母线电压、降低电流上限，或复核电感与电阻。",
            )
        )

    if not result.feasible_points:
        issues.append(
            CapabilityIssue(
                "NO_FIELD_WEAKENING_SOLUTION",
                "ERROR",
                "在所检查的任何转速下都不存在同时满足电流与电压约束的工作点。",
            )
        )
        return tuple(issues)

    if required_speed_rpm:
        if base.resolved and base.speed_rpm < required_speed_rpm:
            issues.append(
                CapabilityIssue(
                    "BASE_SPEED_BELOW_REQUIRED",
                    "WARNING",
                    f"基速 {base.speed_rpm:.0f} rpm 低于要求转速 "
                    f"{required_speed_rpm:.0f} rpm：在要求转速下必须依靠弱磁运行，"
                    "可用转矩低于恒转矩区的峰值。这不一定是缺陷，但应确认是有意为之。",
                )
            )
        if maximum.bounded and maximum.speed_rpm < required_speed_rpm:
            issues.append(
                CapabilityIssue(
                    "MAX_SPEED_BELOW_REQUIRED",
                    "SEVERE_DESIGN_RISK",
                    f"最高可行转速 {maximum.speed_rpm:.0f} rpm 低于要求转速 "
                    f"{required_speed_rpm:.0f} rpm：在该母线电压与电流上限下，"
                    "要求转速无法达到。",
                )
            )

    if required_torque_nm:
        reachable = max(point.torque_nm for point in result.feasible_points)
        if reachable < required_torque_nm * (1.0 - 1.0e-9):
            issues.append(
                CapabilityIssue(
                    "CURRENT_LIMIT_EXCEEDED",
                    "SEVERE_DESIGN_RISK",
                    f"包络内的最大转矩 {reachable:.4f} N·m 低于要求转矩 "
                    f"{required_torque_nm:.4f} N·m：当前电流上限不足以产生该转矩。",
                )
            )
        if required_speed_rpm:
            at_speed = result.point_at(required_speed_rpm)
            if at_speed and at_speed.torque_nm < required_torque_nm * (1.0 - 1.0e-9):
                issues.append(
                    CapabilityIssue(
                        "TORQUE_AT_REQUIRED_SPEED_INSUFFICIENT",
                        "SEVERE_DESIGN_RISK",
                        f"在约 {at_speed.speed_rpm:.0f} rpm 处包络转矩为 "
                        f"{at_speed.torque_nm:.4f} N·m，低于要求的 "
                        f"{required_torque_nm:.4f} N·m。",
                    )
                )

    if any(
        point.region is Region.NO_FEASIBLE_OPERATING_POINT for point in result.envelope
    ):
        issues.append(
            CapabilityIssue(
                "NO_FIELD_WEAKENING_SOLUTION",
                "WARNING",
                "包络中存在无可行工作点的转速：这些转速已超出该机器/逆变器组合的能力。",
            )
        )

    if not result.field_weakening_active and base.resolved:
        issues.append(
            CapabilityIssue(
                "NO_FIELD_WEAKENING_SOLUTION",
                "INFO",
                "包络内未出现负 id：该设计在所检查的转速范围内没有进入弱磁运行。",
            )
        )

    return tuple(issues)


def has_blocking_capability_issue(issues) -> bool:
    return any(issue.severity in {"ERROR", "SEVERE_DESIGN_RISK"} for issue in issues)
