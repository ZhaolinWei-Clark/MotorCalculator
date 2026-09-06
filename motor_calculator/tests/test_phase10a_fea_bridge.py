"""Phase 10A: FEMM validation bridge.

These tests lock the behaviour that makes the bridge trustworthy rather than
merely present: that it refuses to invent geometry, that mock data can never
become evidence, that no FEA result can move an analytical parameter, and that
the mapping from the analytical model to the solved geometry is the one the
analytical equations actually describe.
"""

from __future__ import annotations

import json
import math
from math import gcd
from pathlib import Path

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.fea import (
    AUTO_CALIBRATION_ENABLED,
    FEAComparisonStatus,
    FEACoreModelPolicy,
    FEAMeshPolicy,
    FEAPositionSample,
    FEASupportability,
    FEAValidationTarget,
    MockFEASolver,
    assess_supportability,
    build_comparison,
    build_evidence_record,
    build_slice_model,
    build_validation_case,
    case_from_dict,
    case_to_dict,
    compare_metric,
    compute_analytical_fingerprint,
    compute_case_hash,
    derive_symmetry_plan,
    detect_femm,
    export_bundle,
    extract_back_emf,
    extract_cogging,
    generate_case_scripts,
    numerical_confidence_statement,
    plan_angle_sampling,
    plot_series,
    render_case_review_zh,
    render_run_zh,
    run_validation,
)
from motor_calculator.fea.availability import FEMMAvailability, FEMMIntegrationPath
from motor_calculator.fea.case_builder import FEAModellingParameters
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_ID,
    PHASE10A_REFERENCE_TARGETS,
    build_reference_case,
)
from motor_calculator.fea.results import FEARawResult
from motor_calculator.fea.view_model import FEAValidationViewModel
from motor_calculator.fea.winding import allocate_all_phases, slot_belt_index
from motor_calculator.motor_core.constants import MU0
from motor_calculator.motor_core.winding_factor import build_slot_star
from motor_calculator.validation.fea_reference import EvidenceClassification

REFERENCE_JSON = (
    Path(__file__).resolve().parents[2]
    / "validation_data"
    / "fea_cases"
    / "phase10a_coreless_ssdr_reference_v1.json"
)

MODELLING = FEAModellingParameters(
    rotor_back_iron_thickness_m=0.006,
    coil_span_slots=1,
    provenance="declared FEA-only modelling parameters for this test",
)


def _design(**overrides):
    bridge = LegacyGuiMotorModelBridge(
        parse_legacy_gui_params(build_sample_legacy_params(**overrides))
    )
    analysis = bridge.run_full_analysis()
    return bridge.input_data, analysis


def _case(target=FEAValidationTarget.NO_LOAD_BACK_EMF, modelling=MODELLING, **overrides):
    inputs, analysis = _design(**overrides)
    return build_validation_case(inputs, analysis, target=target, modelling=modelling)


# ---------------------------------------------------------------------------
# 1. FEMM availability detection
# ---------------------------------------------------------------------------


def test_availability_probe_reports_exactly_one_verdict_and_where_it_looked():
    report = detect_femm()
    assert report.availability in (
        FEMMAvailability.FEMM_AVAILABLE,
        FEMMAvailability.FEMM_NOT_INSTALLED,
    )
    # The probe must be auditable: it says where it looked, not just what it found.
    assert report.searched_locations
    assert any(entry.startswith("PATH:") for entry in report.searched_locations)
    assert report.is_available is (report.availability is FEMMAvailability.FEMM_AVAILABLE)
    assert report.execution_blocked is not report.is_available


def test_availability_honours_an_explicit_override_only_when_the_file_exists(tmp_path):
    # An override naming a file that does not exist is ignored: the probe falls
    # through to its normal search rather than pointing the adapter at nothing.
    # (It may then legitimately find a real installation, so the verdict itself
    # is not what this asserts.)
    bogus = tmp_path / "nope.exe"
    missing = detect_femm(environment_override=str(bogus))
    assert missing.executable_path != bogus.resolve()

    fake = tmp_path / "femm.exe"
    fake.write_bytes(b"")
    found = detect_femm(environment_override=str(fake))
    assert found.availability is FEMMAvailability.FEMM_AVAILABLE
    assert found.integration_path is FEMMIntegrationPath.SUBPROCESS_LUA
    assert found.executable_path == fake.resolve()


def test_importing_the_bridge_never_requires_a_solver():
    """A packaged build must start on a machine with no FEA software at all."""

    import importlib

    for name in (
        "motor_calculator.fea",
        "motor_calculator.fea.adapter",
        "motor_calculator.fea.femm_lua",
        "motor_calculator.fea.view_model",
    ):
        assert importlib.import_module(name) is not None


# ---------------------------------------------------------------------------
# 2/3. Case serialization and hash determinism
# ---------------------------------------------------------------------------


def test_case_serialization_round_trips_and_revalidates():
    case = _case()
    restored = case_from_dict(case_to_dict(case))
    assert restored.case_id == case.case_id
    assert compute_case_hash(restored) == case.case_id
    assert restored.winding.coil_phase_assignment == case.winding.coil_phase_assignment


def test_case_hash_is_deterministic_across_rebuilds():
    assert _case().case_id == _case().case_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"h_mag": 6.0},            # geometry
        {"Br": 1.30},              # material
        {"N_ph_turns": 60},        # winding
        {"n_rated": 2600.0},       # operating point
    ],
)
def test_changing_the_solved_machine_changes_the_case_hash(overrides):
    assert _case(**overrides).case_id != _case().case_id


