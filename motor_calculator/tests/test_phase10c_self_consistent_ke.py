"""Phase 10C: geometry-consistent winding factor, and the error decomposition.

Phase 10B's Ke comparison appeared to agree to -0.22%. It did not agree; a
+7.39% winding-factor error was cancelling a -6.59% flux error. These tests lock
the machinery that made that visible and keep it visible.

No real solver is needed: the Phase 10B field solution is reused, and its
reusability is itself asserted by comparing the emitted solver scripts.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from motor_calculator.fea import FEAValidationTarget, build_comparison
from motor_calculator.fea.adapter import generate_case_scripts
from motor_calculator.fea.decomposition import (
    DECOMPOSITION_SCHEMA_VERSION,
    decompose_ke_error,
    fea_equivalent_flux_per_pole_wb,
)
from motor_calculator.fea.hashing import (
    ANALYTICAL_FINGERPRINT_EXTRA_FIELDS,
    CASE_HASH_EXCLUDED_NESTED_FIELDS,
    FEA_CASE_HASH_VERSION,
    compute_analytical_fingerprint,
    compute_case_hash,
)
from motor_calculator.fea.reference_cases import (
    PHASE10A_REFERENCE_PARAMETERS,
    PHASE10C_REFERENCE_ID,
    build_reference_case,
    build_self_consistent_reference_case,
    phase10c_reference_parameters,
    resolve_self_consistent_winding_factor,
)
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.constants import LEGACY_SINE_EMF_FACTOR
from motor_calculator.motor_core.validation import parse_legacy_gui_params
from motor_calculator.motor_core.winding_factor import (
    WindingFactorMode,
    WindingFactorProvenance,
)

REPO = Path(__file__).resolve().parents[2]
FROZEN = REPO / "validation_data" / "fea_results" / "phase10b_winding_factor_inconsistent"
SELF_CONSISTENT = REPO / "validation_data" / "fea_results" / "phase10c_self_consistent"
TARGET = FEAValidationTarget.NO_LOAD_BACK_EMF


def _analysis(parameters):
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(dict(parameters)))
    return bridge, bridge.run_full_analysis()


# ---------------------------------------------------------------------------
# 1/2. Geometry-derived winding factor and AUTO provenance
# ---------------------------------------------------------------------------


def test_geometry_derived_winding_factor_reference():
    """Q=24, 2p=16, 1-slot span. Derived, not hardcoded into production."""

    resolution = resolve_self_consistent_winding_factor()
    breakdown = resolution.breakdown
    assert breakdown is not None
    assert breakdown.slots == 24
    assert breakdown.pole_count == 16
    assert breakdown.phases == 3
    assert breakdown.coil_span_slots == 1
    assert breakdown.full_pitch_slots == pytest.approx(1.5)
    assert breakdown.slots_per_pole_per_phase == pytest.approx(0.5)
    assert breakdown.slot_electrical_angle_deg == pytest.approx(120.0)
    assert breakdown.distribution_factor == pytest.approx(1.0)
    assert breakdown.pitch_factor == pytest.approx(math.sin(math.radians(60.0)))
    assert breakdown.skew_factor == pytest.approx(1.0)
    assert breakdown.fundamental_winding_factor == pytest.approx(0.8660254037844386)


def test_the_self_consistent_case_uses_auto_provenance():
    resolution = resolve_self_consistent_winding_factor()
    assert resolution.mode is WindingFactorMode.AUTO
    assert resolution.provenance is WindingFactorProvenance.AUTO_GEOMETRY
    # The manual value is preserved on the resolution, not silently discarded.
    assert resolution.manual_value == pytest.approx(0.93)

    case = build_self_consistent_reference_case(TARGET)
    assert case.winding.winding_factor_analytical == pytest.approx(0.8660254037844386)
    assert "AUTO_GEOMETRY" in case.winding.winding_factor_provenance


def test_only_the_winding_factor_differs_between_the_two_reference_cases():
    historical = dict(PHASE10A_REFERENCE_PARAMETERS)
    self_consistent = phase10c_reference_parameters()
    differing = {
        key for key in set(historical) | set(self_consistent)
        if historical.get(key) != self_consistent.get(key)
    }
    assert differing == {"k_w"}


# ---------------------------------------------------------------------------
# 3. The Phase 10B historical record is preserved
# ---------------------------------------------------------------------------


def test_the_phase10b_historical_evidence_is_preserved_and_labelled():
    assert FROZEN.is_dir()
    for name in (
        "fea_case.json", "fea_comparison.json", "fea_comparison.csv",
        "fea_raw_result.json", "fea_raw_samples.csv", "FROZEN_README_zh.md",
    ):
        assert (FROZEN / name).is_file(), name

    readme = (FROZEN / "FROZEN_README_zh.md").read_text(encoding="utf-8")
    assert "WINDING_FACTOR_INCONSISTENT_REFERENCE" in readme
    assert "0.93" in readme and "0.8660254" in readme
    assert "-0.2168" in readme or "−0.2168" in readme

    stored = json.loads((FROZEN / "fea_comparison.json").read_text(encoding="utf-8"))
    comparison = stored["comparison"]
    # It still carries the v1 case_id it was computed under.
    assert comparison["case_id"] == (
        "4f5f6f03c71a35093445885feabb56fbf99fbc600226658bb910c56fa0b692ee"
    )
    assert comparison["is_mock"] is False


def test_the_historical_record_must_not_be_read_as_isolated_validation():
    readme = (FROZEN / "FROZEN_README_zh.md").read_text(encoding="utf-8")
    assert "不能被解读为磁路模型已被验证" in readme
    assert "抵消" in readme


# ---------------------------------------------------------------------------
# 4. Analytical Ke scales with the winding factor
# ---------------------------------------------------------------------------


def test_analytical_ke_scales_exactly_with_the_winding_factor():
    """Only k_w changed, so Ke must move by exactly the k_w ratio."""

    old_bridge, old = _analysis(PHASE10A_REFERENCE_PARAMETERS)
    new_bridge, new = _analysis(phase10c_reference_parameters())

    ke_old = old.electrical.back_emf_constant_phase_rms_v_per_rad_s
    ke_new = new.electrical.back_emf_constant_phase_rms_v_per_rad_s
    kw_ratio = new_bridge.input_data.winding_factor / old_bridge.input_data.winding_factor

    assert ke_new / ke_old == pytest.approx(kw_ratio, rel=1e-15)
    # Nothing magnetic moved: the flux is untouched by a winding-factor edit.
    assert new.magnetic.pole_flux_wb == old.magnetic.pole_flux_wb
    assert new.magnetic.air_gap_flux_density_peak_t == old.magnetic.air_gap_flux_density_peak_t


def test_the_self_consistent_analytical_ke_is_lower_than_the_historical_one():
    _old_bridge, old = _analysis(PHASE10A_REFERENCE_PARAMETERS)
    _new_bridge, new = _analysis(phase10c_reference_parameters())
    assert (
        new.electrical.back_emf_constant_phase_rms_v_per_rad_s
        < old.electrical.back_emf_constant_phase_rms_v_per_rad_s
    )


# ---------------------------------------------------------------------------
# 5. Multiplicative error decomposition
# ---------------------------------------------------------------------------


def _decomposition():
    stored = json.loads((SELF_CONSISTENT / "ke_error_decomposition.json").read_text(encoding="utf-8"))
    return decompose_ke_error(
        winding_factor_entered=stored["manual_winding_factor"],
        winding_factor_geometric=stored["geometry_winding_factor"],
        analytical_flux_per_pole_wb=stored["analytical_flux_per_pole_wb"],
        fea_equivalent_flux_per_pole_wb=stored["fea_equivalent_flux_per_pole_wb"],
        ke_analytical_entered=stored["ke_analytical_manual"],
        ke_analytical_self_consistent=stored["ke_analytical_self_consistent"],
        ke_fea=stored["ke_fea"],
        sine_emf_factor=LEGACY_SINE_EMF_FACTOR,
        fea_total_to_fundamental_rms_ratio=stored["fea_total_to_fundamental_rms_ratio"],
    )


def test_the_decomposition_reconstructs_the_observed_ratio_exactly():
    """A*B alone leaves 8.9e-4; the two known basis factors close it entirely."""

    dec = _decomposition()
    assert abs(dec.reconstruction_residual) > 1e-5, "the naive product should not already match"
    assert dec.reconstruction_residual_exact == pytest.approx(0.0, abs=1e-12)


def test_the_decomposition_is_multiplicative_not_additive():
    dec = _decomposition()
    additive = (dec.winding_factor_ratio - 1.0) + (dec.flux_ratio - 1.0) + 1.0
    assert dec.reconstructed_net_ratio != pytest.approx(additive, abs=1e-9)
    assert dec.reconstructed_net_ratio == pytest.approx(
        dec.winding_factor_ratio * dec.flux_ratio, rel=1e-15
    )
    assert "multiplicativ" in dec.rationale


def test_the_cancellation_is_detected():
    dec = _decomposition()
    # Two large, opposed component errors and a small net.
    assert dec.winding_factor_error_percent > 5.0
    assert dec.flux_error_percent < -5.0
    assert abs(dec.historical_ke_error_percent) < 1.0
    assert abs(dec.self_consistent_ke_error_percent) > 5.0
    assert dec.cancellation_is_confirmed is True


def test_a_genuinely_consistent_case_is_not_flagged_as_cancellation():
    dec = decompose_ke_error(
        winding_factor_entered=0.866, winding_factor_geometric=0.866,
        analytical_flux_per_pole_wb=1.0e-4, fea_equivalent_flux_per_pole_wb=1.001e-4,
        ke_analytical_entered=0.09, ke_analytical_self_consistent=0.09, ke_fea=0.0901,
    )
    assert dec.cancellation_is_confirmed is False


def test_fea_equivalent_flux_divides_out_turns_and_geometric_winding_factor():
    flux = fea_equivalent_flux_per_pole_wb(
        fundamental_flux_linkage_peak_wb_turn=0.0159004286,
        turns_per_phase=50,
        winding_factor_geometric=0.8660254037844386,
    )
    assert flux == pytest.approx(0.0159004286 / (50 * 0.8660254037844386), rel=1e-15)
    with pytest.raises(ValueError):
        fea_equivalent_flux_per_pole_wb(
            fundamental_flux_linkage_peak_wb_turn=0.01, turns_per_phase=0,
            winding_factor_geometric=0.9,
        )
    with pytest.raises(ValueError):
        fea_equivalent_flux_per_pole_wb(
            fundamental_flux_linkage_peak_wb_turn=0.01, turns_per_phase=50,
            winding_factor_geometric=1.5,
        )


# ---------------------------------------------------------------------------
# 6/7/8. Hash semantics: the Phase 10C architectural fix
# ---------------------------------------------------------------------------


def test_hash_version_records_the_changed_digest_definition():
    assert FEA_CASE_HASH_VERSION == "rc4.fea.hash.v3"


def test_an_analytical_only_change_leaves_the_solver_visible_hash_alone():
    """The solver never sees the winding factor, so it must not invalidate a solve."""

    historical = build_reference_case(TARGET)
    self_consistent = build_self_consistent_reference_case(TARGET)
    assert historical.winding.winding_factor_analytical != (
        self_consistent.winding.winding_factor_analytical
    )
    assert historical.case_id == self_consistent.case_id
    assert compute_case_hash(historical) == compute_case_hash(self_consistent)


def test_an_analytical_only_change_does_move_the_fingerprint():
    historical = build_reference_case(TARGET)
    self_consistent = build_self_consistent_reference_case(TARGET)
    assert compute_analytical_fingerprint(historical) != compute_analytical_fingerprint(
        self_consistent
    )


def test_the_fingerprint_moves_even_when_only_the_winding_factor_is_edited():
    """Guards the fingerprint side directly, without a full recomputation."""

    case = build_reference_case(TARGET)
    edited = replace(
        case,
        winding=replace(case.winding, winding_factor_analytical=0.8660254037844386),
    )
    assert compute_case_hash(edited) == compute_case_hash(case)
    assert compute_analytical_fingerprint(edited) != compute_analytical_fingerprint(case)


def test_a_solver_visible_change_still_moves_the_case_hash():
    case = build_reference_case(TARGET)
    for field, value in (("coil_span_slots", 2), ("turns_per_phase", 60)):
        altered = replace(case, winding=replace(case.winding, **{field: value}))
        assert compute_case_hash(altered) != compute_case_hash(case), field


def test_the_excluded_nested_fields_are_exactly_the_analytical_ones():
    assert CASE_HASH_EXCLUDED_NESTED_FIELDS["winding"] == frozenset(
        {"winding_factor_analytical", "winding_factor_provenance"}
    )
    assert set(ANALYTICAL_FINGERPRINT_EXTRA_FIELDS) == {
        ("winding", "winding_factor_analytical"),
        ("winding", "winding_factor_provenance"),
    }


def test_a_comparison_against_a_stale_fingerprint_is_reported_stale():
    """Reusing a solve is fine; reusing a comparison across a k_w change is not."""

    from motor_calculator.fea.adapter import build_provenance
    from motor_calculator.fea.results import FEAPositionSample, FEARawResult

    historical = build_reference_case(TARGET)
    self_consistent = build_self_consistent_reference_case(TARGET)
    angles = historical.operating_point.rotor_angles_mech_deg()
    samples = tuple(
        FEAPositionSample(
            rotor_angle_mech_deg=angle,
            phase_flux_linkage_wb_turn={
                "A": 0.01 * math.cos(math.radians(8 * angle)),
                "B": 0.01 * math.cos(math.radians(8 * angle) - 2 * math.pi / 3),
                "C": 0.01 * math.cos(math.radians(8 * angle) + 2 * math.pi / 3),
            },
            circumferential_force_n=0.0,
        )
        for angle in angles
    )
    # Provenance bound to the *historical* analytical fingerprint.
    result = FEARawResult(
        target=TARGET,
        provenance=build_provenance(
            historical, solver="FEMM", solver_version="4.2.0.0", is_mock=False,
            element_count=1000, solve_seconds=1.0,
        ),
        samples=samples,
        mechanical_speed_rpm=historical.operating_point.mechanical_speed_rpm,
        mean_radius_m=historical.geometry.mean_radius_m,
        pole_pairs=historical.geometry.pole_pairs,
        span_mech_deg=historical.operating_point.rotor_angle_span_mech_deg,
    )
    report = build_comparison(self_consistent, result)
    assert report.stale is True
    assert any("analytical prediction has changed" in r for r in report.stale_reasons)
    # The machine itself did not change, so this is not a case-hash mismatch.
    assert not any("different case hash" in r for r in report.stale_reasons)


# ---------------------------------------------------------------------------
# 9/10. The self-consistent comparison and its evidence
# ---------------------------------------------------------------------------


def test_the_self_consistent_comparison_was_exported():
    for name in (
        "fea_case.json", "fea_comparison.json", "fea_comparison.csv",
        "fea_raw_result.json", "fea_raw_samples.csv", "ke_error_decomposition.json",
    ):
        assert (SELF_CONSISTENT / name).is_file(), name


def test_the_self_consistent_evidence_is_real_admissible_and_not_stale():
    stored = json.loads((SELF_CONSISTENT / "fea_comparison.json").read_text(encoding="utf-8"))
    comparison = stored["comparison"]
    assert comparison["is_mock"] is False
    assert comparison["stale"] is False
    assert comparison["evidence_admissible"] is True
    assert comparison["auto_calibration_enabled"] is False
    assert comparison["fidelity_tier"] == "FEA_TIER_3"


def test_the_winding_factor_metric_now_agrees_in_the_self_consistent_case():
    stored = json.loads((SELF_CONSISTENT / "fea_comparison.json").read_text(encoding="utf-8"))
    metric = next(
        m for m in stored["comparison"]["metrics"]
        if m["quantity"] == "winding_factor_entered_vs_solved_geometry"
    )
    assert metric["relative_error_percent"] == pytest.approx(0.0, abs=1e-9)
    assert metric["status"] == "CLOSE_AGREEMENT"


def test_the_self_consistent_residual_matches_the_flux_residual():
    """If Ke and flux residuals agree, the winding factor is no longer confounding."""

    stored = json.loads((SELF_CONSISTENT / "ke_error_decomposition.json").read_text(encoding="utf-8"))
    ke_residual = stored["self_consistent_ke_error_percent"]
    # Same convention as the Ke residual: FEA relative to analytical. The
    # reciprocal figure is also exported, and mixing the two would make one
    # finding look like two.
    flux_residual = stored["flux_residual_fea_vs_analytical_percent"]
    assert ke_residual > 5.0
    assert flux_residual > 5.0
    # Same sign, same order; they differ only by the known basis factors.
    assert abs(ke_residual - flux_residual) < 0.5
    # The opposite convention is the reciprocal, not a different result.
    other = stored["flux_residual_analytical_vs_fea_percent"]
    assert (1.0 + flux_residual / 100.0) * (1.0 + other / 100.0) == pytest.approx(1.0, rel=1e-12)


def test_the_export_carries_the_full_decomposition_provenance():
    stored = json.loads((SELF_CONSISTENT / "ke_error_decomposition.json").read_text(encoding="utf-8"))
    for key in (
        "manual_winding_factor", "geometry_winding_factor", "winding_factor_provenance",
        "distribution_factor", "pitch_factor", "skew_factor",
        "analytical_flux_per_pole_wb", "fea_equivalent_flux_per_pole_wb",
        "flux_residual_analytical_vs_fea_percent",
        "flux_residual_fea_vs_analytical_percent", "historical_ke_error_percent",
        "self_consistent_ke_error_percent", "mesh_sensitivity_percent",
        "fea_rerun_required", "fea_reuse_justification", "solver", "solver_version",
        "case_id", "analytical_fingerprint", "fea_tier",
    ):
        assert key in stored, key
    assert stored["schema_version"] == DECOMPOSITION_SCHEMA_VERSION
    assert stored["fea_rerun_required"] is False
    assert stored["cancellation_confirmed"] is True


def test_the_numerical_and_model_form_scales_are_separated():
    stored = json.loads((SELF_CONSISTENT / "ke_error_decomposition.json").read_text(encoding="utf-8"))
    mesh = stored["mesh_sensitivity_percent"]
    residual = abs(stored["self_consistent_ke_error_percent"])
    assert mesh < 0.2, "mesh sensitivity should be a small fraction of a percent"
    assert residual > 20.0 * mesh, "the residual must be far above discretisation noise"


# ---------------------------------------------------------------------------
# 11/12. No physics change, no calibration
# ---------------------------------------------------------------------------


def test_the_field_solution_is_reusable_because_the_scripts_are_identical(tmp_path):
    """The reuse justification, asserted rather than asserted-about."""

    historical = build_reference_case(TARGET)
    self_consistent = build_self_consistent_reference_case(TARGET)
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_scripts = generate_case_scripts(historical, a_dir)
    b_scripts = generate_case_scripts(self_consistent, b_dir)
    assert len(a_scripts) == len(b_scripts)
    for a, b in zip(a_scripts, b_scripts):
        ta = a.read_text(encoding="utf-8").replace(a_dir.as_posix(), "<WS>")
        tb = b.read_text(encoding="utf-8").replace(b_dir.as_posix(), "<WS>")
        assert ta == tb, a.name


def test_phase10c_changed_no_analytical_physics():
    """Only k_w moved, and it moved to the value the geometry already implied."""

    historical = dict(PHASE10A_REFERENCE_PARAMETERS)
    self_consistent = phase10c_reference_parameters()
    for key in ("Br", "alpha_p", "sigma_m", "mu_r_mag", "g_side", "h_mag",
                "w_magnet", "L_magnet", "D_out", "D_in", "h_coil", "slots", "p",
                "N_ph_turns", "d_wire", "n_parallel", "slot_type", "coreless"):
        assert historical[key] == self_consistent[key], key


def test_no_calibration_was_performed():
    from motor_calculator.fea import AUTO_CALIBRATION_ENABLED

    assert AUTO_CALIBRATION_ENABLED is False
    stored = json.loads((SELF_CONSISTENT / "fea_comparison.json").read_text(encoding="utf-8"))
    assert stored["comparison"]["auto_calibration_enabled"] is False
    # The decomposition module reports ratios; it must not fit anything.
    source = (REPO / "motor_calculator" / "fea" / "decomposition.py").read_text(encoding="utf-8")
    for forbidden in ("curve_fit", "least_squares", "minimize(", "polyfit"):
        assert forbidden not in source


def test_the_reference_id_is_versioned_and_distinct():
    assert PHASE10C_REFERENCE_ID == "phase10c_coreless_ssdr_self_consistent_v1"


# ---------------------------------------------------------------------------
# 13. Reporting
# ---------------------------------------------------------------------------


def test_the_historical_figure_is_never_offered_without_its_caveat():
    from motor_calculator.fea.view_model import (
        HISTORICAL_KE_COMPARISON_ZH,
        PREFERRED_KE_COMPARISON_ZH,
    )

    assert "0.22" in HISTORICAL_KE_COMPARISON_ZH
    assert "抵消" in HISTORICAL_KE_COMPARISON_ZH
    assert "不可作为磁路模型已被验证的依据" in HISTORICAL_KE_COMPARISON_ZH
    assert "AUTO_GEOMETRY" in PREFERRED_KE_COMPARISON_ZH
    assert "0.8660254" in PREFERRED_KE_COMPARISON_ZH
