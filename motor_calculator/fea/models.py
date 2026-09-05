"""Structured FEA validation case, result and comparison models for Phase 10A.

Phase 10A adds a numerical-electromagnetic validation bridge. Nothing in this
package changes analytical physics: every model here only *describes* a case,
*records* a solver result, or *reports* a difference. The analytical kernel
(``motor_core/calculations.py``) is never consulted for calibration and never
modified by this package.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

# ---------------------------------------------------------------------------
# Semantic version of the Phase 10A case schema. Any change that alters the
# meaning of a serialized field must bump this string, because the case hash
# includes it and stale FEA results must not be silently reused.
# ---------------------------------------------------------------------------
FEA_CASE_SCHEMA_VERSION = "phase10a.fea.case.v1"


class FEAValidationTarget(str, Enum):
    """The three quantities Phase 10A is allowed to validate."""

    NO_LOAD_BACK_EMF = "NO_LOAD_BACK_EMF"
    AVERAGE_TORQUE = "AVERAGE_TORQUE"
    COGGING_TORQUE = "COGGING_TORQUE"


class FEASupportability(str, Enum):
    """Whether a MotorCalculator design can be mapped to the FEMM bridge."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_ENOUGH_GEOMETRY = "NOT_ENOUGH_GEOMETRY"


class FEAComparisonStatus(str, Enum):
    """Descriptive agreement bands.

    These are deliberately descriptive rather than PASS/FAIL. The numeric bands
    that map an error onto one of these names are project-provisional and are
    labeled as such wherever they are reported.
    """

    CLOSE_AGREEMENT = "CLOSE_AGREEMENT"
    MODERATE_DEVIATION = "MODERATE_DEVIATION"
    LARGE_DEVIATION = "LARGE_DEVIATION"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FEACoreModelPolicy(str, Enum):
    """How ferromagnetic material is represented in the FEA model.

    ``LINEAR_HIGH_PERMEABILITY`` reproduces the analytical model's implicit
    assumption that iron carries no reluctance, which isolates the comparison to
    air-gap and leakage modelling. ``SATURABLE_LIBRARY_BH`` uses a named solver
    library B-H curve and therefore tests *more* physics than the analytical
    model contains; the extra physics is an explicit, declared difference.
    """

    LINEAR_HIGH_PERMEABILITY = "LINEAR_HIGH_PERMEABILITY"
    SATURABLE_LIBRARY_BH = "SATURABLE_LIBRARY_BH"
    NOT_APPLICABLE_CORELESS = "NOT_APPLICABLE_CORELESS"


