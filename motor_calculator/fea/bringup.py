"""Minimal real-FEMM bring-up case.

Phase 10B step 5. Before a MotorCalculator-generated motor model is ever handed
to FEMM, the smallest possible magnetostatic problem is solved to prove the
external integration itself: the executable launches, a Lua script runs, a path
containing spaces survives, the working directory is usable, a problem
definition and a material are accepted, meshing and solving succeed, the
solution loads, one scalar field quantity comes back, and FEMM exits cleanly.

This is *not* motor validation. It answers one question only: does the plumbing
work?

Honesty note
------------
This module was written on a machine with no FEMM installed, so the emitted Lua
has never been executed by a real solver. Its structure and its checks are unit
tested; "the script is well formed" is not the same claim as "the script
solves", and nothing here asserts the second.
"""

from __future__ import annotations

import hashlib
import math
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .availability import FEMMAvailabilityReport, detect_femm

FEMM_BRINGUP_VERSION = "phase10b.femm.bringup.v1"

#: A single block magnet in air. Dimensions are arbitrary but fixed, so the
#: result is reproducible and comparable between machines.
BRINGUP_MAGNET_WIDTH_M = 0.020
BRINGUP_MAGNET_HEIGHT_M = 0.010
BRINGUP_MAGNET_REMANENCE_T = 1.20
BRINGUP_MAGNET_RELATIVE_PERMEABILITY = 1.05
BRINGUP_DOMAIN_HALF_SIZE_M = 0.100
BRINGUP_DEPTH_M = 0.030
BRINGUP_GLOBAL_MESH_M = 0.004
BRINGUP_MAGNET_MESH_M = 0.001

#: Deliberately contains a space, so the very first real solve proves that a
#: quoted path round-trips through the command line and through Lua.
BRINGUP_DIRECTORY_NAME = "femm bringup"

#: Probe points, in metres, in the same frame the script builds.
#: The magnet is centred on the origin and magnetized toward +y.
BRINGUP_PROBE_MAGNET_CENTRE = (0.0, 0.0)
BRINGUP_PROBE_ABOVE_POLE = (0.0, BRINGUP_MAGNET_HEIGHT_M / 2.0 + 0.002)
BRINGUP_PROBE_FAR_FIELD = (0.0, BRINGUP_DOMAIN_HALF_SIZE_M * 0.9)

#: Wall-clock ceiling for the bring-up solve. It is a tiny problem; if it has
#: not finished in this time something is wrong with the integration, not the
#: physics.
BRINGUP_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class BringUpCheck:
    """One falsifiable sanity check on the solved field."""

    name: str
    passed: bool
    detail: str
    measured: float | None = None


