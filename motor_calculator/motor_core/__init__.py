"""Public API for the refactored motor core."""

from .calculations import LegacyGuiMotorModelBridge, MotorAnalysisEngine, calculate_from_legacy_params
from .electrical_semantics import MotorControlMode, MotorSemanticsError, normalize_motor_control_mode
from .models import AnalysisResult, MotorAnalysisInput
from .pmsm_ke_kt_models import (
    calculate_mechanical_power_from_torque_and_speed_w,
    calculate_pmsm_three_phase_electromagnetic_power_w,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed,
    compare_legacy_and_revised_pmsm_ke_kt,
    derive_revised_pmsm_torque_constants_from_power_balance,
)
from .rated_torque_models import calculate_legacy_rated_torque_nm, calculate_revised_rated_torque_nm, compare_rated_torque_models
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
    "calculate_mechanical_power_from_torque_and_speed_w",
    "calculate_from_legacy_params",
    "calculate_legacy_rated_torque_nm",
    "calculate_pmsm_three_phase_electromagnetic_power_w",
    "calculate_revised_rated_torque_nm",
    "calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed",
    "calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed",
    "compare_rated_torque_models",
    "compare_legacy_and_revised_pmsm_ke_kt",
    "derive_revised_pmsm_torque_constants_from_power_balance",
    "legacy_params_to_model_input",
    "normalize_motor_control_mode",
    "parse_legacy_gui_params",
]