def test_changing_the_mesh_policy_changes_the_case_hash():
    case = _case()
    from dataclasses import replace

    coarser = replace(
        case,
        mesh_policy=FEAMeshPolicy(
            **{
                **{
                    field: getattr(case.mesh_policy, field)
                    for field in case.mesh_policy.__dataclass_fields__
                },
                "air_gap_size_m": case.mesh_policy.air_gap_size_m * 2.0,
            }
        ),
    )
    assert compute_case_hash(coarser) != case.case_id


def test_analytical_fingerprint_is_separate_from_the_case_hash():
    """A changed analytical model must invalidate the comparison, not the solve."""

    case = _case()
    from dataclasses import replace

    moved = replace(
        case,
        analytical=replace(case.analytical, back_emf_phase_rms_v=case.analytical.back_emf_phase_rms_v * 1.01),
    )
    assert compute_case_hash(moved) == case.case_id
    assert compute_analytical_fingerprint(moved) != compute_analytical_fingerprint(case)


# ---------------------------------------------------------------------------
# 4. Geometry mapping
# ---------------------------------------------------------------------------


def test_unrolled_slice_reproduces_the_analytical_pole_area_exactly():
    """The slice is the analytical model's own geometry, not a new assumption.

    ``(pi/2p)(Ro^2 - Ri^2) * alpha_p`` must equal ``tau_p * L_r * alpha_p``.
    """

    inputs, _analysis = _design()
    case = _case()
    geometry = case.geometry

    analytical_pole_area = (
        (math.pi / (2.0 * inputs.pole_pairs))
        * ((inputs.outer_diameter_m / 2.0) ** 2 - (inputs.inner_diameter_m / 2.0) ** 2)
        * inputs.pole_arc_coefficient
    )
    slice_pole_area = (
        geometry.pole_pitch_m
        * geometry.radial_active_length_m
        * geometry.pole_arc_coefficient
    )
    assert slice_pole_area == pytest.approx(analytical_pole_area, rel=1e-15)


def test_slice_magnetic_gap_equals_the_analytical_effective_gap():
    inputs, _analysis = _design()
    case = _case()
    assert case.geometry.magnetic_gap_between_magnet_faces_m == pytest.approx(
        inputs.coil_height_m + 2.0 * inputs.air_gap_per_side_m, rel=1e-15
    )


def test_slice_regions_cover_every_magnet_pole_and_both_rotors():
    case = _case()
    model = _model(case)
    magnets = model.regions_with_role("magnet")
    total_magnet_area = sum(region.area_m2 for region in magnets)
    expected = (
        2  # two rotors
        * 2 * case.geometry.pole_pairs
        * case.geometry.magnet_arc_length_m
        * case.geometry.magnet_thickness_m
    )
    assert total_magnet_area == pytest.approx(expected, rel=1e-9)
    assert len(model.regions_with_role("back_iron")) == 2


def _model(case, rotor_angle_mech_deg: float = 0.0):
    from motor_calculator.fea.adapter import _mesh_size_map

    return build_slice_model(
        case.geometry,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=rotor_angle_mech_deg,
    )


def test_a_magnet_straddling_the_periodic_seam_keeps_its_full_area():
    """Rotation must not shrink or displace a magnet at the x = 0 seam."""

    case = _case()
    aligned = _model(case, rotor_angle_mech_deg=0.0)
    rotated = _model(case, rotor_angle_mech_deg=1.234)
    aligned_area = sum(r.area_m2 for r in aligned.regions_with_role("magnet"))
    rotated_area = sum(r.area_m2 for r in rotated.regions_with_role("magnet"))
    assert rotated_area == pytest.approx(aligned_area, rel=1e-9)
    span = rotated.modelled_span_m
    for region in rotated.regions_with_role("magnet"):
        for x, _y in region.polygon_m:
            assert -1e-12 <= x <= span + 1e-12


# ---------------------------------------------------------------------------
# 5/6. Material mapping and magnet polarity
# ---------------------------------------------------------------------------


def test_magnet_coercivity_follows_from_br_and_mu_r():
    inputs, _analysis = _design()
    materials = _case().materials
    assert materials.magnet_coercivity_a_per_m == pytest.approx(
        inputs.remanence_t / (MU0 * inputs.magnet_relative_permeability), rel=1e-15
    )


def test_a_coreless_case_declares_no_stator_core_material_or_bh_curve():
    materials = _case().materials
    assert materials.core_model_policy is FEACoreModelPolicy.NOT_APPLICABLE_CORELESS
    assert materials.core_relative_permeability is None
    assert materials.core_library_material_name is None


def test_material_mismatches_are_reported_rather_than_invented():
    materials = _case().materials
    joined = " ".join(materials.property_mismatches)
    assert "no iron reluctance" in joined
    assert "leakage_factor" in joined
    assert "Carter factor" in joined


def test_magnet_polarity_alternates_and_both_rotors_face_the_same_way():
    """The analytical MMF is two magnets in series, so a pole's magnets align."""

    case = _case()
    model = _model(case)
    by_pole: dict[str, list[float]] = {}
    for region in model.regions_with_role("magnet"):
        _prefix, side, pole, _piece = region.name.split("_")
        by_pole.setdefault(pole, []).append(region.magnetization_direction_deg)
    for directions in by_pole.values():
        # Every magnet of a pole, upper rotor and lower rotor, points the same way.
        assert len(set(directions)) == 1
    poles = sorted(by_pole)
    assert by_pole[poles[0]][0] != by_pole[poles[1]][0]


