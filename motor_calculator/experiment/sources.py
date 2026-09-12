"""Phase 11A: what kind of thing a dataset actually is.

This project's whole validation posture rests on one distinction: a number that
was *measured on hardware* and a number that came out of a *model*. Phases 10A
through 10H spent most of their effort keeping FEA from being read as
measurement. Importing outside data reopens the same wound in three new ways, so
the classes are named here and the rules are enforced structurally rather than
by convention.

The four classes
----------------
``USER_EXPERIMENT``
    A measurement the user or the user's lab performed. This is the only class
    that can say anything about *this* machine from physical evidence.

``PUBLIC_REFERENCE_EXPERIMENT``
    A physical measurement published by somebody else, on somebody else's
    hardware. It is genuinely experimental, and it is genuinely not about the
    design in the project unless the machines match -- which is a separate
    question, answered in :mod:`.compatibility`.

``SIMULATED_REFERENCE``
    Data a model produced. Another party's FEA, a published simulation, or this
    project's own synthetic test fixtures. Never experimental, however
    measurement-shaped the CSV is.

``METHODOLOGY_ONLY``
    A source that describes how a test was performed but carries no usable
    numbers. Worth importing for its procedure and citation; it can never
    support a comparison, because there is nothing to compare.

What is enforced here
---------------------
* :data:`EXPERIMENTAL_SOURCE_TYPES` is the complete set of classes that may be
  called experimental. ``SIMULATED_REFERENCE`` is not in it and there is no code
  path that adds it.
* :data:`OWN_MACHINE_SOURCE_TYPES` is narrower still: only a user experiment can
  speak about the machine in the project without a compatibility argument.
* Reclassification is one-directional and explicit. :func:`may_reclassify`
  refuses every promotion toward "more experimental", so an import, an edit or a
  round-trip through a file cannot launder a simulation into a measurement.
"""

from __future__ import annotations

from enum import Enum

EXPERIMENT_SOURCE_SCHEMA_VERSION = "phase11a.experiment.sources.v1"


class DatasetSourceType(str, Enum):
    """Where a dataset's numbers came from."""

    USER_EXPERIMENT = "USER_EXPERIMENT"
    PUBLIC_REFERENCE_EXPERIMENT = "PUBLIC_REFERENCE_EXPERIMENT"
    SIMULATED_REFERENCE = "SIMULATED_REFERENCE"
    METHODOLOGY_ONLY = "METHODOLOGY_ONLY"


#: The classes that represent physical measurement. A comparison may be labelled
#: experimental if and only if its dataset's source type is in this set.
EXPERIMENTAL_SOURCE_TYPES = frozenset(
    {
        DatasetSourceType.USER_EXPERIMENT,
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
    }
)

#: The classes that may speak about the project's own machine without a
#: machine-compatibility argument. Published measurements are measurements of
#: *another* machine until proven otherwise.
OWN_MACHINE_SOURCE_TYPES = frozenset({DatasetSourceType.USER_EXPERIMENT})

#: Classes that carry usable numeric samples at all.
DATA_BEARING_SOURCE_TYPES = frozenset(
    {
        DatasetSourceType.USER_EXPERIMENT,
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
        DatasetSourceType.SIMULATED_REFERENCE,
    }
)

SOURCE_TYPE_LABELS_ZH = {
    DatasetSourceType.USER_EXPERIMENT: "用户实验测量",
    DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT: "公开文献实测数据（他人机器）",
    DatasetSourceType.SIMULATED_REFERENCE: "仿真参考数据（非实验）",
    DatasetSourceType.METHODOLOGY_ONLY: "仅方法学描述（无可用测量值）",
}

SOURCE_TYPE_CAVEATS_ZH = {
    DatasetSourceType.USER_EXPERIMENT: (
        "由用户/用户实验室在实物上测得。是本项目唯一可以在机器一致时直接支撑"
        "「已实验验证」结论的证据类别。"
    ),
    DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT: (
        "是真实的物理测量，但测的是**别人的电机**。除非机器身份可比，"
        "它只能验证建模方法与数据流程，不能验证当前设计。"
    ),
    DatasetSourceType.SIMULATED_REFERENCE: (
        "由模型产生，**不是实验数据**。无论其格式与实测数据多么相似，"
        "都不会被计入实验证据。"
    ),
    DatasetSourceType.METHODOLOGY_ONLY: (
        "只描述试验方法，不含可用测量值。可用于记录试验规程与引用，"
        "但不能参与任何数值比较。"
    ),
}


def is_experimental(source_type: DatasetSourceType | str) -> bool:
    """Whether this class represents physical measurement.

    The single predicate every caller must use. Nothing else in the codebase is
    permitted to decide this question with its own ``==`` comparison.
    """

    return _coerce(source_type) in EXPERIMENTAL_SOURCE_TYPES


def is_own_machine_capable(source_type: DatasetSourceType | str) -> bool:
    """Whether this class can speak about the project's machine unaided."""

    return _coerce(source_type) in OWN_MACHINE_SOURCE_TYPES


def carries_measurements(source_type: DatasetSourceType | str) -> bool:
    """Whether a dataset of this class is expected to contain samples."""

    return _coerce(source_type) in DATA_BEARING_SOURCE_TYPES


#: Reclassifications that are allowed, as ``(from, to)``. Every entry moves
#: *away* from an experimental claim or toward a weaker one. There is no entry
#: that turns a simulation into a measurement, and adding one would be the
#: single most damaging change anybody could make to this project.
ALLOWED_RECLASSIFICATIONS = frozenset(
    {
        # A source thought to carry data turns out to describe only a procedure.
        (DatasetSourceType.USER_EXPERIMENT, DatasetSourceType.METHODOLOGY_ONLY),
        (DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, DatasetSourceType.METHODOLOGY_ONLY),
        (DatasetSourceType.SIMULATED_REFERENCE, DatasetSourceType.METHODOLOGY_ONLY),
        # A paper's "measured" table turns out to be its simulation.
        (DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, DatasetSourceType.SIMULATED_REFERENCE),
        (DatasetSourceType.USER_EXPERIMENT, DatasetSourceType.SIMULATED_REFERENCE),
        # A user's own measurement re-filed as somebody else's publication.
        (DatasetSourceType.USER_EXPERIMENT, DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT),
    }
)


class ReclassificationError(ValueError):
    """Raised when a dataset is asked to become a stronger kind of evidence."""


def may_reclassify(
    current: DatasetSourceType | str, proposed: DatasetSourceType | str
) -> bool:
    """Whether ``current`` may be relabelled ``proposed``."""

    old, new = _coerce(current), _coerce(proposed)
    return old is new or (old, new) in ALLOWED_RECLASSIFICATIONS


def require_reclassifiable(
    current: DatasetSourceType | str, proposed: DatasetSourceType | str
) -> DatasetSourceType:
    """Return ``proposed``, or refuse the relabelling with the reason."""

    old, new = _coerce(current), _coerce(proposed)
    if may_reclassify(old, new):
        return new
    raise ReclassificationError(
        f"a {old.value} dataset may not be relabelled {new.value}: this would "
        "present non-experimental data, or another machine's data, as a "
        "measurement of this design. Re-import the source under the correct "
        "class instead."
    )


def _coerce(value: DatasetSourceType | str) -> DatasetSourceType:
    if isinstance(value, DatasetSourceType):
        return value
    return DatasetSourceType(str(value).strip().upper())
