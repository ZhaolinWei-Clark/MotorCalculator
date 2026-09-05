"""Deterministic, human-readable serialization of FEA cases and results."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .models import (
    FEA_CASE_SCHEMA_VERSION,
    FEAAnalyticalPrediction,
    FEACoreModelPolicy,
    FEAMaterialSet,
    FEAMeshPolicy,
    FEAOperatingPoint,
    FEASupportability,
    FEASupportabilityReport,
    FEASymmetryPlan,
    FEAUnrolledSliceGeometry,
    FEAValidationCase,
    FEAValidationTarget,
    FEAWindingMap,
)


def _plain(value: Any) -> Any:
    """Convert a dataclass tree to JSON-compatible primitives."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite values cannot be serialized")
        return value
    return value


def case_to_dict(case: FEAValidationCase) -> dict[str, Any]:
    """Serialize a case to a plain dictionary suitable for JSON."""

    return _plain(case)


def _tuple_of_str(raw: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in raw)


def case_from_dict(raw: Mapping[str, Any]) -> FEAValidationCase:
    """Rebuild a case from its serialized form, re-running every validator."""

    if raw.get("schema_version") != FEA_CASE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported FEA case schema version {raw.get('schema_version')!r}; "
            f"this build understands {FEA_CASE_SCHEMA_VERSION!r}"
        )
    geometry_raw = dict(raw["geometry"])
    geometry_raw["omitted_three_dimensional_effects"] = _tuple_of_str(
        geometry_raw["omitted_three_dimensional_effects"]
    )
    materials_raw = dict(raw["materials"])
    materials_raw["core_model_policy"] = FEACoreModelPolicy(materials_raw["core_model_policy"])
    materials_raw["property_mismatches"] = _tuple_of_str(materials_raw["property_mismatches"])
    winding_raw = dict(raw["winding"])
    winding_raw["coil_phase_assignment"] = _tuple_of_str(winding_raw["coil_phase_assignment"])
    winding_raw["coil_polarity"] = tuple(int(item) for item in winding_raw["coil_polarity"])
    operating_raw = dict(raw["operating_point"])
    operating_raw["target"] = FEAValidationTarget(operating_raw["target"])
    supportability_raw = dict(raw["supportability"])
    supportability_raw["state"] = FEASupportability(supportability_raw["state"])
    supportability_raw["blocking_reasons"] = _tuple_of_str(supportability_raw["blocking_reasons"])
    supportability_raw["approximation_labels"] = _tuple_of_str(
        supportability_raw["approximation_labels"]
    )

    return FEAValidationCase(
        case_id=str(raw["case_id"]),
        schema_version=str(raw["schema_version"]),
        application_version=str(raw["application_version"]),
        target=FEAValidationTarget(raw["target"]),
        supportability=FEASupportabilityReport(**supportability_raw),
        geometry=FEAUnrolledSliceGeometry(**geometry_raw),
        materials=FEAMaterialSet(**materials_raw),
        winding=FEAWindingMap(**winding_raw),
        operating_point=FEAOperatingPoint(**operating_raw),
        mesh_policy=FEAMeshPolicy(**raw["mesh_policy"]),
        symmetry=FEASymmetryPlan(**raw["symmetry"]),
        analytical=FEAAnalyticalPrediction(**raw["analytical"]),
        units=dict(raw["units"]),
        solver_family=str(raw["solver_family"]),
        torque_extraction_method=str(raw["torque_extraction_method"]),
        back_emf_extraction_method=str(raw["back_emf_extraction_method"]),
        notes=_tuple_of_str(raw.get("notes", ())),
    )
