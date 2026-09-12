"""Phase 10B: behaviour learned from running against a real FEMM installation.

Every assertion here exists because the real solver contradicted an assumption
that unit tests alone had accepted. The integration tests at the bottom are
marked ``femm_integration`` and skip when FEMM is absent.
"""

from __future__ import annotations

import math
import subprocess
import time
from pathlib import Path

import pytest

from motor_calculator.fea import (
    FEAValidationTarget,
    build_comparison,
    build_evidence_record,
    build_slice_model,
    detect_femm,
)
from motor_calculator.fea.adapter import (
    FEMMSubprocessSolver,
    _mesh_size_map,
    generate_case_scripts,
    parse_samples_csv,
    windows_file_version,
)
from motor_calculator.fea.femm_lua import (
    build_position_script,
    declared_material_names,
    unit_turns_scale,
)
from motor_calculator.fea.models import FEAComparisonStatus
from motor_calculator.fea.reference_cases import build_reference_case
from motor_calculator.fea.winding import allocate_all_phases, belt_to_phase_map
from motor_calculator.motor_core.winding_factor import (
    build_slot_star,
    compute_fundamental_winding_factor,
)
from motor_calculator.validation.fea_reference import EvidenceClassification

FEMM_REPORT = detect_femm()
FEMM_PRESENT = FEMM_REPORT.is_available

requires_femm = pytest.mark.skipif(
    not FEMM_PRESENT, reason="FEMM is not installed; real-solver test is blocked, not failed"
)


def _case(target=FEAValidationTarget.NO_LOAD_BACK_EMF):
    return build_reference_case(target)


def _model(case, angle=0.0):
    return build_slice_model(
        case.geometry,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=angle,
    )


# ---------------------------------------------------------------------------
# Lua the real solver actually accepts
# ---------------------------------------------------------------------------


def test_every_segment_endpoint_is_declared_as_a_node(tmp_path):
    """mi_addsegment joins existing nodes; it does not create them."""

    case = _case()
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    nodes = set()
    for line in script.splitlines():
        if line.startswith("mi_addnode("):
            nodes.add(line[len("mi_addnode(") : -1])
    assert nodes
    missing = []
    for line in script.splitlines():
        if not line.startswith("mi_addsegment("):
            continue
        x1, y1, x2, y2 = line[len("mi_addsegment(") : -1].split(", ")
        for point in (f"{x1}, {y1}", f"{x2}, {y2}"):
            if point not in nodes:
                missing.append(point)
    assert not missing, f"{len(missing)} segment endpoints have no node: {missing[:3]}"


def test_no_two_segments_overlap_on_the_periodic_seams(tmp_path):
    """Collinear overlapping segments are invalid mesher input.

    Full-width regions used to duplicate their vertical edges on top of the
    domain's side edges, and the analysis then refused to mesh.
    """

    case = _case()
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    model = _model(case)
    span = model.modelled_span_m

    for seam in (0.0, span):
        intervals = []
        for line in script.splitlines():
            if not line.startswith("mi_addsegment("):
                continue
            x1, y1, x2, y2 = (float(v) for v in line[len("mi_addsegment(") : -1].split(", "))
            if abs(x1 - seam) < 1e-9 and abs(x2 - seam) < 1e-9:
                intervals.append((min(y1, y2), max(y1, y2)))
        intervals.sort()
        for (a0, a1), (b0, b1) in zip(intervals, intervals[1:]):
            assert a1 <= b0 + 1e-12, f"overlapping seam segments at x={seam}: {(a0,a1)} {(b0,b1)}"


def test_the_script_terminates_femm(tmp_path):
    """Without quit() FEMM keeps its window open and the subprocess never returns."""

    case = _case()
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    assert script.rstrip().endswith("quit()")


def test_every_block_label_names_a_material_the_script_defines(tmp_path):
    """A label whose material is undefined gets block type 0 and refuses to mesh.

    FEMM does not report that; the analysis simply produces no mesh.
    """

    case = _case()
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    defined = {
        line.split('"')[1]
        for line in script.splitlines()
        if line.startswith("mi_addmaterial(")
    }
    used = {
        line.split('"')[1]
        for line in script.splitlines()
        if line.startswith("mi_setblockprop(")
    }
    assert used, "no block properties were assigned"
    assert used <= defined, f"materials used but never defined: {sorted(used - defined)}"
    assert declared_material_names(case.materials, is_coreless=True) >= used


