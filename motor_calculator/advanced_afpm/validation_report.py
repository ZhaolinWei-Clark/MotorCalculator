"""Deterministic Phase 7E source evaluation and Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .comparability import AFPMComparabilityPlanner, ComparabilityLevel
from .completeness import AFPMCompletenessGate, AFPMTargetMetric
from .electrical import BackEMFScope, BackEMFValueKind, WaveformFamily
from .radial_slice_back_emf import RadialSliceBackEMFModel
from .source_adapter import AdvancedAFPMCase


@dataclass(frozen=True)
class ExternalBackEMFValidationRow:
    source_id: str
    topology: str
    completeness_status: str
    comparability_level: str
    slice_count: int
    radial_slice_inputs_used: tuple[str, ...]
    semantic_compatibility: str
    predicted_value: float | None
    reference_value: float | None
    reference_unit: str | None
    absolute_error: float | None
    relative_error_percent: float | None
    remaining_blockers: tuple[str, ...]
    provenance: str


def evaluate_external_back_emf_cases(
    cases: tuple[AdvancedAFPMCase, ...],
    *,
    slice_count: int = 100,
) -> tuple[ExternalBackEMFValidationRow, ...]:
    gate = AFPMCompletenessGate()
    planner = AFPMComparabilityPlanner(gate)
    model = RadialSliceBackEMFModel()
    rows = []
    for case in cases:
        completeness = gate.evaluate(case, AFPMTargetMetric.BACK_EMF)
        plan = planner.plan(case, AFPMTargetMetric.BACK_EMF)
        reference = case.source_field(case.back_emf_reference_field) if case.back_emf_reference_field else None
        predicted = None
        absolute_error = None
        relative_error = None
        blockers = tuple(dict.fromkeys((*completeness.missing_fields, *plan.reasoning)))
        if plan.level in {ComparabilityLevel.DIRECT, ComparabilityLevel.SAFE_TRANSFORM}:
            predicted = model.compute(case, slice_count=slice_count).phase_fundamental_rms_v
            if plan.transformation and "sqrt(2)" in plan.transformation:
                predicted *= math.sqrt(2.0)
            elif plan.transformation and "sqrt(3)" in plan.transformation:
                predicted *= math.sqrt(3.0)
            absolute_error = abs(predicted - float(reference.value))
            relative_error = absolute_error / abs(float(reference.value)) * 100.0
            blockers = ()
        provenance = "unavailable"
        if reference is not None:
            provenance = f"{reference.source_url}; {reference.page}; {reference.location}"
        rows.append(ExternalBackEMFValidationRow(
            source_id=case.source_id,
            topology=case.topology.topology_type.name,
            completeness_status=completeness.status.value,
            comparability_level=plan.level.value,
            slice_count=slice_count,
            radial_slice_inputs_used=completeness.available_fields,
            semantic_compatibility=_semantic_compatibility(case),
            predicted_value=predicted,
            reference_value=None if reference is None or not reference.is_usable else float(reference.value),
            reference_unit=None if reference is None else reference.unit,
            absolute_error=absolute_error,
            relative_error_percent=relative_error,
            remaining_blockers=blockers,
            provenance=provenance,
        ))
    return tuple(rows)


def _semantic_compatibility(case: AdvancedAFPMCase) -> str:
    semantics = case.back_emf_semantics
    if semantics is None:
        return "BLOCKED: source semantics unavailable"
    if semantics.waveform_family is not WaveformFamily.SINUSOIDAL:
        return (
            "BLOCKED: sinusoidal fundamental prototype cannot represent "
            f"{semantics.waveform_family.value}/{semantics.value_kind.value}"
        )
    if semantics.scope is BackEMFScope.PHASE and semantics.value_kind in {
        BackEMFValueKind.RMS,
        BackEMFValueKind.FUNDAMENTAL_RMS,
    }:
        return "DIRECT if completeness becomes READY"
    if semantics.scope is BackEMFScope.PHASE and semantics.value_kind is BackEMFValueKind.PEAK:
        return "SAFE_TRANSFORM if READY: sinusoidal phase RMS to phase peak"
    return "BLOCKED: source-native semantics outside approved transformations"


def render_external_back_emf_report(rows: tuple[ExternalBackEMFValidationRow, ...]) -> str:
    lines = [
        "# Phase 7E Advanced AFPM Back-EMF Validation",
        "",
        "本报告来自 opt-in sandbox；不校准、不补 production defaults、不修改 legacy outputs。",
        "",
        "| source | topology | completeness | inputs represented | semantics | comparability | N | predicted | reference | error | blockers | provenance |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        predicted = "BLOCKED" if row.predicted_value is None else f"{row.predicted_value:.6f}"
        reference = "UNAVAILABLE" if row.reference_value is None else f"{row.reference_value:.6f} {row.reference_unit or ''}".strip()
        error = "N/A" if row.relative_error_percent is None else f"{row.relative_error_percent:.6f}%"
        blockers = "; ".join(row.remaining_blockers) or "none"
        inputs = "; ".join(row.radial_slice_inputs_used) or "none"
        lines.append(
            f"| {row.source_id} | {row.topology} | {row.completeness_status} | {inputs} | "
            f"{row.semantic_compatibility} | {row.comparability_level} | {row.slice_count} | {predicted} | {reference} | "
            f"{error} | {blockers} | {row.provenance} |"
        )
    lines.extend((
        "",
        "## Decision",
        "",
        "Only DIRECT or approved SAFE_TRANSFORM rows may report model error. BLOCKED rows preserve their source values and provenance without a prediction.",
        "",
    ))
    return "\n".join(lines)
