"""Phase 11A: is this dataset even about the machine in the project?

This is the question that decides whether an agreeing number means anything.

A published back-EMF curve for a 10-pole, 12-slot hub motor can match this
project's analytical Ke to 1 % and prove nothing whatsoever about this project's
design. If the software shows "experimental agreement: 1.0 %" next to that, it
has told the user something false, and it has done so using entirely real,
entirely honest measurements. That is a more dangerous failure than a wrong
number, because nothing about it looks wrong.

So compatibility is answered before any comparison is labelled, and the four
answers are kept distinct:

``SAME_MACHINE``
    Every identity field that both sides declare agrees. A measurement of this
    design.

``COMPATIBLE_REFERENCE``
    The topology and the electromagnetically decisive counts agree, but
    something meaningful differs -- turns, rated point, a geometry note. Useful
    for testing whether the *modelling approach* transfers. Not a validation of
    this design.

``DIFFERENT_MACHINE``
    At least one decisive field conflicts. The data is real and may be perfectly
    good; it is about something else.

``INSUFFICIENT_METADATA``
    Not enough is declared to tell. Deliberately *not* optimistic: an unknown
    machine is not assumed to be this one.

Only ``SAME_MACHINE`` may support a validation claim about the current design,
and :func:`may_validate_current_design` is the single place that decides it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .schema import UNKNOWN, MachineIdentity
from .sources import DatasetSourceType, is_experimental

COMPATIBILITY_SCHEMA_VERSION = "phase11a.experiment.compatibility.v1"


class MachineCompatibility(str, Enum):
    SAME_MACHINE = "SAME_MACHINE"
    COMPATIBLE_REFERENCE = "COMPATIBLE_REFERENCE"
    DIFFERENT_MACHINE = "DIFFERENT_MACHINE"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


COMPATIBILITY_LABELS_ZH = {
    MachineCompatibility.SAME_MACHINE: "同一台机器",
    MachineCompatibility.COMPATIBLE_REFERENCE: "可比参考机器（非同一台）",
    MachineCompatibility.DIFFERENT_MACHINE: "不同的机器",
    MachineCompatibility.INSUFFICIENT_METADATA: "元数据不足，无法判断",
}

#: Fields whose disagreement makes two machines electromagnetically different.
#: A conflict in any of these is decisive on its own.
DECISIVE_FIELDS: tuple[tuple[str, str], ...] = (
    ("pole_count", "极数"),
    ("slot_count", "槽数"),
    ("phases", "相数"),
    ("topology", "拓扑"),
    ("connection", "接法"),
)

#: Fields that distinguish two builds of the same electromagnetic design.
#: Disagreement here demotes to COMPATIBLE_REFERENCE rather than to
#: DIFFERENT_MACHINE.
DISTINGUISHING_FIELDS: tuple[tuple[str, str], ...] = (
    ("turns_per_phase", "每相匝数"),
    ("rated_speed_rpm", "额定转速"),
    ("rated_power_w", "额定功率"),
    ("machine_id", "机器编号"),
)

#: The minimum number of decisive fields both sides must declare before any
#: verdict other than INSUFFICIENT_METADATA is possible.
MINIMUM_COMPARED_DECISIVE_FIELDS = 2


@dataclass(frozen=True)
class FieldComparison:
    field: str
    label_zh: str
    dataset_value: Any
    project_value: Any
    #: "AGREE", "CONFLICT", "DATASET_UNKNOWN", "PROJECT_UNKNOWN", "BOTH_UNKNOWN"
    verdict: str

    @property
    def compared(self) -> bool:
        return self.verdict in {"AGREE", "CONFLICT"}


@dataclass(frozen=True)
class CompatibilityAssessment:
    """The verdict, and every field that produced it."""

    schema_version: str
    status: MachineCompatibility
    status_label_zh: str
    decisive: tuple[FieldComparison, ...]
    distinguishing: tuple[FieldComparison, ...]
    reason_zh: str
    #: What this dataset may be used for, stated rather than implied.
    permitted_use_zh: str

    @property
    def conflicts(self) -> tuple[FieldComparison, ...]:
        return tuple(
            item
            for item in (*self.decisive, *self.distinguishing)
            if item.verdict == "CONFLICT"
        )

    @property
    def compared_decisive_count(self) -> int:
        return sum(1 for item in self.decisive if item.compared)


def _known(value: Any) -> bool:
    return value is not None and value != UNKNOWN and str(value).strip() != ""


def _equal(left: Any, right: Any) -> bool:
    """Compare numerically when both look numeric, textually otherwise."""

    try:
        return abs(float(left) - float(right)) <= 1e-9 * max(1.0, abs(float(right)))
    except (TypeError, ValueError):
        return str(left).strip().casefold() == str(right).strip().casefold()


def _compare(field: str, label: str, dataset_value: Any, project_value: Any) -> FieldComparison:
    dataset_known, project_known = _known(dataset_value), _known(project_value)
    if not dataset_known and not project_known:
        verdict = "BOTH_UNKNOWN"
    elif not dataset_known:
        verdict = "DATASET_UNKNOWN"
    elif not project_known:
        verdict = "PROJECT_UNKNOWN"
    else:
        verdict = "AGREE" if _equal(dataset_value, project_value) else "CONFLICT"
    return FieldComparison(field, label, dataset_value, project_value, verdict)


def project_machine_identity(
    parameters: Mapping[str, Any],
    *,
    topology: str = "AFPM_DUAL_ROTOR_SINGLE_STATOR",
    connection: Any = UNKNOWN,
    machine_id: Any = UNKNOWN,
) -> MachineIdentity:
    """The current design's identity, from its own parameters.

    Only what the parameters actually state. Nothing is inferred, and anything
    absent stays ``UNKNOWN`` so it compares as unknown rather than as a match.
    """

    def _get(name: str) -> Any:
        value = parameters.get(name)
        return UNKNOWN if value is None else value

    pole_pairs = parameters.get("p")
    return MachineIdentity(
        description="当前项目设计",
        machine_id=machine_id,
        topology=topology,
        pole_count=UNKNOWN if pole_pairs is None else int(pole_pairs) * 2,
        slot_count=_get("slots"),
        phases=3,
        connection=connection,
        turns_per_phase=_get("N_ph_turns"),
        rated_speed_rpm=_get("n_rated"),
        rated_power_w=_get("P_rated"),
    )


def assess_compatibility(
    dataset_machine: MachineIdentity, project_machine: MachineIdentity
) -> CompatibilityAssessment:
    """Decide what an imported dataset is allowed to say about this design."""

    decisive = tuple(
        _compare(
            name, label,
            getattr(dataset_machine, name), getattr(project_machine, name),
        )
        for name, label in DECISIVE_FIELDS
    )
    distinguishing = tuple(
        _compare(
            name, label,
            getattr(dataset_machine, name), getattr(project_machine, name),
        )
        for name, label in DISTINGUISHING_FIELDS
    )

    decisive_conflicts = [item for item in decisive if item.verdict == "CONFLICT"]
    distinguishing_conflicts = [item for item in distinguishing if item.verdict == "CONFLICT"]
    compared_decisive = sum(1 for item in decisive if item.compared)

    if decisive_conflicts:
        status = MachineCompatibility.DIFFERENT_MACHINE
        reason = "以下决定性参数不一致：" + "、".join(
            f"{item.label_zh}（数据 {item.dataset_value} vs 项目 {item.project_value}）"
            for item in decisive_conflicts
        )
    elif compared_decisive < MINIMUM_COMPARED_DECISIVE_FIELDS:
        status = MachineCompatibility.INSUFFICIENT_METADATA
        reason = (
            f"只有 {compared_decisive} 项决定性参数能够两边对比"
            f"（至少需要 {MINIMUM_COMPARED_DECISIVE_FIELDS} 项）。"
            "元数据不足时**不假定**是同一台机器。"
        )
    elif distinguishing_conflicts:
        status = MachineCompatibility.COMPATIBLE_REFERENCE
        reason = "决定性参数一致，但以下参数不同：" + "、".join(
            f"{item.label_zh}（数据 {item.dataset_value} vs 项目 {item.project_value}）"
            for item in distinguishing_conflicts
        )
    else:
        status = MachineCompatibility.SAME_MACHINE
        reason = (
            f"两边共同声明的 {compared_decisive} 项决定性参数全部一致，"
            "且没有区分性参数冲突。"
        )

    permitted = {
        MachineCompatibility.SAME_MACHINE: (
            "可用于验证当前设计（仍需数据源本身为实验测量）。"
        ),
        MachineCompatibility.COMPATIBLE_REFERENCE: (
            "可用于检验建模方法与数据流程是否可迁移，"
            "**不能**用于声称当前设计已被验证。"
        ),
        MachineCompatibility.DIFFERENT_MACHINE: (
            "只能用于测试数据管线与方法学，**不能**验证当前设计的任何量。"
        ),
        MachineCompatibility.INSUFFICIENT_METADATA: (
            "在补齐机器识别信息之前，不能用于任何关于当前设计的结论。"
        ),
    }[status]

    return CompatibilityAssessment(
        schema_version=COMPATIBILITY_SCHEMA_VERSION,
        status=status,
        status_label_zh=COMPATIBILITY_LABELS_ZH[status],
        decisive=decisive,
        distinguishing=distinguishing,
        reason_zh=reason,
        permitted_use_zh=permitted,
    )


def may_validate_current_design(
    source_type: DatasetSourceType | str, compatibility: MachineCompatibility | str
) -> bool:
    """The single gate on "this design has experimental support".

    Both conditions must hold: the numbers must be measurements, and they must
    be measurements *of this machine*. Every caller asks this function; nothing
    re-derives it.
    """

    return (
        is_experimental(source_type)
        and MachineCompatibility(compatibility) is MachineCompatibility.SAME_MACHINE
    )
