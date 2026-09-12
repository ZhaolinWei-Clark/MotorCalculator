"""Phase 11B: machine topology, and why CREATOR cannot enter the AFPM kernel.

The Phase 11B-A audit found something that changes what this phase is allowed to
attempt. ``motor_core/calculations.py`` opens with *"Pure calculation kernel for
the AFPM PMSM/BLDC model"*, and its inputs are axial-flux by construction:
``D_out`` and ``D_in`` describe an annulus, ``g_side`` is the per-side gap of a
dual-rotor stack, and ``h_coil``/``h_yoke``/``L_magnet`` measure along the axis.

The CREATOR PMSM is a radial-flux inset machine: stator bore 47.8 mm, rotor OD
47 mm, a 0.4 mm *radial* gap, 30.1 mm of stack. There is no assignment of those
dimensions to the AFPM fields that preserves the physics. A project built that
way would run, produce plausible-looking numbers, and mean nothing.

That is a worse outcome than an error, because it looks like a result. So the
mismatch is made structural: :func:`require_compatible_topology` refuses, and
the refusal names the reason rather than failing obscurely.

This module adds no physics and changes none. It is a gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

TOPOLOGY_SCHEMA_VERSION = "phase11b.topology.v1"


class MachineTopology(str, Enum):
    """Topologies this project can name. Only one of them it can model."""

    #: The production kernel's topology, and the only one it models.
    AFPM_DUAL_ROTOR_SINGLE_STATOR = "AFPM_DUAL_ROTOR_SINGLE_STATOR"
    AFPM_SINGLE_ROTOR_SINGLE_STATOR = "AFPM_SINGLE_ROTOR_SINGLE_STATOR"
    RADIAL_FLUX_INSET_PMSM = "RADIAL_FLUX_INSET_PMSM"
    RADIAL_FLUX_SURFACE_PMSM = "RADIAL_FLUX_SURFACE_PMSM"
    RADIAL_FLUX_INTERIOR_PMSM = "RADIAL_FLUX_INTERIOR_PMSM"
    RADIAL_FLUX_BLDC = "RADIAL_FLUX_BLDC"
    INDUCTION_SQUIRREL_CAGE = "INDUCTION_SQUIRREL_CAGE"
    UNKNOWN = "UNKNOWN"


TOPOLOGY_LABELS_ZH = {
    MachineTopology.AFPM_DUAL_ROTOR_SINGLE_STATOR: "轴向磁通 双转子单定子",
    MachineTopology.AFPM_SINGLE_ROTOR_SINGLE_STATOR: "轴向磁通 单转子单定子",
    MachineTopology.RADIAL_FLUX_INSET_PMSM: "径向磁通 嵌入式永磁同步电机",
    MachineTopology.RADIAL_FLUX_SURFACE_PMSM: "径向磁通 表贴式永磁同步电机",
    MachineTopology.RADIAL_FLUX_INTERIOR_PMSM: "径向磁通 内置式永磁同步电机",
    MachineTopology.RADIAL_FLUX_BLDC: "径向磁通 无刷直流电机",
    MachineTopology.INDUCTION_SQUIRREL_CAGE: "鼠笼式感应电机",
    MachineTopology.UNKNOWN: "拓扑未知",
}

#: The topologies ``motor_core.calculations`` is actually about. Everything else
#: must be refused rather than approximated.
AFPM_KERNEL_TOPOLOGIES = frozenset(
    {
        MachineTopology.AFPM_DUAL_ROTOR_SINGLE_STATOR,
        MachineTopology.AFPM_SINGLE_ROTOR_SINGLE_STATOR,
    }
)

#: The AFPM-specific input fields. Their meaning is axial; a radial machine has
#: no quantity that belongs in any of them.
AFPM_GEOMETRY_FIELDS = frozenset(
    {
        "D_out", "D_in", "g_side", "D_stator_out", "D_stator_in",
        "h_stator", "h_coil", "h_yoke", "h_mag", "w_magnet", "L_magnet",
        "alpha_p", "magnet_type", "magnetization",
    }
)


class TopologyMismatchError(TypeError):
    """A machine was offered to a model that cannot represent it.

    Deliberately a ``TypeError``: this is a category error, not a bad value.
    No amount of adjusting the numbers makes a radial machine axial.
    """


def is_afpm_modellable(topology: MachineTopology | str) -> bool:
    """Whether the production kernel can represent this topology at all."""

    return _coerce(topology) in AFPM_KERNEL_TOPOLOGIES


def require_compatible_topology(
    topology: MachineTopology | str, *, context: str = "AFPM production model"
) -> MachineTopology:
    """Return the topology, or refuse with the reason it cannot be modelled."""

    machine = _coerce(topology)
    if is_afpm_modellable(machine):
        return machine
    raise TopologyMismatchError(
        f"{context} models axial-flux machines only; "
        f"{machine.value} ({TOPOLOGY_LABELS_ZH.get(machine, machine.value)}) "
        "cannot be represented by it. Its geometry has no meaning in the AFPM "
        "fields (D_out/D_in describe an annulus, g_side is a per-side axial gap), "
        "so a project built this way would produce plausible numbers that mean "
        "nothing. Import this machine's measurements as public reference "
        "evidence instead; do not construct a project from it."
    )


def reject_afpm_project_construction(
    topology: MachineTopology | str, parameters=None, *, context: str = "project construction"
) -> None:
    """Refuse to build an AFPM project for a machine that is not axial-flux.

    Called at the boundary of anything that would turn imported geometry into a
    production project. Also refuses when a caller has already begun packing
    radial dimensions into AFPM fields, which is the failure this exists to stop.
    """

    machine = _coerce(topology)
    if not is_afpm_modellable(machine):
        raise TopologyMismatchError(
            f"refusing {context} for {machine.value}: "
            + require_afpm_refusal_reason(machine)
        )
    if parameters:
        used = sorted(AFPM_GEOMETRY_FIELDS & set(parameters))
        if used and machine is MachineTopology.UNKNOWN:
            raise TopologyMismatchError(
                f"refusing {context}: AFPM geometry fields {used} were supplied "
                "for a machine of unknown topology"
            )


def require_afpm_refusal_reason(topology: MachineTopology | str) -> str:
    """The refusal text. Says the same thing as :func:`require_compatible_topology`.

    Both refusal paths are reached by users, so they state the same fact in the
    same words rather than each inventing its own phrasing.
    """

    machine = _coerce(topology)
    return (
        f"the AFPM production model is axial-flux only and cannot represent "
        f"{machine.value}. "
        f"{TOPOLOGY_LABELS_ZH.get(machine, machine.value)} 不是轴向磁通结构，"
        "AFPM 生产内核无法表示它。其几何量在 AFPM 输入字段中没有对应含义，"
        "强行映射只会得到看似合理、实则无意义的结果。"
    )


def _coerce(topology: MachineTopology | str) -> MachineTopology:
    if isinstance(topology, MachineTopology):
        return topology
    try:
        return MachineTopology(str(topology).strip().upper())
    except ValueError:
        return MachineTopology.UNKNOWN


#: What a successful public-reference ingestion is entitled to claim, and what it
#: is not. Kept as constants so the GUI, the report and the tests use one string.
PIPELINE_VALIDATED = "PUBLIC_REFERENCE_PIPELINE_VALIDATED"
AFPM_NOT_VALIDATED = "CURRENT_AFPM_NOT_EXPERIMENTALLY_VALIDATED"

PIPELINE_VALIDATED_NOTE_ZH = (
    "成功导入并复现公开实测数据，验证的是**本软件的数据处理链**："
    "解析、单位、语义、波形处理与证据分级。"
    "它**不验证**当前 AFPM 设计本身——那台机器与本项目的设计是不同的机器。"
)
