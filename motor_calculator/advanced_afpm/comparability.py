"""Plan source-native comparisons against the sinusoidal sandbox prototype."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .completeness import AFPMCompletenessGate, AFPMTargetMetric, CompletenessStatus
from .electrical import BackEMFScope, BackEMFValueKind, WaveformFamily
from .source_adapter import AdvancedAFPMCase


class ComparabilityLevel(str, Enum):
    DIRECT = "DIRECT"
    SAFE_TRANSFORM = "SAFE_TRANSFORM"
    APPROXIMATE = "APPROXIMATE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ComparabilityPlan:
    target_metric: AFPMTargetMetric
    level: ComparabilityLevel
    reasoning: tuple[str, ...]
    required_physics_path: str
    transformation: str | None = None


class AFPMComparabilityPlanner:
    def __init__(self, completeness_gate: AFPMCompletenessGate | None = None):
        self.completeness_gate = completeness_gate or AFPMCompletenessGate()

    def plan(self, case: AdvancedAFPMCase, target_metric: AFPMTargetMetric | str) -> ComparabilityPlan:
        metric = AFPMTargetMetric(target_metric)
        completeness = self.completeness_gate.evaluate(case, metric)
        physics_path = (
            "advanced_afpm.radial_slice_back_emf"
            if metric is AFPMTargetMetric.BACK_EMF
            else f"not_implemented:{metric.value}_physics"
        )
        if completeness.status is not CompletenessStatus.READY:
            semantic_reasons = ()
            semantics = case.back_emf_semantics
            if metric is AFPMTargetMetric.BACK_EMF and semantics is not None:
                if semantics.waveform_family is not WaveformFamily.SINUSOIDAL:
                    semantic_reasons = (
                        "semantic: prototype predicts sinusoidal fundamental RMS only",
                        f"semantic: source waveform is {semantics.waveform_family.value}/{semantics.value_kind.value}",
                    )
            return ComparabilityPlan(
                metric,
                ComparabilityLevel.BLOCKED,
                (f"completeness={completeness.status.value}", *completeness.missing_fields, *semantic_reasons),
                physics_path,
            )
        semantics = case.back_emf_semantics
        if semantics is None:
            return ComparabilityPlan(metric, ComparabilityLevel.BLOCKED, ("back-EMF semantics unavailable",), physics_path)
        if semantics.waveform_family is not WaveformFamily.SINUSOIDAL:
            return ComparabilityPlan(
                metric,
                ComparabilityLevel.BLOCKED,
                ("prototype predicts sinusoidal fundamental RMS only", "source waveform is not sinusoidal"),
                physics_path,
            )
        if semantics.scope is BackEMFScope.PHASE and semantics.value_kind in {
            BackEMFValueKind.RMS,
            BackEMFValueKind.FUNDAMENTAL_RMS,
        }:
            return ComparabilityPlan(metric, ComparabilityLevel.DIRECT, ("phase fundamental RMS semantics match",), physics_path)
        if semantics.scope is BackEMFScope.PHASE and semantics.value_kind is BackEMFValueKind.PEAK:
            return ComparabilityPlan(
                metric,
                ComparabilityLevel.SAFE_TRANSFORM,
                ("sinusoidal phase RMS-to-peak conversion is explicit",),
                physics_path,
                "phase_peak_v = sqrt(2) * phase_fundamental_rms_v",
            )
        if semantics.scope is BackEMFScope.LINE and case.winding.connection in {"Y", "star"}:
            return ComparabilityPlan(
                metric,
                ComparabilityLevel.SAFE_TRANSFORM,
                ("known Y connection permits phase-to-line conversion",),
                physics_path,
                "line_rms_v = sqrt(3) * phase_fundamental_rms_v",
            )
        return ComparabilityPlan(
            metric,
            ComparabilityLevel.BLOCKED,
            ("source-native quantity is outside approved transformations",),
            physics_path,
        )
