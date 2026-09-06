"""Phase 10A FEMM validation bridge.

MotorCalculator analytical result
  -> structured validation case
  -> FEMM model generation
  -> FEMM execution when available
  -> FEMM result extraction
  -> analytical vs FEA comparison
  -> validation evidence record
  -> engineering validation report

Importing this package never requires FEMM, and never touches the analytical
kernel. Nothing here calibrates, fits or corrects an analytical parameter.
"""

from .adapter import (
    FEASolveOutcome,
    FEASolver,
    FEASolverExecutionError,
    FEMMSubprocessSolver,
    MockFEASolver,
    default_workspace_root,
    generate_case_scripts,
    parse_samples_csv,
)
from .availability import (
    FEMMAvailability,
    FEMMAvailabilityReport,
    FEMMIntegrationPath,
    detect_femm,
)
from .bringup import (
    FEABringUpOutcome,
    build_bringup_script,
    evaluate_bringup_checks,
    parse_bringup_output,
    run_bringup,
)
from .case_builder import (
    FEAModellingParameters,
    assess_supportability,
    build_mesh_policy,
    build_slice_geometry,
    build_validation_case,
)
from .comparison import (
    AUTO_CALIBRATION_ENABLED,
    FEAComparisonReport,
    FEAMetricComparison,
    FEASampleStatistics,
    build_comparison,
    compare_metric,
    sample_statistics,
)
from .evidence import (
    CONFIDENCE_POLICY_STATEMENT,
    FEAEvidenceRecord,
    build_evidence_record,
    numerical_confidence_statement,
    worst_status,
)
from .export import (
    export_bundle,
    export_case_json,
    export_comparison_csv,
    export_comparison_json,
    export_raw_result_json,
    export_raw_samples_csv,
    plot_series,
)
from .geometry import (
    FEARegion,
    FEASliceModel,
    build_slice_model,
    cogging_period_mech_deg,
    derive_symmetry_plan,
    machine_periodicity,
)
from .hashing import compute_analytical_fingerprint, compute_case_hash
from .materials import build_material_set
from .models import (
    FEA_CASE_SCHEMA_VERSION,
    FEAAnalyticalPrediction,
    FEAComparisonStatus,
    FEACoreModelPolicy,
    FEAMaterialSet,
    FEAMeshPolicy,
    FEAOperatingPoint,
    FEASupportability,
    FEASupportabilityReport,
    FEASymmetryPlan,
    FEAUnrolledSliceGeometry,
    FEAValidationCase,
    FEAValidationTarget,
    FEAWindingMap,
)
from .report import render_case_review_zh, render_comparison_zh, render_run_zh
from .results import (
    FEABackEmfExtraction,
    FEACoggingExtraction,
    FEAPositionSample,
    FEARawResult,
    FEAResultProvenance,
    FEATorqueExtraction,
    extract_average_torque,
    extract_back_emf,
    extract_cogging,
)
from .sampling import FEAAngleSamplingPlan, plan_angle_sampling
from .serialization import case_from_dict, case_to_dict
from .service import (
    SOLVER_UNAVAILABLE_MESSAGE_ZH,
    FEACasePreview,
    FEAValidationRun,
    export_scripts_only,
    preview_case,
    run_validation,
)
from .winding import allocate_all_phases, build_winding_map

__all__ = [
    "AUTO_CALIBRATION_ENABLED",
    "CONFIDENCE_POLICY_STATEMENT",
    "FEAAnalyticalPrediction",
    "FEAAngleSamplingPlan",
    "FEABackEmfExtraction",
    "FEABringUpOutcome",
    "FEACasePreview",
    "FEACoggingExtraction",
    "FEAComparisonReport",
    "FEAComparisonStatus",
    "FEACoreModelPolicy",
    "FEAEvidenceRecord",
    "FEAMaterialSet",
    "FEAMeshPolicy",
    "FEAMetricComparison",
    "FEAModellingParameters",
    "FEAOperatingPoint",
    "FEAPositionSample",
    "FEARawResult",
    "FEARegion",
    "FEAResultProvenance",
    "FEASampleStatistics",
    "FEASliceModel",
    "FEASolveOutcome",
    "FEASolver",
    "FEASolverExecutionError",
    "FEASupportability",
    "FEASupportabilityReport",
    "FEASymmetryPlan",
    "FEATorqueExtraction",
    "FEAUnrolledSliceGeometry",
    "FEAValidationCase",
    "FEAValidationRun",
    "FEAValidationTarget",
    "FEAWindingMap",
    "FEA_CASE_SCHEMA_VERSION",
    "FEMMAvailability",
    "FEMMAvailabilityReport",
    "FEMMIntegrationPath",
    "FEMMSubprocessSolver",
    "MockFEASolver",
    "SOLVER_UNAVAILABLE_MESSAGE_ZH",
    "allocate_all_phases",
    "assess_supportability",
    "build_bringup_script",
    "build_comparison",
    "build_evidence_record",
    "build_material_set",
    "build_mesh_policy",
    "build_slice_geometry",
    "build_slice_model",
    "build_validation_case",
    "build_winding_map",
    "case_from_dict",
    "case_to_dict",
    "cogging_period_mech_deg",
    "compare_metric",
    "compute_analytical_fingerprint",
    "compute_case_hash",
    "default_workspace_root",
    "derive_symmetry_plan",
    "detect_femm",
    "evaluate_bringup_checks",
    "export_bundle",
    "export_case_json",
    "export_comparison_csv",
    "export_comparison_json",
    "export_raw_result_json",
    "export_raw_samples_csv",
    "export_scripts_only",
    "extract_average_torque",
    "extract_back_emf",
    "extract_cogging",
    "generate_case_scripts",
    "machine_periodicity",
    "numerical_confidence_statement",
    "parse_bringup_output",
    "parse_samples_csv",
    "plan_angle_sampling",
    "plot_series",
    "preview_case",
    "render_case_review_zh",
    "render_comparison_zh",
    "render_run_zh",
    "run_bringup",
    "run_validation",
    "sample_statistics",
    "worst_status",
]
