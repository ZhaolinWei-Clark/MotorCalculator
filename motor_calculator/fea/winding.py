"""Coil-resolved winding mapping for the FEA bridge.

The belt allocation below is the same exact-integer arithmetic that
``motor_core.winding_factor.build_slot_star`` uses for phase A; this module only
extends it to *all* phases, which the analytical star does not need. The two are
locked together by a regression test that replays every phase-A slot and sign.

``motor_core/winding_factor.py`` is not modified: winding-factor semantics are
unchanged by Phase 10A.

Why the coil, not the slot, is the unit
---------------------------------------
The slot star assigns a phase and a series sense to each *coil*. A coil has two
sides, and only the pair of them carries zero net current. For an integer-slot
distributed winding the star happens to place matching ``+`` and ``-`` coil
sides in different slots, so a one-layer-per-slot model looks fine. For a
``q = 0.5`` fractional-slot winding such as ``Q = 24, 2p = 16`` every phase-A
slot lands in the same belt, and a one-layer model would place a non-zero net
in-plane current for that phase, giving a flux linkage that is not the coil's
flux linkage at all. Building both layers explicitly removes that failure mode
for every slot/pole combination rather than only for the convenient ones.
"""

from __future__ import annotations

import math

from ..motor_core.winding_factor import DEFAULT_PHASES, build_slot_star
from .models import FEAWindingMap

#: Phase labels in belt order. FEMM circuit names must be plain ASCII.
PHASE_LABELS = ("A", "B", "C")

#: How the two layers of a slot are placed relative to each other. Declared
#: rather than inferred, because the analytical model carries no layer geometry.
LAYER_ARRANGEMENT = "SIDE_BY_SIDE_DOUBLE_LAYER_GO_THEN_RETURN"

SLOT_OCCUPANCY_BASIS = (
    "each coil side is a homogenised current region carrying the phase current "
    "times its signed turns; it is not a conductor-by-conductor packing "
    "geometry, and the analytical bare-copper occupancy ratio is not a fill map"
)


def slot_belt_index(slot_index: int, slots: int, pole_pairs: int, phases: int) -> int:
    """Belt number of a slot, in exact integer arithmetic.

    Identical in form to the allocation in ``build_slot_star``. Evaluating the
    belt boundary in floating point puts phasors that land exactly on an edge on
    either side depending on rounding, which silently unbalances integer-slot
    windings such as ``Q=24, 2p=4``.
    """

    residue = (slot_index * pole_pairs) % slots
    return ((residue * 4 * phases + slots) // (2 * slots)) % (2 * phases)


def belt_to_phase_map(phases: int = DEFAULT_PHASES) -> dict[int, tuple[int, int]]:
    """Map each belt onto ``(phase index, series sign)``.

    The belts sit at successive multiples of ``180 / m`` electrical degrees, so
    for three phases they are at 0, 60, 120, 180, 240 and 300 degrees. Phase
    ``j`` is centred ``j * 360 / m`` degrees round, which is belt ``2j``, and its
    reversed belt is 180 degrees away at ``2j + m``:

        belt 0 -> A+   belt 1 -> C-   belt 2 -> B+
        belt 3 -> A-   belt 4 -> C+   belt 5 -> B-

    Taking ``PHASE_LABELS[belt % m]`` instead looks plausible and is wrong: it
    yields A+, B+, C+, A-, B-, C-, which places the three phases 60 electrical
    degrees apart rather than 120. The real solver showed exactly that -- three
    flux-linkage waveforms of equal amplitude at 150, 90 and 30 degrees, whose
    sum was not zero at any position.
    """

    mapping: dict[int, tuple[int, int]] = {}
    for phase_index in range(phases):
        mapping[(2 * phase_index) % (2 * phases)] = (phase_index, 1)
        mapping[(2 * phase_index + phases) % (2 * phases)] = (phase_index, -1)
    if len(mapping) != 2 * phases:
        raise ValueError(
            f"{phases} phases do not produce {2 * phases} distinct belts; the "
            "belt allocation is only defined for an odd phase count"
        )
    return mapping


def allocate_all_phases(
    slots: int, pole_pairs: int, phases: int = DEFAULT_PHASES
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Return the phase label and series sense of every coil."""

    if phases > len(PHASE_LABELS):
        raise ValueError("only three-phase windings have declared FEA circuit labels")
    mapping = belt_to_phase_map(phases)
    labels: list[str] = []
    signs: list[int] = []
    for slot_index in range(slots):
        belt = slot_belt_index(slot_index, slots, pole_pairs, phases)
        phase_index, sign = mapping[belt]
        labels.append(PHASE_LABELS[phase_index])
        signs.append(sign)
    return tuple(labels), tuple(signs)


def full_pitch_span_slots(slots: int, pole_pairs: int) -> float:
    """The full-pitch coil span, ``Q / 2p`` slots. Not rounded here."""

    return float(slots) / float(2 * pole_pairs)


def build_winding_map(
    *,
    slots: int,
    pole_pairs: int,
    turns_per_phase: int,
    parallel_paths: int,
    coil_span_slots: int,
    winding_factor_analytical: float,
    winding_factor_provenance: str,
    wire_diameter_m: float,
    phases: int = DEFAULT_PHASES,
) -> FEAWindingMap:
    """Build the coil-resolved winding map, or refuse an unbalanced winding."""

    star = build_slot_star(slots, pole_pairs, phases)
    if not star.balanced:
        raise ValueError(
            f"slot/pole combination Q={slots}, 2p={2 * pole_pairs}, m={phases} does not "
            "produce a balanced symmetric winding and cannot be mapped to phase circuits"
        )
    labels, signs = allocate_all_phases(slots, pole_pairs, phases)

    coils_per_phase = slots // phases
    # ``turns_per_phase`` is the analytical *series* turns per phase, so a coil
    # of that phase carries that many turns divided across the phase's coils.
    turns_per_coil = float(turns_per_phase) / float(coils_per_phase)

    # Homogenised copper cross-section of one coil side, from the declared wire
    # diameter and parallel paths. This is the conductor area actually carrying
    # current, not a slot packing geometry.
    strand_area_m2 = math.pi * (wire_diameter_m / 2.0) ** 2
    slot_copper_area_m2 = strand_area_m2 * parallel_paths * turns_per_coil

    return FEAWindingMap(
        phases=phases,
        slot_count=slots,
        pole_pairs=pole_pairs,
        turns_per_phase=turns_per_phase,
        parallel_paths=parallel_paths,
        coil_span_slots=coil_span_slots,
        turns_per_coil=turns_per_coil,
        coil_phase_assignment=labels,
        coil_polarity=signs,
        layer_arrangement=LAYER_ARRANGEMENT,
        winding_factor_analytical=winding_factor_analytical,
        winding_factor_provenance=winding_factor_provenance,
        slot_copper_area_m2=slot_copper_area_m2,
        slot_occupancy_basis=SLOT_OCCUPANCY_BASIS,
    )
