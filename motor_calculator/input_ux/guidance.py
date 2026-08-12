"""Non-formula input guidance layered over existing production validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from motor_calculator.motor_core.units import legacy_params_to_model_input
from motor_calculator.motor_core.validation import (
    MotorValidationError,
    parse_legacy_gui_params,
    validate_motor_input,
)


class GuidanceLevel(str, Enum):
    NORMAL = "NORMAL"
    CHECK = "CHECK"
    UNUSUAL = "UNUSUAL"
    INVALID = "INVALID"


class GuidanceSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class GuidanceIssue:
    level: GuidanceLevel
    severity: GuidanceSeverity
    field_names: tuple[str, ...]
    message: str
    blocks_calculation: bool


def evaluate_input_guidance(canonical_inputs: Mapping[str, Any]) -> tuple[GuidanceIssue, ...]:
    try:
        parsed = parse_legacy_gui_params(canonical_inputs)
        validate_motor_input(legacy_params_to_model_input(parsed))
    except (MotorValidationError, TypeError, ValueError) as exc:
        return (GuidanceIssue(GuidanceLevel.INVALID, GuidanceSeverity.ERROR, (), str(exc), True),)
    issues: list[GuidanceIssue] = []
    if float(parsed["g_side"]) > 5.0:
        issues.append(GuidanceIssue(
            GuidanceLevel.UNUSUAL, GuidanceSeverity.INFO, ("g_side",),
            "Air gap is outside the typical quick-adjust range; the value is preserved and remains calculable.", False,
        ))
    if float(parsed["n_rated"]) > 10000.0:
        issues.append(GuidanceIssue(
            GuidanceLevel.CHECK, GuidanceSeverity.WARNING, ("n_rated",),
            "Rated speed is above the guided display range; review mechanical and voltage assumptions.", False,
        ))
    if float(parsed["Temp_coil"]) > 150.0 or float(parsed["Temp_coil"]) < -40.0:
        issues.append(GuidanceIssue(
            GuidanceLevel.UNUSUAL, GuidanceSeverity.WARNING, ("Temp_coil",),
            "Winding temperature is unusual for the current reference guidance; verify materials and conditions.", False,
        ))
    if float(parsed["k_w"]) < 0.5:
        issues.append(GuidanceIssue(
            GuidanceLevel.CHECK, GuidanceSeverity.INFO, ("k_w",),
            "Low winding factor is valid but deserves review of pitch/distribution semantics.", False,
        ))
    if not issues:
        issues.append(GuidanceIssue(
            GuidanceLevel.NORMAL, GuidanceSeverity.INFO, (),
            "Inputs pass existing model validation and no soft guidance threshold is triggered.", False,
        ))
    return tuple(issues)
