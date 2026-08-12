"""Read-only registry for packaged engineering presets."""

from __future__ import annotations

import importlib.resources
from dataclasses import dataclass

from .loader import load_preset_file
from .models import PresetCategory, PresetDefinition


@dataclass(frozen=True)
class PresetRegistry:
    presets: tuple[PresetDefinition, ...]

    def __post_init__(self) -> None:
        identifiers = [preset.preset_id for preset in self.presets]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Preset IDs must be unique")

    def get(self, preset_id: str) -> PresetDefinition:
        for preset in self.presets:
            if preset.preset_id == preset_id:
                return preset
        raise KeyError(f"Unknown preset: {preset_id}")

    def by_category(self, category: PresetCategory, *, available_only: bool = False) -> tuple[PresetDefinition, ...]:
        return tuple(
            preset for preset in self.presets
            if preset.category is category and (preset.available or not available_only)
        )


def default_preset_registry() -> PresetRegistry:
    resource = importlib.resources.files("motor_calculator.presets").joinpath("data/presets.json")
    with importlib.resources.as_file(resource) as path:
        return PresetRegistry(load_preset_file(path))
