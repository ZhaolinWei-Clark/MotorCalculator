"""Phase 10G: electrical axes, winding factors, slot fill and manufacturability.

No solver runs here. The one test that consumes FEMM output reads the committed
Phase 10G recheck evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from motor_calculator.fea.meshed_winding import meshed_winding_factor_for_case
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import build_self_consistent_reference_case
from motor_calculator.winding.electrical_axis import (
    ELECTRICAL_AXIS_SCHEMA_VERSION,
    GEOMETRY_DERIVED,
    derive_electrical_axes,
    electrical_axes_for_case,
    excitation_angle_for_case,
    inverse_park_abc,
)
from motor_calculator.winding.panel_text import (
    build_winding_panel_rows,
    render_winding_panel_zh,
)
from motor_calculator.winding.report import (
    WindingTopology,
    build_winding_report,
    classify_topology,
)
from motor_calculator.winding.slot_fill import (
    DEFAULT_PACKING_FACTOR,
    ConductorSpec,
    ManufacturabilityStatus,
    Provenance,
    SlotFillResult,
    SlotGeometry,
    compute_slot_fill,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10g_winding"


def _case(target=FEAValidationTarget.AVERAGE_TORQUE):
    return build_self_consistent_reference_case(target)


# ---------------------------------------------------------------------------
# Angles
# ---------------------------------------------------------------------------


def test_mechanical_to_electrical_angle_scales_by_pole_pairs():
    case = _case()
    pole_pairs = case.geometry.pole_pairs
    base = electrical_axes_for_case(case, rotor_angle_mech_deg=0.0).d_axis_from_phase_a_elec_deg
    for mechanical in (5.625, 11.25, 22.5):
        measured = electrical_axes_for_case(
            case, rotor_angle_mech_deg=mechanical
        ).d_axis_from_phase_a_elec_deg
        expected = (base + pole_pairs * mechanical) % 360.0
        assert (measured - expected + 180.0) % 360.0 - 180.0 == pytest.approx(0.0, abs=0.2)


def test_the_d_axis_is_derived_and_carries_its_provenance():
    axes = electrical_axes_for_case(_case(), rotor_angle_mech_deg=0.0)
    assert axes.provenance == GEOMETRY_DERIVED
    assert axes.schema_version == ELECTRICAL_AXIS_SCHEMA_VERSION


def test_the_q_axis_is_ninety_electrical_degrees_from_the_d_axis():
    axes = electrical_axes_for_case(_case(), rotor_angle_mech_deg=0.0)
    delta = (axes.q_axis_from_phase_a_elec_deg - axes.d_axis_from_phase_a_elec_deg) % 360.0
    assert delta == pytest.approx(90.0)
    assert (axes.q_axis_elec_deg - axes.d_axis_elec_deg) % 360.0 == pytest.approx(90.0)


def test_the_alignment_is_not_hard_coded_to_the_reference_machine():
    """Different slot/pole geometry must give a different electrical axis.

    Phase 10F found 150 degrees empirically for one machine. A constant would
    reproduce that value everywhere; a derivation must not.
    """

    from motor_calculator.fea.case_builder import build_validation_case
    from motor_calculator.fea.reference_cases import (
        PHASE10A_REFERENCE_MODELLING,
        PHASE10A_REFERENCE_PARAMETERS,
        resolve_self_consistent_winding_factor,
    )
    from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
    from motor_calculator.motor_core.validation import parse_legacy_gui_params

    observed = set()
    for slots, pole_pairs in ((24, 8), (36, 6), (12, 5)):
        parameters = dict(PHASE10A_REFERENCE_PARAMETERS)
        parameters["slots"] = slots
        parameters["p"] = pole_pairs
        parameters["k_w"] = resolve_self_consistent_winding_factor().value
        bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(parameters))
        analysis = bridge.run_full_analysis()
        case = build_validation_case(
            bridge.input_data, analysis,
            target=FEAValidationTarget.NO_LOAD_BACK_EMF,
            modelling=PHASE10A_REFERENCE_MODELLING,
            winding_factor_provenance="test",
        )
        observed.add(
            round(
                electrical_axes_for_case(
                    case, rotor_angle_mech_deg=0.0
                ).d_axis_from_phase_a_elec_deg,
                3,
            )
        )
    assert len(observed) > 1, f"the axis is constant across machines: {observed}"


def test_the_reference_machine_reproduces_the_phase10f_measurement():
    axes = electrical_axes_for_case(_case(), rotor_angle_mech_deg=0.0)
    assert axes.d_axis_from_phase_a_elec_deg == pytest.approx(150.0, abs=0.5)


def test_the_derived_axis_matches_the_solved_no_load_flux_linkage():
    """An independent check: lambda_A should equal peak * cos(derived angle)."""

    import numpy as np

    raw = json.loads(
        (
            REPOSITORY_ROOT / "validation_data" / "fea_results"
            / "phase10c_self_consistent" / "fea_raw_result.json"
        ).read_text(encoding="utf-8")
    )["result"]
    samples = sorted(raw["samples"], key=lambda s: s["rotor_angle_mech_deg"])
    angles = np.array([s["rotor_angle_mech_deg"] for s in samples])
    linkage = np.array([s["phase_flux_linkage_wb_turn"]["A"] for s in samples])
    peak = float(np.abs(np.fft.rfft(linkage)).max() * 2.0 / linkage.size)

    case = _case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    for mechanical in (0.0, 11.25, 22.5):
        derived = electrical_axes_for_case(
            case, rotor_angle_mech_deg=mechanical
        ).d_axis_from_phase_a_elec_deg
        index = int(np.argmin(np.abs(angles - mechanical)))
        assert linkage[index] / peak == pytest.approx(
            math.cos(math.radians(derived)), abs=0.03
        )


def test_derive_electrical_axes_rejects_a_model_without_magnets():
    class _Model:
        regions = ()
        circuit_names = ("A",)
        modelled_span_m = 0.3
        rotor_angle_mech_deg = 0.0

    with pytest.raises(ValueError):
        derive_electrical_axes(_Model(), pole_pairs=4)


def test_derive_electrical_axes_rejects_nonpositive_pole_pairs():
    case = _case()
    with pytest.raises(ValueError):
        electrical_axes_for_case(case).__class__  # touch the type
        derive_electrical_axes(None, pole_pairs=0)


def test_the_excitation_angle_helper_returns_the_d_axis():
    case = _case()
    assert excitation_angle_for_case(case, rotor_angle_mech_deg=0.0) == pytest.approx(
        electrical_axes_for_case(case, rotor_angle_mech_deg=0.0).d_axis_from_phase_a_elec_deg
    )


# ---------------------------------------------------------------------------
# Inverse Park
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theta", [0.0, 37.0, 90.0, 150.0, 270.0, 359.9])
def test_the_three_phase_currents_always_sum_to_zero(theta: float):
    currents = inverse_park_abc(id_a=3.0, iq_a=17.0, theta_e_deg=theta)
    assert currents.sum == pytest.approx(0.0, abs=1e-12)


def test_amplitude_invariance_with_id_zero():
    """For id = 0 the peak phase current is iq."""

    peaks = [
        abs(inverse_park_abc(id_a=0.0, iq_a=17.0, theta_e_deg=t).ia)
        for t in range(0, 360)
    ]
    assert max(peaks) == pytest.approx(17.0, rel=1e-3)


def test_zero_current_gives_zero_phases():
    currents = inverse_park_abc(id_a=0.0, iq_a=0.0, theta_e_deg=123.0)
    assert currents.as_dict() == {"A": 0.0, "B": 0.0, "C": 0.0}


def test_pure_d_axis_current_is_orthogonal_to_pure_q_axis_current():
    d = inverse_park_abc(id_a=10.0, iq_a=0.0, theta_e_deg=0.0)
    q = inverse_park_abc(id_a=0.0, iq_a=10.0, theta_e_deg=0.0)
    dot = d.ia * q.ia + d.ib * q.ib + d.ic * q.ic
    assert dot == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Topology and winding factors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slots,pole_pairs,span,expected",
    [
        (24, 8, 1, WindingTopology.FRACTIONAL_SLOT_CONCENTRATED),
        (12, 5, 1, WindingTopology.FRACTIONAL_SLOT_CONCENTRATED),
        (36, 2, 9, WindingTopology.INTEGER_SLOT_DISTRIBUTED),
        (24, 2, 6, WindingTopology.INTEGER_SLOT_DISTRIBUTED),
        (48, 4, 6, WindingTopology.INTEGER_SLOT_DISTRIBUTED),
    ],
)
def test_topology_classification(slots, pole_pairs, span, expected):
    assert classify_topology(
        slots=slots, pole_pairs=pole_pairs, coil_span_slots=span
    ) == expected


def test_topology_rejects_degenerate_counts():
    with pytest.raises(ValueError):
        classify_topology(slots=0, pole_pairs=4, coil_span_slots=1)


def test_q_is_slots_over_poles_times_phases():
    report = build_winding_report(slots=24, pole_pairs=8, coil_span_slots=1)
    assert report.slots_per_pole_per_phase == pytest.approx(24 / (16 * 3))
    assert report.pole_count == 16


def test_a_full_pitch_integer_slot_winding_has_unit_pitch_factor():
    report = build_winding_report(slots=36, pole_pairs=2, coil_span_slots=9)
    assert report.pitch_factor == pytest.approx(1.0, rel=1e-9)
    assert report.topology == WindingTopology.INTEGER_SLOT_DISTRIBUTED


def test_a_short_pitch_winding_has_a_pitch_factor_below_one():
    full = build_winding_report(slots=36, pole_pairs=2, coil_span_slots=9)
    short = build_winding_report(slots=36, pole_pairs=2, coil_span_slots=7)
    assert short.pitch_factor < full.pitch_factor


def test_skew_reduces_the_winding_factor():
    straight = build_winding_report(slots=24, pole_pairs=8, coil_span_slots=1, skew_slots=0.0)
    skewed = build_winding_report(slots=24, pole_pairs=8, coil_span_slots=1, skew_slots=1.0)
    assert skewed.skew_factor < straight.skew_factor
    assert skewed.factors.ideal_slot_star < straight.factors.ideal_slot_star


def test_the_reference_winding_factors():
    report = build_winding_report(slots=24, pole_pairs=8, coil_span_slots=1)
    assert report.distribution_factor == pytest.approx(1.0)
    assert report.pitch_factor == pytest.approx(math.sqrt(3.0) / 2.0)
    assert report.skew_factor == pytest.approx(1.0)
    assert report.factors.ideal_slot_star == pytest.approx(math.sqrt(3.0) / 2.0)


def test_the_three_winding_factors_are_never_collapsed():
    case = _case()
    meshed = meshed_winding_factor_for_case(case).value
    report = build_winding_report(
        slots=24, pole_pairs=8, coil_span_slots=1,
        entered_winding_factor=0.93, meshed_winding_factor=meshed,
    )
    factors = report.factors
    assert factors.entered == pytest.approx(0.93)
    assert factors.ideal_slot_star == pytest.approx(math.sqrt(3.0) / 2.0)
    assert factors.meshed_geometry == pytest.approx(meshed)
    # Three genuinely different numbers.
    assert len({round(v, 6) for v in (factors.entered, factors.ideal_slot_star, factors.meshed_geometry)}) == 3
    assert factors.entered_matches_geometry is False
    assert report.notes_zh, "a mismatch must be explained, not left silent"


def test_a_manual_factor_matching_the_geometry_raises_no_note():
    case = _case()
    meshed = meshed_winding_factor_for_case(case).value
    report = build_winding_report(
        slots=24, pole_pairs=8, coil_span_slots=1,
        entered_winding_factor=meshed, meshed_winding_factor=meshed,
    )
    assert report.factors.entered_matches_geometry is True


def test_an_unbalanced_combination_is_reported_not_crashed():
    report = build_winding_report(slots=5, pole_pairs=8, coil_span_slots=1)
    assert report.factors.ideal_slot_star is None
    assert report.notes_zh


# ---------------------------------------------------------------------------
# Slot geometry and conductors
# ---------------------------------------------------------------------------


def _geometry(**overrides) -> SlotGeometry:
    kwargs = dict(
        slot_count=24, top_width_mm=8.0, bottom_width_mm=6.0, depth_mm=15.0,
        wedge_height_mm=2.0, liner_thickness_mm=0.25, clearance_mm=0.10,
    )
    kwargs.update(overrides)
    return SlotGeometry(**kwargs)


def test_gross_slot_area_is_the_trapezoid():
    assert _geometry().gross_area_mm2 == pytest.approx((8.0 + 6.0) / 2.0 * 15.0)


def test_usable_area_is_strictly_less_than_gross():
    geometry = _geometry()
    assert geometry.usable_area_mm2 < geometry.gross_area_mm2


def test_removing_every_allowance_makes_usable_equal_gross():
    geometry = _geometry(wedge_height_mm=0.0, liner_thickness_mm=0.0, clearance_mm=0.0)
    assert geometry.usable_area_mm2 == pytest.approx(geometry.gross_area_mm2)


def test_slot_geometry_rejects_nonpositive_and_negative_inputs():
    with pytest.raises(ValueError):
        _geometry(depth_mm=0.0)
    with pytest.raises(ValueError):
        _geometry(liner_thickness_mm=-1.0)


def test_bare_and_insulated_conductor_areas():
    conductor = ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.296)
    assert conductor.bare_area_mm2 == pytest.approx(math.pi * 0.6**2)
    assert conductor.envelope_area_mm2 == pytest.approx(math.pi * (1.296 / 2.0) ** 2)
    assert conductor.envelope_area_mm2 > conductor.bare_area_mm2


def test_parallel_strands_multiply_both_areas():
    single = ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.3)
    triple = ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.3, parallel_strands=3)
    assert triple.bare_area_mm2 == pytest.approx(3.0 * single.bare_area_mm2)
    assert triple.envelope_area_mm2 == pytest.approx(3.0 * single.envelope_area_mm2)


def test_insulated_smaller_than_bare_is_rejected():
    with pytest.raises(ValueError, match="cannot be smaller"):
        ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.0)


def test_a_missing_insulated_diameter_falls_back_and_says_so():
    result = compute_slot_fill(
        geometry=_geometry(),
        conductor=ConductorSpec(bare_diameter_mm=1.2),
        turns_per_coil=5.0, coil_sides_per_slot=2,
    )
    assert result.envelope_area_per_slot_mm2 == pytest.approx(
        result.bare_copper_area_per_slot_mm2
    )
    assert any("绝缘" in w for w in result.warnings)


def test_conductor_spec_rejects_degenerate_values():
    with pytest.raises(ValueError):
        ConductorSpec(bare_diameter_mm=0.0)
    with pytest.raises(ValueError):
        ConductorSpec(bare_diameter_mm=1.0, parallel_strands=0)


# ---------------------------------------------------------------------------
# Occupancy
# ---------------------------------------------------------------------------


def _fill(**overrides) -> SlotFillResult:
    kwargs = dict(
        geometry=_geometry(),
        conductor=ConductorSpec(bare_diameter_mm=1.2, insulated_diameter_mm=1.296, parallel_strands=3),
        turns_per_coil=5.25,
        coil_sides_per_slot=2,
    )
    kwargs.update(overrides)
    return compute_slot_fill(**kwargs)


def test_conductors_per_slot_counts_layers():
    single = _fill(coil_sides_per_slot=1)
    double = _fill(coil_sides_per_slot=2)
    assert double.conductors_per_slot == pytest.approx(2.0 * single.conductors_per_slot)
    assert double.bare_copper_area_per_slot_mm2 == pytest.approx(
        2.0 * single.bare_copper_area_per_slot_mm2
    )


def test_the_four_fill_ratios_use_four_different_denominators():
    result = _fill()
    # usable < gross, so usable-based ratios are larger.
    assert result.usable_copper_fill > result.gross_copper_fill
    assert result.usable_envelope_fill > result.gross_envelope_fill
    # envelope > copper, so envelope ratios are larger than copper ratios.
    assert result.gross_envelope_fill > result.gross_copper_fill
    assert result.usable_envelope_fill > result.usable_copper_fill


def test_the_denominators_are_exactly_what_they_claim():
    result = _fill()
    assert result.gross_copper_fill == pytest.approx(
        result.bare_copper_area_per_slot_mm2 / result.gross_slot_area_mm2
    )
    assert result.usable_copper_fill == pytest.approx(
        result.bare_copper_area_per_slot_mm2 / result.usable_slot_area_mm2
    )
    assert result.gross_envelope_fill == pytest.approx(
        result.envelope_area_per_slot_mm2 / result.gross_slot_area_mm2
    )
    assert result.usable_envelope_fill == pytest.approx(
        result.envelope_area_per_slot_mm2 / result.usable_slot_area_mm2
    )


def test_the_packing_factor_is_labelled_an_engineering_assumption():
    result = _fill()
    assert result.packing_factor == pytest.approx(DEFAULT_PACKING_FACTOR)
    assert result.packing_factor_provenance == Provenance.ENGINEERING_ASSUMPTION
    assert result.status_provenance == Provenance.ENGINEERING_ASSUMPTION


def test_an_overfilled_slot_is_reported_not_clipped():
    result = _fill(turns_per_coil=40.0)
    assert result.status == ManufacturabilityStatus.OVERFILLED
    assert result.usable_envelope_fill > 1.0
    # The number is reported as computed; nothing is clamped to look achievable.
    assert result.envelope_area_per_slot_mm2 > result.usable_slot_area_mm2
    assert any("超过" in w for w in result.warnings)


def test_status_bands_move_with_occupancy():
    statuses = [
        _fill(turns_per_coil=turns).status
        for turns in (2.0, 6.0, 9.0, 40.0)
    ]
    assert statuses[0] == ManufacturabilityStatus.COMFORTABLE
    assert ManufacturabilityStatus.OVERFILLED in statuses
    # and the sequence never improves as turns increase.
    order = {
        ManufacturabilityStatus.COMFORTABLE: 0,
        ManufacturabilityStatus.FEASIBLE: 1,
        ManufacturabilityStatus.TIGHT: 2,
        ManufacturabilityStatus.OVERFILLED: 3,
    }
    ranks = [order[s] for s in statuses]
    assert ranks == sorted(ranks)


def test_a_slot_with_no_usable_area_is_refused_with_a_reason():
    result = _fill(geometry=_geometry(liner_thickness_mm=6.0, clearance_mm=2.0))
    assert result.status == ManufacturabilityStatus.NOT_CALCULABLE
    assert result.usable_envelope_fill is None
    assert not result.is_calculable
    assert result.warnings


def test_non_integer_turns_are_flagged():
    assert any("非整数" in w for w in _fill(turns_per_coil=5.25).warnings)
    assert not any("非整数" in w for w in _fill(turns_per_coil=5.0).warnings)


def test_compute_slot_fill_rejects_impossible_arguments():
    with pytest.raises(ValueError):
        _fill(coil_sides_per_slot=0)
    with pytest.raises(ValueError):
        _fill(turns_per_coil=0.0)
    with pytest.raises(ValueError):
        _fill(packing_factor=0.0)
    with pytest.raises(ValueError):
        _fill(packing_factor=1.5)


def test_the_calculation_is_available_even_when_the_verdict_is_bad():
    """The number must survive a recommendation the user may disagree with."""

    result = _fill(turns_per_coil=9.0)
    assert result.status in {
        ManufacturabilityStatus.TIGHT, ManufacturabilityStatus.OVERFILLED
    }
    assert result.usable_envelope_fill is not None
    assert result.bare_copper_area_per_slot_mm2 > 0.0


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


def test_every_panel_row_carries_provenance():
    report = build_winding_report(
        slots=24, pole_pairs=8, coil_span_slots=1,
        entered_winding_factor=0.93, meshed_winding_factor=0.9557520074850538,
        finite_width_factor=0.9881902167882565,
    )
    sections = build_winding_panel_rows(
        report=report, fill=_fill(),
        axes=electrical_axes_for_case(_case(), rotor_angle_mech_deg=0.0),
    )
    rows = [row for _title, section in sections for row in section]
    assert rows
    for row in rows:
        assert row.provenance is not None, row.label_zh


def test_the_panel_renders_and_names_its_denominators():
    report = build_winding_report(slots=24, pole_pairs=8, coil_span_slots=1)
    rendered = render_winding_panel_zh(
        build_winding_panel_rows(report=report, fill=_fill())
    )
    assert "分母：槽毛面积" in rendered
    assert "分母：可用槽面积" in rendered
    assert "工程假设" in rendered


def test_an_empty_panel_says_so_rather_than_rendering_nothing():
    assert "不足以计算" in render_winding_panel_zh(())


# ---------------------------------------------------------------------------
# Bridge integration and protected physics
# ---------------------------------------------------------------------------


def test_the_bridge_no_longer_needs_a_hard_coded_offset():
    payload = json.loads((EVIDENCE / "phase10g_torque_recheck.json").read_text(encoding="utf-8"))
    assert payload["hard_coded_offset_used"] is False
    assert payload["positive_iq_gives_positive_torque"] is True
    assert payload["calibration_performed"] is False
    # and it reproduces the Phase 10F result obtained WITH the hard-coded value.
    assert payload["residual_percent"] == pytest.approx(7.02, abs=0.05)


def test_the_no_load_scripts_are_unchanged_by_the_alignment_fix():
    import tempfile

    from motor_calculator.fea.adapter import generate_case_scripts

    case = _case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    workspace = Path(tempfile.mkdtemp())
    texts = [
        Path(path).read_text(encoding="utf-8")
        for path in generate_case_scripts(case, workspace)
    ]
    normalised = [
        text.replace(str(workspace).replace("\\", "/"), "<WORKSPACE>").replace(
            case.case_id, "<CASE_ID>"
        )
        for text in texts
    ]
    assert hashlib.sha256("".join(normalised).encode()).hexdigest() == (
        "8fbb95e97f092f59c0384b2a34864b5c8f7e02e2251489352d76a466d9cb96e9"
    )


def test_production_physics_is_untouched_by_phase10g():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_phase10g_did_not_mutate_any_production_default():
    from motor_calculator.fea.reference_cases import PHASE10A_REFERENCE_PARAMETERS

    assert PHASE10A_REFERENCE_PARAMETERS["k_w"] == 0.93
    assert PHASE10A_REFERENCE_PARAMETERS["fill_limit"] == 0.65
    assert PHASE10A_REFERENCE_PARAMETERS["d_wire"] == 0.9


def test_the_winding_package_never_writes_into_the_analytical_kernel():
    package = REPOSITORY_ROOT / "motor_calculator" / "winding"
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("curve_fit", "least_squares", "polyfit", "calibrat"):
            assert forbidden not in source.lower(), f"{path.name} must not contain {forbidden}"


def test_the_packaged_build_declares_the_lazily_imported_winding_dialog():
    """The menu entry imports it lazily; without the hidden import the packaged
    build would open onto an ImportError."""

    spec = (REPOSITORY_ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    for module in (
        "motor_calculator.gui.winding_dialog",
        "motor_calculator.winding.electrical_axis",
        "motor_calculator.winding.slot_fill",
        "motor_calculator.winding.report",
        "motor_calculator.winding.panel_text",
    ):
        assert module in spec, module
