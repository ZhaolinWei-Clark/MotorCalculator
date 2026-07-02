"""Public API for the refactored motor core."""

from .calculations import LegacyGuiMotorModelBridge, MotorAnalysisEngine, calculate_from_legacy_params
from .electrical_semantics import MotorControlMode, MotorSemanticsError, normalize_motor_control_mode
from .models import AnalysisResult, MotorAnalysisInput
from .units import legacy_params_to_model_input
from .validation import MotorCalculationError, MotorCalculatorError, MotorValidationError, parse_legacy_gui_params

__all__ = [
    "AnalysisResult",
    "LegacyGuiMotorModelBridge",
    "MotorAnalysisEngine",
    "MotorAnalysisInput",
    "MotorControlMode",
    "MotorCalculationError",
    "MotorCalculatorError",
    "MotorSemanticsError",
    "MotorValidationError",
    "calculate_from_legacy_params",
    "legacy_params_to_model_input",
    "normalize_motor_control_mode",
    "parse_legacy_gui_params",
]
