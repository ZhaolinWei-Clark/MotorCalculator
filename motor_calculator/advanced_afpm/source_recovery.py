"""Load Phase 7F source-recovery evidence without changing Phase 7C records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


class RecoveryFieldStatus(str, Enum):
    SOURCE_PROVIDED = "source_provided"
    SAFELY_DERIVED = "safely_derived"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RecoveredField:
    status: RecoveryFieldStatus
    value: Any
    unit: str | None
    source_url: str
    page: str
    location: str
    note: str
    derivation: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status in {RecoveryFieldStatus.SOURCE_PROVIDED, RecoveryFieldStatus.SAFELY_DERIVED}


def load_phase7f_source_recovery(path: Path) -> Mapping[str, Mapping[str, RecoveredField]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    recovered = {}
    for source_id, source_raw in raw["sources"].items():
        fields = {}
        for name, field in source_raw["fields"].items():
            status = RecoveryFieldStatus(field["status"])
            value = field.get("value")
            if status is RecoveryFieldStatus.UNAVAILABLE and value is not None:
                raise ValueError(f"unavailable recovery field {name} must be null")
            if status in {RecoveryFieldStatus.SOURCE_PROVIDED, RecoveryFieldStatus.SAFELY_DERIVED} and value is None:
                raise ValueError(f"usable recovery field {name} requires a value")
            provenance = field["provenance"]
            derivation = field.get("derivation")
            if status is RecoveryFieldStatus.SAFELY_DERIVED and not derivation:
                raise ValueError(f"safely derived recovery field {name} requires derivation")
            fields[name] = RecoveredField(
                status=status,
                value=value,
                unit=field.get("unit"),
                source_url=provenance["source_url"],
                page=provenance["page"],
                location=provenance["location"],
                note=provenance["note"],
                derivation=derivation,
            )
        recovered[source_id] = MappingProxyType(fields)
    return MappingProxyType(recovered)
