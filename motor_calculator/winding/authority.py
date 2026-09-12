"""Phase 10H: one authority for the production winding factor.

Three numbers in this project have been called ``k_w``, and the last four phases
were largely spent on what that cost. Phase 10G named them. This module decides
which one production is allowed to use, and records why.

The three authority states
--------------------------
``AUTO_FROM_GEOMETRY``
    The production winding factor comes from the production winding model: the
    slot-EMF star's ``kd * kp * ks``. Geometry-derived, and reproducible from
    the stored inputs.

``MANUAL_OVERRIDE``
    The user deliberately chose a value. The software says so, and says what the
    geometry would have given, so an override is visible rather than silent.

``LEGACY_MANUAL``
    A project or preset created before these semantics existed. Its stored value
    is preserved **exactly**. It is never re-derived from geometry, because
    doing so would silently change the results of an existing design.

``UNRESOLVED``
    AUTO was requested but the geometry does not support a derivation, and no
    manual value is available. No number is invented; the caller is told.

The firewall
------------
``meshed_geometry_winding_factor`` -- Phase 10E's Fourier projection of the
conductor layout a solver meshes -- is **never** production-authoritative. It
describes a 2D unrolled slice built for FEA interpretation, not the real
three-dimensional winding a production back-EMF formula is about. For the
reference design the two differ by 10.4 %, so the distinction is not academic.

:func:`resolve_production_winding_factor` accepts no argument by which a meshed
value could enter, and :data:`PRODUCTION_ADMISSIBLE_PROVENANCE` enumerates what
may. A test asserts both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

WINDING_AUTHORITY_SCHEMA_VERSION = "phase10h.winding_authority.v1"


class WindingAuthority(str, Enum):
    """Who decides the production winding factor."""

    AUTO_FROM_GEOMETRY = "AUTO_FROM_GEOMETRY"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    LEGACY_MANUAL = "LEGACY_MANUAL"
    UNRESOLVED = "UNRESOLVED"


AUTHORITY_LABELS_ZH = {
    WindingAuthority.AUTO_FROM_GEOMETRY: "自动（由绕组几何推导）",
    WindingAuthority.MANUAL_OVERRIDE: "手动覆盖",
    WindingAuthority.LEGACY_MANUAL: "历史项目手动值",
    WindingAuthority.UNRESOLVED: "未解析（几何不足且无手动值）",
}

#: Provenance strings a production winding factor may legitimately carry.
#: ``MESHED_GEOMETRY`` is deliberately absent.
PRODUCTION_ADMISSIBLE_PROVENANCE = frozenset(
    {
        "IDEAL_SLOT_STAR_GEOMETRY",
        "MANUAL_USER",
        "LEGACY_PROJECT",
        "NONE",
    }
)

#: The provenance a meshed FEA winding factor carries. Never admissible above.
MESHED_FEA_PROVENANCE = "MESHED_GEOMETRY_FEA_DIAGNOSTIC_ONLY"


@dataclass(frozen=True)
class ProductionWindingFactor:
    """The production winding factor and the reason it is that value."""

    schema_version: str
    value: float | None
    authority: WindingAuthority
    provenance: str
    #: What the slot-star geometry gives, when it can be computed at all. Shown
    #: alongside an override so the difference is visible.
    geometry_value: float | None
    #: The stored manual number, when one exists.
    manual_value: float | None
    reason_zh: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.provenance not in PRODUCTION_ADMISSIBLE_PROVENANCE:
            raise ValueError(
                f"{self.provenance!r} is not admissible as production winding-factor "
                "provenance; a meshed FEA winding factor is diagnostic only"
            )
        if self.value is not None and not 0.0 < self.value <= 1.0:
            raise ValueError(
                f"a production winding factor must lie in (0, 1]; got {self.value!r}"
            )

    @property
    def is_resolved(self) -> bool:
        return self.value is not None

    @property
    def overrides_geometry(self) -> bool:
        """True when a manual value is in force and differs from the geometry."""

        if self.authority is WindingAuthority.AUTO_FROM_GEOMETRY:
            return False
        if self.value is None or self.geometry_value is None:
            return False
        return abs(self.value / self.geometry_value - 1.0) > 5.0e-4

    @property
    def geometry_delta_percent(self) -> float | None:
        if self.value is None or not self.geometry_value:
            return None
        return (self.value / self.geometry_value - 1.0) * 100.0


def ideal_geometry_winding_factor(
    *,
    slots,
    pole_pairs,
    coil_span_slots,
    phases: int = 3,
    skew_slots: float = 0.0,
) -> float | None:
    """The production geometry value: the slot-EMF star's ``kd * kp * ks``.

    Returns ``None`` rather than a guess when the combination admits no balanced
    symmetric winding or the inputs are incomplete. Nothing here consults a
    solver model.
    """

    from ..motor_core.winding_factor import (
        WindingFactorError,
        compute_fundamental_winding_factor,
    )

    try:
        slot_count = int(slots)
        pole_pair_count = int(pole_pairs)
        span = int(coil_span_slots)
    except (TypeError, ValueError):
        return None
    if slot_count <= 0 or pole_pair_count <= 0 or span <= 0:
        return None
    try:
        return compute_fundamental_winding_factor(
            slots=slot_count,
            pole_pairs=pole_pair_count,
            coil_span_slots=span,
            phases=phases,
            skew_slots=skew_slots,
        ).fundamental_winding_factor
    except (WindingFactorError, ValueError):
        return None


def resolve_production_winding_factor(
    *,
    authority: WindingAuthority | str,
    manual_value: float | None,
    slots=None,
    pole_pairs=None,
    coil_span_slots=None,
    phases: int = 3,
    skew_slots: float = 0.0,
) -> ProductionWindingFactor:
    """The single decision point for which winding factor production may use.

    There is deliberately **no parameter** through which a meshed FEA winding
    factor could be supplied. Callers that hold one must not pass it here.

    ``LEGACY_MANUAL`` never re-derives: an existing project keeps the number it
    was designed with, whatever the geometry would now say.
    """

    state = (
        authority
        if isinstance(authority, WindingAuthority)
        else WindingAuthority(str(authority).strip().upper())
    )
    geometry = ideal_geometry_winding_factor(
        slots=slots,
        pole_pairs=pole_pairs,
        coil_span_slots=coil_span_slots,
        phases=phases,
        skew_slots=skew_slots,
    )
    manual = None
    if manual_value is not None:
        candidate = float(manual_value)
        if math.isfinite(candidate) and 0.0 < candidate <= 1.0:
            manual = candidate

    warnings: list[str] = []

    if state is WindingAuthority.LEGACY_MANUAL:
        if manual is None:
            return ProductionWindingFactor(
                schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
                value=None, authority=WindingAuthority.UNRESOLVED, provenance="NONE",
                geometry_value=geometry, manual_value=None,
                reason_zh="历史项目标记为手动值，但未存储可用的绕组系数。",
                warnings=("legacy project carries no usable manual winding factor",),
            )
        if geometry is not None and abs(manual / geometry - 1.0) > 5.0e-4:
            warnings.append(
                "历史项目的手动绕组系数与当前几何推导值不同；为保持既有结果不变，"
                "此处保留手动值，不会自动改用几何值。"
            )
        return ProductionWindingFactor(
            schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
            value=manual, authority=state, provenance="LEGACY_PROJECT",
            geometry_value=geometry, manual_value=manual,
            reason_zh=(
                "该项目创建于绕组权威语义引入之前，按原样保留其存储的绕组系数，"
                "以保证历史结果不被静默改变。"
            ),
            warnings=tuple(warnings),
        )

    if state is WindingAuthority.MANUAL_OVERRIDE:
        if manual is None:
            return ProductionWindingFactor(
                schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
                value=None, authority=WindingAuthority.UNRESOLVED, provenance="NONE",
                geometry_value=geometry, manual_value=None,
                reason_zh="选择了手动覆盖，但未提供有效的绕组系数。",
                warnings=("manual override selected with no usable value",),
            )
        if geometry is not None and abs(manual / geometry - 1.0) > 5.0e-4:
            warnings.append(
                f"手动值 {manual:.6f} 覆盖了几何推导值 {geometry:.6f}"
                f"（相差 {(manual / geometry - 1.0) * 100.0:+.2f} %）。"
            )
        return ProductionWindingFactor(
            schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
            value=manual, authority=state, provenance="MANUAL_USER",
            geometry_value=geometry, manual_value=manual,
            reason_zh="用户显式选择手动绕组系数，覆盖几何推导结果。",
            warnings=tuple(warnings),
        )

    # AUTO_FROM_GEOMETRY
    if geometry is None:
        return ProductionWindingFactor(
            schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
            value=None, authority=WindingAuthority.UNRESOLVED, provenance="NONE",
            geometry_value=None, manual_value=manual,
            reason_zh=(
                "选择了自动模式，但槽数、极对数或线圈节距不足以推导绕组系数，"
                "且不会凭空假设一个值。请补全绕组几何，或显式选择手动覆盖。"
            ),
            warnings=("automatic winding factor requested without sufficient geometry",),
        )
    return ProductionWindingFactor(
        schema_version=WINDING_AUTHORITY_SCHEMA_VERSION,
        value=geometry, authority=state, provenance="IDEAL_SLOT_STAR_GEOMETRY",
        geometry_value=geometry, manual_value=manual,
        reason_zh="由槽电势星形图的 kd·kp·ks 推导，可从存储输入完整复现。",
        warnings=(),
    )


def classify_loaded_authority(
    stored: Mapping | None, *, has_manual_value: bool
) -> WindingAuthority:
    """Decide the authority state for a project being loaded.

    A document with no authority block predates these semantics. If it carries a
    manual value it becomes ``LEGACY_MANUAL`` and keeps that number; it is never
    promoted to AUTO on load, because that would change an existing design's
    results without the user asking.
    """

    if not stored:
        return (
            WindingAuthority.LEGACY_MANUAL
            if has_manual_value
            else WindingAuthority.UNRESOLVED
        )
    raw = stored.get("authority") if hasattr(stored, "get") else None
    if raw is None:
        return (
            WindingAuthority.LEGACY_MANUAL
            if has_manual_value
            else WindingAuthority.UNRESOLVED
        )
    try:
        return WindingAuthority(str(raw).strip().upper())
    except ValueError:
        return (
            WindingAuthority.LEGACY_MANUAL
            if has_manual_value
            else WindingAuthority.UNRESOLVED
        )

