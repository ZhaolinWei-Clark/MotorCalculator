"""Solver-neutral planar geometry generation for the unrolled AFPM slice.

Why an unrolled mean-radius slice is the defensible mapping
----------------------------------------------------------
The analytical pole area is

    A_pole = (pi / 2p) * (R_out^2 - R_in^2) * alpha_p

and, since ``(R_out^2 - R_in^2) = (R_out + R_in) * (R_out - R_in) = D_avg * L_r``,

    A_pole = (pi * D_avg / 2p) * L_r * alpha_p = tau_p * L_r * alpha_p

which is *identically* the pole face area of a linear machine of pole pitch
``tau_p`` and depth ``L_r``. The analytical magnetic circuit is therefore already
a mean-radius unrolled model, and the planar slice is its exact geometric
counterpart rather than an arbitrary simplification.

Why the magnets face through the stator
---------------------------------------
The analytical circuit uses an MMF of ``2 * (B_r / mu0) * h_m / mu_r`` against a
reluctance of one ``h_coil + 2g`` air gap plus ``2 * h_m`` of magnet. Two magnets
in series across a single gap that spans the stator is the axially-through
(N-S facing) dual-rotor arrangement. That arrangement is what this module
builds, so the geometry matches the equation being tested instead of some other
machine.

What the slice still cannot see is recorded on the case as
``omitted_three_dimensional_effects`` and keeps the fidelity tier at
``FEA_TIER_3``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import gcd
from typing import Iterable

from .models import FEASymmetryPlan, FEAUnrolledSliceGeometry, FEAValidationTarget

#: 3D effects a single mean-radius planar slice structurally cannot represent.
OMITTED_THREE_DIMENSIONAL_EFFECTS = (
    "pole pitch, coil-side width and magnet width all grow with radius; only the mean radius is solved",
    "inner-radius and outer-radius edge fringing and end leakage are absent",
    "end-winding geometry, its leakage and its resistance are absent",
    "the local tangential speed varies as omega*r across the active radius; only omega*r_mean is represented",
    "any radial variation of magnet coverage or coil shape is absent",
)

#: The circumferential span, in units of the pole pitch, that the far-field air
#: boundary is pushed away from the active stack. Large enough that the outer
#: boundary condition does not load the active region.
AIR_DOMAIN_MARGIN_POLE_PITCHES = 1.0


@dataclass(frozen=True)
class FEARegion:
    """One meshable planar region with an explicit material and mesh size."""

    name: str
    role: str
    polygon_m: tuple[tuple[float, float], ...]
    block_label_m: tuple[float, float]
    material_key: str
    mesh_size_m: float
    magnetization_direction_deg: float | None = None
    circuit_name: str | None = None
    signed_turns: float | None = None

    def __post_init__(self) -> None:
        if len(self.polygon_m) < 3:
            raise ValueError("a region polygon needs at least three vertices")
        if not math.isfinite(self.mesh_size_m) or self.mesh_size_m <= 0.0:
            raise ValueError("region mesh size must be finite and positive")

    @property
    def area_m2(self) -> float:
        """Shoelace area; always positive regardless of vertex winding order."""

        total = 0.0
        count = len(self.polygon_m)
        for index in range(count):
            x0, y0 = self.polygon_m[index]
            x1, y1 = self.polygon_m[(index + 1) % count]
            total += x0 * y1 - x1 * y0
        return abs(total) / 2.0


@dataclass(frozen=True)
class FEASliceModel:
    """A complete solver-neutral planar model of one unrolled slice."""

    regions: tuple[FEARegion, ...]
    domain_polygon_m: tuple[tuple[float, float], ...]
    depth_m: float
    modelled_span_m: float
    rotor_angle_mech_deg: float
    rotor_offset_m: float
    stack_extent_y_m: tuple[float, float]
    circuit_names: tuple[str, ...]

    def regions_with_role(self, role: str) -> tuple[FEARegion, ...]:
        return tuple(region for region in self.regions if region.role == role)


def machine_periodicity(slot_count: int, pole_count: int) -> int:
    """``t = gcd(Q, 2p)``: how many times the machine repeats around the bore."""

    return gcd(int(slot_count), int(pole_count))


def cogging_period_mech_deg(slot_count: int, pole_count: int) -> float:
    """Fundamental cogging period, ``360 / lcm(Q, 2p)`` mechanical degrees."""

    slot_count = int(slot_count)
    pole_count = int(pole_count)
    lcm = slot_count * pole_count // gcd(slot_count, pole_count)
    return 360.0 / float(lcm)


def derive_symmetry_plan(
    *,
    slot_count: int,
    pole_count: int,
    target: FEAValidationTarget,
    apply_symmetry: bool = False,
) -> FEASymmetryPlan:
    """Derive the circumferential periodic sector and decide whether to use it.

    The sector is always *reported* so a reader can see it; it is only *applied*
    when the caller explicitly asks. The default is the full circumference,
    because a wrongly reduced sector silently destroys cogging content and the
    solver is not available here to catch it.
    """

    periodicity = machine_periodicity(slot_count, pole_count)
    poles_in_sector = pole_count // periodicity
    slots_in_sector = slot_count // periodicity
    # A sector is only usable for cogging when it is a whole number of both slot
    # and pole pitches; that is exactly what dividing by gcd(Q, 2p) guarantees.
    valid_for_cogging = (
        periodicity >= 1
        and slot_count % periodicity == 0
        and pole_count % periodicity == 0
        and poles_in_sector % 2 == 0
    )
    if periodicity == 1:
        rationale = (
            "gcd(Q, 2p) = 1: the machine has no circumferential repetition, so the "
            "full 360 mechanical degrees must be modelled."
        )
    else:
        rationale = (
            f"gcd(Q, 2p) = {periodicity}: the slot/pole pattern repeats {periodicity} times, "
            f"so one sector spans {slots_in_sector} slots and {poles_in_sector} poles."
        )
    if apply_symmetry and not valid_for_cogging:
        raise ValueError(
            "the derived sector does not contain a whole even number of poles and "
            "cannot carry a periodic magnet pattern"
        )
    if apply_symmetry and target is FEAValidationTarget.COGGING_TORQUE and periodicity == 1:
        raise ValueError("cogging cannot be reduced when the machine has no repetition")

    applied = bool(apply_symmetry)
    return FEASymmetryPlan(
        machine_periodicity=periodicity,
        poles_in_sector=poles_in_sector,
        slots_in_sector=slots_in_sector,
        sector_fraction=1.0 / float(periodicity),
        boundary_kind="PERIODIC" if applied else "NONE_FULL_CIRCUMFERENCE",
        applied=applied,
        valid_for_cogging=valid_for_cogging,
        rationale=rationale,
    )


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _trapezoid(
    x_center: float, y0: float, y1: float, width_at_y0: float, width_at_y1: float
) -> tuple[tuple[float, float], ...]:
    half0 = width_at_y0 / 2.0
    half1 = width_at_y1 / 2.0
    return (
        (x_center - half0, y0),
        (x_center + half0, y0),
        (x_center + half1, y1),
        (x_center - half1, y1),
    )


def _wrap(value: float, span: float) -> float:
    """Wrap a circumferential coordinate into ``[0, span)``."""

    return value - span * math.floor(value / span)


def _split_across_seam(
    x0: float, x1: float, span: float
) -> tuple[tuple[float, float], ...]:
    """Clip an interval to ``[0, span)``, splitting it at the periodic seam.

    The unrolled model's two circumferential ends are the same physical place,
    so an interval that runs off one end reappears at the other.
    """

    start = _wrap(x0, span)
    width = x1 - x0
    if width >= span:
        return ((0.0, span),)
    end = start + width
    if end <= span:
        return ((start, end),)
    return ((start, span), (0.0, end - span))


def build_slice_model(
    geometry: FEAUnrolledSliceGeometry,
    *,
    slot_layers: Iterable[Iterable[tuple[str, float]]],
    mesh_sizes: dict[str, float],
    symmetry: FEASymmetryPlan,
    rotor_angle_mech_deg: float,
) -> FEASliceModel:
    """Generate the planar region set for one rotor position.

    ``rotor_angle_mech_deg`` moves *only* the rotor blocks (magnets and back
    iron). The stator stays fixed, which is what makes a position sweep produce
    a physically meaningful flux-linkage and force waveform.
    """

    layers = tuple(tuple(entry) for entry in slot_layers)
    if len(layers) != geometry.slot_count:
        raise ValueError("slot layer map must cover every slot")
    if any(len(entry) == 0 for entry in layers):
        raise ValueError("every slot must carry at least one conductor layer")

    span = geometry.circumference_m * symmetry.sector_fraction if symmetry.applied else geometry.circumference_m
    slots_modelled = geometry.slot_count if not symmetry.applied else symmetry.slots_in_sector
    poles_modelled = (
        2 * geometry.pole_pairs if not symmetry.applied else symmetry.poles_in_sector
    )

    half_coil = geometry.winding_region_thickness_m / 2.0
    gap = geometry.mechanical_air_gap_per_side_m
    magnet_inner_y = half_coil + gap
    magnet_outer_y = magnet_inner_y + geometry.magnet_thickness_m
    back_iron_outer_y = magnet_outer_y + geometry.rotor_back_iron_thickness_m

    regions: list[FEARegion] = []

    # ------------------------------------------------------------------
    # Stator: coil-side regions on a uniform slot pitch.
    # ------------------------------------------------------------------
    slot_pitch = span / float(slots_modelled)
    if geometry.is_coreless:
        coil_width = (
            (geometry.slot_top_width_m or 0.0) + (geometry.slot_bottom_width_m or 0.0)
        ) / 2.0
        if coil_width <= 0.0:
            # A coreless stator has no slot walls; fall back to the declared
            # winding region thickness only when the schema gave no width.
            raise ValueError("a coreless coil-side width could not be derived from the schema")
        coil_width = min(coil_width, slot_pitch * 0.98)
        for index in range(slots_modelled):
            x_center = (index + 0.5) * slot_pitch
            slot_layer = layers[index]
            layer_width = coil_width / float(len(slot_layer))
            for layer_index, (phase, signed_turns) in enumerate(slot_layer):
                layer_x0 = x_center - coil_width / 2.0 + layer_index * layer_width
                regions.append(
                    FEARegion(
                        name=f"coil_{index:03d}_layer{layer_index}",
                        role="winding",
                        polygon_m=_rectangle(
                            layer_x0, -half_coil, layer_x0 + layer_width, half_coil
                        ),
                        block_label_m=(layer_x0 + layer_width / 2.0, 0.0),
                        material_key="conductor",
                        mesh_size_m=mesh_sizes["winding"],
                        circuit_name=phase,
                        signed_turns=signed_turns,
                    )
                )
    else:
        slot_height = float(geometry.slot_height_m or 0.0)
        opening_height = float(geometry.slot_opening_height_m or 0.0)
        opening_width = float(geometry.slot_opening_width_m or 0.0)
        wedge_height = float(geometry.wedge_height_m or 0.0)
        top_width = float(geometry.slot_top_width_m or 0.0)
        bottom_width = float(geometry.slot_bottom_width_m or 0.0)
        yoke_height = float(geometry.yoke_height_m or 0.0)
        # The cored stator is built symmetrically about y = 0 so the axially
        # through-flux dual-rotor arrangement sees an identical face on each
        # side. Slots open toward each air gap; the yoke sits at the centre.
        tooth_outer_y = half_coil
        slot_root_y = tooth_outer_y - slot_height
        core_span_y = (slot_root_y - yoke_height / 2.0, tooth_outer_y)
        for sign in (1.0, -1.0):
            side = "upper" if sign > 0 else "lower"
            regions.append(
                FEARegion(
                    name=f"core_{side}",
                    role="core",
                    polygon_m=_rectangle(0.0, sign * core_span_y[0], span, sign * core_span_y[1]),
                    block_label_m=(slot_pitch * 0.5, sign * (slot_root_y - yoke_height / 4.0)),
                    material_key="core",
                    mesh_size_m=mesh_sizes["core"],
                )
            )
            for index in range(slots_modelled):
                x_center = (index + 0.5) * slot_pitch
                body_top = tooth_outer_y - opening_height - wedge_height
                slot_layer = layers[index]
                layer_count = len(slot_layer)
                for layer_index, (phase, signed_turns) in enumerate(slot_layer):
                    # Layers sit side by side across the slot width; the slot
                    # tapers, so each layer gets its share of both widths.
                    fraction_lo = layer_index / layer_count - 0.5
                    fraction_hi = (layer_index + 1) / layer_count - 0.5
                    layer_center_fraction = (fraction_lo + fraction_hi) / 2.0
                    regions.append(
                        FEARegion(
                            name=f"coil_{side}_{index:03d}_layer{layer_index}",
                            role="winding",
                            polygon_m=(
                                (x_center + fraction_lo * bottom_width, sign * slot_root_y),
                                (x_center + fraction_hi * bottom_width, sign * slot_root_y),
                                (x_center + fraction_hi * top_width, sign * body_top),
                                (x_center + fraction_lo * top_width, sign * body_top),
                            ),
                            block_label_m=(
                                x_center
                                + layer_center_fraction * (bottom_width + top_width) / 2.0,
                                sign * (slot_root_y + body_top) / 2.0,
                            ),
                            material_key="conductor",
                            mesh_size_m=mesh_sizes["winding"],
                            circuit_name=phase,
                            # The central yoke splits one physical coil side into
                            # an upper and a lower half. Each half carries half
                            # the turns so the ampere-turns are not doubled.
                            signed_turns=0.5 * signed_turns,
                        )
                    )
                if opening_height > 0.0 and opening_width > 0.0:
                    regions.append(
                        FEARegion(
                            name=f"slot_opening_{side}_{index:03d}",
                            role="air",
                            polygon_m=_rectangle(
                                x_center - opening_width / 2.0,
                                sign * (tooth_outer_y - opening_height),
                                x_center + opening_width / 2.0,
                                sign * tooth_outer_y,
                            ),
                            block_label_m=(x_center, sign * (tooth_outer_y - opening_height / 2.0)),
                            material_key="air",
                            mesh_size_m=mesh_sizes["slot_opening"],
                        )
                    )

    # ------------------------------------------------------------------
    # Rotors: alternating axially magnetized magnets plus back iron.
    #
    # At a given pole both magnets point the same way along y, so the flux
    # crosses the stator axially and returns through the neighbouring pole.
    # That is the two-magnets-in-series circuit the analytical model assumes.
    # ------------------------------------------------------------------
    pole_pitch = span / float(poles_modelled)
    magnet_width = geometry.magnet_arc_length_m
    rotor_offset = geometry.circumference_m * (rotor_angle_mech_deg / 360.0)
    for pole in range(poles_modelled):
        # +1 for a magnet whose flux leaves the upper rotor toward the stator.
        pole_sign = 1.0 if pole % 2 == 0 else -1.0
        x_center = _wrap((pole + 0.5) * pole_pitch + rotor_offset, span)
        for sign in (1.0, -1.0):
            side = "upper" if sign > 0 else "lower"
            # ``-90`` deg is the -y direction in FEMM's degree convention.
            direction_deg = -90.0 if pole_sign > 0 else 90.0
            # A rotated magnet can straddle the periodic seam at x = 0. The two
            # sides of the seam are the same physical location, so the magnet is
            # emitted as the two pieces that actually lie inside the modelled
            # span rather than being pushed back inside and silently displaced.
            for piece, (piece_x0, piece_x1) in enumerate(
                _split_across_seam(
                    x_center - magnet_width / 2.0, x_center + magnet_width / 2.0, span
                )
            ):
                regions.append(
                    FEARegion(
                        name=f"magnet_{side}_{pole:03d}_{piece}",
                        role="magnet",
                        polygon_m=_rectangle(
                            piece_x0,
                            sign * magnet_inner_y,
                            piece_x1,
                            sign * magnet_outer_y,
                        ),
                        block_label_m=(
                            (piece_x0 + piece_x1) / 2.0,
                            sign * (magnet_inner_y + magnet_outer_y) / 2.0,
                        ),
                        material_key="magnet",
                        mesh_size_m=mesh_sizes["magnet"],
                        magnetization_direction_deg=direction_deg,
                    )
                )
    for sign in (1.0, -1.0):
        side = "upper" if sign > 0 else "lower"
        regions.append(
            FEARegion(
                name=f"back_iron_{side}",
                role="back_iron",
                polygon_m=_rectangle(
                    0.0, sign * magnet_outer_y, span, sign * back_iron_outer_y
                ),
                block_label_m=(slot_pitch * 0.5, sign * (magnet_outer_y + back_iron_outer_y) / 2.0),
                material_key="back_iron",
                mesh_size_m=mesh_sizes["core"] if not geometry.is_coreless else mesh_sizes["magnet"],
            )
        )

    margin = geometry.air_domain_margin_m
    domain_y = back_iron_outer_y + margin
    regions.append(
        FEARegion(
            name="air_domain_upper",
            role="air_domain",
            polygon_m=_rectangle(0.0, -domain_y, span, domain_y),
            block_label_m=(slot_pitch * 0.25, back_iron_outer_y + margin / 2.0),
            material_key="air",
            mesh_size_m=mesh_sizes["air_domain"],
        )
    )
    # ------------------------------------------------------------------
    # Every enclosed subregion needs its own block label: FEMM refuses to mesh
    # a model that contains a region carrying no material, and the refusal is
    # silent from Lua's point of view -- the real solver returned from
    # mi_analyze without writing a mesh at all.
    #
    # The two rotor back-iron bands span the full width, so they cut the air
    # into three disconnected parts rather than one:
    #   * outside the upper back iron   (labelled above)
    #   * outside the lower back iron   (its mirror; a separate region)
    #   * everything inside the stack   (the two air gaps and the spaces
    #     between magnets and between coil sides, which are all connected to
    #     each other through the gaps between coil sides)
    # ------------------------------------------------------------------
    regions.append(
        FEARegion(
            name="air_domain_lower",
            role="air_domain_label_only",
            polygon_m=_rectangle(0.0, -domain_y, span, domain_y),
            block_label_m=(slot_pitch * 0.25, -(back_iron_outer_y + margin / 2.0)),
            material_key="air",
            mesh_size_m=mesh_sizes["air_domain"],
        )
    )
    regions.append(
        FEARegion(
            name="air_active_stack",
            role="air_domain_label_only",
            polygon_m=_rectangle(0.0, -domain_y, span, domain_y),
            # Inside the upper mechanical air gap, which carries no other
            # region at any circumferential position.
            block_label_m=(slot_pitch * 0.5, half_coil + gap / 2.0),
            material_key="air",
            mesh_size_m=mesh_sizes["air_gap"],
        )
    )

    circuit_names = tuple(
        sorted({region.circuit_name for region in regions if region.circuit_name is not None})
    )
    return FEASliceModel(
        regions=tuple(regions),
        domain_polygon_m=_rectangle(0.0, -domain_y, span, domain_y),
        depth_m=geometry.radial_active_length_m,
        modelled_span_m=span,
        rotor_angle_mech_deg=rotor_angle_mech_deg,
        rotor_offset_m=rotor_offset,
        stack_extent_y_m=(-back_iron_outer_y, back_iron_outer_y),
        circuit_names=circuit_names,
    )
