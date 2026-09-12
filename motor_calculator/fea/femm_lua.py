"""Deterministic FEMM Lua script generation.

The script this module emits is a pure text artefact: generating it needs no
FEMM installation, so it can be produced, inspected, exported and regression
tested on a machine with no FEA software.

Verified against a real solver
-----------------------------
Phase 10B ran this against FEMM 4.2 and the solver rejected three assumptions
Phase 10A's unit tests could not catch:

* ``mi_addsegment`` joins two *existing* nodes. Without ``mi_addnode`` the
  segments were silently dropped and the mesher received a geometry declaring
  zero nodes and zero segments.
* ``mo_getb`` does not exist. The postprocessor point query is
  ``mo_getpointvalues``, returning ``A, Bx, By``.
* Without ``quit()`` FEMM keeps its main window open after the script ends, so
  the subprocess never returns.

``mo_getcircuitproperties``, ``mo_blockintegral(18)``, ``mo_groupselectblock``
and ``mo_numelements`` were confirmed to behave as assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import FEASliceModel
from .models import FEAMaterialSet, FEAValidationCase, FEAValidationTarget

FEMM_LUA_GENERATOR_VERSION = "phase10b.femm.lua.v2"

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


def _lua_path(value: str) -> str:
    """A filesystem path as a Lua string literal.

    Forward slashes are used deliberately. FEMM accepts them on Windows, and
    they remove an entire class of bug: a Windows path inside a Lua string needs
    every backslash doubled, and one missed escape turns a path segment into an
    escape sequence.
    """

    return _lua_string(value.replace("\\", "/"))


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
            'mi_addmaterial({name}, 1, 1, 0, 0, {sigma}, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
                name=_lua_string(materials.conductor_name),
                sigma=_num(materials.conductor_conductivity_ms_per_m),
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


#: Region material keys that do not literally name a FEMM material.
#:
#: A key that resolves to a name no ``mi_addmaterial`` call defined is not an
#: error FEMM reports: ``mi_setblockprop`` leaves the label with block type 0,
#: meaning *no material*, and the analysis then silently refuses to mesh. The
#: real solver reached that state with 48 winding labels carrying no material
#: because the geometry layer says "conductor" and the material is named after
#: the conductor itself.
def _region_material_name(region_material_key: str, materials: FEAMaterialSet) -> str:
    if region_material_key == "core" and materials.core_library_material_name:
        return materials.core_library_material_name
    if region_material_key == "conductor":
        return materials.conductor_name
    return region_material_key


def unit_turns_scale(model: FEASliceModel) -> float:
    """The turns magnitude every winding region shares.

    FEMM stores the block ``turns`` property as an **integer**: a coil of 6.25
    turns is written to the model file as 6, understating the flux linkage by
    4%. Measured against the real solver, flux linkage is *exactly* linear in
    turns (ratios of 2.0000000000 and 5.0000000000 for 2x and 5x), so the script
    emits unit turns carrying only the series sign and the extracted linkage is
    multiplied by this scale afterwards. That is exact and cannot truncate.

    Every winding region of the model shares one turns magnitude -- a whole coil
    side for a coreless stator, half of one for a cored stator whose central
    yoke splits it -- so a single scale is well defined. A model that ever
    breaks that assumption is rejected rather than silently mis-scaled.
    """

    magnitudes = {
        abs(float(region.signed_turns))
        for region in model.regions
        if region.role == "winding" and region.signed_turns
    }
    if not magnitudes:
        return 1.0
    if len(magnitudes) > 1:
        raise ValueError(
            "winding regions carry more than one turns magnitude "
            f"({sorted(magnitudes)}); a single unit-turns scale would mis-weight them"
        )
    return magnitudes.pop()


def declared_material_names(materials: FEAMaterialSet, *, is_coreless: bool) -> set[str]:
    """Every material name the emitted script defines."""

    names = {"air", "magnet", materials.conductor_name, "back_iron"}
    if not is_coreless:
        names.add(materials.core_library_material_name or "core")
    return names


def emit_geometry_lua(
    model: FEASliceModel, materials: FEAMaterialSet, *, is_coreless: bool
) -> list[str]:
    """Nodes, segments, boundaries and block labels for one rotor position."""

    lines: list[str] = ["-- Geometry"]

    # ------------------------------------------------------------------
    # Nodes first. ``mi_addsegment`` joins two *existing* nodes; it does not
    # create them. Emitting segments without nodes silently produces an empty
    # geometry -- the real solver wrote a .poly file declaring zero nodes and
    # zero segments, meshed nothing, and never produced a solution.
    # FEMM merges coincident nodes, so shared polygon corners are safe.
    # ------------------------------------------------------------------
    domain = model.domain_polygon_m
    span = model.modelled_span_m
    domain_y = max(abs(point[1]) for point in domain)

    def _is_seam(x: float) -> bool:
        return abs(x) < 1e-12 or abs(x - span) < 1e-12

    # ------------------------------------------------------------------
    # The two circumferential seams need special handling. Regions that span
    # the full width (the rotor back iron, and a cored stator core) have their
    # own vertical edges lying *on* the domain's side edges. Emitting both
    # produces overlapping collinear segments, which is invalid input for the
    # mesher: the real solver returned from mi_analyze without writing a mesh.
    #
    # Instead each seam is emitted once, subdivided at every y-coordinate any
    # region places on it, so region edges coincide exactly with seam pieces
    # rather than overlapping them.
    # ------------------------------------------------------------------
    seam_breakpoints: set[float] = {-domain_y, domain_y}
    for region in model.regions:
        if region.role in ("air_domain", "air_domain_label_only"):
            continue
        for x, y in region.polygon_m:
            if _is_seam(x):
                seam_breakpoints.add(y)
    ordered_breakpoints = sorted(seam_breakpoints)

    seen_nodes: set[tuple[float, float]] = set()
    lines.append("-- Nodes")

    def _add_node(point: tuple[float, float]) -> None:
        if point in seen_nodes:
            return
        seen_nodes.add(point)
        lines.append(f"mi_addnode({_num(point[0])}, {_num(point[1])})")

    for region in model.regions:
        if region.role in ("air_domain", "air_domain_label_only"):
            continue
        for point in region.polygon_m:
            _add_node(point)
    for point in domain:
        _add_node(point)
    for seam_x in (0.0, span):
        for y in ordered_breakpoints:
            _add_node((seam_x, y))

    lines.append("-- Segments")
    seen_segments: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    def _add_segment(start: tuple[float, float], end: tuple[float, float]) -> None:
        key = tuple(sorted((start, end)))
        if key in seen_segments:
            return
        seen_segments.add(key)
        lines.append(
            f"mi_addsegment({_num(start[0])}, {_num(start[1])}, "
            f"{_num(end[0])}, {_num(end[1])})"
        )

    # Seam pieces first, so a region edge lying on a seam is deduplicated
    # against an exactly matching piece instead of overlapping a longer one.
    for seam_x in (0.0, span):
        for lower, upper in zip(ordered_breakpoints, ordered_breakpoints[1:]):
            _add_segment((seam_x, lower), (seam_x, upper))

    for region in model.regions:
        if region.role in ("air_domain", "air_domain_label_only"):
            continue
        polygon = region.polygon_m
        for index in range(len(polygon)):
            _add_segment(polygon[index], polygon[(index + 1) % len(polygon)])

    # Only the horizontal far-field edges remain; the vertical ones were
    # emitted as seam pieces above.
    for index in range(len(domain)):
        start = domain[index]
        end = domain[(index + 1) % len(domain)]
        if _is_seam(start[0]) and _is_seam(end[0]) and start[0] == end[0]:
            continue
        _add_segment(start, end)

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
    for edge_y in (-domain_y, domain_y):
        lines.append(
            f"mi_selectsegment({_num(span / 2.0)}, {_num(edge_y)})"
        )
    lines.append('mi_setsegmentprop("outer_A0", 0, 1, 0, 0)')
    lines.append("mi_clearselected()")

    # One periodic pair per seam piece. FEMM requires a periodic boundary to be
    # applied to exactly two segments, so the intervals here must be the same
    # ones the seams were actually subdivided into; a property that selects
    # nothing makes the analysis refuse to run.
    for index, (lower, upper) in enumerate(
        zip(ordered_breakpoints, ordered_breakpoints[1:])
    ):
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
    declared = declared_material_names(materials, is_coreless=is_coreless)
    undeclared = sorted(
        {
            _region_material_name(region.material_key, materials)
            for region in model.regions
        }
        - declared
    )
    if undeclared:
        # Refuse loudly here rather than emitting a script whose labels carry no
        # material and whose analysis refuses to mesh without saying why.
        raise ValueError(
            "these region materials are never defined in the script: "
            + ", ".join(undeclared)
        )
    for region in model.regions:
        label_x, label_y = region.block_label_m
        group = _region_group(region.role)
        if region.role in ("magnet", "back_iron") and label_y < 0.0:
            group = GROUP_ROTOR_LOWER
        material_name = _region_material_name(region.material_key, materials)
        circuit = region.circuit_name or ""
        magdir = region.magnetization_direction_deg or 0.0
        # Unit turns carrying only the series sign: FEMM truncates the turns
        # property to an integer, so the magnitude is applied in Python instead
        # (see unit_turns_scale).
        raw_turns = region.signed_turns if region.signed_turns is not None else 0.0
        turns = 0.0 if not raw_turns else (1.0 if raw_turns > 0 else -1.0)
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
    # Phase 10F. The winding regions carry unit turns so FEMM's integer ``turns``
    # property cannot truncate a fractional coil (see ``unit_turns_scale``). For a
    # no-load sweep that is exact: flux linkage is linear in turns and is rescaled
    # after extraction.
    #
    # For a LOADED solve it is not. The field the armature produces depends on
    # ampere-turns, and a model wound with 1 turn instead of N carries 1/N of the
    # real MMF, so the armature field and every torque derived from it come out
    # 1/N too small. Measured on the Phase 10A reference case: the block-integral
    # torque was 6.2034x below the energy-conservation value against a turns scale
    # of exactly 6.25, agreeing to 0.745%.
    #
    # Scaling the circuit current by the same factor restores the ampere-turns
    # exactly, and leaves a no-load script byte-identical because the current is
    # zero either way.
    #
    # The emitted comment below is deliberately left unchanged: Phase 10C and
    # 10D both rest on the no-load campaign scripts being byte-identical across
    # revisions, and that property is worth more than a nicer comment.
    turns_scale = unit_turns_scale(model)
    lines.append("-- Circuits: series connected, one per phase")
    for name in phase_names:
        current = phase_currents.values.get(name, 0.0) * turns_scale
        lines.append(f"mi_addcircprop({_lua_string(name)}, {_num(current)}, 1)")
    lines.extend(emit_geometry_lua(model, materials, is_coreless=case.geometry.is_coreless))

    lines.extend(
        [
            "-- Solve",
            f"mi_saveas({_lua_path(fem_path)})",
            "mi_analyze(1)",
            "mi_loadsolution()",
        ]
    )

    mode = "a" if append else "w"
    lines.append(f"handle = openfile({_lua_path(output_path)}, {_lua_string(mode)})")
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
    # Without quit() FEMM keeps its main window open after the script ends and
    # the subprocess never returns, so every position would sit until timeout.
    lines.append("quit()")
    return "\n".join(lines) + "\n"
