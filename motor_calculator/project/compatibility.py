"""Read-only compatibility inspection for local project and backup files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .schema import PROJECT_MODEL_FAMILY, PROJECT_SCHEMA_VERSION
from .serializer import (
    PROJECT_MIGRATIONS,
    ProjectIntegrityError,
    ProjectSerializationError,
    UnsupportedProjectVersionError,
    validate_project,
)


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    MIGRATION_AVAILABLE = "MIGRATION_AVAILABLE"
    NEWER_SCHEMA_UNSUPPORTED = "NEWER_SCHEMA_UNSUPPORTED"
    CORRUPT = "CORRUPT"
    INVALID = "INVALID"


class IntegrityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    NOT_CHECKED = "NOT_CHECKED"


class RecoveryPriority(str, Enum):
    AUTOSAVE_NEWER = "AUTOSAVE_NEWER"
    OFFICIAL_PROJECT = "OFFICIAL_PROJECT"
    BACKUP = "BACKUP"
    CORRUPT_OFFICIAL_WITH_VALID_BACKUP = "CORRUPT_OFFICIAL_WITH_VALID_BACKUP"


@dataclass(frozen=True)
class CompatibilityReport:
    path: Path
    status: CompatibilityStatus
    schema_version: int | None
    application_version: str | None
    migration_required: bool
    required_fields_present: bool
    integrity_status: IntegrityStatus
    model_compatible: bool
    message: str


@dataclass(frozen=True)
class ProjectSourceOptions:
    official: CompatibilityReport
    backup: CompatibilityReport | None
    priorities: tuple[RecoveryPriority, ...]


def _has_migration_path(version: int) -> bool:
    while version < PROJECT_SCHEMA_VERSION:
        if version not in PROJECT_MIGRATIONS:
            return False
        version += 1
    return True


def inspect_project(path: str | Path) -> CompatibilityReport:
    """Inspect without migrating, mutating, or installing the project."""

    source = Path(path).expanduser().resolve()
    try:
        payload: Any = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return CompatibilityReport(
            source, CompatibilityStatus.INVALID, None, None, False, False,
            IntegrityStatus.NOT_CHECKED, False, f"Project JSON could not be read: {exc}",
        )
    if not isinstance(payload, Mapping):
        return CompatibilityReport(
            source, CompatibilityStatus.INVALID, None, None, False, False,
            IntegrityStatus.NOT_CHECKED, False, "Project root must be a JSON object",
        )
    version = payload.get("schema_version")
    metadata = payload.get("metadata")
    application_version = metadata.get("application_version") if isinstance(metadata, Mapping) else None
    required = all(name in payload for name in ("schema_version", "metadata", "model", "inputs"))
    if not isinstance(version, int) or isinstance(version, bool):
        return CompatibilityReport(
            source, CompatibilityStatus.INVALID, None, str(application_version) if application_version else None,
            False, required, IntegrityStatus.NOT_CHECKED, False,
            "schema_version must be an integer",
        )
    model = payload.get("model")
    model_compatible = isinstance(model, Mapping) and model.get("model_family") == PROJECT_MODEL_FAMILY
    if version > PROJECT_SCHEMA_VERSION:
        return CompatibilityReport(
            source, CompatibilityStatus.NEWER_SCHEMA_UNSUPPORTED, version,
            str(application_version) if application_version else None, False, required,
            IntegrityStatus.NOT_CHECKED, model_compatible,
            f"Project schema {version} is newer than supported schema {PROJECT_SCHEMA_VERSION}",
        )
    if version < PROJECT_SCHEMA_VERSION and _has_migration_path(version):
        return CompatibilityReport(
            source, CompatibilityStatus.MIGRATION_AVAILABLE, version,
            str(application_version) if application_version else None, True, required,
            IntegrityStatus.NOT_CHECKED, model_compatible,
            f"An approved migration from schema {version} is available",
        )
    try:
        document = validate_project(payload)
    except ProjectIntegrityError as exc:
        return CompatibilityReport(
            source, CompatibilityStatus.CORRUPT, version,
            str(application_version) if application_version else None, False, required,
            IntegrityStatus.FAILED, model_compatible, str(exc),
        )
    except UnsupportedProjectVersionError as exc:
        return CompatibilityReport(
            source, CompatibilityStatus.INVALID, version,
            str(application_version) if application_version else None, False, required,
            IntegrityStatus.NOT_CHECKED, model_compatible, str(exc),
        )
    except ProjectSerializationError as exc:
        return CompatibilityReport(
            source, CompatibilityStatus.INVALID, version,
            str(application_version) if application_version else None, False, required,
            IntegrityStatus.NOT_CHECKED, model_compatible, str(exc),
        )
    return CompatibilityReport(
        source, CompatibilityStatus.COMPATIBLE, document.schema_version,
        document.metadata.application_version, False, True, IntegrityStatus.VERIFIED,
        document.model.model_family == PROJECT_MODEL_FAMILY, "Project is compatible",
    )


def inspect_project_sources(path: str | Path) -> ProjectSourceOptions:
    source = Path(path).expanduser().resolve()
    official = inspect_project(source)
    backup_path = source.with_name(source.name + ".bak")
    backup = inspect_project(backup_path) if backup_path.is_file() else None
    priorities: list[RecoveryPriority] = []
    if official.status is CompatibilityStatus.COMPATIBLE:
        priorities.append(RecoveryPriority.OFFICIAL_PROJECT)
    if backup is not None and backup.status is CompatibilityStatus.COMPATIBLE:
        priorities.append(RecoveryPriority.BACKUP)
        if official.status in {CompatibilityStatus.CORRUPT, CompatibilityStatus.INVALID}:
            priorities.insert(0, RecoveryPriority.CORRUPT_OFFICIAL_WITH_VALID_BACKUP)
    return ProjectSourceOptions(official, backup, tuple(priorities))