# ---------------------------------------------------------------------------
# 7. Winding phase assignment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slots,pole_pairs", [(24, 8), (24, 2), (36, 3), (12, 5), (48, 10), (9, 4)]
)
def test_all_phase_allocation_agrees_with_the_analytical_slot_star(slots, pole_pairs):
    """The FEA map extends the analytical star; it must not contradict it."""

    star = build_slot_star(slots, pole_pairs)
    if not star.balanced:
        pytest.skip("unbalanced winding is refused by both layers")
    labels, signs = allocate_all_phases(slots, pole_pairs)
    replayed = tuple(
        (index, sign)
        for index, (label, sign) in enumerate(zip(labels, signs))
        if label == "A"
    )
    assert tuple(index for index, _sign in replayed) == star.phase_a_slots
    assert tuple(sign for _index, sign in replayed) == star.phase_a_signs


def test_belt_allocation_uses_exact_integer_arithmetic_at_the_boundary():
    """Q=24, 2p=4 lands phasors exactly on a belt edge; floats unbalance it."""

    labels, _signs = allocate_all_phases(24, 2)
    counts = {name: labels.count(name) for name in set(labels)}
    assert counts == {"A": 8, "B": 8, "C": 8}
    assert slot_belt_index(0, 24, 2, 3) == 0


def test_every_phase_carries_zero_net_in_plane_current():
    """A one-layer-per-slot model would fail this for q = 0.5 windings."""

    case = _case()
    assert case.winding.coil_span_slots == 1
    for phase, net in case.winding.net_signed_turns_per_phase().items():
        assert net == pytest.approx(0.0, abs=1e-12), phase

    model = _model(case)
    totals: dict[str, float] = {}
    for region in model.regions_with_role("winding"):
        totals[region.circuit_name] = totals.get(region.circuit_name, 0.0) + region.signed_turns
    assert set(totals) == {"A", "B", "C"}
    for phase, total in totals.items():
        assert total == pytest.approx(0.0, abs=1e-12), phase


def test_series_turns_per_phase_are_preserved_by_the_coil_mapping():
    inputs, _analysis = _design()
    winding = _case().winding
    coils_per_phase = winding.slot_count // winding.phases
    assert winding.turns_per_coil * coils_per_phase == pytest.approx(
        float(inputs.turns_per_phase), rel=1e-15
    )


def test_an_unbalanced_slot_pole_combination_is_refused():
    """Q = 12, 2p = 6 puts every phase-A coil side in one belt with none left
    for the other phases, so no balanced circuit assignment exists."""

    inputs, analysis = _design(slots=12, p=3)
    with pytest.raises(ValueError, match="balanced"):
        build_validation_case(
            inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF, modelling=MODELLING
        )


def test_a_slot_count_not_divisible_by_three_is_refused_before_any_mapping():
    inputs, _analysis = _design(slots=20, p=8)
    report = assess_supportability(inputs, modelling=MODELLING)
    assert report.state is FEASupportability.UNSUPPORTED
    assert any("not divisible by the three phases" in r for r in report.blocking_reasons)


# ---------------------------------------------------------------------------
# 8/9/10/11. Operating point, units and semantics
# ---------------------------------------------------------------------------


def test_no_load_targets_carry_exactly_zero_current():
    for target in (FEAValidationTarget.NO_LOAD_BACK_EMF, FEAValidationTarget.COGGING_TORQUE):
        assert _case(target).operating_point.phase_current_rms_a == 0.0


def test_the_torque_case_uses_the_analytical_phase_current_at_id_zero():
    inputs, analysis = _design()
    case = build_validation_case(
        inputs, analysis, target=FEAValidationTarget.AVERAGE_TORQUE, modelling=MODELLING
    )
    assert case.operating_point.phase_current_rms_a == pytest.approx(
        analysis.performance.phase_current_rms_a, rel=1e-15
    )
    assert case.operating_point.current_angle_electrical_deg == 90.0


def test_units_and_bases_are_declared_explicitly():
    case = _case()
    assert case.units["current"] == "ampere_rms_per_phase"
    assert case.units["angle"] == "mechanical_degree"
    assert case.units["length"] == "meter"
    assert "phase RMS" in case.analytical.basis_notes["back_emf"]
    assert "electrical angle is p times mechanical" in case.analytical.basis_notes["angle"]


def test_rotor_angles_are_uniform_and_exclude_the_duplicate_endpoint():
    point = _case().operating_point
    angles = point.rotor_angles_mech_deg()
    assert len(angles) == point.rotor_angle_sample_count
    assert angles[0] == point.rotor_angle_start_mech_deg
    assert angles[-1] < point.rotor_angle_start_mech_deg + point.rotor_angle_span_mech_deg
    steps = {round(b - a, 12) for a, b in zip(angles, angles[1:])}
    assert len(steps) == 1


