"""Phase 10H: winding manufacturability as a first-class feasibility reason.

A design whose copper cannot physically be wound into the slot is not feasible,
however comfortable its current density and voltage margin look. Until now the
feasibility layer reported an approximate bare-copper occupancy and nothing
about whether the insulated conductors actually fit.

These checks are strictly **additive**: every one of them fires only on a
genuine problem, so a design that was feasible before this module existed
remains feasible with exactly the same issue list. Nothing is ever adjusted to
make a design pass -- the turns are not reduced, the wire is not thinned, the
packing factor is not relaxed. A design that does not fit is reported as not
fitting.
"""

from __future__ import annotations

from dataclasses import dataclass

from .authority import ProductionWindingFactor, WindingAuthority
from .slot_fill import ManufacturabilityStatus, SlotFillResult

WINDING_FEASIBILITY_SCHEMA_VERSION = "phase10h.winding_feasibility.v1"


@dataclass(frozen=True)
class WindingFeasibilityIssue:
    """One manufacturability finding, in the feasibility layer's own shape."""

    code: str
    severity: str
    message_zh: str


def winding_manufacturability_issues(
    *,
    fill: SlotFillResult | None,
    production: ProductionWindingFactor | None = None,
) -> tuple[WindingFeasibilityIssue, ...]:
    """Manufacturability and winding-authority findings, or an empty tuple.

    Returns nothing at all when there is nothing wrong, which is what keeps this
    additive.
    """

    issues: list[WindingFeasibilityIssue] = []

    if production is not None and not production.is_resolved:
        issues.append(
            WindingFeasibilityIssue(
                "WINDING_FACTOR_UNRESOLVED",
                "ERROR",
                "绕组系数未解析：选择了自动模式但绕组几何不足，且没有可用的手动值。"
                "请补全槽数、极对数与线圈节距，或显式选择手动覆盖。"
                "在解析之前，反电动势、转矩常数与电压需求都不应被采信。",
            )
        )

    if fill is None:
        return tuple(issues)

    if fill.status == ManufacturabilityStatus.OVERFILLED:
        fill_percent = (
            fill.usable_envelope_fill * 100.0
            if fill.usable_envelope_fill is not None
            else float("nan")
        )
        issues.append(
            WindingFeasibilityIssue(
                "SLOT_OVERFILLED",
                "SEVERE_DESIGN_RISK",
                f"按可用槽面积计算的绝缘包络占比为 {fill_percent:.1f} %，"
                f"在装填系数 {fill.packing_factor:.2f} 下无法绕入。"
                "可减少匝数、改用更细导线、增加并联支路或加大槽面积；"
                "本软件不会为了让设计通过而自动调整这些量。",
            )
        )
    elif fill.status == ManufacturabilityStatus.TIGHT:
        issues.append(
            WindingFeasibilityIssue(
                "SLOT_FILL_TIGHT",
                "WARNING",
                f"按可用槽面积计算的绝缘包络占比为 "
                f"{fill.usable_envelope_fill * 100.0:.1f} %，属于偏紧区间，"
                "实际绕制难度较高，建议与绕线工艺确认。"
                "该阈值带是工程假设，不是标准。",
            )
        )
    elif fill.status == ManufacturabilityStatus.NOT_CALCULABLE:
        issues.append(
            WindingFeasibilityIssue(
                "SLOT_FILL_NOT_CALCULABLE",
                "WARNING",
                "扣除楔块、槽绝缘与间隙之后没有可用槽面积，无法评估可制造性。"
                "请检查槽几何与绝缘允许量。",
            )
        )

    if fill.usable_envelope_fill is not None and fill.usable_envelope_fill > 1.0:
        issues.append(
            WindingFeasibilityIssue(
                "SLOT_GEOMETRICALLY_IMPOSSIBLE",
                "ERROR",
                f"绝缘包络面积超过可用槽面积本身"
                f"（{fill.usable_envelope_fill * 100.0:.1f} %），"
                "与装填系数无关，导体在几何上就放不下。",
            )
        )

    return tuple(issues)


def has_blocking_winding_issue(issues) -> bool:
    """Whether any finding should prevent a design being called feasible."""

    return any(issue.severity in {"ERROR", "SEVERE_DESIGN_RISK"} for issue in issues)
