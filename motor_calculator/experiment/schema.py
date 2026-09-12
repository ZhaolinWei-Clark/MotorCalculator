"""Phase 11A: the dataset record.

Two opposing failure modes had to be avoided here.

Demanding complete metadata would make the framework useless for exactly the
data it exists to accept: a 1998 paper does not record who operated the
dynamometer, and a textbook table has no acquisition timestamp. A schema that
refuses such a source pushes the user into inventing values to satisfy it.

Accepting silent blanks is worse, because a missing field then reads as a
measured zero or an implied default.

So: almost every field is optional, and every absent field is the explicit
sentinel :data:`UNKNOWN`. ``UNKNOWN`` is a value that says "nobody knows", it
renders as such in every view, and it is never a number.

Only four things are genuinely required -- an id, a title, a source type and a
test type -- because a dataset without them cannot be filed, displayed or
compared at all.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .sources import DatasetSourceType, require_reclassifiable

DATASET_SCHEMA_VERSION = "phase11a.experiment.dataset.v1"


class _Unknown:
    """The sentinel for information that is genuinely not known.

    Distinct from ``None`` on purpose: ``None`` in this codebase already means
    "not applicable" or "not yet computed" in a dozen places, and conflating
    "the paper does not say" with "we did not compute it" is how an unknown
    silently becomes a default.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "UNKNOWN"

    def __str__(self) -> str:
        return "UNKNOWN"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Unknown) or other == "UNKNOWN"

    def __hash__(self) -> int:
        return hash("UNKNOWN")


UNKNOWN = _Unknown()

#: What a field holds when it is optional: a string, or ``UNKNOWN``.
Optional = Any


class TestType(str, Enum):
    """The kinds of bench test this framework understands.

    The four implemented now are the four that can be compared against something
    this project actually models. The rest are declared so an importer, a
    template and a persisted dataset written today remain readable when they are
    implemented, rather than needing a schema migration to add a member.
    """

    #: "Test" here means a bench test, not a unit test. Without this, pytest
    #: tries to collect the enum as a test class wherever it is imported.
    __test__ = False

    # Implemented in Phase 11A.
    PHASE_RESISTANCE = "PHASE_RESISTANCE"
    NO_LOAD_BACK_EMF = "NO_LOAD_BACK_EMF"
    TORQUE_CURRENT = "TORQUE_CURRENT"
    EFFICIENCY = "EFFICIENCY"

    # Declared, not implemented. Importing one is accepted and stored; it simply
    # has no analysis attached yet, and says so.
    INDUCTANCE = "INDUCTANCE"
    THERMAL = "THERMAL"
    TORQUE_SPEED = "TORQUE_SPEED"
    NO_LOAD_CURRENT = "NO_LOAD_CURRENT"
    LOSS_MAP = "LOSS_MAP"


#: Test types with an analysis implementation in this phase.
IMPLEMENTED_TEST_TYPES = frozenset(
    {
        TestType.PHASE_RESISTANCE,
        TestType.NO_LOAD_BACK_EMF,
        TestType.TORQUE_CURRENT,
        TestType.EFFICIENCY,
    }
)

TEST_TYPE_LABELS_ZH = {
    TestType.PHASE_RESISTANCE: "相电阻测量",
    TestType.NO_LOAD_BACK_EMF: "空载反电动势（Ke）",
    TestType.TORQUE_CURRENT: "转矩-电流",
    TestType.EFFICIENCY: "效率",
    TestType.INDUCTANCE: "电感（尚未实现分析）",
    TestType.THERMAL: "温升（尚未实现分析）",
    TestType.TORQUE_SPEED: "转矩-转速包络（尚未实现分析）",
    TestType.NO_LOAD_CURRENT: "空载电流（尚未实现分析）",
    TestType.LOSS_MAP: "损耗分布图（尚未实现分析）",
}


class RedistributionStatus(str, Enum):
    """Whether the raw numbers may be committed to this repository."""

    ALLOWED = "ALLOWED"
    NOT_ALLOWED = "NOT_ALLOWED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Citation:
    """Where a public source came from. Every field may be ``UNKNOWN``."""

    title: Any = UNKNOWN
    authors: Any = UNKNOWN
    publication: Any = UNKNOWN
    year: Any = UNKNOWN
    doi: Any = UNKNOWN
    url: Any = UNKNOWN
    page: Any = UNKNOWN
    table_or_figure: Any = UNKNOWN
    license: Any = UNKNOWN
    redistribution: RedistributionStatus = RedistributionStatus.UNKNOWN
    notes: Any = UNKNOWN

    @property
    def may_commit_raw_data(self) -> bool:
        """Raw numbers may be committed only on an explicit yes.

        ``UNKNOWN`` is treated as no. An unclear licence is not permission, and
        the cost of guessing wrong is a copyright problem in a public repo.
        """

        return self.redistribution is RedistributionStatus.ALLOWED


