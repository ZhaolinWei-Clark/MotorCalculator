"""Public API for the refactored motor core."""

from .calculations import LegacyGuiMotorModelBridge, MotorAnalysisEngine, calculate_from_legacy_params
from .models import AnalysisResult, MotorAnalysisInput
from .units import legacy_params_to_model_input
from .validation import MotorCalculationError, MotorCalculatorError, MotorValidationError, parse_legacy_gui_params

__all__ = [
    "AnalysisResult",
    "LegacyGuiMotorModelBridge",
    "MotorAnalysisEngine",
    "MotorAnalysisInput",
    "MotorCalculationError",
    "MotorCalculatorError",
    "MotorValidationError",
    "calculate_from_legacy_params",
    "legacy_params_to_model_input",
    "parse_legacy_gui_params",
]
