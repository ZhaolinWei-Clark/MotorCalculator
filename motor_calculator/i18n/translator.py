"""Stable-key translator with Simplified Chinese as the offline default."""

from __future__ import annotations

from typing import Any

from . import strings_en_US, strings_zh_CN

DEFAULT_LOCALE = "zh_CN"
_RESOURCES = {
    "zh_CN": strings_zh_CN,
    "en_US": strings_en_US,
}
_locale = DEFAULT_LOCALE


def available_locales() -> tuple[str, ...]:
    return tuple(_RESOURCES)


def get_locale() -> str:
    return _locale


def set_locale(locale: str) -> None:
    if locale not in _RESOURCES:
        raise ValueError(f"Unsupported locale: {locale}")
    global _locale
    _locale = locale


def tr(key: str, *, locale: str | None = None, default: str | None = None, **values: Any) -> str:
    resource = _RESOURCES[locale or _locale]
    text = resource.STRINGS.get(key)
    if text is None:
        text = strings_en_US.STRINGS.get(key, default)
    if text is None:
        raise KeyError(f"Unknown localization key: {key}")
    return text.format(**values)


def input_label(field_name: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    labels = getattr(resource, "INPUT_LABELS", {})
    if field_name in labels:
        return labels[field_name]
    from motor_calculator.input_ux.metadata import INPUT_DEFINITIONS

    return INPUT_DEFINITIONS[field_name].gui_label


def input_tooltip(field_name: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    tooltips = getattr(resource, "INPUT_TOOLTIPS", {})
    if field_name in tooltips:
        return tooltips[field_name]
    from motor_calculator.input_ux.metadata import INPUT_DEFINITIONS

    return INPUT_DEFINITIONS[field_name].tooltip


def preset_name(preset_id: str, fallback: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "PRESET_NAMES", {}).get(preset_id, fallback)


def localize_status(value: Any, *, locale: str | None = None) -> str:
    raw = str(getattr(value, "value", value))
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "STATUS_LABELS", {}).get(raw, raw)


def localize_message(message: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "MESSAGE_TRANSLATIONS", {}).get(str(message), str(message))


def parameter_label(parameter_name: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "PARAMETER_LABELS", {}).get(parameter_name, parameter_name)


def metric_label(metric_name: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "METRIC_LABELS", {}).get(metric_name, metric_name)


def semantic_label(value: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    return getattr(resource, "SEMANTIC_LABELS", {}).get(value, value)


def semantic_value(display_value: str, *, locale: str | None = None) -> str:
    resource = _RESOURCES[locale or _locale]
    labels = getattr(resource, "SEMANTIC_LABELS", {})
    return next((raw for raw, display in labels.items() if display == display_value), display_value)