def test_back_emf_extraction_uses_mechanical_speed_and_phase_rms():
    """A known sinusoidal flux linkage must give back exactly omega*lambda/sqrt(2)."""

    case = _case()
    peak = 0.01
    speed_rpm = case.operating_point.mechanical_speed_rpm
    angles = case.operating_point.rotor_angles_mech_deg()
    samples = tuple(
        FEAPositionSample(
            rotor_angle_mech_deg=angle,
            phase_flux_linkage_wb_turn={
                "A": peak * math.cos(math.radians(case.geometry.pole_pairs * angle))
            },
            circumferential_force_n=0.0,
        )
        for angle in angles
    )
    from motor_calculator.fea.adapter import build_provenance

    result = FEARawResult(
        target=case.target,
        provenance=build_provenance(
            case, solver="MOCK_FEA_SOLVER", solver_version="t", is_mock=True,
            element_count=None, solve_seconds=0.0,
        ),
        samples=samples,
        mechanical_speed_rpm=speed_rpm,
        mean_radius_m=case.geometry.mean_radius_m,
        pole_pairs=case.geometry.pole_pairs,
        span_mech_deg=case.operating_point.rotor_angle_span_mech_deg,
    )
    extraction = extract_back_emf(result)
    omega_mech = speed_rpm * 2.0 * math.pi / 60.0
    omega_elec = omega_mech * case.geometry.pole_pairs
    assert extraction.phase_peak_v == pytest.approx(omega_elec * peak, rel=1e-9)
    assert extraction.phase_rms_v == pytest.approx(omega_elec * peak / math.sqrt(2.0), rel=1e-9)
    assert extraction.line_rms_v == pytest.approx(
        math.sqrt(3.0) * extraction.phase_rms_v, rel=1e-9
    )
    assert "magnetostatic" in extraction.speed_scaling_note


# ---------------------------------------------------------------------------
# 12. Angle sampling and aliasing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slots,pole_pairs", [(24, 8), (36, 3), (12, 5), (48, 10), (24, 2)])
def test_cogging_span_is_exactly_one_cogging_period(slots, pole_pairs):
    plan = plan_angle_sampling(
        target=FEAValidationTarget.COGGING_TORQUE, slot_count=slots, pole_pairs=pole_pairs
    )
    pole_count = 2 * pole_pairs
    lcm = slots * pole_count // gcd(slots, pole_count)
    assert plan.span_mech_deg == pytest.approx(360.0 / lcm, rel=1e-15)


def test_back_emf_span_is_one_electrical_period():
    plan = plan_angle_sampling(
        target=FEAValidationTarget.NO_LOAD_BACK_EMF, slot_count=24, pole_pairs=8
    )
    assert plan.span_mech_deg == pytest.approx(45.0, rel=1e-15)


@pytest.mark.parametrize("slots,pole_pairs", [(24, 8), (36, 3), (48, 10), (36, 6)])
def test_sampling_is_coprime_with_the_slot_passing_count(slots, pole_pairs):
    """The Phase 9B aliasing lesson: a shared factor collapses the waveform."""

    plan = plan_angle_sampling(
        target=FEAValidationTarget.NO_LOAD_BACK_EMF, slot_count=slots, pole_pairs=pole_pairs
    )
    events = max(1, round(slots / pole_pairs))
    if events > 1:
        assert gcd(plan.sample_count, events) == 1
    assert plan.sample_count >= 24


def test_sampling_resolves_the_slot_passing_harmonic():
    plan = plan_angle_sampling(
        target=FEAValidationTarget.NO_LOAD_BACK_EMF, slot_count=72, pole_pairs=4
    )
    assert plan.highest_resolved_harmonic >= plan.slot_passing_harmonic


def test_an_unbounded_sample_count_is_refused_rather_than_queued():
    with pytest.raises(ValueError, match="ceiling"):
        plan_angle_sampling(
            target=FEAValidationTarget.NO_LOAD_BACK_EMF, slot_count=600, pole_pairs=1
        )


# ---------------------------------------------------------------------------
# 13. Mesh policy
# ---------------------------------------------------------------------------


def test_the_air_gap_is_meshed_more_finely_than_the_bulk_and_the_far_field_is_coarser():
    policy = _case().mesh_policy
    assert policy.air_gap_size_m < policy.global_size_m
    assert policy.air_domain_size_m > policy.global_size_m
    assert policy.magnet_edge_size_m < policy.magnet_size_m


def test_a_single_mesh_never_claims_convergence():
    assert _case().mesh_policy.convergence_claim == "NO_CONVERGENCE_CLAIM_SINGLE_MESH"
    with pytest.raises(ValueError, match="must not assert convergence"):
        FEAMeshPolicy(
            name="bad", global_size_m=1e-3, air_gap_size_m=1e-4, magnet_size_m=1e-3,
            magnet_edge_size_m=5e-4, slot_opening_size_m=None, winding_size_m=1e-3,
            core_size_m=None, air_domain_size_m=1e-2, minimum_angle_deg=30.0,
            convergence_claim="CONVERGED",
        )


# ---------------------------------------------------------------------------
# 14/15. Supportability and missing geometry
# ---------------------------------------------------------------------------


def test_missing_fea_only_parameters_report_not_enough_geometry_rather_than_a_default():
    inputs, _analysis = _design()
    report = assess_supportability(inputs, modelling=None)
    assert report.state is FEASupportability.NOT_ENOUGH_GEOMETRY
    assert any("rotor back-iron" in reason for reason in report.blocking_reasons)
    assert any("coil span" in reason for reason in report.blocking_reasons)


def test_a_case_cannot_be_built_without_the_declared_parameters():
    inputs, analysis = _design()
    with pytest.raises(ValueError, match="cannot be mapped"):
        build_validation_case(
            inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF, modelling=None
        )


