"""Strict JSON loader for engineering preset records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from motor_calculator.project.schema import PROJECT_INPUT_SPECS

from .models import PresetCategory, PresetDefinition, PresetEvidenceKind


class PresetLoadError(ValueError):
    pass


def load_preset_payload(payload: Mapping[str, Any]) -> tuple[PresetDefinition, ...]:
    if payload.get("schema_version") != 1:
        raise PresetLoadError("Unsupported preset registry schema")
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list):
        raise PresetLoadError("presets must be a list")
    presets: list[PresetDefinition] = []
    for raw in raw_presets:
        if not isinstance(raw, Mapping):
            raise PresetLoadError("Each preset must be an object")
        try:
            values = raw.get("values", {})
            if not isinstance(values, Mapping):
                raise TypeError("values must be an object")
            unknown = sorted(set(values) - set(PROJECT_INPUT_SPECS))
            if unknown:
                raise PresetLoadError(f"Preset contains unsupported fields: {', '.join(unknown)}")
            preset = PresetDefinition(
                preset_id=str(raw["preset_id"]),
                version=int(raw["version"]),
                display_name=str(raw["display_name"]),
                category=PresetCategory(str(raw["category"])),
                evidence_kind=PresetEvidenceKind(str(raw["evidence_kind"])),
                values=dict(values),
                provenance=str(raw["provenance"]),
                assumptions=tuple(str(item) for item in raw.get("assumptions", ())),
                notes=tuple(str(item) for item in raw.get("notes", ())),
                applicable_temperature_c=None if raw.get("applicable_temperature_c") is None else float(raw["applicable_temperature_c"]),
                available=bool(raw.get("available", True)),
                unavailable_reason=None if raw.get("unavailable_reason") is None else str(raw["unavailable_reason"]),
                winding_authority=(
                    None if raw.get("winding_authority") is None
                    else str(raw["winding_authority"])
                ),
                coil_span_slots=(
                    None if raw.get("coil_span_slots") is None
                    else int(raw["coil_span_slots"])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PresetLoadError(f"Invalid preset record: {exc}") from exc
        if not preset.preset_id.strip() or not preset.display_name.strip() or not preset.provenance.strip():
            raise PresetLoadError("Preset ID, display name, and provenance must not be empty")
        if preset.version < 1:
            raise PresetLoadError("Preset version must be positive")
        if not preset.available and not preset.unavailable_reason:
            raise PresetLoadError("Unavailable presets require a reason")
        if preset.winding_authority is not None:
            from ..winding.authority import WindingAuthority

            try:
                declared = WindingAuthority(preset.winding_authority)
            except ValueError as exc:
                raise PresetLoadError(
                    f"Unknown winding_authority {preset.winding_authority!r}"
                ) from exc
            if (
                declared is WindingAuthority.AUTO_FROM_GEOMETRY
                and preset.coil_span_slots is None
            ):
                raise PresetLoadError(
                    "A preset declaring AUTO_FROM_GEOMETRY must supply coil_span_slots, "
                    "because the legacy parameter schema carries no coil span and AUTO "
                    "must never guess one"
                )
        presets.append(preset)
    identifiers = [preset.preset_id for preset in presets]
    if len(identifiers) != len(set(identifiers)):
        raise PresetLoadError("Preset IDs must be unique")
    return tuple(presets)


def load_preset_file(path: str | Path) -> tuple[PresetDefinition, ...]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PresetLoadError(f"Preset file could not be loaded: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise PresetLoadError("Preset root must be an object")
    return load_preset_payload(payload)
