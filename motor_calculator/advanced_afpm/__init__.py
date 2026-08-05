"""Sandbox-only advanced AFPM representation and radial back-EMF API."""

from .comparability import AFPMComparabilityPlanner, ComparabilityLevel, ComparabilityPlan
from .completeness import AFPMCompletenessGate, AFPMTargetMetric, CompletenessResult, CompletenessStatus
from .electrical import (
    AFPMInductance,
    BackEMFScope,
    BackEMFSemantics,
    BackEMFValueKind,
    WaveformFamily,
)
from .geometry import AFPMGeometry, RadialMagnetSample
from .radial_slice_back_emf import (
    ConvergencePoint,
    MeanRadiusBackEMFResult,
    RadialSliceBackEMFModel,
    RadialSliceBackEMFResult,
    RadialSliceInputError,
    build_synthetic_radial_reference_case,
    convergence_study,
)
from .source_adapter import (
    AFPMFieldRecord,
    AFPMFieldStatus,
    AdvancedAFPMCase,
    adapt_reconstructed_case,
    load_advanced_afpm_cases,
)
from .topology import AFPMTopology, AFPMTopologyType
from .torque_semantics import TorqueBoundary, TorqueSemantics
from .winding import AFPMWinding, WindingType

__all__ = [
    "AFPMComparabilityPlanner",
    "AFPMCompletenessGate",
    "AFPMFieldRecord",
    "AFPMFieldStatus",
    "AFPMGeometry",
    "AFPMInductance",
    "AFPMTargetMetric",
    "AFPMTopology",
    "AFPMTopologyType",
    "AFPMWinding",
    "AdvancedAFPMCase",
    "BackEMFScope",
    "BackEMFSemantics",
    "BackEMFValueKind",
    "ComparabilityLevel",
    "ComparabilityPlan",
    "CompletenessResult",
    "CompletenessStatus",
    "ConvergencePoint",
    "MeanRadiusBackEMFResult",
    "RadialMagnetSample",
    "RadialSliceBackEMFModel",
    "RadialSliceBackEMFResult",
    "RadialSliceInputError",
    "TorqueBoundary",
    "TorqueSemantics",
    "WaveformFamily",
    "WindingType",
    "adapt_reconstructed_case",
    "build_synthetic_radial_reference_case",
    "convergence_study",
    "load_advanced_afpm_cases",
]