def test_the_coreless_machine_is_supported_and_the_cored_machine_is_only_partial():
    coreless, _ = _design(coreless=True)
    cored, _ = _design(coreless=False, slot_type="半闭口槽")
    assert assess_supportability(coreless, modelling=MODELLING).state is FEASupportability.SUPPORTED
    cored_report = assess_supportability(cored, modelling=MODELLING)
    assert cored_report.state is FEASupportability.PARTIALLY_SUPPORTED
    joined = " ".join(cored_report.approximation_labels)
    assert "CORED_AFPM_MAGNET_ARRANGEMENT_NOT_DECLARED_IN_SCHEMA" in joined
    assert "ANALYTICAL_GAP_INCLUDES_COIL_HEIGHT_EVEN_WHEN_CORED" in joined


def test_a_two_dimensional_slice_never_claims_a_higher_fidelity_tier():
    case = _case()
    assert case.supportability.fidelity_tier == "FEA_TIER_3"
    assert "MEAN_RADIUS_UNROLLED_2D_SLICE" in case.supportability.approximation_labels
    assert case.geometry.omitted_three_dimensional_effects


def test_symmetry_is_derived_from_slots_and_poles_and_defaults_to_the_full_bore():
    plan = derive_symmetry_plan(
        slot_count=24, pole_count=16, target=FEAValidationTarget.COGGING_TORQUE
    )
    assert plan.machine_periodicity == gcd(24, 16) == 8
    assert plan.slots_in_sector == 3
    assert plan.poles_in_sector == 2
    assert plan.applied is False
    assert plan.boundary_kind == "NONE_FULL_CIRCUMFERENCE"


def test_symmetry_cannot_be_applied_when_the_machine_does_not_repeat():
    with pytest.raises(ValueError):
        derive_symmetry_plan(
            slot_count=9, pole_count=8, target=FEAValidationTarget.COGGING_TORQUE,
            apply_symmetry=True,
        )


# ---------------------------------------------------------------------------
# 16. Mock solver pipeline
# ---------------------------------------------------------------------------


def test_the_mock_solver_stamps_itself_and_can_never_be_evidence():
    case = _case()
    outcome = MockFEASolver().solve(case)
    assert outcome.result is not None
    assert outcome.result.is_mock is True
    assert "MOCK" in outcome.result.provenance.solver
    report = build_comparison(case, outcome.result)
    assert report.is_mock is True
    assert report.evidence_admissible is False
    record = build_evidence_record(
        report, solver="MOCK_FEA_SOLVER", solver_version="mock-1", timestamp_utc="now"
    )
    assert record.admissible is False
    assert any("mock" in reason for reason in record.inadmissible_reasons)


def test_a_result_cannot_lie_about_being_mock():
    case = _case()
    from motor_calculator.fea.adapter import build_provenance

    with pytest.raises(ValueError, match="mock"):
        build_provenance(
            case, solver="FEMM", solver_version="4.2", is_mock=True,
            element_count=None, solve_seconds=1.0,
        )
    with pytest.raises(ValueError, match="mock"):
        build_provenance(
            case, solver="MOCK_FEA_SOLVER", solver_version="1", is_mock=False,
            element_count=None, solve_seconds=1.0,
        )


# ---------------------------------------------------------------------------
# 17. Solver script generation and parsing
# ---------------------------------------------------------------------------


def test_solver_scripts_are_generated_without_any_solver_installed(tmp_path):
    case = _case()
    scripts = generate_case_scripts(case, tmp_path)
    assert len(scripts) == case.operating_point.rotor_angle_sample_count
    text = scripts[0].read_text(encoding="utf-8")
    assert "mi_probdef" in text and '"planar"' in text
    # One circuit per phase, and a block label for every region.
    assert text.count("mi_addcircprop") == 3
    assert text.count("mi_addblocklabel") == text.count("mi_setblockprop")
    # The circumferential ends are the same physical place: periodic, not A = 0.
    assert "periodic_000" in text
    assert "mo_getcircuitproperties" in text
    assert "mo_blockintegral(18)" in text
    assert case.case_id in text


def test_generated_scripts_encode_the_requested_rotor_angles(tmp_path):
    case = _case()
    scripts = generate_case_scripts(case, tmp_path)
    angles = case.operating_point.rotor_angles_mech_deg()
    for path, angle in zip(scripts, angles):
        assert f"-- rotor angle {angle} mechanical degrees" in path.read_text(encoding="utf-8")


def test_solver_output_parsing_rejects_missing_columns(tmp_path):
    from motor_calculator.fea.adapter import FEASolverExecutionError, parse_samples_csv

    path = tmp_path / "out.csv"
    path.write_text("rotor_angle_mech_deg,flux_linkage_A_wb_turn\n0,0.1\n", encoding="utf-8")
    with pytest.raises(FEASolverExecutionError, match="missing required columns"):
        parse_samples_csv(path, ("A",))


def test_solver_output_parsing_reads_a_well_formed_sweep(tmp_path):
    from motor_calculator.fea.adapter import parse_samples_csv

    path = tmp_path / "out.csv"
    path.write_text(
        "rotor_angle_mech_deg,flux_linkage_A_wb_turn,circumferential_force_n,element_count\n"
        "0.0,0.01,1.5,1200\n1.0,0.009,1.4,1200\n",
        encoding="utf-8",
    )
    samples = parse_samples_csv(path, ("A",))
    assert len(samples) == 2
    assert samples[0].phase_flux_linkage_wb_turn["A"] == pytest.approx(0.01)
    assert samples[1].circumferential_force_n == pytest.approx(1.4)
    assert samples[0].element_count == 1200


