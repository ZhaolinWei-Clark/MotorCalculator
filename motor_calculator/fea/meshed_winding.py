"""Phase 10E: the fundamental winding factor of the winding that was meshed.

A slot-EMF star describes an idealised winding: filamentary coil sides sitting at
slot centres, a whole number of slot pitches apart. Phase 10D measured the model
the solver actually meshes and found something else. Under
``SIDE_BY_SIDE_DOUBLE_LAYER_GO_THEN_RETURN`` the two sides of a coil occupy
adjacent layer positions, so their centres are one slot pitch *plus one layer
width* apart, and each side is a finite-width current region rather than a
filament. For the Phase 10A reference case the star says 0.8660 and the meshed
winding is 0.9558 -- a 10.4 % difference that Phase 10C attributed to the
magnetic circuit.

Rather than special-case that topology, this module projects the *actual*
conductor distribution onto the fundamental. For a planar model the flux linkage
of a circuit is

    lambda = sum over regions of  signed_turns * depth * <A_z> over the region

and for a fundamental ``A_z = A1 * sin(k x + phi)`` the region average carries a
``sinc`` from the region's finite width. Collecting the terms as a phasor,

    C = sum over regions of  signed_turns * exp(j k x_centre) * sinc(k w / 2)

gives ``lambda_peak = depth * A1 * |C|``. The fundamental flux per pole is
``Phi1 = 2 * A1 * depth``, and the winding factor is defined by
``lambda_peak = N * k_w * Phi1``, so

    k_w = |C| / (2 N)

with no free parameter. A full-pitch filamentary coil returns exactly 1 and a
two-thirds-pitch coil returns exactly sqrt(3)/2, which is what the slot star
would say for the same winding. The number is a consequence of geometry; nothing
is fitted and no solver result is consulted.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

MESHED_WINDING_SCHEMA_VERSION = "phase10e.meshed_winding.v1"

#: How a meshed winding factor was obtained, for provenance records.
MESHED_WINDING_PROVENANCE = (
    "MESHED_GEOMETRY: fundamental projection of the conductor regions in the "
    "solver model, including coil-side placement and finite region width"
)


@dataclass(frozen=True)
class MeshedWindingFactor:
    """The fundamental winding factor implied by the meshed conductor layout."""

    schema_version: str
    phase: str
    value: float
    region_count: int
    turns_per_phase: float
    pole_pitch_m: float
    #: Centre-to-centre separation of the two coil-side groups, when the phase
    #: has exactly one positive and one negative group per coil. ``None`` for
    #: layouts where a single pitch is not a meaningful description.
    representative_coil_pitch_m: float | None
    representative_coil_side_width_m: float | None
    provenance: str

    def __post_init__(self) -> None:
        if not 0.0 < self.value <= 1.0:
            raise ValueError(
                f"a fundamental winding factor must lie in (0, 1]; got {self.value!r}"
            )

    @property
    def pitch_in_pole_pitches(self) -> float | None:
        if self.representative_coil_pitch_m is None:
            return None
        return self.representative_coil_pitch_m / self.pole_pitch_m


def measure_meshed_winding_factor(
    model,
    *,
    pole_pitch_m: float,
    turns_per_phase: float,
    phase: str | None = None,
) -> MeshedWindingFactor:
    """Project the meshed conductor regions of one phase onto the fundamental.

    ``model`` is an :class:`~motor_calculator.fea.geometry.FEASliceModel`. Only
    its ``winding`` regions are read: their circumferential extent, their centre
    and their signed turns. No solver result is used, so this can be evaluated
    for a case that has never been solved.
    """

    if not math.isfinite(pole_pitch_m) or pole_pitch_m <= 0.0:
        raise ValueError("pole_pitch_m must be finite and positive")
    if not math.isfinite(turns_per_phase) or turns_per_phase <= 0.0:
        raise ValueError("turns_per_phase must be finite and positive")

    name = phase if phase is not None else model.circuit_names[0]
    regions = [
        region
        for region in model.regions
        if region.role == "winding" and region.circuit_name == name
    ]
    if not regions:
        raise ValueError(f"the model has no winding regions for phase {name!r}")

    k = math.pi / pole_pitch_m
    phasor = 0j
    widths: set[float] = set()
    positives: list[float] = []
    negatives: list[float] = []

    for region in regions:
        xs = [point[0] for point in region.polygon_m]
        x0, x1 = min(xs), max(xs)
        width = x1 - x0
        centre = (x0 + x1) / 2.0
        if width <= 0.0:
            raise ValueError(f"winding region {region.name!r} has no width")
        turns = float(region.signed_turns if region.signed_turns is not None else 0.0)
        if turns == 0.0:
            continue
        half = k * width / 2.0
        # sinc over the region: a filament is the limit as the width goes to zero.
        width_factor = math.sin(half) / half if half else 1.0
        phasor += turns * cmath.exp(1j * k * centre) * width_factor
        widths.add(round(width, 12))
        (positives if turns > 0 else negatives).append(centre)

    value = abs(phasor) / (2.0 * turns_per_phase)

    pitch: float | None = None
    if positives and negatives and len(positives) == len(negatives):
        offsets = [
            abs(neg - pos) for pos, neg in zip(sorted(positives), sorted(negatives))
        ]
        if max(offsets) - min(offsets) < 1.0e-9:
            pitch = offsets[0]

    return MeshedWindingFactor(
        schema_version=MESHED_WINDING_SCHEMA_VERSION,
        phase=name,
        value=value,
        region_count=len(regions),
        turns_per_phase=turns_per_phase,
        pole_pitch_m=pole_pitch_m,
        representative_coil_pitch_m=pitch,
        representative_coil_side_width_m=(
            float(next(iter(widths))) if len(widths) == 1 else None
        ),
        provenance=MESHED_WINDING_PROVENANCE,
    )


def meshed_winding_factor_for_case(case, *, phase: str | None = None) -> MeshedWindingFactor:
    """Build the slice model for ``case`` and measure its winding factor.

    Uses the same model builder and mesh policy the solver adapter uses, so the
    winding measured here is the winding that would be meshed.
    """

    from .adapter import _mesh_size_map
    from .geometry import build_slice_model

    model = build_slice_model(
        case.geometry,
        slot_layers=case.winding.slot_layers(),
        mesh_sizes=_mesh_size_map(case),
        symmetry=case.symmetry,
        rotor_angle_mech_deg=case.operating_point.rotor_angle_start_mech_deg,
    )
    return measure_meshed_winding_factor(
        model,
        pole_pitch_m=case.geometry.pole_pitch_m,
        turns_per_phase=float(case.winding.turns_per_phase),
        phase=phase,
    )
