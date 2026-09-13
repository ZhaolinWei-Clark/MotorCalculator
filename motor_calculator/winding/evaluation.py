"""Phase 11A: one winding evaluation, two views.

Phase 10G/10H put the winding report, the slot fill, the production authority and
the manufacturability issues behind four separate calls, and the only caller that
assembled them was the winding engineering dialog -- inside a Tk widget, reading
its own ``StringVar`` assumption fields.

Phase 11A has to show a condensed version of the same thing on the main
dashboard. Reassembling the sequence a second time would create two sources of
truth for a number a user sees in two places, and they would drift. So the
assembly moves here, the dialog becomes one caller, and the dashboard becomes
another. Neither computes anything the other does not.

This module decides nothing new and changes no physics. It resolves the
production winding factor through :func:`resolve_production_winding_factor`, so
the Phase 10H firewall applies unchanged: a meshed FEA winding factor may be
*passed in for display* alongside the others, and can never become the
production value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .authority import ProductionWindingFactor, WindingAuthority, resolve_production_winding_factor
from .feasibility import WindingFeasibilityIssue, winding_manufacturability_issues
from .persistence import WindingProjectState
from .report import WindingReport, build_winding_report
from .slot_fill import ConductorSpec, SlotGeometry, SlotFillResult, compute_slot_fill

WINDING_EVALUATION_SCHEMA_VERSION = "phase11a.winding_evaluation.v1"

NO_SLOT_GEOMETRY_MESSAGE_ZH = (
    "该设计为无槽/无铁芯结构，没有槽面积可供计算；"
    "这里不会用等效面积代替真实槽利用率。"
)

#: RC5.1. The inputs slot fill needs, and what to call each one when it is the
#: reason a user cannot see a fill number. "不可用" on its own tells a user
#: nothing they can act on; the missing field name does.
SLOT_FILL_REQUIRED_FIELDS_ZH: dict[str, str] = {
    "slots": "槽数",
    "h_slot": "槽深",
    "w_slot_top": "槽顶宽",
    "w_slot_bottom": "槽底宽",
    "d_wire": "裸导线直径",
    "n_parallel": "并联支路数",
    "N_ph_turns": "每相串联匝数",
}

#: Named separately because it is an assumption the winding panel owns rather
#: than a design input the user typed.
SLOT_FILL_ASSUMPTION_FIELDS_ZH: dict[str, str] = {
    "liner_thickness_mm": "槽衬厚度",
    "clearance_mm": "绕制间隙",
    "insulation_ratio": "绝缘线径比",
    "packing_factor": "装填系数",
}

SLOT_FILL_UNAVAILABLE_PREFIX_ZH = "槽满率无法计算，缺少："


def missing_slot_fill_fields(parameters: Mapping[str, Any]) -> tuple[str, ...]:
    """Which required slot-fill inputs are absent or unusable.

    Returns field names, not messages, so a caller can render them however it
    needs and a test can assert on the names.
    """

    missing: list[str] = []
    for field in SLOT_FILL_REQUIRED_FIELDS_ZH:
        value = parameters.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            missing.append(field)
            continue
        if not (number > 0.0):
            missing.append(field)
    return tuple(missing)


def describe_missing_slot_fill_fields(missing) -> str:
    """The missing-field list as one sentence a user can act on."""

    names = "、".join(
        f"{SLOT_FILL_REQUIRED_FIELDS_ZH.get(field, field)}（{field}）" for field in missing
    )
    return f"{SLOT_FILL_UNAVAILABLE_PREFIX_ZH}{names}。"


@dataclass(frozen=True)
class WindingEvaluation:
    """Everything both the winding panel and the dashboard need."""

    schema_version: str
    report: WindingReport | None
    fill: SlotFillResult | None
    production: ProductionWindingFactor | None
    issues: tuple[WindingFeasibilityIssue, ...]
    warnings: tuple[str, ...]
    #: True when the design has no slots at all, as opposed to having slots whose
    #: fill could not be computed. The two must not be shown the same way.
    is_slotless: bool
    unavailable_reason_zh: str | None = None
    #: RC5.1. Why there is no slot-fill result, when there is none. ``None``
    #: means a fill was computed.
    fill_unavailable_reason_zh: str | None = None
    #: The specific parameter names that were missing, when that is the reason.
    fill_missing_fields: tuple[str, ...] = ()

    @property
    def is_available(self) -> bool:
        return self.report is not None


def _positive_int(value: Any, fallback: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def evaluate_winding(
    parameters: Mapping[str, Any],
    *,
    authority: WindingAuthority | str,
    manual_winding_factor: float | None = None,
    assumptions: WindingProjectState | None = None,
    meshed_winding_factor: float | None = None,
    finite_width_factor: float | None = None,
) -> WindingEvaluation:
    """Assemble the winding picture for one set of design parameters.

    ``manual_winding_factor`` defaults to the design's own ``k_w`` when not
    given, which is what both callers want: the manual authority states are
    about the number the user entered.
    """

    state = assumptions or WindingProjectState()
    warnings: list[str] = []

    slots = _positive_int(parameters.get("slots"))
    pole_pairs = _positive_int(parameters.get("p"))
    if not slots or not pole_pairs:
        return WindingEvaluation(
            schema_version=WINDING_EVALUATION_SCHEMA_VERSION,
            report=None,
            fill=None,
            production=None,
            issues=(),
            warnings=("缺少槽数或极对数，无法计算绕组。",),
            is_slotless=False,
            unavailable_reason_zh="缺少槽数或极对数，无法计算绕组。",
        )

    layers = max(1, int(state.layers))
    coil_span = parameters.get("coil_span_slots")
    if coil_span in (None, ""):
        coil_span = state.coil_span_slots
    coil_span = float(coil_span or 1)

    if manual_winding_factor is None:
        raw = parameters.get("k_w")
        manual_winding_factor = float(raw) if raw is not None else None

    report = build_winding_report(
        slots=slots,
        pole_pairs=pole_pairs,
        coil_span_slots=coil_span,
        layers=layers,
        parallel_paths=_positive_int(parameters.get("n_parallel"), 1),
        entered_winding_factor=manual_winding_factor,
        entered_provenance="USER_INPUT",
        meshed_winding_factor=meshed_winding_factor,
        finite_width_factor=finite_width_factor,
    )

    is_slotless = bool(parameters.get("coreless")) or str(parameters.get("slot_type")) == "无槽"
    fill: SlotFillResult | None = None
    fill_reason: str | None = None
    fill_missing: tuple[str, ...] = ()
    if is_slotless:
        warnings.append(NO_SLOT_GEOMETRY_MESSAGE_ZH)
        fill_reason = NO_SLOT_GEOMETRY_MESSAGE_ZH
    elif missing_slot_fill_fields(parameters):
        fill_missing = missing_slot_fill_fields(parameters)
        fill_reason = describe_missing_slot_fill_fields(fill_missing)
        warnings.append(fill_reason)
    else:
        try:
            geometry = SlotGeometry(
                slot_count=slots,
                top_width_mm=float(parameters["w_slot_top"]),
                bottom_width_mm=float(parameters["w_slot_bottom"]),
                depth_mm=float(parameters["h_slot"]),
                wedge_height_mm=float(parameters.get("h_wedge") or 0.0),
                liner_thickness_mm=float(state.liner_thickness_mm),
                clearance_mm=float(state.clearance_mm),
            )
            bare = float(parameters["d_wire"])
            conductor = ConductorSpec(
                bare_diameter_mm=bare,
                insulated_diameter_mm=(
                    float(state.insulated_diameter_mm)
                    if state.insulated_diameter_mm
                    else bare * float(state.insulation_ratio)
                ),
                parallel_strands=_positive_int(parameters.get("n_parallel"), 1),
            )
            turns_per_phase = float(parameters["N_ph_turns"])
            fill = compute_slot_fill(
                geometry=geometry,
                conductor=conductor,
                turns_per_coil=turns_per_phase * report.phases / slots,
                coil_sides_per_slot=layers,
                packing_factor=float(state.packing_factor),
            )
            warnings.extend(fill.warnings)
        except (KeyError, TypeError, ValueError) as error:
            fill_reason = f"槽满率无法计算：{error}"
            warnings.append(fill_reason)

    production = resolve_production_winding_factor(
        authority=authority,
        manual_value=manual_winding_factor,
        slots=slots,
        pole_pairs=pole_pairs,
        coil_span_slots=coil_span,
        phases=report.phases,
        skew_slots=float(state.skew_slots),
    )
    warnings.extend(production.warnings)

    issues = winding_manufacturability_issues(fill=fill, production=production)
    return WindingEvaluation(
        schema_version=WINDING_EVALUATION_SCHEMA_VERSION,
        report=report,
        fill=fill,
        production=production,
        issues=issues,
        warnings=tuple(warnings),
        is_slotless=is_slotless,
        fill_unavailable_reason_zh=fill_reason,
        fill_missing_fields=fill_missing,
    )
