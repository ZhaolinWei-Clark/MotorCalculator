"""Phase 10H: winding authority, legacy compatibility, persistence and export."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path

import pytest

from motor_calculator.winding.authority import (
    AUTHORITY_LABELS_ZH,
    MESHED_FEA_PROVENANCE,
    PRODUCTION_ADMISSIBLE_PROVENANCE,
    WINDING_AUTHORITY_SCHEMA_VERSION,
    ProductionWindingFactor,
    WindingAuthority,
    classify_loaded_authority,
    ideal_geometry_winding_factor,
    resolve_production_winding_factor,
)
from motor_calculator.winding.export import (
    MESHED_EXPORT_LABEL,
    assert_no_ambiguous_winding_factor,
    build_winding_export_block,
)
from motor_calculator.winding.feasibility import (
    has_blocking_winding_issue,
    winding_manufacturability_issues,
)
from motor_calculator.winding.persistence import (
    AUTHORITY_KEY,
    WindingProjectState,
    from_preferences,
    new_project_state,
    to_preferences,
)
from motor_calculator.winding.slot_fill import (
    ConductorSpec,
    ManufacturabilityStatus,
    SlotGeometry,
    compute_slot_fill,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASELINE_GEOMETRY = dict(slots=24, pole_pairs=8, coil_span_slots=1)
GEOMETRY_KW = math.sqrt(3.0) / 2.0
LEGACY_KW = 0.93


# ---------------------------------------------------------------------------
# Authority states
# ---------------------------------------------------------------------------


def test_the_four_authority_states_exist():
    assert {a.value for a in WindingAuthority} == {
        "AUTO_FROM_GEOMETRY", "MANUAL_OVERRIDE", "LEGACY_MANUAL", "UNRESOLVED"
    }
    for authority in WindingAuthority:
        assert authority in AUTHORITY_LABELS_ZH


def test_auto_resolves_from_production_geometry():
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.AUTO_FROM_GEOMETRY,
        manual_value=LEGACY_KW, **BASELINE_GEOMETRY,
    )
    assert resolved.value == pytest.approx(GEOMETRY_KW)
    assert resolved.authority is WindingAuthority.AUTO_FROM_GEOMETRY
    assert resolved.provenance == "IDEAL_SLOT_STAR_GEOMETRY"
    # A manual value present in the project must NOT win under AUTO.
    assert resolved.value != pytest.approx(LEGACY_KW)
    assert resolved.overrides_geometry is False


def test_manual_override_wins_and_says_so():
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.MANUAL_OVERRIDE,
        manual_value=LEGACY_KW, **BASELINE_GEOMETRY,
    )
    assert resolved.value == pytest.approx(LEGACY_KW)
    assert resolved.provenance == "MANUAL_USER"
    assert resolved.overrides_geometry is True
    assert resolved.geometry_value == pytest.approx(GEOMETRY_KW)
    assert resolved.warnings, "an override must be visible"


def test_legacy_manual_is_preserved_exactly_and_never_re_derived():
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.LEGACY_MANUAL,
        manual_value=LEGACY_KW, **BASELINE_GEOMETRY,
    )
    assert resolved.value == LEGACY_KW  # exact, not approx
    assert resolved.provenance == "LEGACY_PROJECT"
    assert resolved.geometry_value == pytest.approx(GEOMETRY_KW)
    assert resolved.warnings


def test_auto_without_geometry_invents_nothing():
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.AUTO_FROM_GEOMETRY,
        manual_value=LEGACY_KW, slots=None, pole_pairs=None, coil_span_slots=None,
    )
    assert resolved.value is None
    assert resolved.authority is WindingAuthority.UNRESOLVED
    assert not resolved.is_resolved
    # Crucially it does NOT silently fall back to the manual value.
    assert resolved.value != LEGACY_KW


def test_manual_override_without_a_value_is_unresolved():
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.MANUAL_OVERRIDE, manual_value=None, **BASELINE_GEOMETRY,
    )
    assert resolved.authority is WindingAuthority.UNRESOLVED


def test_an_unbalanced_combination_yields_no_geometry_value():
    assert ideal_geometry_winding_factor(slots=5, pole_pairs=8, coil_span_slots=1) is None


def test_a_resolved_factor_must_lie_in_the_unit_interval():
    with pytest.raises(ValueError):
        ProductionWindingFactor(
            schema_version=WINDING_AUTHORITY_SCHEMA_VERSION, value=1.5,
            authority=WindingAuthority.MANUAL_OVERRIDE, provenance="MANUAL_USER",
            geometry_value=None, manual_value=1.5, reason_zh="",
        )


# ---------------------------------------------------------------------------
# The meshed firewall
# ---------------------------------------------------------------------------


def test_meshed_provenance_is_not_admissible_for_production():
    assert MESHED_FEA_PROVENANCE not in PRODUCTION_ADMISSIBLE_PROVENANCE
    with pytest.raises(ValueError, match="diagnostic only"):
        ProductionWindingFactor(
            schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
            value=0.9557520074850538,
            authority=WindingAuthority.AUTO_FROM_GEOMETRY,
            provenance=MESHED_FEA_PROVENANCE,
            geometry_value=GEOMETRY_KW, manual_value=None, reason_zh="",
        )


def test_the_resolver_has_no_parameter_a_meshed_value_could_enter_through():
    parameters = set(inspect.signature(resolve_production_winding_factor).parameters)
    assert not any("mesh" in name.lower() for name in parameters), parameters
    assert not any("fea" in name.lower() for name in parameters), parameters


def test_auto_never_returns_the_meshed_value_for_the_reference_case():
    """The meshed factor is 0.9558; AUTO must return the slot-star 0.8660."""

    from motor_calculator.fea.meshed_winding import meshed_winding_factor_for_case
    from motor_calculator.fea.models import FEAValidationTarget
    from motor_calculator.fea.reference_cases import build_self_consistent_reference_case

    meshed = meshed_winding_factor_for_case(
        build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    ).value
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority.AUTO_FROM_GEOMETRY,
        manual_value=None, **BASELINE_GEOMETRY,
    )
    assert meshed == pytest.approx(0.9557520074850538)
    assert resolved.value == pytest.approx(GEOMETRY_KW)
    assert resolved.value != pytest.approx(meshed, rel=1e-3)


def test_the_authority_module_never_imports_the_meshed_engine():
    source = (
        REPOSITORY_ROOT / "motor_calculator" / "winding" / "authority.py"
    ).read_text(encoding="utf-8")
    assert "meshed_winding" not in source.replace(MESHED_FEA_PROVENANCE, "")


# ---------------------------------------------------------------------------
# Legacy classification and persistence
# ---------------------------------------------------------------------------


def test_a_document_without_an_authority_key_is_legacy():
    assert classify_loaded_authority(None, has_manual_value=True) is WindingAuthority.LEGACY_MANUAL
    assert classify_loaded_authority({}, has_manual_value=True) is WindingAuthority.LEGACY_MANUAL
    assert classify_loaded_authority(None, has_manual_value=False) is WindingAuthority.UNRESOLVED


def test_an_explicit_authority_key_is_honoured():
    assert classify_loaded_authority(
        {"authority": "AUTO_FROM_GEOMETRY"}, has_manual_value=True
    ) is WindingAuthority.AUTO_FROM_GEOMETRY


def test_a_corrupt_authority_value_degrades_to_legacy_not_to_auto():
    assert classify_loaded_authority(
        {"authority": "nonsense"}, has_manual_value=True
    ) is WindingAuthority.LEGACY_MANUAL


def test_new_projects_default_to_auto_when_geometry_supports_it():
    state = new_project_state(**BASELINE_GEOMETRY)
    assert state.authority is WindingAuthority.AUTO_FROM_GEOMETRY
    assert not state.is_legacy


def test_new_projects_without_geometry_do_not_invent_auto():
    assert new_project_state(
        slots=None, pole_pairs=None, coil_span_slots=None, manual_winding_factor=0.9
    ).authority is WindingAuthority.MANUAL_OVERRIDE
    assert new_project_state(
        slots=None, pole_pairs=None, coil_span_slots=None
    ).authority is WindingAuthority.UNRESOLVED


def test_auto_state_round_trips_through_preferences():
    state = new_project_state(**BASELINE_GEOMETRY)
    restored = from_preferences(to_preferences(state), stored_manual_winding_factor=None)
    assert restored.authority is state.authority
    assert restored.coil_span_slots == state.coil_span_slots
    assert restored.layers == state.layers
    assert restored.packing_factor == pytest.approx(state.packing_factor)


def test_manual_state_round_trips_with_its_value_intact():
    state = WindingProjectState(
        authority=WindingAuthority.MANUAL_OVERRIDE,
        manual_winding_factor=LEGACY_KW, coil_span_slots=1,
        liner_thickness_mm=0.3, clearance_mm=0.15, packing_factor=0.72,
        insulation_ratio=1.11, layers=1, parallel_strands=4, turns_per_coil=7.0,
    )
    restored = from_preferences(to_preferences(state), stored_manual_winding_factor=None)
    assert restored.authority is WindingAuthority.MANUAL_OVERRIDE
    assert restored.manual_winding_factor == LEGACY_KW
    assert restored.liner_thickness_mm == pytest.approx(0.3)
    assert restored.clearance_mm == pytest.approx(0.15)
    assert restored.packing_factor == pytest.approx(0.72)
    assert restored.insulation_ratio == pytest.approx(1.11)
    assert restored.layers == 1
    assert restored.parallel_strands == 4
    assert restored.turns_per_coil == pytest.approx(7.0)


def test_a_pre_10h_project_loads_as_legacy_and_keeps_its_value():
    """RC2-era preferences carry winding_factor_mode but no winding.authority."""

    legacy_preferences = {"winding_factor_mode": "manual", "coil_span_slots": "1"}
    assert AUTHORITY_KEY not in legacy_preferences
    state = from_preferences(legacy_preferences, stored_manual_winding_factor=LEGACY_KW)
    assert state.authority is WindingAuthority.LEGACY_MANUAL
    assert state.manual_winding_factor == LEGACY_KW
    resolved = resolve_production_winding_factor(
        authority=state.authority, manual_value=state.manual_winding_factor,
        **BASELINE_GEOMETRY,
    )
    assert resolved.value == LEGACY_KW


def test_persisted_values_are_all_json_scalars():
    """ui_preferences is a flat scalar mapping; nesting would not survive."""

    for value in to_preferences(new_project_state(**BASELINE_GEOMETRY)).values():
        assert isinstance(value, (str, int, float, bool)) or value is None


def test_derived_values_are_not_persisted():
    """Storing kd/kp/kw would create a second source of truth that can drift."""

    keys = set(to_preferences(new_project_state(**BASELINE_GEOMETRY)))
    for forbidden in ("winding.kd", "winding.kp", "winding.ks", "winding.production_kw"):
        assert forbidden not in keys


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _resolved(authority=WindingAuthority.LEGACY_MANUAL, manual=LEGACY_KW):
    return resolve_production_winding_factor(
        authority=authority, manual_value=manual, **BASELINE_GEOMETRY
    )


def test_the_export_names_the_source_of_every_winding_factor():
    block = build_winding_export_block(production=_resolved())
    authority = block["authority"]
    assert authority["production_winding_factor"] == LEGACY_KW
    assert authority["production_winding_factor_source"] == "LEGACY_MANUAL"
    assert authority["production_winding_factor_provenance"] == "LEGACY_PROJECT"
    assert authority["ideal_geometry_winding_factor"] == pytest.approx(GEOMETRY_KW)
    assert authority["overrides_geometry"] is True


def test_a_meshed_value_in_an_export_is_labelled_non_production():
    block = build_winding_export_block(
        production=_resolved(), meshed_winding_factor=0.9557520074850538
    )
    diagnostic = block["fea_diagnostic"]
    assert diagnostic["status"] == MESHED_EXPORT_LABEL
    assert diagnostic["provenance"] == MESHED_FEA_PROVENANCE
    # and it did not become the production value.
    assert block["authority"]["production_winding_factor"] == LEGACY_KW


def test_the_export_declares_no_calibration():
    assert build_winding_export_block(production=_resolved())["calibration_status"] == "NONE"


def test_a_naked_winding_factor_field_is_rejected():
    for key in ("kw", "k_w", "winding_factor"):
        with pytest.raises(ValueError, match="ambiguous"):
            assert_no_ambiguous_winding_factor({key: 0.93})
    assert_no_ambiguous_winding_factor(build_winding_export_block(production=_resolved()))


def test_the_export_carries_slot_fill_when_available():
    fill = compute_slot_fill(
        geometry=SlotGeometry(
            slot_count=24, top_width_mm=8.0, bottom_width_mm=6.0, depth_mm=15.0,
            wedge_height_mm=2.0, liner_thickness_mm=0.25, clearance_mm=0.1,
        ),
        conductor=ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.296, parallel_strands=3),
        turns_per_coil=5.25, coil_sides_per_slot=2,
    )
    block = build_winding_export_block(production=_resolved(), fill=fill)
    slot = block["slot_fill"]
    for key in (
        "gross_slot_area_mm2", "usable_slot_area_mm2",
        "bare_copper_area_per_slot_mm2", "insulated_envelope_area_per_slot_mm2",
        "gross_copper_fill", "usable_copper_fill",
        "gross_envelope_fill", "usable_envelope_fill",
        "manufacturability_status",
    ):
        assert key in slot
    assert slot["packing_factor_provenance"] == "ENGINEERING_ASSUMPTION"


# ---------------------------------------------------------------------------
# Feasibility
# ---------------------------------------------------------------------------


def _fill(turns: float):
    return compute_slot_fill(
        geometry=SlotGeometry(
            slot_count=24, top_width_mm=8.0, bottom_width_mm=6.0, depth_mm=15.0,
            wedge_height_mm=2.0, liner_thickness_mm=0.25, clearance_mm=0.1,
        ),
        conductor=ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.296, parallel_strands=3),
        turns_per_coil=turns, coil_sides_per_slot=2,
    )


def test_a_comfortable_winding_raises_no_manufacturability_issue():
    """Additive: a design that was feasible before stays feasible."""

    assert winding_manufacturability_issues(fill=_fill(2.0)) == ()


def test_an_overfilled_slot_becomes_a_feasibility_reason():
    issues = winding_manufacturability_issues(fill=_fill(40.0))
    codes = {issue.code for issue in issues}
    assert "SLOT_OVERFILLED" in codes
    assert has_blocking_winding_issue(issues)


def test_a_geometrically_impossible_slot_is_an_error():
    issues = winding_manufacturability_issues(fill=_fill(40.0))
    assert "SLOT_GEOMETRICALLY_IMPOSSIBLE" in {i.code for i in issues}
    assert any(i.severity == "ERROR" for i in issues)


def test_an_unresolved_winding_factor_is_a_feasibility_error():
    unresolved = resolve_production_winding_factor(
        authority=WindingAuthority.AUTO_FROM_GEOMETRY, manual_value=None,
        slots=None, pole_pairs=None, coil_span_slots=None,
    )
    issues = winding_manufacturability_issues(fill=None, production=unresolved)
    assert "WINDING_FACTOR_UNRESOLVED" in {i.code for i in issues}
    assert has_blocking_winding_issue(issues)


def test_nothing_is_adjusted_to_make_a_design_pass():
    """The overfilled result keeps its computed ratio; it is not clipped."""

    fill = _fill(40.0)
    assert fill.status == ManufacturabilityStatus.OVERFILLED
    assert fill.usable_envelope_fill > 1.0
    assert fill.turns_per_coil_side == 40.0


# ---------------------------------------------------------------------------
# Proposal C impact, protected physics, calibration
# ---------------------------------------------------------------------------


def test_the_proposal_c_impact_is_material_and_measured():
    """Switching authority is not a cosmetic default change."""

    import math as _math

    from motor_calculator.input_ux import APPLICATION_DEFAULTS
    from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
    from motor_calculator.motor_core.validation import parse_legacy_gui_params

    def ke_for(kw: float) -> float:
        parameters = dict(APPLICATION_DEFAULTS)
        parameters["k_w"] = kw
        bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(parameters))
        result = bridge.run_full_analysis()
        omega = bridge.input_data.mechanical_speed_rpm * 2.0 * _math.pi / 60.0
        return result.electrical.back_emf_phase_rms_v / omega

    change = ke_for(GEOMETRY_KW) / ke_for(LEGACY_KW) - 1.0
    # Ke scales linearly with kw, so the change is the kw change.
    assert change == pytest.approx(GEOMETRY_KW / LEGACY_KW - 1.0, rel=1e-9)
    assert abs(change) > 0.05, "a >5% change must not be treated as a silent default"


def test_production_physics_is_untouched_by_phase10h():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_no_calibration_anywhere_in_the_winding_package():
    package = REPOSITORY_ROOT / "motor_calculator" / "winding"
    for path in sorted(package.glob("*.py")):
        lowered = path.read_text(encoding="utf-8").lower()
        for forbidden in ("curve_fit", "least_squares", "polyfit"):
            assert forbidden not in lowered, f"{path.name} must not fit anything"


def test_the_packaged_build_declares_the_phase10h_modules():
    spec = (REPOSITORY_ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    for module in (
        "motor_calculator.winding.authority",
        "motor_calculator.winding.persistence",
        "motor_calculator.winding.export",
        "motor_calculator.winding.feasibility",
    ):
        assert module in spec, module
