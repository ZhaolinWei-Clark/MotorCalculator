"""Read-only source reconstruction records for external AFPM validation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


class ReconstructedFieldStatus(str, Enum):
    SOURCE_PROVIDED = "source_provided"
    SAFELY_DERIVED = "safely_derived"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class ReconstructedCaseError(ValueError):
    pass


class MissingReconstructedInputError(ReconstructedCaseError):
    def __init__(self, missing_fields: tuple[str, ...]):
        self.missing_fields = missing_fields
        super().__init__(f"required reconstructed inputs are not usable: {', '.join(missing_fields)}")


@dataclass(frozen=True)
class FieldProvenance:
    source_url: str
    page: str
    location: str
    note: str


@dataclass(frozen=True)
class ReconstructedField:
    status: ReconstructedFieldStatus
    value: Any
    unit: str | None
    provenance: FieldProvenance
    derivation: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status in {
            ReconstructedFieldStatus.SOURCE_PROVIDED,
            ReconstructedFieldStatus.SAFELY_DERIVED,
        }


@dataclass(frozen=True)
class ReconstructedAFPMCase:
    case_id: str
    source_id: str
    source_title: str
    source_url: str
    topology: str
    fields: Mapping[str, ReconstructedField]
    notes: str

    def usable_value(self, field_name: str) -> Any:
        field = self.fields.get(field_name)
        if field is None or not field.is_usable:
            raise MissingReconstructedInputError((field_name,))
        return field.value


@dataclass(frozen=True)
class SafeDerivedValue:
    value: float
    unit: str
    comparability: str
    derivation: str


def _required_text(raw: Mapping[str, Any], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ReconstructedCaseError(f"{name} must be a non-empty string")
    return value.strip()


def _load_field(name: str, raw: Mapping[str, Any]) -> ReconstructedField:
    try:
        status = ReconstructedFieldStatus(raw["status"])
    except (KeyError, ValueError) as exc:
        raise ReconstructedCaseError(f"invalid status for field {name}") from exc
    value = raw.get("value")
    if status is ReconstructedFieldStatus.UNAVAILABLE and value is not None:
        raise ReconstructedCaseError(f"unavailable field {name} must use null, not a placeholder")
    if status in {ReconstructedFieldStatus.SOURCE_PROVIDED, ReconstructedFieldStatus.SAFELY_DERIVED} and value is None:
        raise ReconstructedCaseError(f"usable field {name} requires a value")
    if isinstance(value, float) and not math.isfinite(value):
        raise ReconstructedCaseError(f"field {name} must be finite")
    provenance_raw = raw.get("provenance")
    if not isinstance(provenance_raw, Mapping):
        raise ReconstructedCaseError(f"field {name} requires provenance")
    provenance = FieldProvenance(
        source_url=_required_text(provenance_raw, "source_url"),
        page=_required_text(provenance_raw, "page"),
        location=_required_text(provenance_raw, "location"),
        note=_required_text(provenance_raw, "note"),
    )
    derivation = raw.get("derivation")
    if status is ReconstructedFieldStatus.SAFELY_DERIVED and not derivation:
        raise ReconstructedCaseError(f"safely derived field {name} requires a derivation")
    return ReconstructedField(
        status=status,
        value=value,
        unit=raw.get("unit"),
        provenance=provenance,
        derivation=derivation,
    )


def load_reconstructed_case(path: Path) -> ReconstructedAFPMCase:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    fields_raw = raw.get("fields")
    if not isinstance(fields_raw, Mapping) or not fields_raw:
        raise ReconstructedCaseError("fields must be a non-empty object")
    fields = {name: _load_field(name, value) for name, value in fields_raw.items()}
    return ReconstructedAFPMCase(
        case_id=_required_text(raw, "case_id"),
        source_id=_required_text(raw, "source_id"),
        source_title=_required_text(raw, "source_title"),
        source_url=_required_text(raw, "source_url"),
        topology=_required_text(raw, "topology"),
        fields=MappingProxyType(fields),
        notes=_required_text(raw, "notes"),
    )


def require_reconstructed_inputs(
    case: ReconstructedAFPMCase,
    required_fields: tuple[str, ...],
) -> dict[str, Any]:
    missing = tuple(
        name for name in required_fields
        if name not in case.fields or not case.fields[name].is_usable
    )
    if missing:
        raise MissingReconstructedInputError(missing)
    return {name: case.fields[name].value for name in required_fields}


def normalize_copper_resistance_temperature(
    resistance_ohm: float,
    measured_temperature_c: float,
    target_temperature_c: float,
    *,
    copper_temperature_coefficient_per_c: float = 0.00393,
) -> SafeDerivedValue:
    values = (
        resistance_ohm,
        measured_temperature_c,
        target_temperature_c,
        copper_temperature_coefficient_per_c,
    )
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("resistance temperature transform inputs must be finite")
    if resistance_ohm <= 0.0 or copper_temperature_coefficient_per_c <= 0.0:
        raise ValueError("resistance and copper temperature coefficient must be positive")
    numerator = 1.0 + copper_temperature_coefficient_per_c * (target_temperature_c - 20.0)
    denominator = 1.0 + copper_temperature_coefficient_per_c * (measured_temperature_c - 20.0)
    if numerator <= 0.0 or denominator <= 0.0:
        raise ValueError("temperature transform is outside the valid linear-resistivity range")
    return SafeDerivedValue(
        value=resistance_ohm * numerator / denominator,
        unit="ohm",
        comparability="SAFE_TRANSFORM",
        derivation=(
            "R_target = R_measured * (1 + alpha*(T_target-20)) / "
            "(1 + alpha*(T_measured-20)); copper alpha explicitly supplied"
        ),
    )


def synchronous_reactance_to_inductance_h(
    reactance_ohm: float,
    electrical_frequency_hz: float,
) -> SafeDerivedValue:
    if not math.isfinite(reactance_ohm) or reactance_ohm <= 0.0:
        raise ValueError("reactance_ohm must be finite and positive")
    if not math.isfinite(electrical_frequency_hz) or electrical_frequency_hz <= 0.0:
        raise ValueError("electrical_frequency_hz must be finite and positive")
    return SafeDerivedValue(
        value=reactance_ohm / (2.0 * math.pi * electrical_frequency_hz),
        unit="H",
        comparability="SAFE_TRANSFORM",
        derivation="Axis-specific conversion only: L_axis = X_axis / (2*pi*f); not scalar phase inductance.",
    )