def test_an_undefined_region_material_is_refused_loudly():
    from dataclasses import replace

    case = _case()
    model = _model(case)
    broken = replace(model, regions=tuple(
        replace(r, material_key="unobtainium") if r.role == "winding" else r
        for r in model.regions
    ))
    with pytest.raises(ValueError, match="never defined"):
        build_position_script(
            case, broken,
            phase_currents=type("C", (), {"values": {"A": 0.0, "B": 0.0, "C": 0.0}})(),
            fem_path="m.fem", output_path="o.csv", append=False,
        )


def test_lua_paths_use_forward_slashes(tmp_path):
    """One missed backslash escape turns a path segment into an escape sequence."""

    case = _case()
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    for line in script.splitlines():
        if line.startswith("mi_saveas(") or line.startswith("handle = openfile("):
            assert "\\" not in line, line


def test_all_three_air_regions_carry_a_block_label():
    """The rotor back-iron bands cut the air into three disconnected regions."""

    case = _case()
    model = _model(case)
    air_labels = [
        r for r in model.regions
        if r.role in ("air_domain", "air_domain_label_only")
    ]
    assert len(air_labels) == 3
    ys = sorted(r.block_label_m[1] for r in air_labels)
    # One above the upper back iron, one below the lower, one inside the stack.
    assert ys[0] < 0 < ys[2]
    inner = [r for r in air_labels if r.name == "air_active_stack"][0]
    half_coil = case.geometry.winding_region_thickness_m / 2.0
    gap = case.geometry.mechanical_air_gap_per_side_m
    assert half_coil < inner.block_label_m[1] < half_coil + gap


# ---------------------------------------------------------------------------
# Turns semantics
# ---------------------------------------------------------------------------


def test_turns_are_emitted_as_unit_magnitude(tmp_path):
    """FEMM truncates the turns block property to an integer.

    A 6.25-turn coil became 6, understating flux linkage by 4%.
    """

    case = _case()
    assert case.winding.turns_per_coil == pytest.approx(6.25)
    script = generate_case_scripts(case, tmp_path)[0].read_text(encoding="utf-8")
    turns = {
        float(line.rstrip(")").rsplit(",", 1)[1])
        for line in script.splitlines()
        if line.startswith("mi_setblockprop(")
    }
    assert turns <= {0.0, 1.0, -1.0}, turns
    assert {1.0, -1.0} <= turns


def test_the_turns_magnitude_is_restored_exactly_on_parse(tmp_path):
    case = _case()
    assert FEMMSubprocessSolver._flux_linkage_scale(case) == case.winding.turns_per_coil

    csv = tmp_path / "s.csv"
    csv.write_text(
        "rotor_angle_mech_deg,flux_linkage_A_wb_turn,circumferential_force_n,element_count\n"
        "0.0,0.002,1.0,10\n",
        encoding="utf-8",
    )
    samples = parse_samples_csv(csv, ("A",), flux_linkage_scale=6.25)
    assert samples[0].phase_flux_linkage_wb_turn["A"] == pytest.approx(0.0125)


def test_a_non_uniform_turns_magnitude_is_refused():
    from dataclasses import replace

    case = _case()
    model = _model(case)
    windings = [r for r in model.regions if r.role == "winding"]
    mixed = replace(model, regions=tuple(
        replace(r, signed_turns=3.0) if r is windings[0] else r for r in model.regions
    ))
    with pytest.raises(ValueError, match="more than one turns magnitude"):
        unit_turns_scale(mixed)


# ---------------------------------------------------------------------------
# Belt-to-phase mapping
# ---------------------------------------------------------------------------


def test_belts_place_the_phases_120_electrical_degrees_apart():
    """PHASE_LABELS[belt % m] spaces them 60 degrees apart, which is wrong.

    The real solver showed it: three equal-amplitude flux-linkage waveforms at
    150, 90 and 30 degrees whose sum was never zero.
    """

    mapping = belt_to_phase_map(3)
    assert mapping[0] == (0, 1)    # A+ at 0 deg
    assert mapping[2] == (1, 1)    # B+ at 120 deg
    assert mapping[4] == (2, 1)    # C+ at 240 deg
    assert mapping[3] == (0, -1)   # A- at 180 deg
    assert mapping[5] == (1, -1)
    assert mapping[1] == (2, -1)
    # Positive belts are two belts, i.e. 120 electrical degrees, apart.
    positives = sorted(b for b, (_p, s) in mapping.items() if s == 1)
    assert positives == [0, 2, 4]