@dataclass(frozen=True)
class FEAUnrolledSliceGeometry:
    """Mean-radius circumferentially unrolled planar slice of an AFPM machine.

    The axial-flux machine is cut at its mean radius and unrolled into a planar
    linear machine. ``x`` is circumferential arc length, ``y`` is the axial
    direction, and the planar solver depth is the radial active length.

    This mapping is not an arbitrary choice: the analytical pole area
    ``(pi / 2p) * (R_out^2 - R_in^2) * alpha_p`` is *identically*
    ``pole_pitch_m * radial_active_length_m * alpha_p``, so the analytical
    magnetic circuit is already a mean-radius unrolled model. The slice is its
    exact geometric counterpart. What the slice adds is resolved 2D field
    spreading, inter-pole leakage and real slotting. What it still cannot see is
    listed in :attr:`omitted_three_dimensional_effects`.
    """

    mean_radius_m: float
    radial_active_length_m: float
    circumference_m: float
    pole_pairs: int
    slot_count: int
    pole_pitch_m: float
    slot_pitch_m: float
    magnet_thickness_m: float
    magnet_arc_length_m: float
    pole_arc_coefficient: float
    mechanical_air_gap_per_side_m: float
    winding_region_thickness_m: float
    rotor_back_iron_thickness_m: float
    is_coreless: bool
    # Cored-only stator detail. All ``None`` for a coreless stator.
    stator_core_thickness_m: float | None
    slot_height_m: float | None
    slot_top_width_m: float | None
    slot_bottom_width_m: float | None
    slot_opening_height_m: float | None
    slot_opening_width_m: float | None
    wedge_height_m: float | None
    yoke_height_m: float | None
    air_domain_margin_m: float
    omitted_three_dimensional_effects: tuple[str, ...]

    def __post_init__(self) -> None:
        positive = (
            "mean_radius_m",
            "radial_active_length_m",
            "circumference_m",
            "pole_pitch_m",
            "slot_pitch_m",
            "magnet_thickness_m",
            "magnet_arc_length_m",
            "mechanical_air_gap_per_side_m",
            "winding_region_thickness_m",
            "rotor_back_iron_thickness_m",
            "air_domain_margin_m",
        )
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.pole_pairs <= 0 or self.slot_count <= 0:
            raise ValueError("pole_pairs and slot_count must be positive")
        if not 0.0 < self.pole_arc_coefficient <= 1.0:
            raise ValueError("pole_arc_coefficient must be within (0, 1]")
        if self.magnet_arc_length_m > self.pole_pitch_m * (1.0 + 1e-12):
            raise ValueError("magnet arc length cannot exceed the pole pitch")
        if self.is_coreless:
            for name in ("stator_core_thickness_m", "slot_height_m", "yoke_height_m"):
                if getattr(self, name) is not None:
                    raise ValueError("a coreless slice must not declare stator core geometry")
        else:
            for name in (
                "stator_core_thickness_m",
                "slot_height_m",
                "slot_top_width_m",
                "slot_bottom_width_m",
                "slot_opening_height_m",
                "slot_opening_width_m",
                "wedge_height_m",
                "yoke_height_m",
            ):
                if getattr(self, name) is None:
                    raise ValueError(f"a cored slice requires explicit {name}")

    @property
    def magnetic_gap_between_magnet_faces_m(self) -> float:
        """Physical axial distance between the two rotor magnet faces."""

        return self.winding_region_thickness_m + 2.0 * self.mechanical_air_gap_per_side_m


@dataclass(frozen=True)
class FEAMaterialSet:
    """Explicit material mapping. No property is inferred from a material name."""

    magnet_remanence_t: float
    magnet_relative_permeability: float
    magnet_coercivity_a_per_m: float
    conductor_name: str
    conductor_conductivity_ms_per_m: float
    air_relative_permeability: float
    core_model_policy: FEACoreModelPolicy
    core_relative_permeability: float | None
    core_library_material_name: str | None
    rotor_back_iron_relative_permeability: float
    rotor_back_iron_library_material_name: str | None
    property_mismatches: tuple[str, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.magnet_remanence_t) or self.magnet_remanence_t <= 0.0:
            raise ValueError("magnet_remanence_t must be finite and positive")
        if self.magnet_relative_permeability < 1.0:
            raise ValueError("magnet relative permeability must be at least 1")
        if self.core_model_policy is FEACoreModelPolicy.LINEAR_HIGH_PERMEABILITY:
            if self.core_relative_permeability is None:
                raise ValueError("a linear core policy requires an explicit relative permeability")
            if self.core_library_material_name is not None:
                raise ValueError("a linear core policy must not also name a library B-H material")
        if self.core_model_policy is FEACoreModelPolicy.SATURABLE_LIBRARY_BH:
            if not self.core_library_material_name:
                raise ValueError("a saturable core policy requires an explicit library material name")
            if self.core_relative_permeability is not None:
                raise ValueError("a saturable core policy must not also declare a linear permeability")
        if self.core_model_policy is FEACoreModelPolicy.NOT_APPLICABLE_CORELESS:
            if self.core_relative_permeability is not None or self.core_library_material_name:
                raise ValueError("a coreless case must not declare stator core material")


