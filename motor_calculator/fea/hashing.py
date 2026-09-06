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

#: Bumped by Phase 10C. v1 put the analytical winding factor inside ``case_id``,
#: so changing a number the solver never sees invented a new machine and
#: discarded a perfectly valid field solution, while the analytical fingerprint
#: did not move at all. Digests are not comparable across versions.
FEA_CASE_HASH_VERSION = "phase10c.fea.hash.v2"

#: Fields excluded from ``case_id``. ``case_id`` is the digest itself, and the
#: remaining entries are commentary or the analytical side of the comparison.
CASE_HASH_EXCLUDED_FIELDS = frozenset(
    {"case_id", "analytical", "notes", "supportability"}
)

#: Fields *within* a nested structure that are analytical rather than
#: solver-visible.
#:
#: The winding factor and its provenance live on the winding map for
#: convenience, but they never reach the emitted Lua: the solver sees the coil
#: phase assignment, polarity, span and turns, and computes flux linkage from
#: the field. Leaving them in ``case_id`` meant an analytical-only edit
#: invalidated the FEA result it should have been compared against.
CASE_HASH_EXCLUDED_NESTED_FIELDS = {
    "winding": frozenset({"winding_factor_analytical", "winding_factor_provenance"}),
}

#: Analytical-only fields that the *fingerprint* must cover, addressed as
#: ``(container field, field)``. The comparison reports the entered winding
#: factor against the solved geometry, so a change to it changes the comparison
#: and must invalidate it.
ANALYTICAL_FINGERPRINT_EXTRA_FIELDS = (
    ("winding", "winding_factor_analytical"),
    ("winding", "winding_factor_provenance"),
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
    """Digest of everything the solver would see.

    Analytical-only values are excluded, so an edit the solver cannot observe
    never invalidates a field solution that is still perfectly valid for it.
    """

    payload_fields: dict[str, Any] = {}
    for field in fields(case):
        if field.name in CASE_HASH_EXCLUDED_FIELDS:
            continue
        value = getattr(case, field.name)
        excluded = CASE_HASH_EXCLUDED_NESTED_FIELDS.get(field.name)
        if excluded and is_dataclass(value) and not isinstance(value, type):
            payload_fields[field.name] = {
                nested.name: _canonical(getattr(value, nested.name))
                for nested in fields(value)
                if nested.name not in excluded
            }
        else:
            payload_fields[field.name] = _canonical(value)
    return _digest({"hash_version": FEA_CASE_HASH_VERSION, "fields": payload_fields})


def compute_analytical_fingerprint(case: Any) -> str:
    """Digest of the analytical prediction this case will be compared against.

    Covers the captured prediction *and* the analytical-only values the
    comparison reads, so changing either invalidates the comparison without
    discarding the solver result.
    """

    extra: dict[str, Any] = {}
    for container_name, field_name in ANALYTICAL_FINGERPRINT_EXTRA_FIELDS:
        container = getattr(case, container_name, None)
        if container is not None and hasattr(container, field_name):
            extra[f"{container_name}.{field_name}"] = _canonical(
                getattr(container, field_name)
            )
    payload = {
        "hash_version": FEA_CASE_HASH_VERSION,
        "application_version": case.application_version,
        "analytical": _canonical(case.analytical),
        "analytical_only_inputs": extra,
    }
    return _digest(payload)
