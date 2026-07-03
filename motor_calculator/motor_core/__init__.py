"""Public API for the refactored motor core."""

from .calculations import LegacyGuiMotorModelBridge, MotorAnalysisEngine, calculate_from_legacy_params
from .bldc_ke_kt_models import (
    calculate_bldc_average_electromagnetic_power_from_numeric_integration_w,
    calculate_bldc_average_electromagnetic_power_w,
    calculate_bldc_conduction_current_from_phase_rms_current,
    calculate_bldc_line_current_rms_from_conduction_current,
    calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v,
    calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v,
    calculate_bldc_phase_back_emf_rms_from_flat_top_v,
    calculate_bldc_phase_current_rms_from_conduction_current,
    compare_legacy_and_revised_bldc_ke_kt,
    normalized_bldc_average_electromagnetic_power,
    normalized_bldc_line_to_line_back_emf,
    normalized_bldc_line_to_line_back_emf_rms,
    normalized_bldc_phase_back_emf,
    normalized_bldc_phase_back_emf_rms,
    normalized_bldc_phase_current,
    normalized_bldc_phase_current_rms,
    require_bldc_control_mode,
)
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
    "calculate_bldc_average_electromagnetic_power_from_numeric_integration_w",
    "calculate_bldc_average_electromagnetic_power_w",
    "calculate_bldc_conduction_current_from_phase_rms_current",
    "calculate_bldc_line_current_rms_from_conduction_current",
    "calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v",
    "calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v",
    "calculate_bldc_phase_back_emf_rms_from_flat_top_v",
    "calculate_bldc_phase_current_rms_from_conduction_current",
    "calculate_mechanical_power_from_torque_and_speed_w",
    "calculate_from_legacy_params",
    "calculate_legacy_rated_torque_nm",
    "calculate_pmsm_three_phase_electromagnetic_power_w",
    "calculate_revised_rated_torque_nm",
    "compare_legacy_and_revised_bldc_ke_kt",
    "calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed",
    "calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed",
    "compare_rated_torque_models",
    "compare_legacy_and_revised_pmsm_ke_kt",
    "derive_revised_pmsm_torque_constants_from_power_balance",
    "legacy_params_to_model_input",
    "normalized_bldc_average_electromagnetic_power",
    "normalized_bldc_line_to_line_back_emf",
    "normalized_bldc_line_to_line_back_emf_rms",
    "normalized_bldc_phase_back_emf",
    "normalized_bldc_phase_back_emf_rms",
    "normalized_bldc_phase_current",
    "normalized_bldc_phase_current_rms",
    "normalize_motor_control_mode",
    "parse_legacy_gui_params",
    "require_bldc_control_mode",
]