@dataclass(frozen=True)
class FEAWindingMap:
    """Coil-resolved winding layout with explicit phase, polarity and turns.

    The unit of allocation is the *coil*, not the slot. Coil ``c`` has its go
    side in slot ``c`` and its return side in slot ``(c + coil_span_slots) % Q``,
    so every slot ends up holding two layers. Modelling only one layer per slot
    would leave a phase with a non-zero net in-plane current whenever the slot
    star puts all of that phase's coil sides in one belt, which is exactly what
    happens for ``q = 0.5`` fractional-slot windings.
    """

    phases: int
    slot_count: int
    pole_pairs: int
    turns_per_phase: int
    parallel_paths: int
    coil_span_slots: int
    turns_per_coil: float
    coil_phase_assignment: tuple[str, ...]
    coil_polarity: tuple[int, ...]
    layer_arrangement: str
    winding_factor_analytical: float
    winding_factor_provenance: str
    slot_copper_area_m2: float
    slot_occupancy_basis: str

    def __post_init__(self) -> None:
        if len(self.coil_phase_assignment) != self.slot_count:
            raise ValueError("every coil requires an explicit phase assignment")
        if len(self.coil_polarity) != self.slot_count:
            raise ValueError("every coil requires an explicit polarity")
        if any(value not in (1, -1) for value in self.coil_polarity):
            raise ValueError("coil polarity must be +1 or -1")
        if self.parallel_paths <= 0 or self.turns_per_phase <= 0:
            raise ValueError("turns_per_phase and parallel_paths must be positive")
        if not 0 < self.coil_span_slots < self.slot_count:
            raise ValueError("coil span must be at least one slot and less than a full bore")
        if not 0.0 < self.winding_factor_analytical <= 1.0:
            raise ValueError("winding factor must be within (0, 1]")
        counts = {
            name: self.coil_phase_assignment.count(name)
            for name in set(self.coil_phase_assignment)
        }
        if len(counts) != self.phases:
            raise ValueError("coil assignment must cover exactly the declared phase count")
        if len(set(counts.values())) != 1:
            raise ValueError("each phase must own the same number of coils")
        for phase, net in self.net_signed_turns_per_phase().items():
            if abs(net) > 1e-12:
                raise ValueError(
                    f"phase {phase} carries a non-zero net in-plane ampere-turn count "
                    "({net}); go and return coil sides must cancel"
                )

    def slot_layers(self) -> tuple[tuple[tuple[str, float], ...], ...]:
        """Per slot, the ``(phase, signed turns)`` of its go and return layers."""

        layers: list[tuple[tuple[str, float], ...]] = []
        for slot in range(self.slot_count):
            go_coil = slot
            return_coil = (slot - self.coil_span_slots) % self.slot_count
            layers.append(
                (
                    (
                        self.coil_phase_assignment[go_coil],
                        self.turns_per_coil * self.coil_polarity[go_coil],
                    ),
                    (
                        self.coil_phase_assignment[return_coil],
                        -self.turns_per_coil * self.coil_polarity[return_coil],
                    ),
                )
            )
        return tuple(layers)

    def net_signed_turns_per_phase(self) -> dict[str, float]:
        """Total signed turns each phase places in the solved plane."""

        totals: dict[str, float] = {name: 0.0 for name in set(self.coil_phase_assignment)}
        for slot_layer in self.slot_layers():
            for phase, turns in slot_layer:
                totals[phase] += turns
        return totals


@dataclass(frozen=True)
class FEAOperatingPoint:
    """One controlled excitation and rotor-motion definition."""

    target: FEAValidationTarget
    mechanical_speed_rpm: float
    phase_current_rms_a: float
    current_angle_electrical_deg: float
    temperature_c: float
    rotor_angle_start_mech_deg: float
    rotor_angle_span_mech_deg: float
    rotor_angle_sample_count: int
    sampling_rationale: str

    def __post_init__(self) -> None:
        if self.rotor_angle_sample_count < 8:
            raise ValueError("at least eight rotor positions are required")
        if not math.isfinite(self.rotor_angle_span_mech_deg) or self.rotor_angle_span_mech_deg <= 0.0:
            raise ValueError("rotor_angle_span_mech_deg must be finite and positive")
        if self.phase_current_rms_a < 0.0:
            raise ValueError("phase_current_rms_a must not be negative")
        if self.target is FEAValidationTarget.COGGING_TORQUE and self.phase_current_rms_a != 0.0:
            raise ValueError("cogging torque requires exactly zero stator current")
        if self.target is FEAValidationTarget.NO_LOAD_BACK_EMF and self.phase_current_rms_a != 0.0:
            raise ValueError("no-load back-EMF requires exactly zero stator current")

    @property
    def rotor_angle_step_mech_deg(self) -> float:
        """Endpoint-excluded uniform step over the sampled span."""

        return self.rotor_angle_span_mech_deg / float(self.rotor_angle_sample_count)

    def rotor_angles_mech_deg(self) -> tuple[float, ...]:
        step = self.rotor_angle_step_mech_deg
        return tuple(
            self.rotor_angle_start_mech_deg + step * index
            for index in range(self.rotor_angle_sample_count)
        )


