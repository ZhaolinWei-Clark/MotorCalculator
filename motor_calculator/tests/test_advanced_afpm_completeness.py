from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from advanced_afpm import (
    AFPMComparabilityPlanner,
    AFPMCompletenessGate,
    AFPMFieldRecord,
    AFPMFieldStatus,
    AFPMTargetMetric,
    BackEMFValueKind,
    ComparabilityLevel,
    CompletenessStatus,
    build_synthetic_radial_reference_case,
    load_advanced_afpm_cases,
)
from advanced_afpm.validation_report import evaluate_external_back_emf_cases, render_external_back_emf_report


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "validation_data" / "reconstructed_cases"


def _cases():
    return {case.source_id: case for case in load_advanced_afpm_cases(CASE_DIR)}


def test_back_emf_completeness_is_blocked_with_exact_missing_fields() -> None:
    gate = AFPMCompletenessGate()
    results = {
        source_id: gate.evaluate(case, AFPMTargetMetric.BACK_EMF)
        for source_id, case in _cases().items()
    }

    assert all(result.status is CompletenessStatus.BLOCKED for result in results.values())
    assert "geometry.magnet_coverage" in results["parviainen_2005_afpm_prototype"].missing_fields
    assert "winding.turns_per_phase" in results["hosseini_2008_coreless_afpm_generator"].missing_fields
    assert "material.remanence_t" in results["price_2009_coreless_afpm_generator"].missing_fields
    assert "back_emf.external_reference" in results["abdelli_2026_dssr_afpm"].missing_fields


def test_non_back_emf_metrics_report_partial_or_blocked_without_claiming_physics() -> None:
    gate = AFPMCompletenessGate()
    cases = _cases()

    assert gate.evaluate(cases["parviainen_2005_afpm_prototype"], "inductance").status is CompletenessStatus.PARTIAL
    assert gate.evaluate(cases["price_2009_coreless_afpm_generator"], "torque").status is CompletenessStatus.PARTIAL
    assert gate.evaluate(cases["abdelli_2026_dssr_afpm"], "efficiency").status is CompletenessStatus.BLOCKED


def test_comparability_planner_blocks_all_external_back_emf_rows() -> None:
    planner = AFPMComparabilityPlanner()

    plans = tuple(planner.plan(case, "back_emf") for case in _cases().values())

    assert all(plan.level is ComparabilityLevel.BLOCKED for plan in plans)
    assert all(plan.required_physics_path == "advanced_afpm.radial_slice_back_emf" for plan in plans)


def test_complete_synthetic_case_exercises_direct_and_safe_transform_plans() -> None:
    base = build_synthetic_radial_reference_case()
    reference = AFPMFieldRecord(
        AFPMFieldStatus.SOURCE_PROVIDED,
        28.9,
        "V phase fundamental RMS",
        "internal://phase7e",
        "analytical case",
        "synthetic reference",
        "Not external evidence.",
    )
    complete = replace(
        base,
        back_emf_reference_field="back_emf_reference",
        source_fields=MappingProxyType({"back_emf_reference": reference}),
    )
    planner = AFPMComparabilityPlanner()

    assert planner.plan(complete, "back_emf").level is ComparabilityLevel.DIRECT
    peak_case = replace(
        complete,
        back_emf_semantics=replace(complete.back_emf_semantics, value_kind=BackEMFValueKind.PEAK),
    )
    peak_plan = planner.plan(peak_case, "back_emf")
    assert peak_plan.level is ComparabilityLevel.SAFE_TRANSFORM
    assert "sqrt(2)" in peak_plan.transformation


def test_external_report_is_deterministic_and_does_not_emit_errors_for_blocked_rows() -> None:
    cases = tuple(_cases().values())
    first = evaluate_external_back_emf_cases(cases)
    second = evaluate_external_back_emf_cases(cases)

    assert first == second
    assert render_external_back_emf_report(first) == render_external_back_emf_report(second)
    assert all(row.predicted_value is None for row in first)
    assert all(row.relative_error_percent is None for row in first)
    assert sum(row.comparability_level in {"DIRECT", "SAFE_TRANSFORM"} for row in first) == 0
    by_source = {row.source_id: row for row in first}
    assert "flattened" in by_source["parviainen_2005_afpm_prototype"].semantic_compatibility
    assert "SAFE_TRANSFORM if READY" in by_source["price_2009_coreless_afpm_generator"].semantic_compatibility
