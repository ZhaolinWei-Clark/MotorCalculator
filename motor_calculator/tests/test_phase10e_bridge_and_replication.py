"""Phase 10E: meshed winding semantics, diagnostics panel, cross-design evidence.

No solver run happens here. The tests that consume FEMM output read the
committed Phase 10D and 10E evidence, so the suite stays fast and deterministic.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from motor_calculator.fea.airgap_probe import rectangular_to_fundamental_form_factor
from motor_calculator.fea.diagnostics import (
    CALIBRATION_STATUS,
    DIAGNOSTICS_SCHEMA_VERSION,
    EvidenceLabel,
    build_validation_diagnostics,
    is_affirmative,
    render_diagnostics_zh,
    unavailable_diagnostics,
)
from motor_calculator.fea.flux_budget import build_flux_residual_budget
from motor_calculator.fea.meshed_winding import (
    MESHED_WINDING_SCHEMA_VERSION,
    measure_meshed_winding_factor,
    meshed_winding_factor_for_case,
)
from motor_calculator.fea.models import FEAValidationTarget
from motor_calculator.fea.reference_cases import build_self_consistent_reference_case

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EV10D = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"
EV10E = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10e_replication"
EV10B = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10b_winding_factor_inconsistent"
EV10C = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10c_self_consistent"


class _Region:
    """Minimal stand-in for a meshed conductor region."""

    def __init__(self, x0, x1, turns, circuit="A"):
        self.role = "winding"
        self.circuit_name = circuit
        self.signed_turns = turns
        self.name = f"coil_{x0}"
        self.polygon_m = ((x0, -0.0025), (x1, -0.0025), (x1, 0.0025), (x0, 0.0025))


class _Model:
    def __init__(self, regions):
        self.regions = regions
        self.circuit_names = ("A",)


# ---------------------------------------------------------------------------
# Meshed winding factor: the projection must reproduce textbook values
# ---------------------------------------------------------------------------


def test_a_full_pitch_filament_coil_projects_to_unity():
    tau, n, w = 0.02, 10.0, 1e-7
    model = _Model([_Region(0.0, w, n), _Region(tau, tau + w, -n)])
    measured = measure_meshed_winding_factor(model, pole_pitch_m=tau, turns_per_phase=n)
    assert measured.value == pytest.approx(1.0, rel=1e-6)
    assert measured.schema_version == MESHED_WINDING_SCHEMA_VERSION


def test_a_two_thirds_pitch_filament_coil_projects_to_the_slot_star_value():
    tau, n, w = 0.02, 10.0, 1e-7
    pitch = tau * 2.0 / 3.0
    model = _Model([_Region(0.0, w, n), _Region(pitch, pitch + w, -n)])
    measured = measure_meshed_winding_factor(model, pole_pitch_m=tau, turns_per_phase=n)
    assert measured.value == pytest.approx(math.sqrt(3.0) / 2.0, rel=1e-6)


def test_finite_conductor_width_lowers_the_projection():
    tau, n = 0.02, 10.0
    thin = _Model([_Region(0.0, 1e-7, n), _Region(tau, tau + 1e-7, -n)])
    wide = _Model([_Region(0.0, 0.004, n), _Region(tau, tau + 0.004, -n)])
    a = measure_meshed_winding_factor(thin, pole_pitch_m=tau, turns_per_phase=n).value
    b = measure_meshed_winding_factor(wide, pole_pitch_m=tau, turns_per_phase=n).value
    assert b < a


def test_the_projection_rejects_an_impossible_result_rather_than_returning_it():
    tau, n, w = 0.02, 10.0, 1e-7
    # Turns that do not belong to the declared phase total would imply k_w > 1.
    model = _Model([_Region(0.0, w, n), _Region(tau, tau + w, -n)])
    with pytest.raises(ValueError):
        measure_meshed_winding_factor(model, pole_pitch_m=tau, turns_per_phase=n / 4.0)


def test_the_projection_rejects_degenerate_geometry():
    model = _Model([_Region(0.0, 1e-7, 1.0)])
    with pytest.raises(ValueError):
        measure_meshed_winding_factor(model, pole_pitch_m=0.0, turns_per_phase=1.0)
    with pytest.raises(ValueError):
        measure_meshed_winding_factor(model, pole_pitch_m=0.02, turns_per_phase=0.0)
    with pytest.raises(ValueError):
        measure_meshed_winding_factor(_Model([]), pole_pitch_m=0.02, turns_per_phase=1.0)


def test_the_reference_case_meshed_factor_matches_the_phase10d_measurement():
    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    measured = meshed_winding_factor_for_case(case)
    evidence = json.loads((EV10D / "phase10d_winding_factor_truth.json").read_text(encoding="utf-8"))
    assert measured.value == pytest.approx(
        evidence["winding_factor_meshed_geometry"], rel=1e-12
    )
    # and it is materially different from what the case declares analytically.
    assert measured.value / case.winding.winding_factor_analytical > 1.05


def test_every_phase_of_a_balanced_winding_has_the_same_meshed_factor():
    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    values = [
        meshed_winding_factor_for_case(case, phase=p).value for p in ("A", "B", "C")
    ]
    # The phasor sums run over regions in different circumferential orders, so
    # the three results agree to floating-point rounding rather than bit-exactly.
    for value in values[1:]:
        assert value == pytest.approx(values[0], rel=1e-12)


def test_the_meshed_factor_is_deterministic():
    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    assert (
        meshed_winding_factor_for_case(case).value
        == meshed_winding_factor_for_case(case).value
    )


# ---------------------------------------------------------------------------
# The three winding concepts must stay distinct
# ---------------------------------------------------------------------------


def test_the_bridge_exposes_three_separately_named_winding_factors():
    from motor_calculator.fea.comparison import (
        _flux_inversion_winding_factor,
        _ideal_slot_star_winding_factor,
        _meshed_geometry_winding_factor,
    )

    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    entered = case.winding.winding_factor_analytical
    star = _ideal_slot_star_winding_factor(case)
    meshed = _meshed_geometry_winding_factor(case)
    assert star is not None and meshed is not None
    # The star and the meshed winding are different windings.
    assert star != pytest.approx(meshed, rel=1e-3)
    # The inversion must use the meshed one, not the entered or star value.
    assert _flux_inversion_winding_factor(case) == pytest.approx(meshed, rel=1e-15)
    assert _flux_inversion_winding_factor(case) != pytest.approx(entered, rel=1e-6)


def test_the_comparison_reports_the_superseded_star_as_its_own_row():
    from motor_calculator.fea.comparison import _ideal_slot_star_winding_factor

    case = build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    assert _ideal_slot_star_winding_factor(case) is not None


# ---------------------------------------------------------------------------
# Historical evidence must remain byte-identical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        EV10B / "fea_case.json",
        EV10B / "fea_raw_result.json",
        EV10B / "fea_comparison.json",
        EV10C / "fea_case.json",
        EV10C / "fea_raw_result.json",
        EV10C / "ke_error_decomposition.json",
    ],
)
def test_historical_evidence_files_are_not_rewritten(path: Path):
    """Phase 10E reinterprets old evidence; it must never edit it."""

    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload)
    # The historical records were produced under the slot-star interpretation
    # and must still say so.
    assert "0.955752" not in text, "a Phase 10E value has leaked into historical evidence"


def test_the_historical_decomposition_still_records_the_original_winding_factor():
    payload = json.loads((EV10C / "ke_error_decomposition.json").read_text(encoding="utf-8"))
    assert payload["geometry_winding_factor"] == pytest.approx(0.8660254037844386)
    assert payload["schema_version"] == "phase10c.fea.decomposition.v1"


# ---------------------------------------------------------------------------
# Diagnostics: evidence labels and the no-silent-correction rule
# ---------------------------------------------------------------------------


def _diagnostics(**overrides):
    kwargs = dict(
        fidelity_tier="FEA_TIER_3",
        ke_analytical=0.08396100209642851,
        ke_fea=0.08996782791281241,
        winding_factor_analytical=0.8660254037844386,
        winding_factor_meshed=0.955752007,
        winding_factor_ideal_star=0.8660254037844386,
        analytical_flat_top_flux_wb=0.0003429919194211033,
        fea_direct_fundamental_flux_wb=0.0003328081908,
        fea_linkage_derived_flux_wb=0.00036720466931433246,
    )
    kwargs.update(overrides)
    return build_validation_diagnostics(**kwargs)


def test_only_physically_measured_labels_may_be_styled_affirmatively():
    assert is_affirmative(EvidenceLabel.VALIDATED)
    assert is_affirmative(EvidenceLabel.EXPERIMENTAL_MEASUREMENT)
    for label in (
        EvidenceLabel.NUMERICAL_FEA,
        EvidenceLabel.NOT_YET_VALIDATED,
        EvidenceLabel.MODEL_LIMITATION,
        EvidenceLabel.DEFINITION_CONVENTION_MISMATCH,
        EvidenceLabel.DIAGNOSTIC_ONLY,
        EvidenceLabel.HISTORICAL_INTERPRETATION_SUPERSEDED,
    ):
        assert not is_affirmative(label), f"{label} must not read as validated"


def test_a_numerical_comparison_is_never_reported_as_experimental():
    diagnostics = _diagnostics()
    assert diagnostics.evidence_type == EvidenceLabel.NUMERICAL_FEA
    rendered = render_diagnostics_zh(diagnostics)
    assert EvidenceLabel.EXPERIMENTAL_MEASUREMENT not in [
        row.evidence for section in diagnostics.sections for row in section[1]
    ]
    assert "尚未进行" in rendered


def test_the_panel_never_offers_a_corrected_analytical_value():
    rendered = render_diagnostics_zh(_diagnostics())
    for forbidden in ("已修正", "修正后", "corrected"):
        assert forbidden not in rendered


def test_the_calibration_status_is_a_constant_none():
    assert CALIBRATION_STATUS == "NONE"
    assert _diagnostics().calibration_status == "NONE"
    assert "NONE" in render_diagnostics_zh(_diagnostics())


def test_the_star_row_is_marked_superseded_not_wrong():
    diagnostics = _diagnostics()
    labels = [row.evidence for row in diagnostics.winding]
    assert EvidenceLabel.HISTORICAL_INTERPRETATION_SUPERSEDED in labels
    assert EvidenceLabel.DEFINITION_CONVENTION_MISMATCH in labels


def test_missing_evidence_renders_as_missing_not_as_agreement():
    diagnostics = build_validation_diagnostics(
        fidelity_tier="FEA_TIER_3",
        ke_analytical=None,
        ke_fea=None,
        winding_factor_analytical=0.866,
        winding_factor_meshed=0.956,
    )
    assert not diagnostics.available
    rendered = render_diagnostics_zh(diagnostics)
    assert "尚无真实求解结果" in rendered
    assert "%" not in rendered


def test_a_mock_solver_result_is_refused_as_diagnostic_evidence():
    diagnostics = _diagnostics(is_mock=True)
    assert not diagnostics.available
    assert "模拟求解器" in (diagnostics.unavailable_reason_zh or "")


def test_the_unavailable_state_still_reports_calibration_status():
    rendered = render_diagnostics_zh(unavailable_diagnostics("测试原因"))
    assert "测试原因" in rendered
    assert "NONE" in rendered


def test_the_residual_section_says_so_when_no_budget_is_supplied():
    diagnostics = _diagnostics()
    assert any("尚未计算" in row.value for row in diagnostics.residual)


def test_a_supplied_budget_is_rendered_with_an_unresolved_remainder():
    budget = build_flux_residual_budget(
        winding_factor_meshed=0.955752007,
        winding_factor_assumed=0.8660254037844386,
        analytical_flat_top_flux_wb=0.0003429919194211033,
        fea_fundamental_flux_wb=0.0003328081908,
        pole_arc_coefficient=0.7,
        sine_emf_factor=4.44,
        observed_ke_ratio=1.071543045776,
    )
    diagnostics = _diagnostics(budget=budget)
    rendered = render_diagnostics_zh(diagnostics)
    assert "未解释余量" in rendered
    assert "绕组几何贡献" in rendered
    assert diagnostics.schema_version == DIAGNOSTICS_SCHEMA_VERSION


def test_diagnostics_rendering_is_deterministic():
    assert render_diagnostics_zh(_diagnostics()) == render_diagnostics_zh(_diagnostics())


# ---------------------------------------------------------------------------
# Cross-design replication evidence
# ---------------------------------------------------------------------------


def _replication():
    return json.loads((EV10E / "phase10e_replication.json").read_text(encoding="utf-8"))


def test_the_budget_closes_on_every_replicated_design():
    payload = _replication()
    assert len(payload["designs"]) >= 3
    for design in payload["designs"]:
        assert abs(design["budget"]["unresolved_remainder_percent"]) < 0.05, design["design"]


def test_the_low_cost_ke_route_was_validated_against_a_real_campaign():
    payload = _replication()
    assert abs(payload["ke_route_validation"]["agreement_percent"]) < 0.05
    # and the phase did not silently run a campaign per design.
    assert payload["new_femm_solves"] <= 3


def test_the_replication_records_no_calibration():
    payload = _replication()
    assert payload["diagnostic_only"] is True
    assert payload["calibration_performed"] is False


def test_the_pole_arc_convention_crossover_is_derived_not_asserted():
    payload = _replication()
    crossover = payload["convention_crossover_alpha_p"]
    # The crossover is where the conversion factor equals one, by definition.
    assert rectangular_to_fundamental_form_factor(crossover) == pytest.approx(1.0, abs=1e-9)
    assert rectangular_to_fundamental_form_factor(crossover - 0.05) > 1.0
    assert rectangular_to_fundamental_form_factor(crossover + 0.05) < 1.0


def test_the_convention_term_changes_sign_across_the_replicated_designs():
    designs = {d["alpha_p"]: d["budget"]["convention"] for d in _replication()["designs"]}
    below = [v for a, v in designs.items() if a < 0.747]
    above = [v for a, v in designs.items() if a > 0.748]
    assert below and above, "the matrix must straddle the crossover"
    assert all(v > 1.0 for v in below)
    assert all(v < 1.0 for v in above)


def test_peak_flux_density_agreement_does_not_generalise():
    """Phase 10D's -0.059 % was design-specific; the evidence must keep saying so."""

    designs = _replication()["designs"]
    spread = [abs(d["peak_b_agreement_percent"]) for d in designs]
    assert min(spread) < 0.5
    assert max(spread) > 3.0, "the replication is supposed to show this degrading"


