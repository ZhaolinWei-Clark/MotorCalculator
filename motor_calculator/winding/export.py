"""Phase 10H: exporting the winding engineering block, without ambiguity.

The rule this module exists to enforce: **no naked ``kw`` field**. An export that
says ``kw = 0.93`` tells a reader nothing about whether that is a user's guess, a
slot-star derivation, or a value inherited from a project built before the
distinction existed -- and this project has shipped all three.

Every winding factor in an export therefore travels with its source:

``production_winding_factor`` / ``production_winding_factor_source``
    The value production actually used, and the authority that chose it.

``ideal_geometry_winding_factor``
    What the slot-EMF star gives for this geometry. Always reported when it can
    be computed, even under a manual override, so the override is visible.

``manual_winding_factor``
    The stored manual number, when one exists.

``meshed_fea_winding_factor``
    Reported only when FEA evidence exists, and always carrying
    ``NOT_PRODUCTION_AUTHORITATIVE`` so it cannot be mistaken for the value the
    calculation used.
"""

from __future__ import annotations

from typing import Any, Mapping

from .authority import MESHED_FEA_PROVENANCE, ProductionWindingFactor, WindingAuthority

WINDING_EXPORT_SCHEMA_VERSION = "phase10h.winding_export.v1"

#: Attached to any meshed value that appears in an export.
MESHED_EXPORT_LABEL = "NOT_PRODUCTION_AUTHORITATIVE"


def build_winding_export_block(
    *,
    production: ProductionWindingFactor,
    report=None,
    fill=None,
    meshed_winding_factor: float | None = None,
) -> dict[str, Any]:
    """Assemble the winding section of an export payload.

    ``meshed_winding_factor`` is accepted only so it can be labelled. It never
    influences ``production_winding_factor``.
    """

    block: dict[str, Any] = {
        "schema_version": WINDING_EXPORT_SCHEMA_VERSION,
        "authority": {
            "production_winding_factor": production.value,
            "production_winding_factor_source": production.authority.value,
            "production_winding_factor_provenance": production.provenance,
            "ideal_geometry_winding_factor": production.geometry_value,
            "manual_winding_factor": production.manual_value,
            "overrides_geometry": production.overrides_geometry,
            "geometry_delta_percent": production.geometry_delta_percent,
            "reason_zh": production.reason_zh,
            "warnings": list(production.warnings),
        },
        "calibration_status": "NONE",
    }

    if meshed_winding_factor is not None:
        block["fea_diagnostic"] = {
            "meshed_fea_winding_factor": meshed_winding_factor,
            "provenance": MESHED_FEA_PROVENANCE,
            "status": MESHED_EXPORT_LABEL,
            "note_zh": (
                "剖分几何绕组系数仅用于有限元结果解释，描述的是二维展开切片中的"
                "导体布局，不是生产计算所用的值。"
            ),
        }

    if report is not None:
        block["geometry"] = {
            "slots": report.slots,
            "pole_count": report.pole_count,
            "phases": report.phases,
            "slots_per_pole_per_phase": report.slots_per_pole_per_phase,
            "topology": report.topology,
            "coil_span_slots": report.coil_span_slots,
            "full_pitch_slots": report.full_pitch_slots,
            "layers": report.layers,
            "parallel_paths": report.parallel_paths,
            "provenance": "GEOMETRY_DERIVED",
        }
        block["factors"] = {
            "distribution_factor": report.distribution_factor,
            "pitch_factor": report.pitch_factor,
            "skew_factor": report.skew_factor,
            "ideal_winding_factor": report.factors.ideal_slot_star,
            "production_authoritative_winding_factor": production.value,
            "provenance": "GEOMETRY_DERIVED",
        }

    if fill is not None:
        block["slot_fill"] = {
            "gross_slot_area_mm2": fill.gross_slot_area_mm2,
            "usable_slot_area_mm2": fill.usable_slot_area_mm2,
            "coil_sides_per_slot": fill.coil_sides_per_slot,
            "turns_per_coil_side": fill.turns_per_coil_side,
            "conductors_per_slot": fill.conductors_per_slot,
            "bare_copper_area_per_slot_mm2": fill.bare_copper_area_per_slot_mm2,
            "insulated_envelope_area_per_slot_mm2": fill.envelope_area_per_slot_mm2,
            "gross_copper_fill": fill.gross_copper_fill,
            "usable_copper_fill": fill.usable_copper_fill,
            "gross_envelope_fill": fill.gross_envelope_fill,
            "usable_envelope_fill": fill.usable_envelope_fill,
            "packing_factor": fill.packing_factor,
            "packing_factor_provenance": fill.packing_factor_provenance,
            "manufacturability_status": fill.status,
            "manufacturability_status_provenance": fill.status_provenance,
            "warnings": list(fill.warnings),
        }

    return block


def assert_no_ambiguous_winding_factor(payload: Mapping[str, Any]) -> None:
    """Raise if an export carries a bare ``kw``-style field with no source.

    Used as a guard in tests and at export sites. Historical compatibility
    fields inside a clearly named legacy block are allowed; a new top-level
    ``kw`` is not.
    """

    ambiguous = {"kw", "k_w", "winding_factor"}
    for key in payload:
        if str(key).strip().lower() in ambiguous:
            raise ValueError(
                f"export carries an ambiguous winding factor field {key!r}; use "
                "production_winding_factor together with "
                "production_winding_factor_source"
            )
