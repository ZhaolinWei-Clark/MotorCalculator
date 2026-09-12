"""Phase 10G: slot fill and winding manufacturability.

The project already reports one occupancy number, labelled in the dashboard as
"近似裸铜槽占比" -- an approximate *bare copper* ratio. It subtracts the wedge and
nothing else, models no insulation, assumes round wire tiles perfectly, and is
marked ``APPROXIMATE``. For deciding whether a winding can actually be wound
that is not enough: bare copper against gross slot area routinely reads 20-30
points below the number a winder cares about.

This module separates the quantities that occupancy question actually contains.

Denominators are the whole problem
----------------------------------
"Fill factor" means at least four different ratios. Each is named, and each
states its own denominator:

``gross_copper_fill``
    bare copper area / **gross** slot area. The classical "copper fill", and the
    one most published figures use.

``usable_copper_fill``
    bare copper area / **usable** slot area, after liner, wedge and clearance.
    Always higher than the gross figure, and the one that decides whether the
    copper physically fits.

``gross_envelope_fill`` / ``usable_envelope_fill``
    the same two ratios computed on the *insulated* conductor envelope rather
    than the bare copper. The envelope is what occupies the slot; the copper is
    only what carries current.

Assumptions are labelled, not hidden
------------------------------------
Round wire does not tile a slot perfectly. A packing allowance is therefore
unavoidable, and it is an *engineering assumption* rather than a physical
constant: it depends on wire gauge, winding method, whether the coil is
machine-wound or hand-wound, and how tidy the winder is. It is exposed as an
input with a declared default and a provenance of ``ENGINEERING_ASSUMPTION``,
never presented as a derived quantity.

The same applies to the manufacturability thresholds. The calculation is
reported separately from the recommendation, so a user who disagrees with the
thresholds still gets a usable number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

SLOT_FILL_SCHEMA_VERSION = "phase10g.slot_fill.v1"


class Provenance:
    """Where a value came from. Rendered next to it, never dropped."""

    GEOMETRY_DERIVED = "GEOMETRY_DERIVED"
    USER_INPUT = "USER_INPUT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    ENGINEERING_ASSUMPTION = "ENGINEERING_ASSUMPTION"
    NUMERICAL_FEA = "NUMERICAL_FEA"


class ManufacturabilityStatus:
    """How comfortable the winding is to actually wind.

    These bands are an ENGINEERING_ASSUMPTION, not a standard. They reflect
    common practice for random-wound round-wire stators and are exposed so a
    user can disagree with them without losing the underlying number.
    """

    COMFORTABLE = "COMFORTABLE"
    FEASIBLE = "FEASIBLE"
    TIGHT = "TIGHT"
    OVERFILLED = "OVERFILLED"
    NOT_CALCULABLE = "NOT_CALCULABLE"


#: Usable-slot envelope fill bands. Declared, sourced, and overridable.
DEFAULT_STATUS_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.60, ManufacturabilityStatus.COMFORTABLE),
    (0.75, ManufacturabilityStatus.FEASIBLE),
    (1.00, ManufacturabilityStatus.TIGHT),
)

#: Round wire cannot tile a slot. This is the fraction of the usable slot area a
#: real winding can reach with the envelope area, before the slot is full.
#:
#: ENGINEERING_ASSUMPTION. Typical random-wound round-wire practice. Not a
#: physical constant and not fitted to anything.
DEFAULT_PACKING_FACTOR = 0.80


@dataclass(frozen=True)
class SlotGeometry:
    """The slot cross-section, and what is unavailable inside it."""

    slot_count: int
    top_width_mm: float
    bottom_width_mm: float
    depth_mm: float
    wedge_height_mm: float = 0.0
    liner_thickness_mm: float = 0.0
    clearance_mm: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("slot_count", self.slot_count),
            ("top_width_mm", self.top_width_mm),
            ("bottom_width_mm", self.bottom_width_mm),
            ("depth_mm", self.depth_mm),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name, value in (
            ("wedge_height_mm", self.wedge_height_mm),
            ("liner_thickness_mm", self.liner_thickness_mm),
            ("clearance_mm", self.clearance_mm),
        ):
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

    @property
    def gross_area_mm2(self) -> float:
        """Trapezoidal slot cross-section, before any allowance."""

        return (self.top_width_mm + self.bottom_width_mm) / 2.0 * self.depth_mm

    @property
    def usable_area_mm2(self) -> float:
        """Gross area less the wedge, the liner and the clearance.

        The liner lines the perimeter, so it costs area on both widths and on
        the depth. Returned unclamped: a negative value is a real answer meaning
        the allowances do not fit, and is reported rather than floored at zero.
        """

        wedge = self.top_width_mm * self.wedge_height_mm
        remaining_depth = self.depth_mm - self.wedge_height_mm
        liner = self.liner_thickness_mm + self.clearance_mm
        lined_top = self.top_width_mm - 2.0 * liner
        lined_bottom = self.bottom_width_mm - 2.0 * liner
        lined_depth = remaining_depth - 2.0 * liner
        if lined_top <= 0.0 or lined_bottom <= 0.0 or lined_depth <= 0.0:
            return self.gross_area_mm2 - wedge - 2.0 * liner * (
                self.top_width_mm + self.depth_mm
            )
        return (lined_top + lined_bottom) / 2.0 * lined_depth


@dataclass(frozen=True)
class ConductorSpec:
    """One conductor, bare and insulated."""

    bare_diameter_mm: float
    insulated_diameter_mm: float | None = None
    parallel_strands: int = 1

    def __post_init__(self) -> None:
        if not math.isfinite(self.bare_diameter_mm) or self.bare_diameter_mm <= 0.0:
            raise ValueError("bare_diameter_mm must be finite and positive")
        if self.parallel_strands < 1:
            raise ValueError("parallel_strands must be at least 1")
        if self.insulated_diameter_mm is not None:
            if not math.isfinite(self.insulated_diameter_mm):
                raise ValueError("insulated_diameter_mm must be finite")
            if self.insulated_diameter_mm < self.bare_diameter_mm:
                raise ValueError(
                    "insulated_diameter_mm cannot be smaller than bare_diameter_mm; "
                    f"got {self.insulated_diameter_mm} < {self.bare_diameter_mm}"
                )

    @property
    def effective_insulated_diameter_mm(self) -> float:
        """Falls back to the bare diameter, which the report labels as such."""

        return (
            self.insulated_diameter_mm
            if self.insulated_diameter_mm is not None
            else self.bare_diameter_mm
        )

    @property
    def bare_area_mm2(self) -> float:
        """Copper cross-section of one turn, summed over parallel strands."""

        single = math.pi * (self.bare_diameter_mm / 2.0) ** 2
        return single * self.parallel_strands

    @property
    def envelope_area_mm2(self) -> float:
        """Insulated cross-section of one turn, summed over parallel strands."""

        diameter = self.effective_insulated_diameter_mm
        return math.pi * (diameter / 2.0) ** 2 * self.parallel_strands


@dataclass(frozen=True)
class SlotFillResult:
    """Everything the occupancy question contains, with each denominator named."""

    schema_version: str
    # Geometry
    gross_slot_area_mm2: float
    usable_slot_area_mm2: float
    # Occupancy
    coil_sides_per_slot: int
    turns_per_coil_side: float
    conductors_per_slot: float
    bare_copper_area_per_slot_mm2: float
    envelope_area_per_slot_mm2: float
    # Ratios, each against a stated denominator
    gross_copper_fill: float | None
    usable_copper_fill: float | None
    gross_envelope_fill: float | None
    usable_envelope_fill: float | None
    # Assumptions
    packing_factor: float
    packing_factor_provenance: str
    achievable_envelope_area_mm2: float | None
    # Verdict, kept separate from the numbers above
    status: str
    status_provenance: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_calculable(self) -> bool:
        return self.usable_envelope_fill is not None


def _status_for(fill: float | None, thresholds) -> str:
    if fill is None or not math.isfinite(fill):
        return ManufacturabilityStatus.NOT_CALCULABLE
    for limit, label in thresholds:
        if fill <= limit:
            return label
    return ManufacturabilityStatus.OVERFILLED


def compute_slot_fill(
    *,
    geometry: SlotGeometry,
    conductor: ConductorSpec,
    turns_per_coil: float,
    coil_sides_per_slot: int,
    packing_factor: float = DEFAULT_PACKING_FACTOR,
    thresholds=DEFAULT_STATUS_THRESHOLDS,
) -> SlotFillResult:
    """Occupancy of one slot, with every denominator named and no silent clipping.

    ``coil_sides_per_slot`` is the winding's own business: a single-layer winding
    puts one coil side in a slot, a double-layer winding two. It is not inferred,
    because inferring it is how a factor-of-two error gets in.

    A design that does not fit is reported as not fitting. Nothing is clamped to
    make a result look achievable.
    """

    warnings: list[str] = []

    if coil_sides_per_slot < 1:
        raise ValueError("coil_sides_per_slot must be at least 1")
    if not math.isfinite(turns_per_coil) or turns_per_coil <= 0.0:
        raise ValueError("turns_per_coil must be finite and positive")
    if not 0.0 < packing_factor <= 1.0:
        raise ValueError("packing_factor must lie in (0, 1]")

    gross = geometry.gross_area_mm2
    usable = geometry.usable_area_mm2

    conductors_per_slot = turns_per_coil * coil_sides_per_slot
    bare = conductor.bare_area_mm2 * conductors_per_slot
    envelope = conductor.envelope_area_mm2 * conductors_per_slot

    if conductor.insulated_diameter_mm is None:
        warnings.append(
            "未提供带绝缘线径，绝缘包络面积按裸铜线径计算，因此槽占比被低估。"
        )

    if usable <= 0.0:
        warnings.append(
            "扣除楔块、槽绝缘与间隙后可用槽面积不为正，该槽无法容纳任何导体。"
        )
        return SlotFillResult(
            schema_version=SLOT_FILL_SCHEMA_VERSION,
            gross_slot_area_mm2=gross,
            usable_slot_area_mm2=usable,
            coil_sides_per_slot=coil_sides_per_slot,
            turns_per_coil_side=turns_per_coil,
            conductors_per_slot=conductors_per_slot,
            bare_copper_area_per_slot_mm2=bare,
            envelope_area_per_slot_mm2=envelope,
            gross_copper_fill=bare / gross if gross > 0.0 else None,
            usable_copper_fill=None,
            gross_envelope_fill=envelope / gross if gross > 0.0 else None,
            usable_envelope_fill=None,
            packing_factor=packing_factor,
            packing_factor_provenance=Provenance.ENGINEERING_ASSUMPTION,
            achievable_envelope_area_mm2=None,
            status=ManufacturabilityStatus.NOT_CALCULABLE,
            status_provenance=Provenance.ENGINEERING_ASSUMPTION,
            warnings=tuple(warnings),
        )

    achievable = usable * packing_factor
    usable_envelope_fill = envelope / usable

    if envelope > achievable:
        warnings.append(
            f"绝缘包络面积 {envelope:.2f} mm² 超过可用槽面积在装填系数 "
            f"{packing_factor:.2f} 下可达到的 {achievable:.2f} mm²，"
            "该绕组按此线径与匝数无法绕入。"
        )
    if usable_envelope_fill > 1.0:
        warnings.append(
            f"可用槽面积占比 {usable_envelope_fill * 100.0:.1f} % 超过 100 %，"
            "导体在几何上就放不下，与装填系数无关。"
        )
    if turns_per_coil != int(turns_per_coil):
        warnings.append(
            f"每线圈匝数 {turns_per_coil} 非整数；实际绕组只能是整数匝，"
            "该值应视为串并联折算后的等效匝数。"
        )
    if conductor.parallel_strands > 1 and conductor.insulated_diameter_mm is None:
        warnings.append(
            f"使用 {conductor.parallel_strands} 根并绕股线但未提供绝缘线径，"
            "并绕股线之间的绝缘与间隙完全未被计入。"
        )

    return SlotFillResult(
        schema_version=SLOT_FILL_SCHEMA_VERSION,
        gross_slot_area_mm2=gross,
        usable_slot_area_mm2=usable,
        coil_sides_per_slot=coil_sides_per_slot,
        turns_per_coil_side=turns_per_coil,
        conductors_per_slot=conductors_per_slot,
        bare_copper_area_per_slot_mm2=bare,
        envelope_area_per_slot_mm2=envelope,
        gross_copper_fill=bare / gross,
        usable_copper_fill=bare / usable,
        gross_envelope_fill=envelope / gross,
        usable_envelope_fill=usable_envelope_fill,
        packing_factor=packing_factor,
        packing_factor_provenance=Provenance.ENGINEERING_ASSUMPTION,
        achievable_envelope_area_mm2=achievable,
        status=_status_for(usable_envelope_fill / packing_factor, thresholds),
        status_provenance=Provenance.ENGINEERING_ASSUMPTION,
        warnings=tuple(warnings),
    )
