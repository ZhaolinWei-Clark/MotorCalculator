"""Input presentation, interaction, and engineering-guidance helpers."""

from .controls import (
    SLIDER_SPECS,
    SliderSpec,
    SliderSyncResult,
    parse_spinbox_integer,
    slider_from_numeric_text,
    slider_range_for_units,
    slider_to_numeric_text,
)
from .guidance import GuidanceIssue, GuidanceLevel, GuidanceSeverity, evaluate_input_guidance
from .metadata import (
    APPLICATION_DEFAULTS,
    BASIC_INPUT_FIELDS,
    INPUT_DEFINITIONS,
    InputControlType,
    InputDefinition,
)
from .units import (
    DisplayUnitPreferences,
    canonical_to_display_inputs,
    convert_display_value,
    display_to_canonical_inputs,
    format_engineering_value,
)

__all__ = [
    "APPLICATION_DEFAULTS",
    "BASIC_INPUT_FIELDS",
    "DisplayUnitPreferences",
    "GuidanceIssue",
    "GuidanceLevel",
    "GuidanceSeverity",
    "INPUT_DEFINITIONS",
    "InputControlType",
    "InputDefinition",
    "SLIDER_SPECS",
    "SliderSpec",
    "SliderSyncResult",
    "canonical_to_display_inputs",
    "convert_display_value",
    "display_to_canonical_inputs",
    "evaluate_input_guidance",
    "format_engineering_value",
    "parse_spinbox_integer",
    "slider_from_numeric_text",
    "slider_range_for_units",
    "slider_to_numeric_text",
]