@dataclass(frozen=True)
class FEABringUpOutcome:
    """The result of the minimal real-solver bring-up."""

    status: str
    version: str
    executable_path: str | None
    solver_version: str | None
    workspace: str | None
    script_sha256: str | None
    exit_code: int | None
    seconds: float | None
    b_magnet_centre_t: float | None
    b_above_pole_y_t: float | None
    b_far_field_t: float | None
    checks: tuple[BringUpCheck, ...] = field(default_factory=tuple)
    stdout_tail: str = ""
    stderr_tail: str = ""
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def _num(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("non-finite values cannot be written into a Lua script")
    return repr(float(value))


def _lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_bringup_script(*, fem_path: Path, output_path: Path) -> str:
    """Emit the smallest useful magnetostatic FEMM Lua script.

    A block magnet centred on the origin, magnetized toward ``+y``, inside a
    square air domain with a prescribed-zero vector potential boundary. Three
    field probes are written out.
    """

    half_w = BRINGUP_MAGNET_WIDTH_M / 2.0
    half_h = BRINGUP_MAGNET_HEIGHT_M / 2.0
    domain = BRINGUP_DOMAIN_HALF_SIZE_M
    coercivity = BRINGUP_MAGNET_REMANENCE_T / (
        4.0e-7 * math.pi * BRINGUP_MAGNET_RELATIVE_PERMEABILITY
    )
    lines = [
        f"-- MotorCalculator FEMM bring-up, {FEMM_BRINGUP_VERSION}",
        "-- Smallest real magnetostatic case. Not motor validation.",
        "newdocument(0)",
        f'mi_probdef(0, "meters", "planar", 1e-8, {_num(BRINGUP_DEPTH_M)}, 30, 0)',
        'mi_addmaterial("air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)',
        'mi_addmaterial("bringup_magnet", {mur}, {mur}, {hc}, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)'.format(
            mur=_num(BRINGUP_MAGNET_RELATIVE_PERMEABILITY), hc=_num(coercivity)
        ),
        "-- Magnet block",
        f"mi_addsegment({_num(-half_w)}, {_num(-half_h)}, {_num(half_w)}, {_num(-half_h)})",
        f"mi_addsegment({_num(half_w)}, {_num(-half_h)}, {_num(half_w)}, {_num(half_h)})",
        f"mi_addsegment({_num(half_w)}, {_num(half_h)}, {_num(-half_w)}, {_num(half_h)})",
        f"mi_addsegment({_num(-half_w)}, {_num(half_h)}, {_num(-half_w)}, {_num(-half_h)})",
        "-- Air domain",
        f"mi_addsegment({_num(-domain)}, {_num(-domain)}, {_num(domain)}, {_num(-domain)})",
        f"mi_addsegment({_num(domain)}, {_num(-domain)}, {_num(domain)}, {_num(domain)})",
        f"mi_addsegment({_num(domain)}, {_num(domain)}, {_num(-domain)}, {_num(domain)})",
        f"mi_addsegment({_num(-domain)}, {_num(domain)}, {_num(-domain)}, {_num(-domain)})",
        '-- Boundary: A = 0 on the outer square',
        'mi_addboundprop("bringup_outer", 0, 0, 0, 0, 0, 0, 0, 0, 0)',
        f"mi_selectsegment({_num(0.0)}, {_num(-domain)})",
        f"mi_selectsegment({_num(0.0)}, {_num(domain)})",
        f"mi_selectsegment({_num(-domain)}, {_num(0.0)})",
        f"mi_selectsegment({_num(domain)}, {_num(0.0)})",
        'mi_setsegmentprop("bringup_outer", 0, 1, 0, 0)',
        "mi_clearselected()",
        "-- Block labels. 90 degrees is +y in FEMM's magnetisation convention.",
        f"mi_addblocklabel({_num(0.0)}, {_num(0.0)})",
        f"mi_selectlabel({_num(0.0)}, {_num(0.0)})",
        'mi_setblockprop("bringup_magnet", 0, {mesh}, "", 90, 1, 0)'.format(
            mesh=_num(BRINGUP_MAGNET_MESH_M)
        ),
        "mi_clearselected()",
        f"mi_addblocklabel({_num(domain * 0.5)}, {_num(domain * 0.5)})",
        f"mi_selectlabel({_num(domain * 0.5)}, {_num(domain * 0.5)})",
        'mi_setblockprop("air", 0, {mesh}, "", 0, 0, 0)'.format(
            mesh=_num(BRINGUP_GLOBAL_MESH_M)
        ),
        "mi_clearselected()",
        "-- Solve",
        f"mi_saveas({_lua_string(str(fem_path))})",
        "mi_analyze(1)",
        "mi_loadsolution()",
        "-- Extract three field probes",
    ]
    probes = (
        ("magnet_centre", BRINGUP_PROBE_MAGNET_CENTRE),
        ("above_pole", BRINGUP_PROBE_ABOVE_POLE),
        ("far_field", BRINGUP_PROBE_FAR_FIELD),
    )
    lines.append(f"handle = openfile({_lua_string(str(output_path))}, {_lua_string('w')})")
    lines.append('write(handle, "probe,bx_t,by_t\\n")')
    for name, (x, y) in probes:
        lines.append(f"bx_{name}, by_{name} = mo_getb({_num(x)}, {_num(y)})")
        lines.append(
            f'write(handle, {_lua_string(name)}, ",", bx_{name}, ",", by_{name}, "\\n")'
        )
    lines.extend(
        [
            "closefile(handle)",
            "mo_close()",
            "mi_close()",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_bringup_output(text: str) -> dict[str, tuple[float, float]]:
    """Parse the three-probe CSV the bring-up script writes."""

    probes: dict[str, tuple[float, float]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("probe,"):
            continue
        parts = line.split(",")
        if len(parts) != 3:
            raise ValueError(f"malformed bring-up probe line: {line!r}")
        name, bx_raw, by_raw = parts
        bx, by = float(bx_raw), float(by_raw)
        if not (math.isfinite(bx) and math.isfinite(by)):
            raise ValueError(f"bring-up probe {name} returned a non-finite field")
        probes[name.strip()] = (bx, by)
    if not probes:
        raise ValueError("bring-up produced no probe values")
    return probes


def evaluate_bringup_checks(
    probes: dict[str, tuple[float, float]]
) -> tuple[BringUpCheck, ...]:
    """Falsifiable sanity checks on the solved field.

    These are not expected values fitted to anything. They are the properties a
    correctly built and correctly solved permanent magnet must have, and each
    one catches a specific integration failure: a dead field, a units error, an
    inverted magnetisation, or a boundary placed too close.
    """

    checks: list[BringUpCheck] = []
    missing = [
        name for name in ("magnet_centre", "above_pole", "far_field") if name not in probes
    ]
    if missing:
        return (
            BringUpCheck(
                name="probes_present",
                passed=False,
                detail=f"missing probe values: {', '.join(missing)}",
            ),
        )

    centre = math.hypot(*probes["magnet_centre"])
    above_x, above_y = probes["above_pole"]
    far = math.hypot(*probes["far_field"])

    checks.append(
        BringUpCheck(
            name="field_is_nonzero",
            passed=centre > 1.0e-6,
            detail="a magnet must produce a non-zero field; zero means the material, "
            "the magnetisation or the solve did not take effect",
            measured=centre,
        )
    )
    checks.append(
        BringUpCheck(
            name="field_below_remanence",
            passed=centre < BRINGUP_MAGNET_REMANENCE_T * 1.5,
            detail="|B| inside an open-circuit magnet stays below its remanence; a much "
            "larger value indicates a units or coercivity error",
            measured=centre,
        )
    )
    checks.append(
        BringUpCheck(
            name="pole_face_polarity",
            passed=above_y > 0.0,
            detail="the magnet is magnetised toward +y, so By just outside its upper "
            "pole face must be positive; a negative value means inverted magnetisation",
            measured=above_y,
        )
    )
    checks.append(
        BringUpCheck(
            name="field_decays_with_distance",
            passed=far < centre,
            detail="the field must be weaker far from the magnet than inside it; a "
            "comparable far-field value means the boundary is loading the solution",
            measured=far,
        )
    )
    checks.append(
        BringUpCheck(
            name="pole_face_is_dominantly_axial",
            passed=abs(above_y) > abs(above_x),
            detail="on the pole-face centreline the normal component dominates; a "
            "dominant tangential component means the geometry is rotated",
            measured=abs(above_x),
        )
    )
    return tuple(checks)


def run_bringup(
    *,
    availability: FEMMAvailabilityReport | None = None,
    workspace_root: Path | None = None,
    timeout_seconds: float = BRINGUP_TIMEOUT_SECONDS,
    keep_artifacts_on_failure: bool = True,
) -> FEABringUpOutcome:
    """Run the minimal real FEMM case, or say exactly why it could not run."""

    from .adapter import default_workspace_root

    report = availability if availability is not None else detect_femm()
    if not report.is_available:
        return FEABringUpOutcome(
            status="BLOCKED_BY_ENVIRONMENT",
            version=FEMM_BRINGUP_VERSION,
            executable_path=None,
            solver_version=None,
            workspace=None,
            script_sha256=None,
            exit_code=None,
            seconds=None,
            b_magnet_centre_t=None,
            b_above_pole_y_t=None,
            b_far_field_t=None,
            detail=(
                "FEMM is not installed on this machine, so no field was solved. "
                "The bring-up script can still be generated and inspected."
            ),
        )

    executable = report.executable_path
    assert executable is not None
    root = workspace_root if workspace_root is not None else default_workspace_root()
    # The directory name contains a space on purpose: quoting is one of the
    # things this bring-up exists to prove.
    workspace = Path(root) / BRINGUP_DIRECTORY_NAME
    workspace.mkdir(parents=True, exist_ok=True)

    fem_path = workspace / "bringup.fem"
    output_path = workspace / "bringup_probes.csv"
    script_path = workspace / "bringup.lua"
    for stale in (fem_path, output_path):
        if stale.exists():
            stale.unlink()

    script = build_bringup_script(fem_path=fem_path, output_path=output_path)
    script_path.write_text(script, encoding="utf-8")
    script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()

    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 - explicit path, no shell
            [str(executable), "-lua-script=" + str(script_path), "-windowhide"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return FEABringUpOutcome(
            status="FAIL",
            version=FEMM_BRINGUP_VERSION,
            executable_path=str(executable),
            solver_version=None,
            workspace=str(workspace),
            script_sha256=script_sha256,
            exit_code=None,
            seconds=time.perf_counter() - started,
            b_magnet_centre_t=None,
            b_above_pole_y_t=None,
            b_far_field_t=None,
            detail=f"FEMM did not finish the bring-up within {timeout_seconds:.0f} s",
        )
    seconds = time.perf_counter() - started

    stdout_tail = (completed.stdout or "")[-2000:]
    stderr_tail = (completed.stderr or "")[-2000:]

    def _fail(detail: str) -> FEABringUpOutcome:
        return FEABringUpOutcome(
            status="FAIL",
            version=FEMM_BRINGUP_VERSION,
            executable_path=str(executable),
            solver_version=None,
            workspace=str(workspace) if keep_artifacts_on_failure else None,
            script_sha256=script_sha256,
            exit_code=completed.returncode,
            seconds=seconds,
            b_magnet_centre_t=None,
            b_above_pole_y_t=None,
            b_far_field_t=None,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            detail=detail,
        )

    if completed.returncode != 0:
        return _fail(f"FEMM exited with code {completed.returncode}")
    if not output_path.is_file():
        return _fail(
            "FEMM exited cleanly but wrote no probe file; the Lua script did not "
            "reach its output stage"
        )
    try:
        probes = parse_bringup_output(output_path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as error:
        return _fail(f"bring-up output could not be parsed: {error}")

    checks = evaluate_bringup_checks(probes)
    centre = math.hypot(*probes["magnet_centre"])
    above_y = probes["above_pole"][1]
    far = math.hypot(*probes["far_field"])
    all_passed = all(check.passed for check in checks)

    return FEABringUpOutcome(
        status="PASS" if all_passed else "FAIL",
        version=FEMM_BRINGUP_VERSION,
        executable_path=str(executable),
        solver_version=None,
        workspace=str(workspace),
        script_sha256=script_sha256,
        exit_code=completed.returncode,
        seconds=seconds,
        b_magnet_centre_t=centre,
        b_above_pole_y_t=above_y,
        b_far_field_t=far,
        checks=checks,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        detail=(
            "FEMM launched, solved the minimal magnetostatic case and exited cleanly."
            if all_passed
            else "FEMM ran but the solved field failed at least one sanity check."
        ),
    )
