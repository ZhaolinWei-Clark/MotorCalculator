"""Explicit material mapping from MotorCalculator inputs to FEA material data.

No property is ever inferred from a material *name*. Every value either comes
from an explicit input field or is a declared FEA-only modelling parameter, and
anything the analytical model does not contain is recorded in
``property_mismatches`` rather than invented.
"""

from __future__ import annotations

from ..motor_core.constants import MU0, RHO_CU_20, RHO_CU_TEMP_COEFF
from .models import FEACoreModelPolicy, FEAMaterialSet

#: Relative permeability used when the FEA core is modelled as linear.
#:
#: The analytical magnetic circuit contains *no* iron reluctance at all: its
#: only reluctances are the air gap and the magnets. A linear core of very high
#: permeability is the FEA representation of exactly that assumption, which
#: keeps the comparison focused on gap and leakage modelling instead of
#: confounding it with saturation the analytical model never claimed to model.
LINEAR_CORE_RELATIVE_PERMEABILITY = 5000.0

#: Same reasoning for the rotor back iron.
LINEAR_BACK_IRON_RELATIVE_PERMEABILITY = 5000.0

#: Mismatches between what the analytical model knows and what a field solver
#: needs. These are reported, never silently filled in.
ANALYTICAL_PROPERTY_MISMATCHES = (
    "the analytical magnetic circuit carries no iron reluctance and no B-H data; "
    "the FEA core permeability is a declared FEA-only modelling parameter",
    "the analytical model carries no rotor back-iron thickness; it is a declared "
    "FEA-only modelling parameter supplied per case",
    "magnet and steel electrical conductivity are irrelevant to a magnetostatic "
    "solve and are not transferred",
    "the analytical `leakage_factor` is a lumped scalar with no field-solver "
    "counterpart; the solver resolves leakage geometrically instead",
    "the analytical Carter factor is a fixed table value keyed by the slot-type "
    "name and ignores the entered slot opening width and air gap; the solver "
    "resolves real slotting instead",
)

SATURABLE_CORE_MISMATCH = (
    "a saturable library B-H curve models more physics than the analytical model "
    "contains, so a disagreement cannot be attributed to the analytical model alone"
)


def copper_conductivity_ms_per_m(temperature_c: float) -> float:
    """Copper conductivity in MS/m at the given temperature.

    Uses the same resistivity law the analytical winding resistance uses, so the
    solver and the analytical model describe the same conductor.
    """

    resistivity = RHO_CU_20 * (1.0 + RHO_CU_TEMP_COEFF * (temperature_c - 20.0))
    return 1.0 / resistivity / 1.0e6


def magnet_coercivity_a_per_m(remanence_t: float, relative_permeability: float) -> float:
    """``H_c = B_r / (mu0 * mu_r)`` for a linear recoil magnet."""

    return remanence_t / (MU0 * relative_permeability)


def build_material_set(
    *,
    remanence_t: float,
    magnet_relative_permeability: float,
    coil_temperature_c: float,
    is_coreless: bool,
    core_model_policy: FEACoreModelPolicy | None = None,
    core_library_material_name: str | None = None,
) -> FEAMaterialSet:
    """Map explicit input values onto an explicit FEA material set."""

    if core_model_policy is None:
        core_model_policy = (
            FEACoreModelPolicy.NOT_APPLICABLE_CORELESS
            if is_coreless
            else FEACoreModelPolicy.LINEAR_HIGH_PERMEABILITY
        )
    if is_coreless and core_model_policy is not FEACoreModelPolicy.NOT_APPLICABLE_CORELESS:
        raise ValueError("a coreless stator cannot declare a stator core material policy")
    if not is_coreless and core_model_policy is FEACoreModelPolicy.NOT_APPLICABLE_CORELESS:
        raise ValueError("a cored stator requires an explicit core material policy")

    mismatches = list(ANALYTICAL_PROPERTY_MISMATCHES)
    core_relative_permeability: float | None = None
    library_name: str | None = None
    if core_model_policy is FEACoreModelPolicy.LINEAR_HIGH_PERMEABILITY:
        core_relative_permeability = LINEAR_CORE_RELATIVE_PERMEABILITY
    elif core_model_policy is FEACoreModelPolicy.SATURABLE_LIBRARY_BH:
        if not core_library_material_name:
            raise ValueError("a saturable core policy requires an explicit library material name")
        library_name = core_library_material_name
        mismatches.append(SATURABLE_CORE_MISMATCH)

    return FEAMaterialSet(
        magnet_remanence_t=remanence_t,
        magnet_relative_permeability=magnet_relative_permeability,
        magnet_coercivity_a_per_m=magnet_coercivity_a_per_m(
            remanence_t, magnet_relative_permeability
        ),
        conductor_name="copper",
        conductor_conductivity_ms_per_m=copper_conductivity_ms_per_m(coil_temperature_c),
        air_relative_permeability=1.0,
        core_model_policy=core_model_policy,
        core_relative_permeability=core_relative_permeability,
        core_library_material_name=library_name,
        rotor_back_iron_relative_permeability=LINEAR_BACK_IRON_RELATIVE_PERMEABILITY,
        rotor_back_iron_library_material_name=None,
        property_mismatches=tuple(mismatches),
    )
