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
from .winding_network import (
    AFPMWindingNetwork,
    PhaseConnection,
    StatorConnection,
    StatorEMFCombination,
    WindingFactorMethod,
    WindingFactorResolution,
)

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
    "AFPMWindingNetwork",
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
    "PhaseConnection",
    "RadialMagnetSample",
    "RadialSliceBackEMFModel",
    "RadialSliceBackEMFResult",
    "RadialSliceInputError",
    "TorqueBoundary",
    "TorqueSemantics",
    "StatorConnection",
    "StatorEMFCombination",
    "WaveformFamily",
    "WindingType",
    "WindingFactorMethod",
    "WindingFactorResolution",
    "adapt_reconstructed_case",
    "build_synthetic_radial_reference_case",
    "convergence_study",
    "load_advanced_afpm_cases",
]
