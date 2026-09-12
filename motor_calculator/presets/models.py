"""Preset records and non-mutating preview/application helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class PresetCategory(str, Enum):
    MOTOR_TOPOLOGY = "motor_topology"
    MAGNET_MATERIAL = "magnet_material"
    DESIGN_EXAMPLE = "design_example"
    OPERATING_POINT = "operating_point"


class PresetEvidenceKind(str, Enum):
    REFERENCE = "reference"
    TYPICAL = "typical"
    DEMONSTRATION = "demonstration"


@dataclass(frozen=True)
class PresetDefinition:
    preset_id: str
    version: int
    display_name: str
    category: PresetCategory
    evidence_kind: PresetEvidenceKind
    values: Mapping[str, str | int | float | bool]
    provenance: str
    assumptions: tuple[str, ...]
    notes: tuple[str, ...]
    applicable_temperature_c: float | None = None
    available: bool = True
    unavailable_reason: str | None = None
    #: Phase 10H.1. Production winding-factor authority this preset declares.
    #: ``None`` means the preset says nothing about authority, which is how
    #: every pre-10H.1 preset behaves and why they are unaffected.
    winding_authority: str | None = None
    #: Coil span in slots, needed before AUTO can derive a winding factor. The
    #: legacy parameter schema has no field for it, so a preset that declares
    #: AUTO must supply it here.
    coil_span_slots: int | None = None


@dataclass(frozen=True)
class PresetChange:
    field_name: str
    current_value: Any
    preset_value: Any


def preview_preset(current: Mapping[str, Any], preset: PresetDefinition) -> tuple[PresetChange, ...]:
    if not preset.available:
        raise ValueError(preset.unavailable_reason or "Preset is unavailable")
    return tuple(
        PresetChange(name, current.get(name), value)
        for name, value in preset.values.items()
        if current.get(name) != value
    )


def apply_preset(current: Mapping[str, Any], preset: PresetDefinition) -> dict[str, Any]:
    result = dict(current)
    for change in preview_preset(current, preset):
        result[change.field_name] = change.preset_value
    return result
