"""Lightweight offline localization for user-facing application text."""

from .translator import (
    DEFAULT_LOCALE,
    available_locales,
    get_locale,
    input_label,
    input_tooltip,
    localize_message,
    localize_status,
    metric_label,
    parameter_label,
    preset_name,
    semantic_label,
    semantic_value,
    set_locale,
    tr,
)

__all__ = [
    "DEFAULT_LOCALE",
    "available_locales",
    "get_locale",
    "input_label",
    "input_tooltip",
    "localize_message",
    "localize_status",
    "metric_label",
    "parameter_label",
    "preset_name",
    "semantic_label",
    "semantic_value",
    "set_locale",
    "tr",
]
