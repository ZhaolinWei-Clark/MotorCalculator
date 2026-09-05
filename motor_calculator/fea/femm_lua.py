"""Deterministic FEMM Lua script generation.

The script this module emits is a pure text artefact: generating it needs no
FEMM installation, so it can be produced, inspected, exported and regression
tested on a machine with no FEA software.

Honesty note
------------
FEMM is not installed in the environment this module was written in, so the
emitted Lua has never been executed by a real solver here. Its *structure* is
regression tested (element counts, materials, circuits, boundary pairing,
numeric formatting), but "the script is well formed" is not the same claim as
"the script solves correctly", and Phase 10A does not make the second claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import FEASliceModel
from .models import FEAMaterialSet, FEAValidationCase, FEAValidationTarget

FEMM_LUA_GENERATOR_VERSION = "phase10a.femm.lua.v1"

#: FEMM group numbers. The rotor groups are integrated for force; the stator
#: group is left alone.
GROUP_AIR = 0
GROUP_STATOR = 1
GROUP_ROTOR_UPPER = 2
GROUP_ROTOR_LOWER = 3

ROTOR_GROUPS = (GROUP_ROTOR_UPPER, GROUP_ROTOR_LOWER)

#: FEMM ``mo_blockintegral`` selector for the x component of the steady-state
#: weighted stress tensor force.
BLOCK_INTEGRAL_FORCE_X = 18

#: FEMM boundary format codes.
BOUNDARY_PRESCRIBED_A = 0
BOUNDARY_PERIODIC = 4

#: Solver precision passed to ``mi_probdef``.
SOLVER_PRECISION = 1.0e-8


def _num(value: float) -> str:
    """Format a number for Lua with enough digits to round-trip a double."""

    if not math.isfinite(value):
        raise ValueError("non-finite values cannot be written into a Lua script")
    if value == 0.0:
        return "0"
    return repr(float(value))


def _lua_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@dataclass(frozen=True)
class PhaseCurrents:
    """Instantaneous phase currents for one solved position, in amperes."""

    values: dict[str, float]


def balanced_phase_currents(
    *,
    phase_rms_a: float,
    electrical_angle_deg: float,
    current_angle_electrical_deg: float,
    phase_names: tuple[str, ...],
) -> PhaseCurrents:
    """Balanced instantaneous currents at one rotor position.

    ``electrical_angle_deg`` is ``p`` times the mechanical rotor angle measured
    from the phase-A flux-linkage maximum, so ``current_angle_electrical_deg =
    90`` places the current vector in quadrature with the rotor flux, which is
    the ``id = 0`` condition the analytical torque constant is defined at.
    """

    peak = math.sqrt(2.0) * phase_rms_a
    total = electrical_angle_deg + current_angle_electrical_deg
    values: dict[str, float] = {}
    for index, name in enumerate(phase_names):
        values[name] = peak * math.cos(math.radians(total - 120.0 * index))
    return PhaseCurrents(values=values)


def _material_definitions(materials: FEAMaterialSet, is_coreless: bool) -> list[str]:
    """``mi_addmaterial`` calls for every material the model uses."""

    lines = [
        "-- Materials. Every property is explicit; none is inferred from a name.",
        'mi_addmaterial("air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)',
        (
            'mi_addmaterial("magnet", {mur}, {mur}, {hc}, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
                mur=_num(materials.magnet_relative_permeability),
                hc=_num(materials.magnet_coercivity_a_per_m),
            )
        ),
        (
            'mi_addmaterial("copper", 1, 1, 0, 0, {sigma}, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
                sigma=_num(materials.conductor_conductivity_ms_per_m)
            )
        ),
        (
            'mi_addmaterial("back_iron", {mur}, {mur}, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
                mur=_num(materials.rotor_back_iron_relative_permeability)
            )
        ),
    ]
    if not is_coreless:
        if materials.core_library_material_name:
            lines.append(
                "mi_getmaterial({name})".format(
                    name=_lua_string(materials.core_library_material_name)
                )
            )
        else:
            lines.append(
                'mi_addmaterial("core", {mur}, {mur}, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
                    mur=_num(float(materials.core_relative_permeability or 0.0))
                )
            )
    return lines


def _region_group(role: str) -> int:
    if role in ("magnet", "back_iron"):
        return GROUP_ROTOR_UPPER
    if role in ("winding", "core"):
        return GROUP_STATOR
    return GROUP_AIR


def _region_material_name(region_material_key: str, materials: FEAMaterialSet) -> str:
    if region_material_key == "core" and materials.core_library_material_name:
        return materials.core_library_material_name
    return region_material_key


def emit_geometry_lua(
    model: FEASliceModel, materials: FEAMaterialSet, *, is_coreless: bool
) -> list[str]:
    """Nodes, segments, boundaries and block labels for one rotor position."""

    lines: list[str] = ["-- Geometry"]
    seen_segments: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for region in model.regions:
        if region.role == "air_domain":
            continue
        polygon = region.polygon_m
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
            key = tuple(sorted((start, end)))
            if key in seen_segments:
                continue
            seen_segments.add(key)
            lines.append(
                f"mi_addsegment({_num(start[0])}, {_num(start[1])}, "
                f"{_num(end[0])}, {_num(end[1])})"
            )

    domain = model.domain_polygon_m
    for index in range(len(domain)):
        start = domain[index]
        end = domain[(index + 1) % len(domain)]
        lines.append(
            f"mi_addsegment({_num(start[0])}, {_num(start[1])}, "
            f"{_num(end[0])}, {_num(end[1])})"
        )

    # ------------------------------------------------------------------
    # Boundaries. The two circumferential ends are the *same physical place*
    # after unrolling, so they carry matched periodic conditions rather than a
    # prescribed potential, which would otherwise impose a false flux barrier
    # inside the machine.
    # ------------------------------------------------------------------
    lines.append("-- Boundaries")
    lines.append(
        'mi_addboundprop("outer_A0", 0, 0, 0, 0, 0, 0, 0, 0, '
        f"{BOUNDARY_PRESCRIBED_A})"
    )
    low_y, high_y = model.stack_extent_y_m
    domain_y = max(abs(point[1]) for point in domain)
    span = model.modelled_span_m
    for edge_y in (-domain_y, domain_y):
        lines.append(
            f"mi_selectsegment({_num(span / 2.0)}, {_num(edge_y)})"
        )
    lines.append('mi_setsegmentprop("outer_A0", 0, 1, 0, 0)')
    lines.append("mi_clearselected()")

    breakpoints = sorted(
        {
            -domain_y,
            low_y,
            high_y,
            domain_y,
            *(
                coordinate
                for region in model.regions
                if region.role != "air_domain"
                for coordinate in {point[1] for point in region.polygon_m}
            ),
        }
    )
    for index, (lower, upper) in enumerate(zip(breakpoints, breakpoints[1:])):
        midpoint = (lower + upper) / 2.0
        name = f"periodic_{index:03d}"
        lines.append(
            f"mi_addboundprop({_lua_string(name)}, 0, 0, 0, 0, 0, 0, 0, 0, "
            f"{BOUNDARY_PERIODIC})"
        )
        lines.append(f"mi_selectsegment({_num(0.0)}, {_num(midpoint)})")
        lines.append(f"mi_selectsegment({_num(span)}, {_num(midpoint)})")
        lines.append(f'mi_setsegmentprop({_lua_string(name)}, 0, 1, 0, 0)')
        lines.append("mi_clearselected()")

    lines.append("-- Block labels")
    for region in model.regions:
        label_x, label_y = region.block_label_m
        group = _region_group(region.role)
        if region.role in ("magnet", "back_iron") and label_y < 0.0:
            group = GROUP_ROTOR_LOWER
        material_name = _region_material_name(region.material_key, materials)
        circuit = region.circuit_name or ""
        magdir = region.magnetization_direction_deg or 0.0
        turns = region.signed_turns if region.signed_turns is not None else 0.0
        lines.append(f"mi_addblocklabel({_num(label_x)}, {_num(label_y)})")
        lines.append(f"mi_selectlabel({_num(label_x)}, {_num(label_y)})")
        lines.append(
            "mi_setblockprop({material}, 0, {mesh}, {circuit}, {magdir}, {group}, {turns})".format(
                material=_lua_string(material_name),
                mesh=_num(region.mesh_size_m),
                circuit=_lua_string(circuit),
                magdir=_num(magdir),
                group=group,
                turns=_num(float(turns)),
            )
        )
        lines.append("mi_clearselected()")
    return lines


def build_position_script(
    case: FEAValidationCase,
    model: FEASliceModel,
    *,
    phase_currents: PhaseCurrents,
    fem_path: str,
    output_path: str,
    append: bool,
) -> str:
    """Emit the complete Lua script that solves and reports one rotor position."""

    materials = case.materials
    phase_names = tuple(model.circuit_names)
    lines: list[str] = [
        f"-- MotorCalculator Phase 10A FEA bridge, generator {FEMM_LUA_GENERATOR_VERSION}",
        f"-- case_id {case.case_id}",
        f"-- target {case.target.value}",
        f"-- rotor angle {model.rotor_angle_mech_deg} mechanical degrees",
        "-- This script is generated; do not edit it by hand.",
        "newdocument(0)",
        (
            'mi_probdef(0, "meters", "planar", {precision}, {depth}, {minangle}, 0)'.format(
                precision=_num(SOLVER_PRECISION),
                depth=_num(model.depth_m),
                minangle=_num(case.mesh_policy.minimum_angle_deg),
            )
        ),
    ]
    lines.extend(_material_definitions(materials, case.geometry.is_coreless))
    lines.append("-- Circuits: series connected, one per phase")
    for name in phase_names:
        current = phase_currents.values.get(name, 0.0)
        lines.append(f"mi_addcircprop({_lua_string(name)}, {_num(current)}, 1)")
    lines.extend(emit_geometry_lua(model, materials, is_coreless=case.geometry.is_coreless))

    lines.extend(
        [
            "-- Solve",
            f"mi_saveas({_lua_string(fem_path)})",
            "mi_analyze(1)",
            "mi_loadsolution()",
        ]
    )

    mode = "a" if append else "w"
    lines.append(f"handle = openfile({_lua_string(output_path)}, {_lua_string(mode)})")
    if not append:
        header = "rotor_angle_mech_deg," + ",".join(
            f"flux_linkage_{name}_wb_turn" for name in phase_names
        ) + ",circumferential_force_n,element_count"
        lines.append(f"write(handle, {_lua_string(header)}, \"\\n\")")

    lines.append(f"write(handle, {_num(model.rotor_angle_mech_deg)}, \",\")")
    for name in phase_names:
        lines.append(
            f"current_{name}, volts_{name}, flux_{name} = "
            f"mo_getcircuitproperties({_lua_string(name)})"
        )
        lines.append(f"write(handle, flux_{name}, \",\")")

    lines.append("mo_clearblock()")
    for group in ROTOR_GROUPS:
        lines.append(f"mo_groupselectblock({group})")
    lines.append(f"force_x = mo_blockintegral({BLOCK_INTEGRAL_FORCE_X})")
    lines.append("mo_clearblock()")
    lines.append('write(handle, force_x, ",")')
    lines.append("write(handle, mo_numelements(), \"\\n\")")
    lines.append("closefile(handle)")
    lines.append("mo_close()")
    lines.append("mi_close()")
    return "\n".join(lines) + "\n"