@dataclass(frozen=True)
class FEAMeshPolicy:
    """Reproducible, physically motivated mesh sizing.

    Refinement is concentrated where the field gradient governs the validated
    quantities. No convergence claim is attached to a single mesh; the Phase 7H
    ``assess_mesh_convergence`` gate remains the only convergence authority.
    """

    name: str
    global_size_m: float
    air_gap_size_m: float
    magnet_size_m: float
    magnet_edge_size_m: float
    slot_opening_size_m: float | None
    winding_size_m: float
    core_size_m: float | None
    air_domain_size_m: float
    minimum_angle_deg: float
    convergence_claim: str

    def __post_init__(self) -> None:
        for name in (
            "global_size_m",
            "air_gap_size_m",
            "magnet_size_m",
            "magnet_edge_size_m",
            "winding_size_m",
            "air_domain_size_m",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.air_gap_size_m >= self.global_size_m:
            raise ValueError("the air gap must be meshed more finely than the global default")
        if self.air_domain_size_m <= self.global_size_m:
            raise ValueError("the far air domain must be coarser than the active region")
        if self.convergence_claim != "NO_CONVERGENCE_CLAIM_SINGLE_MESH":
            raise ValueError("a single mesh policy must not assert convergence")


@dataclass(frozen=True)
class FEASymmetryPlan:
    """Derived circumferential periodicity, and whether it may actually be used."""

    machine_periodicity: int
    poles_in_sector: int
    slots_in_sector: int
    sector_fraction: float
    boundary_kind: str
    applied: bool
    valid_for_cogging: bool
    rationale: str


@dataclass(frozen=True)
class FEASupportabilityReport:
    """Why a design is (or is not) mappable, with every blocking reason listed."""

    state: FEASupportability
    topology: str
    dimensionality_note: str
    fidelity_tier: str
    blocking_reasons: tuple[str, ...]
    approximation_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.state in (FEASupportability.UNSUPPORTED, FEASupportability.NOT_ENOUGH_GEOMETRY):
            if not self.blocking_reasons:
                raise ValueError("an unsupported design must state at least one blocking reason")
        if self.state is FEASupportability.SUPPORTED and self.blocking_reasons:
            raise ValueError("a supported design must not carry blocking reasons")


@dataclass(frozen=True)
class FEAAnalyticalPrediction:
    """The analytical numbers this case will be compared against.

    Captured at case-build time so that a later comparison cannot silently drift
    onto a different analytical run.
    """

    back_emf_phase_rms_v: float
    back_emf_line_rms_v: float
    back_emf_constant_phase_rms_v_per_rad_s: float | None
    flux_per_pole_wb: float
    air_gap_flux_density_peak_t: float
    average_torque_nm: float
    torque_constant_nm_per_phase_rms_a: float | None
    cogging_torque_peak_nm: float
    cogging_model_provenance: str
    basis_notes: Mapping[str, str]


@dataclass(frozen=True)
class FEAValidationCase:
    """A complete, self-contained, deterministic FEA validation case."""

    case_id: str
    schema_version: str
    application_version: str
    target: FEAValidationTarget
    supportability: FEASupportabilityReport
    geometry: FEAUnrolledSliceGeometry
    materials: FEAMaterialSet
    winding: FEAWindingMap
    operating_point: FEAOperatingPoint
    mesh_policy: FEAMeshPolicy
    symmetry: FEASymmetryPlan
    analytical: FEAAnalyticalPrediction
    units: Mapping[str, str]
    solver_family: str
    torque_extraction_method: str
    back_emf_extraction_method: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_version != FEA_CASE_SCHEMA_VERSION:
            raise ValueError("case schema version mismatch")
        if self.supportability.state is FEASupportability.UNSUPPORTED:
            raise ValueError("an unsupported design must not be built into a solvable case")
