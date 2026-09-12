"""Phase 10H: persisting winding authority and manufacturability state.

Why no schema bump
------------------
``ProjectDocument.ui_preferences`` is already persisted, already round-trips, and
already carries RC2's ``winding_factor_mode``. Putting the winding state there as
flat scalar keys means:

* ``PROJECT_SCHEMA_VERSION`` does not move, so **every existing .motorproj file
  keeps loading exactly as before** -- no migration to get wrong, and no risk of
  invalidating a historical file;
* the *absence* of ``winding.authority`` in a document is itself the signal that
  the project predates these semantics, which is precisely the ``LEGACY_MANUAL``
  condition;
* a new project round-trips exactly, because the values are plain scalars.

A schema bump would have bought a nested block and cost a migration path for
every file already in existence. The trade was not worth it, and the decision is
recorded here rather than left implicit.

``ui_preferences`` is typed as a flat scalar mapping, so keys are namespaced with
a ``winding.`` prefix instead of nesting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .authority import WindingAuthority, classify_loaded_authority
from .slot_fill import DEFAULT_PACKING_FACTOR

WINDING_PERSISTENCE_SCHEMA_VERSION = "phase10h.winding_persistence.v1"

#: Namespace for every key this module owns inside ``ui_preferences``.
PREFIX = "winding."

#: The key whose absence means "this project predates winding authority".
AUTHORITY_KEY = PREFIX + "authority"

DEFAULT_LINER_THICKNESS_MM = 0.25
DEFAULT_CLEARANCE_MM = 0.10
DEFAULT_INSULATION_RATIO = 1.08
DEFAULT_LAYERS = 2


@dataclass(frozen=True)
class WindingProjectState:
    """Everything about the winding that a project must remember.

    Derived quantities -- ``kd``, ``kp``, ``ks``, the production winding factor,
    the fill ratios -- are deliberately **not** stored. They are deterministic
    functions of these inputs, and storing them would create a second source of
    truth that can drift from the first.
    """

    schema_version: str = WINDING_PERSISTENCE_SCHEMA_VERSION
    authority: WindingAuthority = WindingAuthority.LEGACY_MANUAL
    manual_winding_factor: float | None = None
    coil_span_slots: int | None = None
    layers: int = DEFAULT_LAYERS
    parallel_strands: int | None = None
    skew_slots: float = 0.0
    turns_per_coil: float | None = None
    insulated_diameter_mm: float | None = None
    insulation_ratio: float = DEFAULT_INSULATION_RATIO
    liner_thickness_mm: float = DEFAULT_LINER_THICKNESS_MM
    clearance_mm: float = DEFAULT_CLEARANCE_MM
    packing_factor: float = DEFAULT_PACKING_FACTOR

    @property
    def is_legacy(self) -> bool:
        return self.authority is WindingAuthority.LEGACY_MANUAL


def _scalar(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def to_preferences(state: WindingProjectState) -> dict[str, Any]:
    """Flatten the winding state into ``ui_preferences`` scalar keys."""

    payload: dict[str, Any] = {
        AUTHORITY_KEY: state.authority.value,
        PREFIX + "schema_version": state.schema_version,
        PREFIX + "layers": int(state.layers),
        PREFIX + "skew_slots": float(state.skew_slots),
        PREFIX + "insulation_ratio": float(state.insulation_ratio),
        PREFIX + "liner_thickness_mm": float(state.liner_thickness_mm),
        PREFIX + "clearance_mm": float(state.clearance_mm),
        PREFIX + "packing_factor": float(state.packing_factor),
    }
    for key, value in (
        ("manual_winding_factor", state.manual_winding_factor),
        ("coil_span_slots", state.coil_span_slots),
        ("parallel_strands", state.parallel_strands),
        ("turns_per_coil", state.turns_per_coil),
        ("insulated_diameter_mm", state.insulated_diameter_mm),
    ):
        if value is not None:
            payload[PREFIX + key] = _scalar(value)
    return payload


def _number(preferences: Mapping[str, Any], key: str, fallback):
    raw = preferences.get(PREFIX + key)
    if raw is None:
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return fallback
    return value if math.isfinite(value) else fallback


def _integer(preferences: Mapping[str, Any], key: str, fallback):
    value = _number(preferences, key, None)
    if value is None:
        return fallback
    return int(round(value))


def from_preferences(
    preferences: Mapping[str, Any] | None, *, stored_manual_winding_factor: float | None
) -> WindingProjectState:
    """Rebuild the winding state from a loaded project.

    A document with no ``winding.authority`` key predates these semantics and is
    classified ``LEGACY_MANUAL``, keeping its stored winding factor exactly. It is
    never promoted to AUTO on load: that would change an existing design's
    results without the user asking for it.
    """

    preferences = preferences or {}
    authority = classify_loaded_authority(
        {"authority": preferences.get(AUTHORITY_KEY)}
        if preferences.get(AUTHORITY_KEY) is not None
        else None,
        has_manual_value=stored_manual_winding_factor is not None,
    )
    return WindingProjectState(
        authority=authority,
        manual_winding_factor=_number(
            preferences, "manual_winding_factor", stored_manual_winding_factor
        ),
        coil_span_slots=_integer(preferences, "coil_span_slots", None),
        layers=_integer(preferences, "layers", DEFAULT_LAYERS) or DEFAULT_LAYERS,
        parallel_strands=_integer(preferences, "parallel_strands", None),
        skew_slots=_number(preferences, "skew_slots", 0.0),
        turns_per_coil=_number(preferences, "turns_per_coil", None),
        insulated_diameter_mm=_number(preferences, "insulated_diameter_mm", None),
        insulation_ratio=_number(preferences, "insulation_ratio", DEFAULT_INSULATION_RATIO),
        liner_thickness_mm=_number(preferences, "liner_thickness_mm", DEFAULT_LINER_THICKNESS_MM),
        clearance_mm=_number(preferences, "clearance_mm", DEFAULT_CLEARANCE_MM),
        packing_factor=_number(preferences, "packing_factor", DEFAULT_PACKING_FACTOR),
    )


def new_project_state(
    *, slots=None, pole_pairs=None, coil_span_slots=None, manual_winding_factor=None
) -> WindingProjectState:
    """The default state for a project created after Phase 10H.

    Prefers ``AUTO_FROM_GEOMETRY`` when the geometry actually supports a
    derivation. When it does not, no winding factor is invented: the project
    falls back to a manual override if a value exists, and to ``UNRESOLVED`` if
    none does.
    """

    from .authority import ideal_geometry_winding_factor

    geometry = ideal_geometry_winding_factor(
        slots=slots, pole_pairs=pole_pairs, coil_span_slots=coil_span_slots
    )
    if geometry is not None:
        authority = WindingAuthority.AUTO_FROM_GEOMETRY
    elif manual_winding_factor is not None:
        authority = WindingAuthority.MANUAL_OVERRIDE
    else:
        authority = WindingAuthority.UNRESOLVED
    return WindingProjectState(
        authority=authority,
        manual_winding_factor=manual_winding_factor,
        coil_span_slots=int(coil_span_slots) if coil_span_slots else None,
    )


# ---------------------------------------------------------------------------
# Phase 11A: the bridge between the authority model and the RC2 ui_preferences
# keys the GUI actually persists.
# ---------------------------------------------------------------------------

#: The RC2 keys ``ui_preferences`` already carries for the winding factor. They
#: are reused rather than duplicated so no project-schema change is needed and
#: every existing file keeps loading exactly as before.
RC2_MODE_KEY = "winding_factor_mode"
RC2_COIL_SPAN_KEY = "coil_span_slots"
RC2_SKEW_KEY = "skew_slots"


def new_project_ui_preferences(
    *,
    slots=None,
    pole_pairs=None,
    coil_span_slots=None,
    manual_winding_factor=None,
    skew_slots: float = 0.0,
) -> dict[str, Any]:
    """The ``ui_preferences`` a project created *now* should be born with.

    This is the production consumer of :func:`new_project_state` that Phase 10H
    specified but never wired in. Without it, ``File -> New`` produced a
    document with no winding keys at all -- which is precisely the signal
    :func:`from_preferences` reads as "this project predates the semantics" --
    so every brand-new project was classified ``LEGACY_MANUAL``.

    A *new* document saying nothing and an *old file* saying nothing are not the
    same statement, and that is the whole bug. Loading still treats silence as
    legacy; only creation is changed.

    ``AUTO`` is emitted only when the geometry genuinely supports a derivation.
    When it does not, the manual value is preserved and the mode stays manual:
    no winding factor is ever invented here.
    """

    from ..motor_core.winding_factor import WindingFactorMode

    state = new_project_state(
        slots=slots,
        pole_pairs=pole_pairs,
        coil_span_slots=coil_span_slots,
        manual_winding_factor=manual_winding_factor,
    )
    is_auto = state.authority is WindingAuthority.AUTO_FROM_GEOMETRY
    return {
        RC2_MODE_KEY: (
            WindingFactorMode.AUTO if is_auto else WindingFactorMode.MANUAL
        ).value,
        RC2_COIL_SPAN_KEY: (
            "" if state.coil_span_slots is None else str(int(state.coil_span_slots))
        ),
        RC2_SKEW_KEY: str(float(skew_slots)),
        AUTHORITY_KEY: state.authority.value,
    }
