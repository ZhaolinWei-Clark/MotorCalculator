"""Deterministic case hashing, so a stale FEA result can never be reused.

Two separate digests are kept, because two different things can go stale:

``case_id``
    Covers everything the *solver* sees: geometry, materials, winding, operating
    point, mesh policy, symmetry and the schema version. If any of these change,
    the machine that was solved is no longer the machine being asked about, and
    the old FEA numbers are void.

``analytical fingerprint``
    Covers the analytical prediction the FEA is compared against. If only this
    changes, the FEA result is still physically valid but the *comparison* is
    stale and must be recomputed.

Floats are hashed through :meth:`float.hex`, which is exact and round-trips, so
the digest cannot drift with decimal formatting.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

FEA_CASE_HASH_VERSION = "phase10a.fea.hash.v1"

#: Fields excluded from ``case_id``. ``case_id`` is the digest itself, and the
#: remaining entries are commentary or the analytical side of the comparison.
CASE_HASH_EXCLUDED_FIELDS = frozenset(
    {"case_id", "analytical", "notes", "supportability"}
)


def _canonical(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite values cannot be hashed")
        # ``float.hex`` is exact; decimal formatting is not.
        return float.hex(value)
    if isinstance(value, int):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, str):
        return value
    raise TypeError(f"cannot canonicalise {type(value)!r} for hashing")


def _digest(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_case_hash(case: Any) -> str:
    """Digest of everything the solver would see."""

    payload = {
        "hash_version": FEA_CASE_HASH_VERSION,
        "fields": {
            field.name: _canonical(getattr(case, field.name))
            for field in fields(case)
            if field.name not in CASE_HASH_EXCLUDED_FIELDS
        },
    }
    return _digest(payload)


def compute_analytical_fingerprint(case: Any) -> str:
    """Digest of the analytical prediction this case will be compared against."""

    payload = {
        "hash_version": FEA_CASE_HASH_VERSION,
        "application_version": case.application_version,
        "analytical": _canonical(case.analytical),
    }
    return _digest(payload)
