"""Phase 10G: one winding report, with every factor separately named.

Three different numbers in this project have been called ``k_w``, and two of the
last three phases were spent untangling what that cost:

* the value a user *typed*, which may describe no winding at all;
* the **ideal slot-star** factor, which describes filamentary coil sides at slot
  centres an integer number of slot pitches apart;
* the **meshed geometry** factor, which describes the conductor layout a solver
  actually meshes, including the layer displacement and the finite side width.

Phase 10C replaced the first with the second and called it self-consistent.
Phase 10D found the second still did not describe the meshed winding and that
the 10.4 % gap had been attributed to the magnetic circuit. This module refuses
to collapse them: all three are reported, side by side, with provenance.

Nothing here modifies a production value. ``resolve_winding_factor`` in
``motor_core`` remains the production authority; this report says what that
authority would get and what the geometry says, and leaves the decision to a
formula gate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WINDING_REPORT_SCHEMA_VERSION = "phase10g.winding_report.v1"


class WindingTopology:
    """How the slot/pole combination is classified."""

    INTEGER_SLOT_DISTRIBUTED = "INTEGER_SLOT_DISTRIBUTED"
    FRACTIONAL_SLOT_DISTRIBUTED = "FRACTIONAL_SLOT_DISTRIBUTED"
    FRACTIONAL_SLOT_CONCENTRATED = "FRACTIONAL_SLOT_CONCENTRATED"
    UNBALANCED = "UNBALANCED"


TOPOLOGY_LABELS_ZH = {
    WindingTopology.INTEGER_SLOT_DISTRIBUTED: "整数槽分布绕组",
    WindingTopology.FRACTIONAL_SLOT_DISTRIBUTED: "分数槽分布绕组",
    WindingTopology.FRACTIONAL_SLOT_CONCENTRATED: "分数槽集中绕组（齿绕）",
    WindingTopology.UNBALANCED: "不对称绕组（无法构成平衡三相）",
}


def classify_topology(
    *, slots: int, pole_pairs: int, phases: int = 3, coil_span_slots: float | None = None
) -> str:
    """Classify from ``q = Q / (2p m)`` and the coil span.

    ``q >= 1`` and integral is an integer-slot distributed winding. ``q < 1``
    means fewer than one slot per pole per phase, which forces a concentrated
    (tooth-wound) layout; the conventional marker is a coil spanning a single
    slot. Anything else fractional is treated as fractional-slot distributed.
    """

    if slots <= 0 or pole_pairs <= 0 or phases <= 0:
        raise ValueError("slots, pole_pairs and phases must be positive")

    q = slots / (2.0 * pole_pairs * phases)
    if q <= 0.0:
        return WindingTopology.UNBALANCED
    if q < 1.0:
        # A tooth-wound coil spans one slot. A wider span on q < 1 is still
        # fractional-slot but no longer concentrated.
        if coil_span_slots is None or coil_span_slots <= 1.0:
            return WindingTopology.FRACTIONAL_SLOT_CONCENTRATED
        return WindingTopology.FRACTIONAL_SLOT_DISTRIBUTED
    if math.isclose(q, round(q), abs_tol=1.0e-9):
        return WindingTopology.INTEGER_SLOT_DISTRIBUTED
    return WindingTopology.FRACTIONAL_SLOT_DISTRIBUTED


@dataclass(frozen=True)
class WindingFactorSet:
    """The three winding factors, never collapsed into one."""

    #: What the user or preset supplied. May describe no real winding.
    entered: float | None
    entered_provenance: str
    #: Slot-EMF star: filaments at slot centres, integer slot pitches apart.
    ideal_slot_star: float | None
    #: Fundamental projection of the meshed conductor layout.
    meshed_geometry: float | None
    #: The part of the meshed value attributable to finite coil-side width.
    finite_width_factor: float | None

    @property
    def meshed_over_ideal(self) -> float | None:
        if not self.ideal_slot_star or self.meshed_geometry is None:
            return None
        return self.meshed_geometry / self.ideal_slot_star

    @property
    def entered_matches_geometry(self) -> bool | None:
        """Whether the entered value agrees with the meshed geometry to 0.5 %."""

        if self.entered is None or self.meshed_geometry is None:
            return None
        return abs(self.entered / self.meshed_geometry - 1.0) < 5.0e-3


@dataclass(frozen=True)
class WindingReport:
    """Everything the winding engineering panel needs."""

    schema_version: str
    slots: int
    pole_pairs: int
    phases: int
    slots_per_pole_per_phase: float
    topology: str
    topology_label_zh: str
    coil_span_slots: float
    full_pitch_slots: float
    layers: int
    parallel_paths: int
    distribution_factor: float | None
    pitch_factor: float | None
    skew_factor: float | None
    factors: WindingFactorSet
    notes_zh: tuple[str, ...] = ()

    @property
    def pole_count(self) -> int:
        return 2 * self.pole_pairs


def build_winding_report(
    *,
    slots: int,
    pole_pairs: int,
    phases: int = 3,
    coil_span_slots: float,
    layers: int = 2,
    parallel_paths: int = 1,
    skew_slots: float = 0.0,
    entered_winding_factor: float | None = None,
    entered_provenance: str = "USER_INPUT",
    meshed_winding_factor: float | None = None,
    finite_width_factor: float | None = None,
) -> WindingReport:
    """Assemble the report from the production slot-star engine plus geometry.

    ``kd``, ``kp``, ``ks`` and the ideal ``kw`` come from
    ``motor_core.winding_factor``, which is the production implementation and is
    not reimplemented here. The meshed values are passed in by the caller,
    because obtaining them requires a solver model.
    """

    from ..motor_core.winding_factor import (
        WindingFactorError,
        compute_fundamental_winding_factor,
        slots_per_pole_per_phase,
    )

    notes: list[str] = []
    try:
        breakdown = compute_fundamental_winding_factor(
            slots=slots,
            pole_pairs=pole_pairs,
            coil_span_slots=int(round(coil_span_slots)),
            phases=phases,
            skew_slots=skew_slots,
        )
        kd = breakdown.distribution_factor
        kp = breakdown.pitch_factor
        ks = breakdown.skew_factor
        ideal = breakdown.fundamental_winding_factor
        full_pitch = breakdown.full_pitch_slots
        q = breakdown.slots_per_pole_per_phase
    except (WindingFactorError, ValueError) as error:
        kd = kp = ks = ideal = None
        full_pitch = slots / (2.0 * pole_pairs)
        q = slots_per_pole_per_phase(slots, pole_pairs, phases)
        notes.append(f"槽电势星形图无法构成平衡绕组：{error}")

    topology = classify_topology(
        slots=slots, pole_pairs=pole_pairs, phases=phases, coil_span_slots=coil_span_slots
    )

    factors = WindingFactorSet(
        entered=entered_winding_factor,
        entered_provenance=entered_provenance,
        ideal_slot_star=ideal,
        meshed_geometry=meshed_winding_factor,
        finite_width_factor=finite_width_factor,
    )
    if factors.entered_matches_geometry is False:
        notes.append(
            "输入的绕组系数与剖分几何推导值不一致；二者描述的不是同一个绕组，"
            "差异本身不代表任何一方有误，但不应互相替代。"
        )
    if factors.meshed_over_ideal is not None and abs(factors.meshed_over_ideal - 1.0) > 0.01:
        notes.append(
            "理想槽电势星形图与剖分几何的绕组系数相差超过 1 %：星形图假设线圈边为"
            "位于槽中心的细丝且间隔整数个槽距，实际层位移与有限边宽都不满足该假设。"
        )

    return WindingReport(
        schema_version=WINDING_REPORT_SCHEMA_VERSION,
        slots=slots,
        pole_pairs=pole_pairs,
        phases=phases,
        slots_per_pole_per_phase=q,
        topology=topology,
        topology_label_zh=TOPOLOGY_LABELS_ZH[topology],
        coil_span_slots=coil_span_slots,
        full_pitch_slots=full_pitch,
        layers=layers,
        parallel_paths=parallel_paths,
        distribution_factor=kd,
        pitch_factor=kp,
        skew_factor=ks,
        factors=factors,
        notes_zh=tuple(notes),
    )
