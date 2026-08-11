"""GUI-neutral current-project, dirty-state, and recent-project management."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from .schema import ProjectDocument, utc_now_iso
from .serializer import ProjectSerializationError, load_project, save_project


class UnsavedChangesDecision(str, Enum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


@dataclass(frozen=True)
class RecentProject:
    path: Path
    project_name: str
    last_accessed_at: str
    exists: bool


class RecentProjectStore:
    def __init__(self, path: str | Path, *, maximum_entries: int = 10) -> None:
        if maximum_entries < 1:
            raise ValueError("maximum_entries must be positive")
        self.path = Path(path)
        self.maximum_entries = maximum_entries

    def _load_payload(self) -> list[dict[str, str]]:
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            return []
        entries = raw.get("recent_projects")
        if not isinstance(entries, list):
            return []
        valid: list[dict[str, str]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            name = item.get("project_name")
            accessed = item.get("last_accessed_at")
            if all(isinstance(value, str) and value.strip() for value in (path, name, accessed)):
                valid.append({"path": path, "project_name": name, "last_accessed_at": accessed})
        return valid[: self.maximum_entries]

    def entries(self, *, existing_only: bool = False) -> tuple[RecentProject, ...]:
        result = tuple(
            RecentProject(
                path=Path(item["path"]),
                project_name=item["project_name"],
                last_accessed_at=item["last_accessed_at"],
                exists=Path(item["path"]).is_file(),
            )
            for item in self._load_payload()
        )
        if existing_only:
            return tuple(item for item in result if item.exists)
        return result

    def add(self, path: str | Path, project_name: str, *, accessed_at: str | None = None) -> None:
        resolved = str(Path(path).expanduser().resolve())
        entries = [item for item in self._load_payload() if item["path"].casefold() != resolved.casefold()]
        entries.insert(
            0,
            {
                "path": resolved,
                "project_name": project_name,
                "last_accessed_at": accessed_at or utc_now_iso(),
            },
        )
        payload = {"schema_version": 1, "recent_projects": entries[: self.maximum_entries]}
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
                temporary = Path(stream.name)
            os.replace(temporary, self.path)
            temporary = None
        except OSError as exc:
            raise ProjectSerializationError(f"Recent-project list could not be saved: {exc}") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


class ProjectManager:
    def __init__(self, recent_store: RecentProjectStore) -> None:
        self.recent_store = recent_store
        self.current_project: ProjectDocument | None = None
        self.current_path: Path | None = None
        self.is_dirty = False

    def new_project(self, document: ProjectDocument) -> ProjectDocument:
        self.current_project = document
        self.current_path = None
        self.is_dirty = False
        return document

    def open_project(self, path: str | Path) -> ProjectDocument:
        document = load_project(path)
        resolved = Path(path).expanduser().resolve()
        self.current_project = document
        self.current_path = resolved
        self.is_dirty = False
        try:
            self.recent_store.add(resolved, document.metadata.project_name)
        except ProjectSerializationError:
            pass
        return document

    def mark_dirty(self) -> None:
        if self.current_project is not None:
            self.is_dirty = True

    def mark_clean(self, document: ProjectDocument | None = None) -> None:
        if document is not None:
            self.current_project = document
        self.is_dirty = False

    def save(self, document: ProjectDocument, *, create_backup: bool = True) -> Path:
        if self.current_path is None:
            raise ProjectSerializationError("Save As is required for a new project")
        return self.save_as(document, self.current_path, create_backup=create_backup)

    def save_as(
        self,
        document: ProjectDocument,
        path: str | Path,
        *,
        create_backup: bool = True,
    ) -> Path:
        target = save_project(document, path, create_backup=create_backup)
        self.current_project = document
        self.current_path = target
        self.is_dirty = False
        try:
            self.recent_store.add(target, document.metadata.project_name)
        except ProjectSerializationError:
            pass
        return target

    def can_abandon(
        self,
        decision: UnsavedChangesDecision,
        *,
        save_callback: Callable[[], bool] | None = None,
    ) -> bool:
        if not self.is_dirty:
            return True
        if decision is UnsavedChangesDecision.CANCEL:
            return False
        if decision is UnsavedChangesDecision.DISCARD:
            return True
        if save_callback is None:
            return False
        return bool(save_callback())
