"""Versioned project-document schema and canonical input mapping."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from motor_calculator.motor_core.validation import parse_legacy_gui_params
from motor_calculator.version import APPLICATION_VERSION


PROJECT_SCHEMA_VERSION = 1
PROJECT_FILE_EXTENSION = ".motorproj"
PROJECT_MODEL_FAMILY = "legacy_afpm_calculator"
PROJECT_TOPOLOGY = "dual-rotor single-stator dual-air-gap AFPM"


class ProjectValidationError(ValueError):
    """Raised when project content cannot represent a valid project document."""


@dataclass(frozen=True)
class InputFieldSpec:
    category: str
    unit: str
    value_type: str
    semantics: tuple[tuple[str, str], ...] = ()


def _spec(
    category: str,
    unit: str,
    value_type: str,
    **semantics: str,
) -> InputFieldSpec:
    return InputFieldSpec(category, unit, value_type, tuple(sorted(semantics.items())))


# These are the canonical units accepted by the legacy GUI input API. SI
# conversion remains centralized in motor_core.units and is not duplicated here.
PROJECT_INPUT_SPECS: Mapping[str, InputFieldSpec] = {
    "V_dc": _spec("electrical", "V", "float", quantity="dc_bus_voltage"),
    "P_rated": _spec("operating_point", "W", "float", boundary="shaft_output"),
    "n_rated": _spec("operating_point", "rpm", "float", quantity="mechanical_speed"),
    "Temp_coil": _spec("operating_point", "degC", "float", quantity="winding_temperature"),
    "D_out": _spec("geometry", "mm", "float", quantity="motor_outer_diameter"),
    "D_in": _spec("geometry", "mm", "float", quantity="motor_inner_diameter"),
    "g_side": _spec("geometry", "mm", "float", quantity="air_gap_per_side"),
    "D_stator_out": _spec("geometry", "mm", "float", quantity="stator_outer_diameter"),
    "D_stator_in": _spec("geometry", "mm", "float", quantity="stator_inner_diameter"),
    "h_stator": _spec("geometry", "mm", "float", quantity="stator_thickness"),
    "h_coil": _spec("geometry", "mm", "float", quantity="coil_height"),
    "h_yoke": _spec("geometry", "mm", "float", quantity="yoke_height"),
    "slots": _spec("geometry", "count", "int", quantity="slot_count"),
    "slot_type": _spec("geometry", "enum", "str", quantity="slot_type"),
    "h_slot": _spec("geometry", "mm", "float", quantity="slot_height"),
    "w_slot_top": _spec("geometry", "mm", "float", quantity="slot_top_width"),
    "w_slot_bottom": _spec("geometry", "mm", "float", quantity="slot_bottom_width"),
    "h_slot_opening": _spec("geometry", "mm", "float", quantity="slot_opening_height"),
    "w_slot_opening": _spec("geometry", "mm", "float", quantity="slot_opening_width"),
    "h_wedge": _spec("geometry", "mm", "float", quantity="wedge_height"),
    "h_mag": _spec("geometry", "mm", "float", quantity="magnet_thickness"),
    "w_magnet": _spec("geometry", "mm", "float", quantity="magnet_tangential_width"),
    "L_magnet": _spec("geometry", "mm", "float", quantity="magnet_radial_length"),
    "magnet_type": _spec("geometry", "enum", "str", quantity="magnet_arrangement"),
    "magnetization": _spec("geometry", "enum", "str", quantity="magnetization_type"),
    "p": _spec("geometry", "pole_pairs", "int", quantity="pole_pairs"),
    "magnet_grade": _spec("material", "enum", "str", quantity="magnet_grade"),
    "Br": _spec("material", "T", "float", quantity="magnet_remanence"),
    "alpha_p": _spec("geometry", "ratio", "float", quantity="pole_arc_coefficient"),
    "sigma_m": _spec("material", "ratio", "float", quantity="leakage_factor"),
    "mu_r_mag": _spec("material", "ratio", "float", quantity="relative_permeability"),
    "N_ph_turns": _spec("winding", "turns_per_phase", "int", quantity="effective_phase_turns"),
    "d_wire": _spec("winding", "mm", "float", quantity="wire_diameter"),
    "n_parallel": _spec("winding", "parallel_paths", "int", quantity="parallel_paths"),
    "k_w": _spec("winding", "ratio", "float", quantity="winding_factor"),
    "fill_limit": _spec("winding", "ratio", "float", quantity="fill_factor_limit"),
    "waveform": _spec("electrical", "enum", "str", quantity="back_emf_waveform"),
    "k_cogging": _spec("electrical", "ratio", "float", quantity="legacy_cogging_factor"),
    "k_ripple_6": _spec("electrical", "ratio", "float", quantity="legacy_sixth_ripple_factor"),
    "k_ripple_12": _spec("electrical", "ratio", "float", quantity="legacy_twelfth_ripple_factor"),
    "coreless": _spec("geometry", "boolean", "bool", quantity="coreless_stator"),
}


@dataclass(frozen=True)
class ProjectInputValue:
    value: str | int | float | bool
    unit: str
    semantics: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectMetadata:
    application_version: str
    created_at: str
    modified_at: str
    project_name: str
    project_uuid: str


@dataclass(frozen=True)
class ProjectModel:
    model_family: str
    calculation_mode: str
    topology: str


@dataclass(frozen=True)
class ResultSnapshot:
    result: Mapping[str, Any]
    result_model_version: str
    result_timestamp: str
    input_hash: str


@dataclass(frozen=True)
class ProjectDocument:
    schema_version: int
    metadata: ProjectMetadata
    model: ProjectModel
    inputs: Mapping[str, Mapping[str, ProjectInputValue]]
    uncertainty_assumptions: tuple[Mapping[str, Any], ...] = ()
    ui_preferences: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)
    notes: str = ""
    validation_record_ids: tuple[str, ...] = ()
    result_snapshot: ResultSnapshot | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def calculation_mode_from_inputs(flat_inputs: Mapping[str, Any]) -> str:
    waveform = str(flat_inputs.get("waveform", "")).strip().lower()
    if waveform in {"sinusoidal", "pmsm_sinusoidal", "正弦波"}:
        return "pmsm_sinusoidal"
    return "bldc_120_degree"


def build_project_inputs(flat_inputs: Mapping[str, Any]) -> dict[str, dict[str, ProjectInputValue]]:
    parsed = parse_legacy_gui_params(flat_inputs)
    missing = sorted(set(PROJECT_INPUT_SPECS) - set(parsed))
    if missing:
        raise ProjectValidationError(f"Project inputs are incomplete; missing: {', '.join(missing)}")
    grouped: dict[str, dict[str, ProjectInputValue]] = {}
    for name, spec in PROJECT_INPUT_SPECS.items():
        grouped.setdefault(spec.category, {})[name] = ProjectInputValue(
            value=parsed[name],
            unit=spec.unit,
            semantics=dict(spec.semantics),
        )
    return grouped


def _validate_input_type(name: str, value: Any, expected: str) -> None:
    if expected == "bool":
        valid = isinstance(value, bool)
    elif expected == "str":
        valid = isinstance(value, str) and bool(value.strip())
    elif expected == "int":
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if valid:
            valid = math.isfinite(float(value))
    if not valid:
        raise ProjectValidationError(f"Project input {name!r} must be {expected}")


def flatten_project_inputs(
    inputs: Mapping[str, Mapping[str, ProjectInputValue]],
) -> dict[str, str | int | float | bool]:
    flattened: dict[str, str | int | float | bool] = {}
    for name, spec in PROJECT_INPUT_SPECS.items():
        category = inputs.get(spec.category)
        if not isinstance(category, Mapping) or name not in category:
            raise ProjectValidationError(f"Project input is missing: {spec.category}.{name}")
        item = category[name]
        if not isinstance(item, ProjectInputValue):
            raise ProjectValidationError(f"Project input {name!r} has an invalid structure")
        if item.unit != spec.unit:
            raise ProjectValidationError(
                f"Project input {name!r} uses unit {item.unit!r}; expected {spec.unit!r}"
            )
        _validate_input_type(name, item.value, spec.value_type)
        flattened[name] = item.value
    parsed = parse_legacy_gui_params(flattened)
    if set(parsed) != set(PROJECT_INPUT_SPECS):
        raise ProjectValidationError("Project inputs cannot be restored exactly")
    return parsed


def project_inputs_hash(inputs: Mapping[str, Mapping[str, ProjectInputValue]]) -> str:
    flattened = flatten_project_inputs(inputs)
    canonical = json.dumps(flattened, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def uncertainty_parameters_to_payload(
    parameters: Sequence[Any] | None,
) -> tuple[Mapping[str, Any], ...]:
    if parameters is None:
        return ()
    payload: list[Mapping[str, Any]] = []
    for parameter in parameters:
        if not is_dataclass(parameter):
            raise ProjectValidationError("Uncertainty parameters must be dataclass records")
        item = asdict(parameter)
        kind = getattr(parameter, "uncertainty_kind", None)
        item["uncertainty_kind"] = getattr(kind, "value", kind)
        item["notes"] = list(getattr(parameter, "notes", ()))
        payload.append(item)
    return uncertainty_parameters_from_payload(payload)


def uncertainty_parameters_from_payload(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    parameters: list[Mapping[str, Any]] = []
    allowed_kinds = {"EXACT", "RANGE", "NORMAL", "UNIFORM", "UNKNOWN"}
    for item in payload:
        try:
            normalized = {
                "parameter_name": str(item["parameter_name"]),
                "nominal_value": float(item["nominal_value"]),
                "unit": str(item["unit"]),
                "uncertainty_kind": str(item["uncertainty_kind"]),
                "lower_bound": item.get("lower_bound"),
                "upper_bound": item.get("upper_bound"),
                "mean": item.get("mean"),
                "standard_deviation": item.get("standard_deviation"),
                "provenance": str(item["provenance"]),
                "confidence": str(item["confidence"]),
                "notes": [str(note) for note in item.get("notes", ())],
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectValidationError(f"Invalid uncertainty assumption: {exc}") from exc
        if not all(
            normalized[name].strip()
            for name in ("parameter_name", "unit", "provenance", "confidence")
        ):
            raise ProjectValidationError("Uncertainty text fields must not be empty")
        if normalized["uncertainty_kind"] not in allowed_kinds:
            raise ProjectValidationError("Unknown uncertainty_kind")
        for numeric_name in (
            "nominal_value",
            "lower_bound",
            "upper_bound",
            "mean",
            "standard_deviation",
        ):
            value = normalized[numeric_name]
            if value is not None:
                try:
                    normalized[numeric_name] = float(value)
                except (TypeError, ValueError) as exc:
                    raise ProjectValidationError(
                        f"Uncertainty field {numeric_name} must be numeric or null"
                    ) from exc
                if not math.isfinite(normalized[numeric_name]):
                    raise ProjectValidationError(f"Uncertainty field {numeric_name} must be finite")
        parameters.append(normalized)
    names = [str(parameter["parameter_name"]) for parameter in parameters]
    if len(names) != len(set(names)):
        raise ProjectValidationError("Uncertainty parameter names must be unique")
    return tuple(parameters)


def _validate_timestamp(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{name} must be a non-empty timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectValidationError(f"{name} is not an ISO-8601 timestamp") from exc


def validate_project_document(document: ProjectDocument) -> ProjectDocument:
    if document.schema_version != PROJECT_SCHEMA_VERSION:
        raise ProjectValidationError(
            f"Unsupported in-memory project schema version: {document.schema_version}"
        )
    metadata = document.metadata
    if not metadata.project_name.strip():
        raise ProjectValidationError("project_name must not be empty")
    try:
        uuid.UUID(metadata.project_uuid)
    except (ValueError, AttributeError) as exc:
        raise ProjectValidationError("project_uuid must be a valid UUID") from exc
    _validate_timestamp("created_at", metadata.created_at)
    _validate_timestamp("modified_at", metadata.modified_at)
    if not metadata.application_version.strip():
        raise ProjectValidationError("application_version must not be empty")
    for name, value in (
        ("model_family", document.model.model_family),
        ("calculation_mode", document.model.calculation_mode),
        ("topology", document.model.topology),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ProjectValidationError(f"{name} must not be empty")
    flat = flatten_project_inputs(document.inputs)
    expected_mode = calculation_mode_from_inputs(flat)
    if document.model.calculation_mode != expected_mode:
        raise ProjectValidationError("calculation_mode does not match the saved waveform")
    uncertainty_parameters_from_payload(document.uncertainty_assumptions)
    if not isinstance(document.notes, str):
        raise ProjectValidationError("notes must be plain text")
    identifiers = document.validation_record_ids
    if any(not isinstance(identifier, str) or not identifier.strip() for identifier in identifiers):
        raise ProjectValidationError("validation record IDs must be non-empty strings")
    if len(identifiers) != len(set(identifiers)):
        raise ProjectValidationError("validation record IDs must be unique")
    if document.result_snapshot is not None:
        snapshot = document.result_snapshot
        _validate_timestamp("result_timestamp", snapshot.result_timestamp)
        if snapshot.input_hash != project_inputs_hash(document.inputs):
            raise ProjectValidationError("result snapshot input hash does not match project inputs")
        if not snapshot.result_model_version.strip():
            raise ProjectValidationError("result_model_version must not be empty")
    return document


def create_project_document(
    project_name: str,
    flat_inputs: Mapping[str, Any],
    *,
    project_uuid: str | None = None,
    created_at: str | None = None,
    modified_at: str | None = None,
    application_version: str = APPLICATION_VERSION,
    uncertainty_assumptions: Sequence[Any] | None = None,
    ui_preferences: Mapping[str, str | int | float | bool | None] | None = None,
    notes: str = "",
    validation_record_ids: Sequence[str] = (),
    result_snapshot: ResultSnapshot | None = None,
) -> ProjectDocument:
    now = utc_now_iso()
    inputs = build_project_inputs(flat_inputs)
    document = ProjectDocument(
        schema_version=PROJECT_SCHEMA_VERSION,
        metadata=ProjectMetadata(
            application_version=application_version,
            created_at=created_at or now,
            modified_at=modified_at or now,
            project_name=project_name,
            project_uuid=project_uuid or str(uuid.uuid4()),
        ),
        model=ProjectModel(
            model_family=PROJECT_MODEL_FAMILY,
            calculation_mode=calculation_mode_from_inputs(flat_inputs),
            topology=PROJECT_TOPOLOGY,
        ),
        inputs=inputs,
        uncertainty_assumptions=uncertainty_parameters_to_payload(uncertainty_assumptions),
        ui_preferences=dict(ui_preferences or {}),
        notes=notes,
        validation_record_ids=tuple(validation_record_ids),
        result_snapshot=result_snapshot,
    )
    return validate_project_document(document)


def missing_feedback_record_ids(
    document: ProjectDocument,
    available_record_ids: Sequence[str],
) -> tuple[str, ...]:
    available = set(available_record_ids)
    return tuple(identifier for identifier in document.validation_record_ids if identifier not in available)