def test_the_subprocess_adapter_never_uses_a_shell():
    import inspect

    from motor_calculator.fea import adapter

    source = inspect.getsource(adapter.FEMMSubprocessSolver._run_script)
    assert "shell=False" in source
    assert "shell=True" not in source
    assert "timeout=" in source


def test_the_solver_workspace_is_outside_the_repository():
    from motor_calculator.fea.adapter import default_workspace_root

    workspace = default_workspace_root()
    repository = Path(__file__).resolve().parents[2]
    assert repository not in workspace.parents
    assert workspace != repository


# ---------------------------------------------------------------------------
# 18/19. Comparison metrics and zero denominators
# ---------------------------------------------------------------------------


def test_relative_error_is_computed_from_the_analytical_denominator():
    metric = compare_metric(
        quantity="q", unit="V", basis="phase RMS", analytical_value=10.0, fea_value=11.0
    )
    assert metric.absolute_error == pytest.approx(1.0)
    assert metric.relative_error_percent == pytest.approx(10.0)
    assert metric.status is FEAComparisonStatus.MODERATE_DEVIATION


@pytest.mark.parametrize(
    "fea,expected",
    [
        (10.2, FEAComparisonStatus.CLOSE_AGREEMENT),
        (11.5, FEAComparisonStatus.MODERATE_DEVIATION),
        (15.0, FEAComparisonStatus.LARGE_DEVIATION),
    ],
)
def test_bands_are_descriptive_and_labelled_provisional(fea, expected):
    metric = compare_metric(
        quantity="q", unit="V", basis="b", analytical_value=10.0, fea_value=fea
    )
    assert metric.status is expected
    assert "PROVISIONAL" in metric.band_statement
    assert "not a pass/fail criterion" in metric.band_statement


def test_a_zero_denominator_reports_no_relative_error():
    metric = compare_metric(
        quantity="cogging", unit="Nm", basis="peak", analytical_value=0.0, fea_value=0.004
    )
    assert metric.relative_error_percent is None
    assert metric.absolute_error == pytest.approx(0.004)
    assert metric.status is FEAComparisonStatus.NOT_COMPARABLE
    assert any("effectively zero" in note for note in metric.notes)


def test_a_zero_denominator_can_still_be_classified_against_a_reference_scale():
    metric = compare_metric(
        quantity="cogging", unit="Nm", basis="peak", analytical_value=0.0, fea_value=0.004,
        reference_scale_name="rated_torque", reference_scale_value=3.0,
    )
    assert metric.relative_error_percent is None
    assert metric.error_relative_to_reference_scale_percent == pytest.approx(0.004 / 3.0 * 100.0)
    assert metric.status is FEAComparisonStatus.CLOSE_AGREEMENT


def test_a_missing_side_reports_insufficient_data_not_a_number():
    metric = compare_metric(
        quantity="q", unit="V", basis="b", analytical_value=None, fea_value=1.0
    )
    assert metric.status is FEAComparisonStatus.INSUFFICIENT_DATA
    assert metric.relative_error_percent is None


def test_paired_sample_statistics():
    from motor_calculator.fea import sample_statistics

    stats = sample_statistics([1.0, 2.0, 3.0], [1.5, 2.5, 3.5], "Nm")
    assert stats.bias == pytest.approx(0.5)
    assert stats.mean_absolute_error == pytest.approx(0.5)
    assert stats.root_mean_square_error == pytest.approx(0.5)


def test_cogging_comparison_records_that_the_analytical_value_is_an_input_assumption():
    case = _case(FEAValidationTarget.COGGING_TORQUE)
    outcome = MockFEASolver().solve(case)
    report = build_comparison(case, outcome.result)
    joined = " ".join(note for metric in report.metrics for note in metric.notes)
    assert "ANALYTICAL_COGGING_IS_A_USER_SUPPLIED_RATIO" in joined
    assert "not from a field solution" in joined
    assert "tests the entered assumption, not a physics formula" in joined


def test_discrepancy_candidates_are_offered_as_candidates_not_causes():
    case = _case()
    report = build_comparison(case, MockFEASolver().solve(case).result)
    assert report.discrepancy_candidates
    assert any("lumped magnetic-circuit" in item for item in report.discrepancy_candidates)


# ---------------------------------------------------------------------------
# 20. Stale case detection
# ---------------------------------------------------------------------------


def test_a_result_from_a_different_machine_is_reported_stale():
    case = _case()
    other = _case(h_mag=6.0)
    result = MockFEASolver().solve(other).result
    from dataclasses import replace

    rebound = replace(result, target=case.target)
    report = build_comparison(case, rebound)
    assert report.stale is True
    assert any("different case hash" in reason for reason in report.stale_reasons)
    assert report.evidence_admissible is False


def test_a_changed_analytical_prediction_marks_only_the_comparison_stale():
    case = _case()
    result = MockFEASolver().solve(case).result
    from dataclasses import replace

    moved = replace(
        case,
        analytical=replace(
            case.analytical, back_emf_phase_rms_v=case.analytical.back_emf_phase_rms_v * 1.05
        ),
    )
    report = build_comparison(moved, result)
    assert report.stale is True
    assert any("analytical prediction has changed" in reason for reason in report.stale_reasons)
    assert not any("different case hash" in reason for reason in report.stale_reasons)


# ---------------------------------------------------------------------------
# 21/22. Evidence provenance and the FEA / experiment distinction
# ---------------------------------------------------------------------------