@dataclass(frozen=True)
class MachineIdentity:
    """What is known about the machine a dataset was measured on.

    Every field is optional. A dataset that knows nothing about its machine is
    accepted and stored; it simply cannot be found compatible with anything,
    which :mod:`.compatibility` reports as ``INSUFFICIENT_METADATA`` rather than
    as a match or a mismatch.
    """

    description: Any = UNKNOWN
    machine_id: Any = UNKNOWN
    topology: Any = UNKNOWN
    pole_count: Any = UNKNOWN
    slot_count: Any = UNKNOWN
    phases: Any = UNKNOWN
    connection: Any = UNKNOWN
    turns_per_phase: Any = UNKNOWN
    rated_speed_rpm: Any = UNKNOWN
    rated_power_w: Any = UNKNOWN
    winding_description: Any = UNKNOWN
    geometry_note: Any = UNKNOWN

    @property
    def known_field_count(self) -> int:
        return sum(1 for value in asdict(self).values() if value != UNKNOWN)


@dataclass(frozen=True)
class DatasetMetadata:
    """Everything known about one imported or entered dataset."""

    dataset_id: str
    title: str
    source_type: DatasetSourceType
    test_type: TestType
    schema_version: str = DATASET_SCHEMA_VERSION
    machine: MachineIdentity = field(default_factory=MachineIdentity)
    citation: Citation = field(default_factory=Citation)
    measurement_date: Any = UNKNOWN
    operator: Any = UNKNOWN
    instrument: Any = UNKNOWN
    notes: Any = UNKNOWN
    #: SHA-256 of the bytes that were imported. The identity of the data, kept
    #: so a later load can say whether the file still holds what was imported.
    raw_file_hash: Any = UNKNOWN
    raw_file_name: Any = UNKNOWN
    import_timestamp_utc: Any = UNKNOWN
    #: How the numbers reached this record: "CSV_IMPORT", "MANUAL_ENTRY",
    #: "SYNTHETIC_FIXTURE", ...
    data_provenance: str = "UNSPECIFIED"
    #: Set only by the test suite's fixture builder. A dataset carrying this flag
    #: is refused by the production dataset store.
    test_fixture_only: bool = False

    def __post_init__(self) -> None:
        if not str(self.dataset_id).strip():
            raise ValueError("a dataset needs an id")
        if not str(self.title).strip():
            raise ValueError("a dataset needs a title")
        object.__setattr__(self, "source_type", DatasetSourceType(self.source_type))
        object.__setattr__(self, "test_type", TestType(self.test_type))
        if self.test_fixture_only and self.source_type is not DatasetSourceType.SIMULATED_REFERENCE:
            raise ValueError(
                "a test fixture must be classified SIMULATED_REFERENCE; a fixture "
                "that claims to be experimental is exactly what the firewall exists "
                "to prevent"
            )

    @property
    def is_experimental(self) -> bool:
        from .sources import is_experimental

        return is_experimental(self.source_type)

    @property
    def analysis_implemented(self) -> bool:
        return self.test_type in IMPLEMENTED_TEST_TYPES

    def reclassified(self, proposed: DatasetSourceType | str) -> "DatasetMetadata":
        """A copy under a new source class, if the change is permitted."""

        return replace(
            self, source_type=require_reclassifiable(self.source_type, proposed)
        )


def file_sha256(path: Path) -> str:
    """The hash recorded as a dataset's identity."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _plain(value: Any) -> Any:
    if isinstance(value, _Unknown):
        return "UNKNOWN"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    return value


def metadata_to_payload(metadata: DatasetMetadata) -> dict[str, Any]:
    """A JSON-safe dict. ``UNKNOWN`` survives as the string ``"UNKNOWN"``."""

    payload = {key: _plain(value) for key, value in asdict(metadata).items()}
    payload["machine"] = {key: _plain(value) for key, value in asdict(metadata.machine).items()}
    payload["citation"] = {key: _plain(value) for key, value in asdict(metadata.citation).items()}
    return payload


def _restore(value: Any) -> Any:
    return UNKNOWN if value == "UNKNOWN" else value


def metadata_from_payload(payload: Mapping[str, Any]) -> DatasetMetadata:
    """Rebuild a record. Anything absent or ``"UNKNOWN"`` stays unknown."""

    machine_payload = dict(payload.get("machine") or {})
    citation_payload = dict(payload.get("citation") or {})
    redistribution = citation_payload.pop("redistribution", "UNKNOWN")
    citation = Citation(
        **{key: _restore(value) for key, value in citation_payload.items()},
        redistribution=RedistributionStatus(str(redistribution or "UNKNOWN")),
    )
    machine = MachineIdentity(
        **{key: _restore(value) for key, value in machine_payload.items()}
    )
    known = {
        key: _restore(value)
        for key, value in payload.items()
        if key not in {"machine", "citation"}
    }
    known.pop("schema_version", None)
    return DatasetMetadata(
        schema_version=str(payload.get("schema_version") or DATASET_SCHEMA_VERSION),
        machine=machine,
        citation=citation,
        **known,
    )


def metadata_to_json(metadata: DatasetMetadata) -> str:
    return json.dumps(
        metadata_to_payload(metadata), ensure_ascii=False, indent=2, sort_keys=True
    )
