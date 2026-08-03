"""Phase 6A calibration sandbox package.

This package is intentionally outside ``motor_core`` so sensitivity exploration
cannot become part of the production calculation chain by accident.
"""

from .perturbation import PerturbationSpec, SensitivityTarget
from .reports import generate_sensitivity_markdown_report, write_sensitivity_markdown_report
from .sensitivity import (
    SensitivityOutputChange,
    SensitivityRunResult,
    SensitivitySandboxError,
    SensitivitySummary,
    get_default_sensitivity_targets,
    run_sensitivity_case,
    run_sensitivity_sweep,
)

__all__ = [
    "PerturbationSpec",
    "SensitivityOutputChange",
    "SensitivityRunResult",
    "SensitivitySandboxError",
    "SensitivitySummary",
    "SensitivityTarget",
    "generate_sensitivity_markdown_report",
    "get_default_sensitivity_targets",
    "run_sensitivity_case",
    "run_sensitivity_sweep",
    "write_sensitivity_markdown_report",
]