def test_every_result_carries_full_provenance():
    case = _case()
    provenance = MockFEASolver().solve(case).result.provenance
    for attribute in (
        "solver", "solver_version", "case_id", "analytical_fingerprint",
        "mesh_policy_name", "timestamp_utc", "extraction_method",
    ):
        assert getattr(provenance, attribute)
    assert provenance.sample_count == case.operating_point.rotor_angle_sample_count
    assert provenance.requested_mesh_sizes_m
    assert provenance.symmetry_applied is case.symmetry.applied


def test_fea_evidence_is_numerical_and_never_experimental():
    case = _case()
    report = build_comparison(case, MockFEASolver().solve(case).result)
    record = build_evidence_record(
        report, solver="MOCK_FEA_SOLVER", solver_version="1", timestamp_utc="now"
    )
    assert record.classification is EvidenceClassification.NUMERICAL_FEA
    assert record.classification is not EvidenceClassification.EXPERIMENTAL_MEASUREMENT
    assert record.supports_experimental_claim is False


def test_an_evidence_record_cannot_be_built_as_experimental_measurement():
    from motor_calculator.fea.evidence import FEAEvidenceRecord

    with pytest.raises(ValueError, match="never experimental"):
        FEAEvidenceRecord(
            schema_version="v", classification=EvidenceClassification.EXPERIMENTAL_MEASUREMENT,
            case_id="x", target="NO_LOAD_BACK_EMF", fidelity_tier="FEA_TIER_3",
            solver="FEMM", solver_version="4.2", timestamp_utc="now", admissible=True,
            inadmissible_reasons=(), worst_status=FEAComparisonStatus.CLOSE_AGREEMENT,
            metric_statuses=(), approximation_labels=(), confidence_policy="p",
            supports_experimental_claim=False,
        )


def test_one_agreeing_case_does_not_become_broad_confidence():
    assert "没有可采信" in numerical_confidence_statement(0)
    single = numerical_confidence_statement(1)
    assert "单点数值证据" in single
    assert "不替代实验验证" in single
    assert "HIGH" not in single


# ---------------------------------------------------------------------------
# 23. No auto-calibration
# ---------------------------------------------------------------------------


def test_auto_calibration_is_disabled_and_reported_as_disabled():
    case = _case()
    report = build_comparison(case, MockFEASolver().solve(case).result)
    assert AUTO_CALIBRATION_ENABLED is False
    assert report.auto_calibration_enabled is False


def test_no_fea_module_writes_back_into_the_analytical_kernel():
    """A grep-level guard: nothing in the bridge may import or mutate the kernel."""

    package = Path(__file__).resolve().parents[1] / "fea"
    for path in sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "MotorAnalysisEngine(" not in source or path.name == "reference_cases.py"
        # Nothing in the bridge may fit a residual or solve for a parameter.
        for forbidden in ("curve_fit", "least_squares", "minimize(", "polyfit"):
            assert forbidden not in source, f"{path.name} must not fit residuals"
        # Calibration may only be named where it is refused, exported as the
        # disabled constant, or described as proposal-only.
        for line in source.splitlines():
            lowered = line.lower()
            if "calibrat" not in lowered:
                continue
            assert any(
                marker in lowered
                for marker in (
                    "auto_calibration_enabled",
                    "not", "never", "false", "proposal", "no ", "#", '"',
                )
            ), f"{path.name}: {line}"


def test_running_a_validation_does_not_change_the_analytical_result():
    inputs, analysis = _design()
    before = (
        analysis.electrical.back_emf_phase_rms_v,
        analysis.performance.average_torque_nm,
        analysis.performance.cogging_torque_peak_nm,
        analysis.magnetic.pole_flux_wb,
    )
    run_validation(
        inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF,
        modelling=MODELLING, force_mock_solver=True,
    )
    after = (
        analysis.electrical.back_emf_phase_rms_v,
        analysis.performance.average_torque_nm,
        analysis.performance.cogging_torque_peak_nm,
        analysis.magnetic.pole_flux_wb,
    )
    assert before == after


# ---------------------------------------------------------------------------
# 24. GUI unavailable state
# ---------------------------------------------------------------------------


def _view_model(**overrides):
    inputs, analysis = _design(**overrides)
    return FEAValidationViewModel(inputs=inputs, analysis=analysis)


def test_the_view_model_blocks_the_run_button_when_no_solver_is_installed():
    model = _view_model()
    model.confirm_modelling_parameters(rotor_back_iron_thickness_m=0.006, coil_span_slots=1)
    if model.solver_available:
        pytest.skip("FEMM is installed on this machine")
    assert model.can_run_solver is False
    assert model.can_generate_case is True
    assert model.solver_message_zh == "未检测到 FEMM。当前可生成验证案例，但无法执行求解。"


def test_the_view_model_refuses_to_run_before_parameters_are_confirmed():
    model = _view_model()
    assert model.can_generate_case is False
    with pytest.raises(ValueError, match="modelling parameters"):
        model.run()


def test_a_blocked_run_shows_no_numbers_and_no_curves():
    # Availability is checked *before* running: with FEMM installed this call
    # would launch a real multi-minute field campaign, which is not what a unit
    # test should do, and the blocked path it covers would not be exercised.
    if detect_femm().is_available:
        pytest.skip("FEMM is installed on this machine; the blocked path does not apply")
    inputs, analysis = _design()
    run = run_validation(
        inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF, modelling=MODELLING
    )
    assert run.outcome.status == "BLOCKED_BY_ENVIRONMENT"
    assert run.comparison is None
    assert run.evidence is None
    text = render_run_zh(run)
    assert "未检测到 FEMM" in text
    assert "不展示任何对比数字" in text


