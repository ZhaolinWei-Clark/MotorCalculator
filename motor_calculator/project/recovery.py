"""Local-only autosave and crash-recovery storage for project documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from motor_calculator.version import APPLICATION_VERSION

from .compatibility import CompatibilityStatus, RecoveryPriority, inspect_project_sources
from .schema import (
    PROJECT_SCHEMA_VERSION,
    ProjectDocument,
    ProjectMetadata,
    project_inputs_hash,
    utc_now_iso,
)
from .serializer import ProjectSerializationError, project_to_payload, validate_project


RECOVERY_SCHEMA_VERSION = 1
DEFAULT_AUTOSAVE_INTERVAL_SECONDS = 60


class RecoveryStatus(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    IDENTICAL_TO_OFFICIAL = "IDENTICAL_TO_OFFICIAL"
    STALE = "STALE"
    CLEAN_SESSION = "CLEAN_SESSION"
    CORRUPT = "CORRUPT"


@dataclass(frozen=True)
class RecoveryRecord:
    recovery_schema_version: int
    recovery_id: str
    session_id: str
    recovery_timestamp: str
    original_project_path: str | None
    last_normal_save_timestamp: str | None
    dirty: bool
    application_version: str
    project_schema_version: int
    project_uuid: str
    input_hash: str
    state_hash: str
    project: ProjectDocument


@dataclass(frozen=True)
class RecoveryCandidate:
    path: Path
    record: RecoveryRecord
    status: RecoveryStatus
    newer_than_official: bool | None
    session_was_clean: bool
    priorities: tuple[RecoveryPriority, ...]
    details: str


@dataclass(frozen=True)
class RecoveryScanResult:
    candidates: tuple[RecoveryCandidate, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryWriteResult:
    written: bool
    path: Path | None = None
    warning: str | None = None


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recoverable_state_hash(document: ProjectDocument) -> str:
    payload = project_to_payload(document, include_integrity=False)
    metadata = dict(payload["metadata"])
    metadata.pop("modified_at", None)
    payload["metadata"] = metadata
    payload["derived_cache"] = None
    return _hash(payload)


def recovery_to_payload(record: RecoveryRecord, *, include_integrity: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "recovery_schema_version": record.recovery_schema_version,
        "recovery_id": record.recovery_id,
        "session_id": record.session_id,
        "recovery_timestamp": record.recovery_timestamp,
        "original_project_path": record.original_project_path,
        "last_normal_save_timestamp": record.last_normal_save_timestamp,
        "dirty": record.dirty,
        "application_version": record.application_version,
        "project_schema_version": record.project_schema_version,
        "project_uuid": record.project_uuid,
        "input_hash": record.input_hash,
        "state_hash": record.state_hash,
        "project": project_to_payload(record.project),
    }
    if include_integrity:
        payload["integrity"] = {
            "algorithm": "sha256",
            "canonical_payload_sha256": _hash(payload),
            "purpose": "accidental corruption detection; not a digital signature",
        }
    return payload


def serialize_recovery(record: RecoveryRecord) -> str:
    return json.dumps(recovery_to_payload(record), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def load_recovery(path: str | Path) -> RecoveryRecord:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProjectSerializationError(f"Recovery file is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ProjectSerializationError("Recovery root must be a JSON object")
    integrity = payload.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("algorithm") != "sha256":
        raise ProjectSerializationError("Recovery integrity metadata is missing or invalid")
    unsigned = dict(payload)
    unsigned.pop("integrity", None)
    if integrity.get("canonical_payload_sha256") != _hash(unsigned):
        raise ProjectSerializationError("Recovery content hash mismatch")
    if payload.get("recovery_schema_version") != RECOVERY_SCHEMA_VERSION:
        raise ProjectSerializationError("Unsupported recovery schema version")
    try:
        project_raw = payload["project"]
        if not isinstance(project_raw, Mapping):
            raise TypeError("project must be an object")
        project = validate_project(project_raw)
        record = RecoveryRecord(
            recovery_schema_version=int(payload["recovery_schema_version"]),
            recovery_id=str(payload["recovery_id"]),
            session_id=str(payload["session_id"]),
            recovery_timestamp=str(payload["recovery_timestamp"]),
            original_project_path=None if payload.get("original_project_path") is None else str(payload["original_project_path"]),
            last_normal_save_timestamp=None if payload.get("last_normal_save_timestamp") is None else str(payload["last_normal_save_timestamp"]),
            dirty=bool(payload["dirty"]),
            application_version=str(payload["application_version"]),
            project_schema_version=int(payload["project_schema_version"]),
            project_uuid=str(payload["project_uuid"]),
            input_hash=str(payload["input_hash"]),
            state_hash=str(payload["state_hash"]),
            project=project,
        )
        uuid.UUID(record.recovery_id)
        uuid.UUID(record.session_id)
        uuid.UUID(record.project_uuid)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectSerializationError(f"Recovery file has invalid required fields: {exc}") from exc
    if not record.dirty:
        raise ProjectSerializationError("Recovery snapshot must represent dirty state")
    if record.project_schema_version != project.schema_version:
        raise ProjectSerializationError("Recovery project schema metadata mismatch")
    if record.project_uuid != project.metadata.project_uuid:
        raise ProjectSerializationError("Recovery project UUID mismatch")
    if record.input_hash != project_inputs_hash(project.inputs):
        raise ProjectSerializationError("Recovery input hash mismatch")
    if record.state_hash != _recoverable_state_hash(project):
        raise ProjectSerializationError("Recovery state hash mismatch")
    if _parse_time(record.recovery_timestamp) is None:
        raise ProjectSerializationError("Recovery timestamp is invalid")
    return record


class RecoveryManager:
    def __init__(self, root: str | Path, *, autosave_interval_seconds: int = DEFAULT_AUTOSAVE_INTERVAL_SECONDS) -> None:
        if autosave_interval_seconds < 1:
            raise ValueError("autosave_interval_seconds must be positive")
        self.root = Path(root)
        self.autosave_interval_seconds = autosave_interval_seconds
        self.session_id: str | None = None

    @property
    def corrupt_dir(self) -> Path:
        return self.root / "corrupt"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def begin_session(self, session_id: str | None = None) -> str:
        self.session_id = session_id or str(uuid.uuid4())
        uuid.UUID(self.session_id)
        self._write_json_atomic(
            self.sessions_dir / f"{self.session_id}.json",
            {
                "schema_version": 1,
                "session_id": self.session_id,
                "started_at": utc_now_iso(),
                "clean_shutdown": False,
                "application_version": APPLICATION_VERSION,
            },
        )
        return self.session_id

    def mark_session_clean(self) -> None:
        if self.session_id is None:
            return
        marker = self.sessions_dir / f"{self.session_id}.json"
        self._write_json_atomic(
            marker,
            {
                "schema_version": 1,
                "session_id": self.session_id,
                "ended_at": utc_now_iso(),
                "clean_shutdown": True,
                "application_version": APPLICATION_VERSION,
            },
        )

    def _session_was_clean(self, session_id: str) -> bool:
        marker = self.sessions_dir / f"{session_id}.json"
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False
        return isinstance(payload, Mapping) and payload.get("clean_shutdown") is True

    def _latest_path(self, project_uuid: str) -> Path:
        return self.root / f"{project_uuid}.recovery.json"

    @staticmethod
    def _previous_path(latest: Path) -> Path:
        return latest.with_name(latest.name.replace(".recovery.json", ".recovery.previous.json"))

    def create_record(
        self,
        document: ProjectDocument,
        *,
        original_project_path: str | Path | None,
        dirty: bool,
        last_normal_save_timestamp: str | None = None,
        recovery_timestamp: str | None = None,
    ) -> RecoveryRecord:
        if not dirty:
            raise ProjectSerializationError("Clean projects do not need recovery snapshots")
        if self.session_id is None:
            raise ProjectSerializationError("Recovery session has not been started")
        return RecoveryRecord(
            RECOVERY_SCHEMA_VERSION,
            str(uuid.uuid4()),
            self.session_id,
            recovery_timestamp or utc_now_iso(),
            None if original_project_path is None else str(Path(original_project_path).expanduser().resolve()),
            last_normal_save_timestamp,
            True,
            APPLICATION_VERSION,
            PROJECT_SCHEMA_VERSION,
            document.metadata.project_uuid,
            project_inputs_hash(document.inputs),
            _recoverable_state_hash(document),
            document,
        )

    def write_recovery(
        self,
        document: ProjectDocument,
        *,
        original_project_path: str | Path | None,
        dirty: bool,
        last_normal_save_timestamp: str | None = None,
        recovery_timestamp: str | None = None,
    ) -> Path | None:
        if not dirty:
            return None
        record = self.create_record(
            document,
            original_project_path=original_project_path,
            dirty=True,
            last_normal_save_timestamp=last_normal_save_timestamp,
            recovery_timestamp=recovery_timestamp,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        latest = self._latest_path(document.metadata.project_uuid)
        previous = self._previous_path(latest)
        if latest.is_file():
            self._write_text_atomic(previous, latest.read_text(encoding="utf-8"))
        self._write_text_atomic(latest, serialize_recovery(record))
        return latest

    def try_write_recovery(self, *args: Any, **kwargs: Any) -> RecoveryWriteResult:
        try:
            path = self.write_recovery(*args, **kwargs)
        except (OSError, UnicodeError, ProjectSerializationError, ValueError) as exc:
            return RecoveryWriteResult(False, warning=f"Recovery autosave failed: {exc}")
        return RecoveryWriteResult(path is not None, path=path)

    def _write_text_atomic(self, target: Path, text: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=target.parent,
                prefix=f".{target.name}.", suffix=".tmp", delete=False,
            ) as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
                temporary = Path(stream.name)
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _write_json_atomic(self, target: Path, payload: Mapping[str, Any]) -> None:
        self._write_text_atomic(target, json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    def _quarantine(self, source: Path) -> Path:
        self.corrupt_dir.mkdir(parents=True, exist_ok=True)
        destination = self.corrupt_dir / f"{source.stem}-{uuid.uuid4().hex[:8]}{source.suffix}"
        os.replace(source, destination)
        return destination

    def _classify(self, path: Path, record: RecoveryRecord) -> RecoveryCandidate:
        clean = self._session_was_clean(record.session_id)
        priorities: list[RecoveryPriority] = [RecoveryPriority.AUTOSAVE_NEWER]
        if clean:
            return RecoveryCandidate(path, record, RecoveryStatus.CLEAN_SESSION, None, True, tuple(priorities), "The originating session ended normally")
        if record.original_project_path is None:
            return RecoveryCandidate(path, record, RecoveryStatus.RECOVERABLE, None, clean, tuple(priorities), "Unsaved project recovery")
        sources = inspect_project_sources(record.original_project_path)
        priorities.extend(sources.priorities)
        if sources.official.status is CompatibilityStatus.COMPATIBLE:
            from .serializer import load_project

            official = load_project(record.original_project_path)
            if _recoverable_state_hash(official) == record.state_hash:
                return RecoveryCandidate(path, record, RecoveryStatus.IDENTICAL_TO_OFFICIAL, False, clean, tuple(priorities), "Recovery inputs match the official project")
            recovery_time = _parse_time(record.recovery_timestamp)
            saved_time = _parse_time(official.metadata.modified_at)
            newer = bool(recovery_time and saved_time and recovery_time > saved_time)
            status = RecoveryStatus.RECOVERABLE if newer else RecoveryStatus.STALE
            return RecoveryCandidate(path, record, status, newer, clean, tuple(priorities), "Recovery differs from the official project")
        return RecoveryCandidate(path, record, RecoveryStatus.RECOVERABLE, None, clean, tuple(priorities), "Official project is unavailable or invalid")

    def scan(self, *, include_non_actionable: bool = False) -> RecoveryScanResult:
        if not self.root.is_dir():
            return RecoveryScanResult((), ())
        candidates: list[RecoveryCandidate] = []
        warnings: list[str] = []
        try:
            recovery_paths = sorted(self.root.glob("*.recovery.json"))
        except OSError as exc:
            return RecoveryScanResult((), (f"Recovery directory could not be scanned: {exc}",))
        for path in recovery_paths:
            try:
                candidate = self._classify(path, load_recovery(path))
            except (OSError, ProjectSerializationError, ValueError) as exc:
                previous = self._previous_path(path)
                try:
                    quarantined = self._quarantine(path)
                    warnings.append(f"Corrupt recovery quarantined at {quarantined}: {exc}")
                except OSError as quarantine_exc:
                    warnings.append(f"Corrupt recovery ignored ({path}): {exc}; quarantine failed: {quarantine_exc}")
                if previous.is_file():
                    try:
                        candidate = self._classify(previous, load_recovery(previous))
                        warnings.append(f"Using previous valid recovery snapshot: {previous}")
                    except (OSError, ProjectSerializationError, ValueError) as previous_exc:
                        try:
                            quarantined = self._quarantine(previous)
                            warnings.append(
                                f"Corrupt previous recovery quarantined at {quarantined}: {previous_exc}"
                            )
                        except OSError as quarantine_exc:
                            warnings.append(
                                f"Corrupt previous recovery ignored ({previous}): {previous_exc}; "
                                f"quarantine failed: {quarantine_exc}"
                            )
                        continue
                else:
                    continue
            if candidate.status is RecoveryStatus.RECOVERABLE or include_non_actionable:
                candidates.append(candidate)
        candidates.sort(key=lambda item: item.record.recovery_timestamp, reverse=True)
        return RecoveryScanResult(tuple(candidates), tuple(warnings))

    def restore(self, candidate_or_path: RecoveryCandidate | str | Path) -> ProjectDocument:
        record = candidate_or_path.record if isinstance(candidate_or_path, RecoveryCandidate) else load_recovery(candidate_or_path)
        metadata = replace(record.project.metadata, project_name="Recovered Project", modified_at=utc_now_iso())
        return replace(record.project, metadata=metadata)

    def discard(self, candidate_or_path: RecoveryCandidate | str | Path) -> None:
        path = candidate_or_path.path if isinstance(candidate_or_path, RecoveryCandidate) else Path(candidate_or_path)
        path.unlink(missing_ok=True)

    def cleanup_project(self, project_uuid: str, *, saved_input_hash: str | None = None) -> int:
        removed = 0
        latest = self._latest_path(project_uuid)
        for path in (latest, self._previous_path(latest)):
            if not path.is_file():
                continue
            if saved_input_hash is not None:
                try:
                    if load_recovery(path).input_hash != saved_input_hash:
                        continue
                except ProjectSerializationError:
                    continue
            path.unlink(missing_ok=True)
            removed += 1
        return removed
