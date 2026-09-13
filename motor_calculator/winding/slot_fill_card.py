"""RC5.1: the slot-fill card on the main results dashboard.

Phase 10G computed gross and usable slot area, bare-copper fill, insulated
envelope fill and a manufacturability finding. Phase 11A put one of those five
numbers -- the usable envelope fill -- on the dashboard, and left the rest
inside the winding engineering dialog. A user who never opened that dialog
therefore saw a single percentage, and when it could not be computed they saw
the word "不可用" with no indication of what was missing.

This module renders the same :class:`WindingEvaluation` the winding panel and
the dashboard summary already use. It computes nothing, decides nothing, and
changes no slot-fill equation: every number here comes from
:func:`motor_calculator.winding.slot_fill.compute_slot_fill` unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evaluation import WindingEvaluation
from .slot_fill import ManufacturabilityStatus

SLOT_FILL_CARD_SCHEMA_VERSION = "rc51.slot_fill_card.v1"

CARD_TITLE_ZH = "槽满率 / Slot Fill"

#: User-facing wording. The raw enum names are kept on the dataclass for tests
#: and exports, but a customer should not have to read `OVERFILLED`.
STATUS_LABELS_ZH = {
    ManufacturabilityStatus.COMFORTABLE: "宽裕",
    ManufacturabilityStatus.FEASIBLE: "可行",
    ManufacturabilityStatus.TIGHT: "偏紧",
    ManufacturabilityStatus.OVERFILLED: "超填",
    ManufacturabilityStatus.NOT_CALCULABLE: "无法计算",
}

#: The headline pair: fill against the area a conductor can actually occupy.
PRIMARY_LABELS_ZH = (
    "铜填充率（可用槽面积）",
    "绝缘包络填充率（可用槽面积）",
)

NOT_AVAILABLE_ZH = "不可用"

#: A slotless machine has no slot fill. That is not the same as a slotted
#: machine whose fill could not be computed, and must not read the same.
SLOTLESS_STATUS_LABEL_ZH = "不适用（无槽结构）"

ASSUMPTION_NOTE_ZH = (
    "装填系数与阈值分档为工程假设（ENGINEERING_ASSUMPTION），"
    "适用于随机绕制圆导线，不是标准规定值。"
)


@dataclass(frozen=True)
class SlotFillCard:
    """Everything the dashboard card shows, already formatted or ``None``."""

    schema_version: str
    title_zh: str
    #: Raw status name, or ``None`` when no fill exists at all.
    status: str | None
    status_label_zh: str
    usable_copper_fill: float | None
    usable_envelope_fill: float | None
    gross_copper_fill: float | None
    gross_envelope_fill: float | None
    gross_slot_area_mm2: float | None
    usable_slot_area_mm2: float | None
    bare_copper_area_mm2: float | None
    envelope_area_mm2: float | None
    packing_factor: float | None
    #: Populated only when there is no fill. Never ``None`` in that case.
    unavailable_reason_zh: str | None
    missing_fields: tuple[str, ...]
    warnings_zh: tuple[str, ...]

    @property
    def is_available(self) -> bool:
        return self.status is not None


def _percent(value: float | None) -> str:
    return NOT_AVAILABLE_ZH if value is None else f"{value * 100.0:.2f} %"


def _area(value: float | None) -> str:
    return NOT_AVAILABLE_ZH if value is None else f"{value:.2f} mm²"


def build_slot_fill_card(evaluation: WindingEvaluation | None) -> SlotFillCard:
    """Render a winding evaluation's slot fill for the dashboard.

    An evaluation with no fill still produces a card: the point of the card is
    that the user learns either the numbers or the reason there are none.
    """

    if evaluation is None:
        return SlotFillCard(
            schema_version=SLOT_FILL_CARD_SCHEMA_VERSION,
            title_zh=CARD_TITLE_ZH,
            status=None,
            status_label_zh=NOT_AVAILABLE_ZH,
            usable_copper_fill=None,
            usable_envelope_fill=None,
            gross_copper_fill=None,
            gross_envelope_fill=None,
            gross_slot_area_mm2=None,
            usable_slot_area_mm2=None,
            bare_copper_area_mm2=None,
            envelope_area_mm2=None,
            packing_factor=None,
            unavailable_reason_zh="尚未计算绕组：请先运行分析。",
            missing_fields=(),
            warnings_zh=(),
        )

    fill = evaluation.fill
    if fill is None:
        reason = (
            evaluation.fill_unavailable_reason_zh
            or evaluation.unavailable_reason_zh
            or "槽满率无法计算：当前输入不足以确定槽几何或导体截面。"
        )
        return SlotFillCard(
            schema_version=SLOT_FILL_CARD_SCHEMA_VERSION,
            title_zh=CARD_TITLE_ZH,
            status=None,
            status_label_zh=(
                SLOTLESS_STATUS_LABEL_ZH
                if evaluation.is_slotless
                else STATUS_LABELS_ZH[ManufacturabilityStatus.NOT_CALCULABLE]
            ),
            usable_copper_fill=None,
            usable_envelope_fill=None,
            gross_copper_fill=None,
            gross_envelope_fill=None,
            gross_slot_area_mm2=None,
            usable_slot_area_mm2=None,
            bare_copper_area_mm2=None,
            envelope_area_mm2=None,
            packing_factor=None,
            unavailable_reason_zh=reason,
            missing_fields=tuple(evaluation.fill_missing_fields),
            warnings_zh=(),
        )

    return SlotFillCard(
        schema_version=SLOT_FILL_CARD_SCHEMA_VERSION,
        title_zh=CARD_TITLE_ZH,
        status=fill.status,
        status_label_zh=STATUS_LABELS_ZH.get(fill.status, str(fill.status)),
        usable_copper_fill=fill.usable_copper_fill,
        usable_envelope_fill=fill.usable_envelope_fill,
        gross_copper_fill=fill.gross_copper_fill,
        gross_envelope_fill=fill.gross_envelope_fill,
        gross_slot_area_mm2=fill.gross_slot_area_mm2,
        usable_slot_area_mm2=fill.usable_slot_area_mm2,
        bare_copper_area_mm2=fill.bare_copper_area_per_slot_mm2,
        envelope_area_mm2=fill.envelope_area_per_slot_mm2,
        packing_factor=fill.packing_factor,
        unavailable_reason_zh=None,
        missing_fields=(),
        warnings_zh=tuple(fill.warnings),
    )


def primary_rows_zh(card: SlotFillCard) -> tuple[tuple[str, str], ...]:
    """The two headline percentages plus the finding."""

    return (
        (PRIMARY_LABELS_ZH[0], _percent(card.usable_copper_fill)),
        (PRIMARY_LABELS_ZH[1], _percent(card.usable_envelope_fill)),
        ("状态", card.status_label_zh),
    )


def detail_rows_zh(card: SlotFillCard) -> tuple[tuple[str, str], ...]:
    """Areas and all four fill ratios, so the headline can be checked."""

    return (
        ("总槽面积", _area(card.gross_slot_area_mm2)),
        ("可用槽面积", _area(card.usable_slot_area_mm2)),
        ("裸铜面积", _area(card.bare_copper_area_mm2)),
        ("绝缘后导体包络面积", _area(card.envelope_area_mm2)),
        ("总槽面积铜填充率", _percent(card.gross_copper_fill)),
        ("可用槽面积铜填充率", _percent(card.usable_copper_fill)),
        ("总槽面积包络填充率", _percent(card.gross_envelope_fill)),
        ("可用槽面积包络填充率", _percent(card.usable_envelope_fill)),
    )


def render_slot_fill_card_zh(card: SlotFillCard) -> str:
    """The card as one block of text for a dashboard label."""

    lines = []
    for label, value in primary_rows_zh(card):
        lines.append(f"  {label}：{value}")
    if not card.is_available:
        lines.append("")
        lines.append(f"  原因：{card.unavailable_reason_zh}")
        return "\n".join(lines)

    lines.append("")
    for label, value in detail_rows_zh(card):
        lines.append(f"  {label}：{value}")
    if card.packing_factor is not None:
        lines.append(f"  装填系数：{card.packing_factor:.2f}")
    if card.warnings_zh:
        lines.append("")
        lines.extend(f"  · {message}" for message in card.warnings_zh)
    lines.append("")
    lines.append(f"  {ASSUMPTION_NOTE_ZH}")
    return "\n".join(lines)