def test_at_least_one_replicated_design_has_a_negative_residual():
    """A residual that changes sign cannot be a fixed bias to calibrate away."""

    residuals = [d["ke_residual_percent"] for d in _replication()["designs"]]
    assert any(r > 0 for r in residuals)
    assert any(r < 0 for r in residuals)


def test_the_winding_factor_gap_is_material_across_slot_pole_combinations():
    payload = json.loads(
        (EV10E / "phase10e_winding_generalization.json").read_text(encoding="utf-8")
    )
    assert payload["femm_solves"] == 0
    assert payload["all_exceed_one_percent"] is True
    assert len(payload["combinations"]) >= 6
    # The direction is NOT universal, and the evidence must record that honestly
    # rather than implying a fixed-sign correction would work.
    assert payload["all_same_direction"] is False


# ---------------------------------------------------------------------------
# Production physics and defaults
# ---------------------------------------------------------------------------


def test_production_physics_is_untouched_by_phase10e():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"


def test_phase10e_did_not_mutate_any_production_default():
    from motor_calculator.fea.reference_cases import PHASE10A_REFERENCE_PARAMETERS

    assert PHASE10A_REFERENCE_PARAMETERS["sigma_m"] == 1.15
    assert PHASE10A_REFERENCE_PARAMETERS["alpha_p"] == 0.7
    assert PHASE10A_REFERENCE_PARAMETERS["h_coil"] == 5.0
    assert PHASE10A_REFERENCE_PARAMETERS["mu_r_mag"] == 1.05


def test_auto_calibration_remains_disabled():
    from motor_calculator.fea.comparison import AUTO_CALIBRATION_ENABLED

    assert AUTO_CALIBRATION_ENABLED is False


def test_the_packaged_build_declares_the_lazily_imported_bridge_module():
    """comparison.py imports meshed_winding inside a function, so PyInstaller
    cannot see it; without the explicit hidden import the packaged build would
    fall back to the entered winding factor silently."""

    spec = (REPOSITORY_ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    assert "motor_calculator.fea.meshed_winding" in spec
    assert "motor_calculator.fea.diagnostics" in spec
