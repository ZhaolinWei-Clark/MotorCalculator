"""Phase 11A: the winding/manufacturability line on the main dashboard.

Phase 10G and 10H put real winding engineering behind a menu item. That is the
right home for the full picture, but it meant a user who never opened it could
run a design whose conductors do not physically fit the slot, and see nothing
about it on the screen they actually look at.

This module produces the condensed version: enough for a normal user to know
which winding factor produced their numbers and whether the coil can be wound,
with a pointer to the full panel for anything more. It deliberately does **not**
reproduce the winding engineering panel -- no kd/kp/ks breakdown, no meshed
comparison, no assumption editors.

It computes nothing itself; it renders a :class:`WindingEvaluation`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .authority import AUTHORITY_LABELS_ZH, WindingAuthority
from .evaluation import WindingEvaluation
from .slot_fill import ManufacturabilityStatus

WINDING_DASHBOARD_SCHEMA_VERSION = "phase11a.winding_dashboard.v1"

#: Severities that should read as a problem rather than as information.
BLOCKING_SEVERITIES = frozenset({"ERROR", "SEVERE_DESIGN_RISK"})

FILL_STATUS_LABELS_ZH = {
    ManufacturabilityStatus.COMFORTABLE: "宽裕",
    ManufacturabilityStatus.FEASIBLE: "可行",
    ManufacturabilityStatus.TIGHT: "偏紧",
    ManufacturabilityStatus.OVERFILLED: "超出可绕入范围",
    ManufacturabilityStatus.NOT_CALCULABLE: "无法计算",
}

#: Shown when the machine has no slots at all. A slotless design has no slot
#: fill to report, which is not the same as a slotted design whose fill failed.
SLOTLESS_TEXT_ZH = "无槽结构：没有槽面积，槽利用率不适用"

UNRESOLVED_TEXT_ZH = "未解析"

PANEL_POINTER_ZH = "完整绕组分解见「分析 → 绕组工程」。"


@dataclass(frozen=True)
class WindingDashboardSummary:
    """The compact winding status for the feasibility summary."""

    schema_version: str
    #: ``AUTO_FROM_GEOMETRY`` / ``MANUAL_OVERRIDE`` / ``LEGACY_MANUAL`` / ``UNRESOLVED``
    authority: str
    authority_label_zh: str
    production_winding_factor: float | None
    provenance: str
    fill_status: str | None
    fill_status_label_zh: str
    usable_envelope_fill: float | None
    has_warning: bool
    has_blocking_issue: bool
    headline_zh: str
    rows_zh: tuple[tuple[str, str], ...]
    warnings_zh: tuple[str, ...]

    @property
    def is_available(self) -> bool:
        return self.production_winding_factor is not None or self.fill_status is not None


def _percent(value: float | None) -> str:
    return "不可用" if value is None else f"{value * 100.0:.1f} %"


def build_winding_dashboard_summary(
    evaluation: WindingEvaluation,
) -> WindingDashboardSummary:
    """Condense a winding evaluation into the dashboard's few lines."""

    production = evaluation.production
    authority = (
        production.authority if production is not None else WindingAuthority.UNRESOLVED
    )
    kw = production.value if production is not None else None
    provenance = production.provenance if production is not None else "NONE"

    if evaluation.is_slotless:
        fill_status = None
        fill_label = SLOTLESS_TEXT_ZH
        envelope = None
    elif evaluation.fill is None:
        fill_status = None
        fill_label = "不可用"
        envelope = None
    else:
        fill_status = evaluation.fill.status
        fill_label = FILL_STATUS_LABELS_ZH.get(fill_status, str(fill_status))
        envelope = evaluation.fill.usable_envelope_fill

    blocking = tuple(
        issue for issue in evaluation.issues if issue.severity in BLOCKING_SEVERITIES
    )
    advisory = tuple(
        issue for issue in evaluation.issues if issue.severity not in BLOCKING_SEVERITIES
    )

    if blocking:
        headline = f"绕组/可制造性：有 {len(blocking)} 项阻断性问题"
    elif advisory:
        headline = f"绕组/可制造性：无阻断性问题；有 {len(advisory)} 项提示"
    elif not evaluation.is_available:
        headline = "绕组/可制造性：不可用"
    else:
        headline = "绕组/可制造性：无阻断性问题"

    rows = (
        ("生产绕组系数来源", AUTHORITY_LABELS_ZH.get(authority, str(authority))),
        (
            "生产绕组系数 k_w1",
            UNRESOLVED_TEXT_ZH if kw is None else f"{kw:.6f}",
        ),
        ("槽利用率状态", fill_label),
        ("可用槽面积包络占比", _percent(envelope)),
    )

    return WindingDashboardSummary(
        schema_version=WINDING_DASHBOARD_SCHEMA_VERSION,
        authority=authority.value if isinstance(authority, WindingAuthority) else str(authority),
        authority_label_zh=AUTHORITY_LABELS_ZH.get(authority, str(authority)),
        production_winding_factor=kw,
        provenance=provenance,
        fill_status=fill_status,
        fill_status_label_zh=fill_label,
        usable_envelope_fill=envelope,
        has_warning=bool(advisory),
        has_blocking_issue=bool(blocking),
        headline_zh=headline,
        rows_zh=rows,
        warnings_zh=tuple(issue.message_zh for issue in blocking + advisory),
    )


def render_winding_dashboard_summary_zh(summary: WindingDashboardSummary) -> str:
    """One short block of text, suitable for a dashboard label."""

    lines = [summary.headline_zh]
    lines.extend(f"  {label}：{value}" for label, value in summary.rows_zh)
    if summary.warnings_zh:
        lines.append("")
        lines.extend(f"  · {message}" for message in summary.warnings_zh)
    lines.append("")
    lines.append(PANEL_POINTER_ZH)
    return "\n".join(lines)
