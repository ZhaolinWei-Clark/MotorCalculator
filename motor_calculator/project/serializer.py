"""Deterministic project serialization, migration, integrity, and atomic saves."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

from .schema import (
    PROJECT_SCHEMA_VERSION,
    ProjectDocument,
    ProjectInputValue,
    ProjectMetadata,
    ProjectModel,
    ProjectValidationError,
    ResultSnapshot,
    validate_project_document,
)


class ProjectSerializationError(RuntimeError):
    """Base error for user-readable project load/save failures."""


class UnsupportedProjectVersionError(ProjectSerializationError):
    """Raised when no safe migration path exists."""


class ProjectIntegrityError(ProjectSerializationError):
    """Raised when the canonical payload does not match its stored hash."""


Migration = Callable[[Mapping[str, Any]], Mapping[str, Any]]

# Production migrations are intentionally explicit. Schema v1 is current, so
# the registry remains empty until a real, reviewed successor exists.
PROJECT_MIGRATIONS: dict[int, Migration] = {}


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(payload_without_integrity: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload_without_integrity).encode("utf-8")).hexdigest()


def _input_payload(document: ProjectDocument) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        category: {
            name: {
                "value": item.value,
                "unit": item.unit,
                "semantics": dict(sorted(item.semantics.items())),
            }
            for name, item in sorted(fields.items())
        }
        for category, fields in sorted(document.inputs.items())
    }


def project_to_payload(document: ProjectDocument, *, include_integrity: bool = True) -> dict[str, Any]:
    validate_project_document(document)
    payload: dict[str, Any] = {
        "schema_version": document.schema_version,
        "metadata": asdict(document.metadata),
        "model": asdict(document.model),
        "inputs": _input_payload(document),
        "uncertainty_assumptions": [dict(item) for item in document.uncertainty_assumptions],
        "ui_preferences": dict(sorted(document.ui_preferences.items())),
        "notes": document.notes,
        "validation_references": {"feedback_record_ids": list(document.validation_record_ids)},
        "derived_cache": None if document.result_snapshot is None else asdict(document.result_snapshot),
    }
    if include_integrity:
        payload["integrity"] = {
            "algorithm": "sha256",
            "canonical_payload_sha256": _content_hash(payload),
            "purpose": "accidental corruption detection; not a digital signature",
        }
    return payload


def serialize_project(document: ProjectDocument) -> str:
    payload = project_to_payload(document)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def migrate_project(
    payload: Mapping[str, Any],
    *,
    migrations: Mapping[int, Migration] | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ProjectSerializationError("Project root must be a JSON object")
    raw_version = payload.get("schema_version")
    if not isinstance(raw_version, int) or isinstance(raw_version, bool):
        raise ProjectSerializationError("schema_version must be an integer")
    if raw_version > PROJECT_SCHEMA_VERSION:
        raise UnsupportedProjectVersionError(
            f"Project schema version {raw_version} is newer than supported version {PROJECT_SCHEMA_VERSION}"
        )
    migrated = dict(payload)
    migration_map = dict(PROJECT_MIGRATIONS if migrations is None else migrations)
    version = raw_version
    while version < PROJECT_SCHEMA_VERSION:
        migration = migration_map.get(version)
        if migration is None:
            raise UnsupportedProjectVersionError(
                f"No approved migration path from project schema version {version}"
            )
        migrated = dict(migration(migrated))
        next_version = migrated.get("schema_version")
        if next_version != version + 1:
            raise ProjectSerializationError("Project migration must advance exactly one schema version")
        version = next_version
    return migrated


def _verify_integrity(payload: Mapping[str, Any]) -> None:
    integrity = payload.get("integrity")
    if not isinstance(integrity, Mapping):
        raise ProjectIntegrityError("Project integrity metadata is missing")
    if integrity.get("algorithm") != "sha256":
        raise ProjectIntegrityError("Unsupported project integrity algorithm")
    expected = integrity.get("canonical_payload_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ProjectIntegrityError("Project integrity hash is invalid")
    hash_payload = dict(payload)
    hash_payload.pop("integrity", None)
    actual = _content_hash(hash_payload)
    if actual != expected.lower():
        raise ProjectIntegrityError("Project content hash mismatch; the file may be corrupted")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectSerializationError(f"{name} must be a JSON object")
    return value


def _project_from_payload(payload: Mapping[str, Any]) -> ProjectDocument:
    try:
        metadata_raw = _mapping(payload["metadata"], "metadata")
        model_raw = _mapping(payload["model"], "model")
        inputs_raw = _mapping(payload["inputs"], "inputs")
        validation_raw = _mapping(payload.get("validation_references", {}), "validation_references")
        inputs: dict[str, dict[str, ProjectInputValue]] = {}
        for category, fields_raw in inputs_raw.items():
            fields = _mapping(fields_raw, f"inputs.{category}")
            inputs[str(category)] = {}
            for name, item_raw in fields.items():
                item = _mapping(item_raw, f"inputs.{category}.{name}")
                inputs[str(category)][str(name)] = ProjectInputValue(
                    value=item["value"],
                    unit=str(item["unit"]),
                    semantics={str(k): str(v) for k, v in _mapping(item.get("semantics", {}), "semantics").items()},
                )
        cache_raw = payload.get("derived_cache")
        snapshot = None
        if cache_raw is not None:
            cache = _mapping(cache_raw, "derived_cache")
            snapshot = ResultSnapshot(
                result=_mapping(cache["result"], "derived_cache.result"),
                result_model_version=str(cache["result_model_version"]),
                result_timestamp=str(cache["result_timestamp"]),
                input_hash=str(cache["input_hash"]),
            )
        document = ProjectDocument(
            schema_version=int(payload["schema_version"]),
            metadata=ProjectMetadata(
                application_version=str(metadata_raw["application_version"]),
                created_at=str(metadata_raw["created_at"]),
                modified_at=str(metadata_raw["modified_at"]),
                project_name=str(metadata_raw["project_name"]),
                project_uuid=str(metadata_raw["project_uuid"]),
            ),
            model=ProjectModel(
                model_family=str(model_raw["model_family"]),
                calculation_mode=str(model_raw["calculation_mode"]),
                topology=str(model_raw["topology"]),
            ),
            inputs=inputs,
            uncertainty_assumptions=tuple(
                _mapping(item, "uncertainty_assumptions item")
                for item in payload.get("uncertainty_assumptions", [])
            ),
            ui_preferences=dict(_mapping(payload.get("ui_preferences", {}), "ui_preferences")),
            notes=str(payload.get("notes", "")),
            validation_record_ids=tuple(
                str(identifier) for identifier in validation_raw.get("feedback_record_ids", [])
            ),
            result_snapshot=snapshot,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectSerializationError(f"Project is missing or has an invalid required field: {exc}") from exc
    try:
        return validate_project_document(document)
    except ProjectValidationError as exc:
        raise ProjectSerializationError(str(exc)) from exc


def validate_project(payload_or_document: Mapping[str, Any] | ProjectDocument) -> ProjectDocument:
    if isinstance(payload_or_document, ProjectDocument):
        return validate_project_document(payload_or_document)
    migrated = migrate_project(payload_or_document)
    _verify_integrity(migrated)
    return _project_from_payload(migrated)


def load_project(path: str | Path) -> ProjectDocument:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectSerializationError(f"Project file could not be read: {exc}") from exc
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProjectSerializationError(f"Project file is not valid UTF-8 JSON: {exc}") from exc
    return validate_project(payload)


def _fsync_copy(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)
    with destination.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())


def save_project(
    document: ProjectDocument,
    path: str | Path,
    *,
    create_backup: bool = True,
) -> Path:
    validate_project_document(document)
    target = Path(path).expanduser().resolve()
    if not target.parent.is_dir():
        raise ProjectSerializationError(f"Project directory does not exist: {target.parent}")
    serialized = serialize_project(document)
    temporary: Path | None = None
    backup_temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        if target.exists() and create_backup:
            backup = target.with_name(target.name + ".bak")
            with tempfile.NamedTemporaryFile(
                dir=target.parent,
                prefix=f".{backup.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                backup_temporary = Path(stream.name)
            _fsync_copy(target, backup_temporary)
            os.replace(backup_temporary, backup)
            backup_temporary = None
        os.replace(temporary, target)
        temporary = None
    except (OSError, ProjectSerializationError) as exc:
        raise ProjectSerializationError(f"Project could not be saved atomically: {exc}") from exc
    finally:
        for candidate in (temporary, backup_temporary):
            if candidate is not None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
    return target
