"""Deterministic rotor-angle sampling policy for FEA position sweeps.

Every solve costs a full field solution, so the sample count is derived from the
highest harmonic each target actually needs to resolve rather than defaulting to
a round number such as 360. The Phase 9B cogging work established the failure
mode this policy avoids: when the sampling grid and the physical periodicity
share a common factor, real content aliases onto a coarser apparent waveform and
the peak is silently understated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import gcd

from .models import FEAValidationTarget

#: Highest electrical harmonic the no-load flux-linkage waveform must resolve.
#: Beyond the 13th, the contribution to phase RMS of a practical PM machine is
#: below the mesh-discretisation noise of a single-mesh solve.
BACK_EMF_HIGHEST_ELECTRICAL_HARMONIC = 13

#: Highest electrical harmonic the loaded torque waveform must resolve. Torque
#: ripple of a three-phase machine is dominated by the 6th and 12th electrical
#: harmonics; the 18th is carried as headroom.
TORQUE_HIGHEST_ELECTRICAL_HARMONIC = 18

#: Highest multiple of the *cogging* fundamental to resolve, matching the Phase
#: 9B analytic cogging sampling policy.
COGGING_HIGHEST_PERIOD_HARMONIC = 3

#: Samples per cycle of the highest resolved harmonic. Nyquist needs more than
#: two; four leaves margin for the derivative taken to get back-EMF.
SAMPLES_PER_HIGHEST_HARMONIC_CYCLE = 4

#: Absolute floor, so that even a very low pole count still yields a waveform
#: the discrete Fourier analysis can work with.
MINIMUM_SAMPLE_COUNT = 24

#: Ceiling, so a pathological slot/pole combination cannot queue an unbounded
#: number of field solves.
MAXIMUM_SAMPLE_COUNT = 720


@dataclass(frozen=True)
class FEAAngleSamplingPlan:
    """The sampled span, count and the reasoning that produced them."""

    target: FEAValidationTarget
    span_mech_deg: float
    sample_count: int
    step_mech_deg: float
    highest_resolved_harmonic: int
    slot_passing_harmonic: float
    aliasing_common_factor: int
    rationale: str


def _lcm(left: int, right: int) -> int:
    return left * right // gcd(left, right)


def cogging_period_mech_deg(slot_count: int, pole_count: int) -> float:
    """``360 / lcm(Q, 2p)`` mechanical degrees."""

    return 360.0 / float(_lcm(int(slot_count), int(pole_count)))


def electrical_period_mech_deg(pole_pairs: int) -> float:
    """``360 / p`` mechanical degrees."""

    return 360.0 / float(pole_pairs)


def plan_angle_sampling(
    *,
    target: FEAValidationTarget,
    slot_count: int,
    pole_pairs: int,
) -> FEAAngleSamplingPlan:
    """Derive the rotor-angle sweep for one validation target."""

    if slot_count <= 0 or pole_pairs <= 0:
        raise ValueError("slot_count and pole_pairs must be positive")
    pole_count = 2 * pole_pairs
    # Slotting modulates the no-load flux linkage at the slot-passing harmonic,
    # so a sweep that resolves only the winding harmonics would alias it.
    slot_passing_harmonic = float(slot_count) / float(pole_pairs)

    if target is FEAValidationTarget.COGGING_TORQUE:
        span = cogging_period_mech_deg(slot_count, pole_count)
        highest = COGGING_HIGHEST_PERIOD_HARMONIC
        required = highest * SAMPLES_PER_HIGHEST_HARMONIC_CYCLE
        rationale = (
            f"one cogging period is 360/lcm(Q={slot_count}, 2p={pole_count}) = "
            f"{span:.6f} mechanical degrees; resolving up to the "
            f"{highest}rd cogging harmonic at {SAMPLES_PER_HIGHEST_HARMONIC_CYCLE} "
            "samples per cycle"
        )
    else:
        span = electrical_period_mech_deg(pole_pairs)
        base = (
            BACK_EMF_HIGHEST_ELECTRICAL_HARMONIC
            if target is FEAValidationTarget.NO_LOAD_BACK_EMF
            else TORQUE_HIGHEST_ELECTRICAL_HARMONIC
        )
        highest = max(base, math.ceil(slot_passing_harmonic) + 1)
        required = highest * SAMPLES_PER_HIGHEST_HARMONIC_CYCLE
        rationale = (
            f"one electrical period is 360/p = {span:.6f} mechanical degrees; "
            f"resolving up to electrical harmonic {highest} "
            f"(max of the {base}th of interest and the slot-passing harmonic "
            f"Q/p = {slot_passing_harmonic:.4f} plus one) at "
            f"{SAMPLES_PER_HIGHEST_HARMONIC_CYCLE} samples per cycle"
        )

    sample_count = max(required, MINIMUM_SAMPLE_COUNT)

    # Anti-aliasing, the Phase 9B lesson: if the sample count shares a factor
    # with the number of physical events in the span, samples land on the same
    # relative position within every event and the waveform collapses. Step the
    # count up until it is coprime with the event count.
    if target is FEAValidationTarget.COGGING_TORQUE:
        events_in_span = 1
    else:
        # Slot passings seen by the rotor over one electrical period.
        events_in_span = max(1, round(slot_passing_harmonic))
    guard = 0
    while events_in_span > 1 and gcd(sample_count, events_in_span) != 1:
        sample_count += 1
        guard += 1
        if guard > events_in_span + 1:
            break
    if sample_count > MAXIMUM_SAMPLE_COUNT:
        raise ValueError(
            f"the required sample count {sample_count} exceeds the Phase 10A ceiling "
            f"of {MAXIMUM_SAMPLE_COUNT} field solves for this slot/pole combination"
        )

    return FEAAngleSamplingPlan(
        target=target,
        span_mech_deg=span,
        sample_count=sample_count,
        step_mech_deg=span / float(sample_count),
        highest_resolved_harmonic=highest,
        slot_passing_harmonic=slot_passing_harmonic,
        aliasing_common_factor=gcd(sample_count, max(events_in_span, 1)),
        rationale=rationale,
    )
