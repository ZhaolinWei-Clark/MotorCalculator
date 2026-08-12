"""Data-driven engineering starting-template API."""

from .loader import PresetLoadError, load_preset_payload
from .models import (
    PresetCategory,
    PresetChange,
    PresetDefinition,
    PresetEvidenceKind,
    apply_preset,
    preview_preset,
)
from .registry import PresetRegistry, default_preset_registry

__all__ = [
    "PresetCategory",
    "PresetChange",
    "PresetDefinition",
    "PresetEvidenceKind",
    "PresetLoadError",
    "PresetRegistry",
    "apply_preset",
    "default_preset_registry",
    "load_preset_payload",
    "preview_preset",
]
