"""Phase 10G: one authoritative electrical-angle convention, derived from geometry.

Phase 10F found the loaded FEMM excitation injecting current 150 electrical
degrees away from where it belonged, and identified the cause: two different
zeros wearing the same name.

``balanced_phase_currents`` documents ``electrical_angle_deg`` as "``p`` times
the mechanical rotor angle measured **from the phase-A flux-linkage maximum**".
The bridge passed ``p * rotor_angle_mech``, where the mechanical zero is the
*geometry builder's* origin -- the corner of the modelled span, which has no
relationship to the phase-A axis. The 150 degrees is exactly the distance
between those two origins for the Phase 10A reference case.

Phase 10F confirmed the value but deliberately did not fix it, because the fix
belongs where the magnets and the coils are placed. This module is that fix.

The authoritative convention
----------------------------
========================  ====================================================
Quantity                  Definition
========================  ====================================================
rotor mechanical angle    ``theta_m``, degrees, zero at the geometry builder's
                          own origin, positive in the +x (circumferential)
                          direction of the unrolled slice.
rotor electrical angle    ``theta_e = p * theta_m``, degrees.
phase-A magnetic axis     The phase of the fundamental projection of phase A's
                          conductor distribution. Derived, never assumed.
d-axis                    The phase of the fundamental projection of the magnet
                          polarity distribution: the centre of a north pole.
                          Derived, never assumed.
q-axis                    ``theta_d + 90`` electrical degrees.
excitation reference      ``theta_d`` measured *from the phase-A axis*. This is
                          the quantity ``balanced_phase_currents`` needs and the
                          bridge was passing as zero.
current phasor angle      ``current_angle_electrical_deg``; 90 degrees is
                          ``id = 0, iq > 0``.
========================  ====================================================

Everything is one electrical convention: a pole pitch is 180 electrical degrees,
so a circumferential wavenumber ``k = pi / pole_pitch`` turns a position in
metres directly into electrical radians.

Nothing here is hard-coded to a machine. The reference case's 150 degrees is an
*output*, and a test asserts it is reproduced for rotor positions other than the
one it was originally observed at.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

ELECTRICAL_AXIS_SCHEMA_VERSION = "phase10g.electrical_axis.v1"

#: Provenance for a value obtained from the modelled geometry.
GEOMETRY_DERIVED = "GEOMETRY_DERIVED"


@dataclass(frozen=True)
class ElectricalAxes:
    """Where the rotor and the winding sit, in one electrical convention."""

    schema_version: str
    rotor_angle_mech_deg: float
    pole_pairs: int
    #: Electrical angle of the phase-A magnetic axis, from the model's x origin.
    phase_a_axis_elec_deg: float
    #: Electrical angle of the rotor d-axis, from the model's x origin.
    d_axis_elec_deg: float
    provenance: str

    @property
    def q_axis_elec_deg(self) -> float:
        return (self.d_axis_elec_deg + 90.0) % 360.0

    @property
    def d_axis_from_phase_a_elec_deg(self) -> float:
        """Rotor d-axis measured from the phase-A axis, on the linkage basis.

        Defined so that ``lambda_A = lambda_peak * cos(this)``, which is the
        angle ``balanced_phase_currents`` documents itself against ("measured
        from the phase-A flux-linkage maximum").

        The ``+ 90`` is not a fudge. The magnet phasor locates the fundamental
        of the normal air-gap flux *density*, but a winding links the magnetic
        vector potential, and in a planar problem ``B_n = -dA/dx``. Recovering
        ``A`` from ``B_n`` is a spatial integration, which rotates a fundamental
        by a quarter period. Omitting it puts the axis 90 electrical degrees
        early, which is exactly the error a first attempt at this made.
        """

        return (
            self.d_axis_elec_deg - self.phase_a_axis_elec_deg + 90.0
        ) % 360.0

    @property
    def q_axis_from_phase_a_elec_deg(self) -> float:
        return (self.d_axis_from_phase_a_elec_deg + 90.0) % 360.0


def _fundamental_phase_deg(
    contributions: list[tuple[float, float]], *, pole_pitch_m: float
) -> float:
    """Phase of the fundamental of a set of ``(position, weight)`` contributions.

    ``k = pi / pole_pitch`` because one pole pitch is 180 electrical degrees, so
    ``k * x`` is already an electrical angle.
    """

    if not contributions:
        raise ValueError("no contributions to project")
    k = math.pi / pole_pitch_m
    phasor = sum(
        weight * cmath.exp(1j * k * position) for position, weight in contributions
    )
    if abs(phasor) < 1.0e-15:
        raise ValueError(
            "the distribution has no fundamental content; its phase is undefined"
        )
    return math.degrees(cmath.phase(phasor)) % 360.0


def derive_electrical_axes(model, *, pole_pairs: int, phase: str | None = None) -> ElectricalAxes:
    """Locate the phase-A axis and the rotor d-axis from the meshed geometry.

    Both are the phase of a fundamental projection:

    * the winding axis from the conductor regions of one phase, weighted by
      signed turns, the same projection Phase 10E uses for the meshed winding
      factor -- that one keeps the magnitude, this one keeps the phase;
    * the d-axis from the magnet regions, weighted by polarity, so the result is
      the centre of a north pole rather than of any magnet.

    No machine constant appears anywhere in this function.
    """

    if pole_pairs <= 0:
        raise ValueError("pole_pairs must be positive")

    pole_pitch = model.modelled_span_m / (2.0 * pole_pairs)
    name = phase if phase is not None else model.circuit_names[0]

    winding: list[tuple[float, float]] = []
    for region in model.regions:
        if region.role != "winding" or region.circuit_name != name:
            continue
        turns = float(region.signed_turns or 0.0)
        if turns == 0.0:
            continue
        xs = [point[0] for point in region.polygon_m]
        winding.append(((min(xs) + max(xs)) / 2.0, turns))
    if not winding:
        raise ValueError(f"the model has no winding regions for phase {name!r}")

    magnets: list[tuple[float, float]] = []
    for region in model.regions:
        if region.role != "magnet":
            continue
        direction = region.magnetization_direction_deg
        if direction is None:
            continue
        # -90 degrees drives flux from the upper rotor toward the stator: a
        # north pole facing the air gap. +90 is the south pole. Only the sign
        # matters for locating the axis.
        polarity = 1.0 if math.isclose(direction, -90.0, abs_tol=1.0) else -1.0
        xs = [point[0] for point in region.polygon_m]
        width = max(xs) - min(xs)
        # Weight by width so the two pieces of a magnet split across the
        # periodic seam contribute exactly as the whole magnet would.
        magnets.append((((min(xs) + max(xs)) / 2.0), polarity * width))
    if not magnets:
        raise ValueError("the model has no magnet regions with a declared polarity")

    return ElectricalAxes(
        schema_version=ELECTRICAL_AXIS_SCHEMA_VERSION,
        rotor_angle_mech_deg=model.rotor_angle_mech_deg,
        pole_pairs=pole_pairs,
        phase_a_axis_elec_deg=_fundamental_phase_deg(winding, pole_pitch_m=pole_pitch),
        d_axis_elec_deg=_fundamental_phase_deg(magnets, pole_pitch_m=pole_pitch),
        provenance=GEOMETRY_DERIVED,
    )


def electrical_axes_for_case(case, *, rotor_angle_mech_deg: float | None = None) -> ElectricalAxes:
    """Build the slice model for ``case`` and locate its electrical axes."""

    from ..fea.adapter import _mesh_size_map
    from ..fea.geometry import build_slice_model

    angle = (
        rotor_angle_mech_deg
        if rotor_angle_mech_deg is not None
        else case.operating_point.rotor_angle_start_mech_deg
    )
    model = build_slice_model(
        case.geometry,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=angle,
    )
    return derive_electrical_axes(model, pole_pairs=case.geometry.pole_pairs)


# ---------------------------------------------------------------------------
# Inverse Park
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseCurrentSet:
    """Instantaneous three-phase currents and the angle they were built at."""

    ia: float
    ib: float
    ic: float
    theta_e_deg: float

    @property
    def sum(self) -> float:
        return self.ia + self.ib + self.ic

    def as_dict(self) -> dict[str, float]:
        return {"A": self.ia, "B": self.ib, "C": self.ic}


def inverse_park_abc(
    *, id_a: float, iq_a: float, theta_e_deg: float
) -> PhaseCurrentSet:
    """Amplitude-invariant inverse Park, in one documented convention.

    ``theta_e`` is the electrical angle of the rotor d-axis measured from the
    phase-A magnetic axis, so:

    * ``ia = id cos(theta_e) - iq sin(theta_e)``
    * ``ib`` and ``ic`` lag by 120 and 240 electrical degrees.

    Amplitude-invariant means ``id`` and ``iq`` are *peak* phase quantities: for
    ``id = 0`` the peak phase current is ``iq``. The three currents sum to zero
    identically, which is asserted rather than assumed.
    """

    theta = math.radians(theta_e_deg)
    values = []
    for shift in (0.0, -2.0 * math.pi / 3.0, 2.0 * math.pi / 3.0):
        angle = theta + shift
        values.append(id_a * math.cos(angle) - iq_a * math.sin(angle))
    return PhaseCurrentSet(ia=values[0], ib=values[1], ic=values[2], theta_e_deg=theta_e_deg)


def excitation_angle_for_case(case, *, rotor_angle_mech_deg: float) -> float:
    """The electrical angle to hand ``balanced_phase_currents`` at this position.

    This is what the bridge should pass instead of ``p * rotor_angle_mech``: the
    d-axis position measured from the phase-A axis, which already contains the
    rotor rotation because the magnets move with it.
    """

    axes = electrical_axes_for_case(case, rotor_angle_mech_deg=rotor_angle_mech_deg)
    return axes.d_axis_from_phase_a_elec_deg
