"""Phase 11A: where a project's measurement data actually lives.

Three options were available, and the decision is worth recording because it is
not obvious.

**Embed the samples in the .motorproj.** Fully self-contained and trivially
reproducible -- and it puts an arbitrary amount of somebody else's data inside a
file the user mails around. A 5,000-point efficiency map would dominate a
project file that is otherwise a few kilobytes of inputs, and importing a
copyrighted table would silently embed it in every copy of the project.

**Reference the user's original file path.** No bloat at all, and no
reproducibility: the project breaks the moment the file is moved, and it says
nothing about whether the file still holds what was imported.

**Copy into an application-controlled data directory, and reference that.**
Chosen. The project stores a small reference -- id, hash, mapping, comparison
configuration -- and the bytes live once in the app's own store, keyed by
content hash. The project file stays small, the data survives the original being
moved, and the recorded hash makes "this file changed since import" a detectable
state rather than a silent one.

The missing-file case is handled explicitly and never fatally: the dataset shows
as ``MISSING`` with its metadata intact, because the metadata is what says what
was lost.

Like Phase 10H, this rides in ``ui_preferences`` under a namespaced prefix, so
``PROJECT_SCHEMA_VERSION`` does not move and every existing project keeps
loading byte-identically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .schema import DatasetMetadata, metadata_from_payload, metadata_to_payload

EXPERIMENT_PERSISTENCE_SCHEMA_VERSION = "phase11a.experiment.persistence.v1"

#: Namespace inside ``ui_preferences``. Same technique as ``winding.``.
PREFIX = "experiment."

#: The single key holding the JSON-encoded dataset reference list.
DATASETS_KEY = PREFIX + "datasets"
SCHEMA_KEY = PREFIX + "schema_version"


class DatasetAvailability(str, Enum):
    """Whether the referenced data is actually there, and still itself."""

    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    #: Present, but its bytes no longer hash to what was imported.
    CHANGED = "CHANGED"
    #: No file was ever stored: a manually entered dataset.
    INLINE = "INLINE"


@dataclass(frozen=True)
class DatasetReference:
    """What a project remembers about one dataset."""

    dataset_id: str
    metadata: DatasetMetadata
    #: Path inside the application data store, relative to the store root.
    stored_relative_path: str | None
    #: The hash recorded at import. The identity check on every load.
    expected_sha256: str | None
    #: The explicit source-header -> canonical-field mapping used at import.
    column_mapping: Mapping[str, str]
    column_units: Mapping[str, str]
    #: How the comparison was configured: voltage basis, connection, and so on.
    comparison_config: Mapping[str, Any]
    #: Manually entered samples live in the project, because they are small and
    #: have no file to point at.
    inline_rows: tuple[Mapping[str, float], ...] = ()

    @property
    def is_inline(self) -> bool:
        return self.stored_relative_path is None


def reference_to_payload(reference: DatasetReference) -> dict[str, Any]:
    return {
        "dataset_id": reference.dataset_id,
        "metadata": metadata_to_payload(reference.metadata),
        "stored_relative_path": reference.stored_relative_path,
        "expected_sha256": reference.expected_sha256,
        "column_mapping": dict(reference.column_mapping),
        "column_units": dict(reference.column_units),
        "comparison_config": dict(reference.comparison_config),
        "inline_rows": [dict(row) for row in reference.inline_rows],
    }


def reference_from_payload(payload: Mapping[str, Any]) -> DatasetReference:
    return DatasetReference(
        dataset_id=str(payload["dataset_id"]),
        metadata=metadata_from_payload(payload["metadata"]),
        stored_relative_path=payload.get("stored_relative_path"),
        expected_sha256=payload.get("expected_sha256"),
        column_mapping=dict(payload.get("column_mapping") or {}),
        column_units=dict(payload.get("column_units") or {}),
        comparison_config=dict(payload.get("comparison_config") or {}),
        inline_rows=tuple(dict(row) for row in payload.get("inline_rows") or ()),
    )


def to_preferences(references: Sequence[DatasetReference]) -> dict[str, Any]:
    """Flatten dataset references into ``ui_preferences`` scalar keys.

    ``ui_preferences`` is a flat scalar map, so the list is JSON-encoded into a
    single string key rather than nested. Sorted and separator-normalised so the
    same references always produce the same bytes.
    """

    if not references:
        return {}
    return {
        SCHEMA_KEY: EXPERIMENT_PERSISTENCE_SCHEMA_VERSION,
        DATASETS_KEY: json.dumps(
            [reference_to_payload(reference) for reference in references],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


def from_preferences(
    preferences: Mapping[str, Any] | None,
) -> tuple[tuple[DatasetReference, ...], tuple[str, ...]]:
    """Rebuild the references, plus any problems found doing so.

    A project with no ``experiment.datasets`` key simply has no datasets, which
    is every project written before this phase. That is not an error and is not
    reported as one.
    """

    preferences = preferences or {}
    raw = preferences.get(DATASETS_KEY)
    if not raw:
        return (), ()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as error:
        return (), (f"数据集引用无法解析，已忽略：{error}",)
    references: list[DatasetReference] = []
    problems: list[str] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            references.append(reference_from_payload(item))
        except (KeyError, TypeError, ValueError) as error:
            problems.append(f"跳过一条无法解析的数据集引用：{error}")
    return tuple(references), tuple(problems)


class DatasetStore:
    """The application-controlled directory holding imported measurement files.

    Content-addressed: a file is stored under its own SHA-256, so importing the
    same data twice stores it once, and the stored path *is* the identity check.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, sha256: str, suffix: str = ".csv") -> Path:
        return self.root / sha256[:2] / f"{sha256}{suffix}"

    def store(self, source: Path, sha256: str) -> str:
        """Copy a file in and return its store-relative path."""

        destination = self.path_for(sha256, Path(source).suffix or ".csv")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(Path(source).read_bytes())
        return str(destination.relative_to(self.root)).replace("\\", "/")

    def store_text(self, text: str, sha256: str, suffix: str = ".csv") -> str:
        destination = self.path_for(sha256, suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_text(text, encoding="utf-8")
        return str(destination.relative_to(self.root)).replace("\\", "/")

    def resolve(self, relative_path: str | None) -> Path | None:
        return None if not relative_path else self.root / relative_path

    def availability(self, reference: DatasetReference) -> DatasetAvailability:
        """Whether the referenced bytes are present and unchanged."""

        from .schema import file_sha256

        if reference.is_inline:
            return DatasetAvailability.INLINE
        path = self.resolve(reference.stored_relative_path)
        if path is None or not path.is_file():
            return DatasetAvailability.MISSING
        if reference.expected_sha256 and file_sha256(path) != reference.expected_sha256:
            return DatasetAvailability.CHANGED
        return DatasetAvailability.AVAILABLE


AVAILABILITY_MESSAGES_ZH = {
    DatasetAvailability.AVAILABLE: "数据文件存在，且与导入时的哈希一致。",
    DatasetAvailability.MISSING: (
        "数据文件缺失。元数据仍然保留，因此可以看出丢失的是什么；"
        "但该数据集不参与任何比较，也不会以任何形式补零。"
    ),
    DatasetAvailability.CHANGED: (
        "数据文件存在，但其哈希与导入时不一致：文件已被改动。"
        "在重新导入并确认之前，该数据集不参与比较。"
    ),
    DatasetAvailability.INLINE: "手工录入的数据，保存在项目文件内部。",
}

#: Availability states in which a dataset may take part in a comparison.
USABLE_AVAILABILITY = frozenset(
    {DatasetAvailability.AVAILABLE, DatasetAvailability.INLINE}
)