def test_the_view_model_never_reports_mock_data_as_real():
    model = _view_model()
    model.confirm_modelling_parameters(rotor_back_iron_thickness_m=0.006, coil_span_slots=1)
    model.run(force_mock_solver=True)
    if model.last_run.used_mock_solver:
        assert model.has_results is True
        assert model.has_real_fea_data is False
        assert "不得作为验证证据" in model.results_text_zh()


def test_the_modelling_parameter_suggestions_are_editable_not_silent():
    from motor_calculator.fea.view_model import MODELLING_PARAMETER_NOTICE_ZH

    model = _view_model()
    back_iron_m, coil_span = model.suggested_values()
    assert back_iron_m > 0.0 and coil_span >= 1
    # Suggesting is not confirming: the case is still unbuildable.
    assert model.modelling is None
    assert model.can_generate_case is False
    assert "MotorCalculator 的输入模型中不存在" in MODELLING_PARAMETER_NOTICE_ZH


def test_the_fea_menu_entry_exists_and_is_explicit():
    source = (
        Path(__file__).resolve().parents[1] / "gui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert 'label="FEA 验证..."' in source
    assert "_open_fea_validation" in source
    # It must not be wired into the normal calculation path.
    assert "_open_fea_validation" not in source.split("def _calculate")[-1].split("def ")[0]


# ---------------------------------------------------------------------------
# 25. Export consistency and plots
# ---------------------------------------------------------------------------


def test_export_bundle_writes_case_result_and_comparison(tmp_path):
    inputs, analysis = _design()
    run = run_validation(
        inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF,
        modelling=MODELLING, force_mock_solver=True,
    )
    written = export_bundle(
        run.case, tmp_path, result=run.outcome.result, report=run.comparison
    )
    names = {path.name for path in written}
    assert names == {
        "fea_case.json", "fea_raw_result.json", "fea_raw_samples.csv",
        "fea_comparison.csv", "fea_comparison.json",
    }
    payload = json.loads((tmp_path / "fea_case.json").read_text(encoding="utf-8"))
    assert payload["case"]["case_id"] == run.case.case_id
    restored = case_from_dict(payload["case"])
    assert compute_case_hash(restored) == run.case.case_id


def test_exported_comparison_csv_carries_the_mock_and_admissibility_flags(tmp_path):
    import csv

    inputs, analysis = _design()
    run = run_validation(
        inputs, analysis, target=FEAValidationTarget.NO_LOAD_BACK_EMF,
        modelling=MODELLING, force_mock_solver=True,
    )
    export_bundle(run.case, tmp_path, result=run.outcome.result, report=run.comparison)
    with (tmp_path / "fea_comparison.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        assert row["is_mock"] == "True"
        assert row["evidence_admissible"] == "False"
        assert row["fidelity_tier"] == "FEA_TIER_3"


def test_export_only_writes_what_exists(tmp_path):
    case = _case()
    written = export_bundle(case, tmp_path)
    assert {path.name for path in written} == {"fea_case.json"}


def test_plot_series_are_only_available_once_a_solver_has_run():
    case = _case()
    result = MockFEASolver().solve(case).result
    series = plot_series(result)
    assert len(series["rotor_angle_mech_deg"]) == case.operating_point.rotor_angle_sample_count
    assert "flux_linkage_A_wb_turn" in series


# ---------------------------------------------------------------------------
# Reference case
# ---------------------------------------------------------------------------


def test_the_reference_case_file_matches_a_fresh_rebuild():
    payload = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    assert payload["reference_id"] == PHASE10A_REFERENCE_ID
    for target in PHASE10A_REFERENCE_TARGETS:
        stored = payload["cases"][target.value]
        rebuilt = build_reference_case(target)
        assert stored["case_id"] == rebuilt.case_id
        assert case_to_dict(rebuilt) == stored


def test_the_reference_case_carries_no_expected_fea_numbers():
    payload = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    assert payload["execution_status"] == "BLOCKED_BY_SOLVER_AVAILABILITY"
    assert "no expected FEA numbers" in payload["expected_solver_values_statement"]
    # No solved quantity may appear anywhere in a case-definition-only file.
    text = REFERENCE_JSON.read_text(encoding="utf-8")
    for forbidden in (
        "flux_linkage_", "circumferential_force", "measured", "solver_result",
        "fea_result", "back_emf_fea",
    ):
        assert forbidden not in text


def test_the_reference_case_is_fully_supported_and_explains_why_it_was_chosen():
    payload = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    assert "no radial-flux topology" in payload["selection_rationale"]
    for target in PHASE10A_REFERENCE_TARGETS:
        case = build_reference_case(target)
        assert case.supportability.state is FEASupportability.SUPPORTED
        assert case.geometry.is_coreless is True


def test_the_review_text_states_every_declared_assumption():
    case = build_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    text = render_case_review_zh(case)
    assert "FEA_TIER_3" in text
    assert "案例哈希" in text
    assert "近似与已知遗漏" in text
    assert "declared FEA-only modelling parameters" in text
    assert "不作收敛声明" in text


def test_a_coreless_cogging_case_says_the_analytical_prediction_is_structurally_zero():
    case = build_reference_case(FEAValidationTarget.COGGING_TORQUE)
    assert case.analytical.cogging_torque_peak_nm == 0.0
    assert any("no cogging by construction" in note for note in case.notes)
    outcome = MockFEASolver().solve(case)
    extraction = extract_cogging(outcome.result)
    assert extraction.amplitude_nm >= 0.0