@pytest.mark.parametrize("slots,pole_pairs", [(24, 8), (24, 2), (36, 3), (12, 5), (48, 10)])
def test_phase_a_still_matches_the_analytical_slot_star(slots, pole_pairs):
    """winding_factor.py is untouched, so phase A must be unchanged."""

    star = build_slot_star(slots, pole_pairs)
    if not star.balanced:
        pytest.skip("unbalanced winding")
    labels, signs = allocate_all_phases(slots, pole_pairs)
    got = tuple((i, s) for i, (l, s) in enumerate(zip(labels, signs)) if l == "A")
    assert tuple(i for i, _ in got) == star.phase_a_slots
    assert tuple(s for _, s in got) == star.phase_a_signs


# ---------------------------------------------------------------------------
# Winding-factor consistency reporting
# ---------------------------------------------------------------------------


def test_the_comparison_reports_entered_against_solved_winding_factor():
    """A back-EMF match can be two offsetting errors rather than two right models."""

    from motor_calculator.fea.comparison import _ideal_slot_star_winding_factor

    case = _case()
    geometric = _ideal_slot_star_winding_factor(case)
    expected = compute_fundamental_winding_factor(
        slots=24, pole_pairs=8, coil_span_slots=case.winding.coil_span_slots
    ).fundamental_winding_factor
    assert geometric == pytest.approx(expected)
    # The reference design enters 0.93; a one-slot span on Q=24/2p=16 gives
    # 0.866. No integer coil span on this combination yields 0.93.
    assert case.winding.winding_factor_analytical == pytest.approx(0.93)
    assert geometric == pytest.approx(0.8660254037844386)


def test_solver_version_is_read_from_the_executable_or_reported_unknown(tmp_path):
    blank = tmp_path / "not_a_pe.exe"
    blank.write_bytes(b"not a real executable")
    assert windows_file_version(blank) is None


# ---------------------------------------------------------------------------
# Real solver integration
# ---------------------------------------------------------------------------


@requires_femm
@pytest.mark.femm_integration
def test_real_femm_version_is_detected():
    version = windows_file_version(FEMM_REPORT.executable_path)
    assert version is not None
    assert version.startswith("4."), version


@requires_femm
@pytest.mark.femm_integration
def test_real_single_motor_position_solves_and_extracts_flux_linkage(tmp_path):
    """One rotor position end to end: geometry, mesh, solve, circuit extraction."""

    case = _case()
    scripts = generate_case_scripts(case, tmp_path)
    started = time.perf_counter()
    completed = subprocess.run(
        [str(FEMM_REPORT.executable_path), "-lua-script=" + str(scripts[0]), "-windowhide"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=600.0, shell=False,
    )
    elapsed = time.perf_counter() - started
    assert completed.returncode == 0, completed.stderr[-500:]
    assert (tmp_path / "position_0000.ans").is_file(), "no solution was produced"

    samples = parse_samples_csv(
        tmp_path / "fea_samples.csv", ("A", "B", "C"),
        flux_linkage_scale=FEMMSubprocessSolver._flux_linkage_scale(case),
    )
    assert len(samples) == 1
    linkage = samples[0].phase_flux_linkage_wb_turn
    assert set(linkage) == {"A", "B", "C"}
    for name, value in linkage.items():
        assert math.isfinite(value), name
    # Non-trivial field, and a balanced instantaneous set sums to roughly zero.
    assert max(abs(v) for v in linkage.values()) > 1e-4
    assert abs(sum(linkage.values())) < 0.05 * max(abs(v) for v in linkage.values())
    assert samples[0].element_count and samples[0].element_count > 1000
    assert elapsed < 600.0


@requires_femm
@pytest.mark.femm_integration
def test_our_own_solver_child_exits_rather_than_being_killed(tmp_path):
    """quit() must terminate the solver we launched.

    Only *our* child is asserted on. Global process state is not: this machine
    may legitimately be running the user's own FEMM window, and a test has no
    business asserting that away or killing it. FEMM also takes a moment to
    fully exit after the subprocess returns, so a global count sampled straight
    after the call sees a process that is already shutting down.
    """

    case = _case()
    scripts = generate_case_scripts(case, tmp_path)
    process = subprocess.Popen(
        [str(FEMM_REPORT.executable_path), "-lua-script=" + str(scripts[0]), "-windowhide"],
        cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
    )
    try:
        process.communicate(timeout=600.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        pytest.fail("FEMM did not exit on its own; the script is missing quit()")
    assert process.returncode == 0
    assert process.poll() is not None
