"""Phase 11B: where a published scalar actually came from.

Phase 11A separated *datasets* by source class. That is not fine-grained enough
for a published parameter table, because one table routinely mixes origins
without saying so in the table itself.

The CREATOR PMSM equivalent-circuit table is the exact case. It is presented as
"electrical parameters derived from diverse experimental tests", and it lists
Rs, Ld, Lq, lambda_pm and E0 side by side. But the source's own README says the
inductances come from JMAG finite-element analysis, not from measurement. A
reader who takes the table at face value will cite an FEA result as a
measurement -- and will do so while reading a document that is, in every other
respect, careful and honest.

So every scalar carried into this project states its own origin, the origin is
required at construction, and there is no default. ``UNKNOWN`` is a real answer
and the only honest one where the source does not say.

The ordering that matters
-------------------------
:data:`EXPERIMENTAL_ORIGINS` is the set that may be described to a user as
measurement. ``FEA_DERIVED`` is not in it, ``CALCULATED`` is not in it, and
``UNKNOWN`` is not in it. :func:`is_measurement` is the only predicate allowed
to answer the question.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

PARAMETER_ORIGIN_SCHEMA_VERSION = "phase11b.parameter_origin.v1"


class ParameterOrigin(str, Enum):
    """How a published scalar was obtained."""

    #: Read off an instrument measuring the physical machine.
    DIRECT_MEASUREMENT = "DIRECT_MEASUREMENT"
    #: Computed from measured data by a stated, reproducible operation --
    #: an FFT fundamental, a slope, a difference of two measurements.
    MEASUREMENT_DERIVED = "MEASUREMENT_DERIVED"
    #: Produced by a field solver. Numerical evidence, never measurement.
    FEA_DERIVED = "FEA_DERIVED"
    #: A number the designer chose; the machine was built to it.
    DESIGN_INPUT = "DESIGN_INPUT"
    #: Computed from design inputs by a formula, with no measurement involved.
    CALCULATED = "CALCULATED"
    #: The source does not say. Not a synonym for "probably measured".
    UNKNOWN = "UNKNOWN"


ORIGIN_LABELS_ZH = {
    ParameterOrigin.DIRECT_MEASUREMENT: "实测",
    ParameterOrigin.MEASUREMENT_DERIVED: "由实测推导",
    ParameterOrigin.FEA_DERIVED: "有限元计算",
    ParameterOrigin.DESIGN_INPUT: "设计输入",
    ParameterOrigin.CALCULATED: "公式计算",
    ParameterOrigin.UNKNOWN: "来源未知",
}

ORIGIN_CAVEATS_ZH = {
    ParameterOrigin.DIRECT_MEASUREMENT: "由仪器在实物上直接测得。",
    ParameterOrigin.MEASUREMENT_DERIVED: (
        "由实测数据经明确、可复现的运算得到（如 FFT 基波、斜率、差值）。"
        "仍属实验证据，但其数值取决于所用的处理方法。"
    ),
    ParameterOrigin.FEA_DERIVED: (
        "由有限元求解器计算得到，**不是实测值**。"
        "无论它出现在哪张「实验参数」表里，都不能当作测量结果引用。"
    ),
    ParameterOrigin.DESIGN_INPUT: "设计阶段选定的数值，机器按此制造。",
    ParameterOrigin.CALCULATED: "由设计参数经公式算出，未涉及任何测量。",
    ParameterOrigin.UNKNOWN: (
        "来源文献未说明该值如何得到。**不得假定为实测**；"
        "在来源澄清之前，它不能支撑任何实验性结论。"
    ),
}

#: Origins that may be described to a user as measurement. FEA_DERIVED,
#: CALCULATED, DESIGN_INPUT and UNKNOWN are deliberately absent.
EXPERIMENTAL_ORIGINS = frozenset(
    {ParameterOrigin.DIRECT_MEASUREMENT, ParameterOrigin.MEASUREMENT_DERIVED}
)

#: Origins that are model output rather than observation.
MODEL_ORIGINS = frozenset(
    {ParameterOrigin.FEA_DERIVED, ParameterOrigin.CALCULATED}
)


def is_measurement(origin: ParameterOrigin | str) -> bool:
    """Whether a scalar of this origin may be called a measurement.

    The single predicate. Nothing else may answer this with its own comparison.
    """

    return _coerce(origin) in EXPERIMENTAL_ORIGINS


def is_model_output(origin: ParameterOrigin | str) -> bool:
    return _coerce(origin) in MODEL_ORIGINS


def _coerce(origin: ParameterOrigin | str) -> ParameterOrigin:
    if isinstance(origin, ParameterOrigin):
        return origin
    return ParameterOrigin(str(origin).strip().upper())


#: Marker for a parameter whose stated value cannot be reconciled with the other
#: values the same source publishes. Not an error in this project.
PROVENANCE_UNRESOLVED = "PARAMETER_PROVENANCE_UNRESOLVED"


@dataclass(frozen=True)
class PublicParameter:
    """One scalar taken from a published source, with its origin attached.

    ``origin`` has no default. A parameter whose origin nobody recorded is a
    parameter nobody can safely cite, so the type refuses to be constructed
    without one.
    """

    name: str
    label_zh: str
    value: float | None
    unit: str
    origin: ParameterOrigin
    #: Exactly where in the source this came from, so a reader can check it.
    source_note: str = ""
    #: Set when the source's own numbers disagree with each other.
    consistency_flag: str | None = None
    consistency_note_zh: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", _coerce(self.origin))
        if not str(self.name).strip():
            raise ValueError("a published parameter needs a name")

    @property
    def is_measurement(self) -> bool:
        return is_measurement(self.origin)

    @property
    def origin_label_zh(self) -> str:
        return ORIGIN_LABELS_ZH[self.origin]

    @property
    def caveat_zh(self) -> str:
        return ORIGIN_CAVEATS_ZH[self.origin]

    @property
    def is_unresolved(self) -> bool:
        return self.consistency_flag == PROVENANCE_UNRESOLVED


@dataclass(frozen=True)
class ParameterSet:
    """The scalars one published source provides, each with its own origin."""

    schema_version: str
    source_id: str
    parameters: tuple[PublicParameter, ...]

    def get(self, name: str) -> PublicParameter | None:
        for parameter in self.parameters:
            if parameter.name == name:
                return parameter
        return None

    @property
    def measured(self) -> tuple[PublicParameter, ...]:
        return tuple(p for p in self.parameters if p.is_measurement)

    @property
    def model_derived(self) -> tuple[PublicParameter, ...]:
        return tuple(p for p in self.parameters if is_model_output(p.origin))

    @property
    def unknown_origin(self) -> tuple[PublicParameter, ...]:
        return tuple(p for p in self.parameters if p.origin is ParameterOrigin.UNKNOWN)

    @property
    def unresolved(self) -> tuple[PublicParameter, ...]:
        return tuple(p for p in self.parameters if p.is_unresolved)

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "parameters": [
                {
                    "name": p.name,
                    "label_zh": p.label_zh,
                    "value": p.value,
                    "unit": p.unit,
                    "origin": p.origin.value,
                    "origin_label_zh": p.origin_label_zh,
                    "is_measurement": p.is_measurement,
                    "source_note": p.source_note,
                    "consistency_flag": p.consistency_flag,
                    "consistency_note_zh": p.consistency_note_zh,
                }
                for p in self.parameters
            ],
        }


def render_parameter_table_zh(parameter_set: ParameterSet) -> str:
    """The table, with the origin beside every number rather than in a footnote."""

    lines = [
        f"来源：{parameter_set.source_id}",
        "",
        f"{'参数':<22}{'数值':>14}  {'单位':<8}{'来源':<10}",
        "-" * 66,
    ]
    for parameter in parameter_set.parameters:
        value = "不可用" if parameter.value is None else f"{parameter.value:.6g}"
        lines.append(
            f"{parameter.label_zh:<22}{value:>14}  {parameter.unit:<8}"
            f"{parameter.origin_label_zh:<10}"
        )
        if parameter.consistency_flag:
            lines.append(f"    ⚠ {parameter.consistency_flag}: {parameter.consistency_note_zh}")
    lines.extend(["", "来源说明："])
    seen: set[ParameterOrigin] = set()
    for parameter in parameter_set.parameters:
        if parameter.origin in seen:
            continue
        seen.add(parameter.origin)
        lines.append(f"  · {parameter.origin_label_zh}：{parameter.caveat_zh}")
    return "\n".join(lines)
