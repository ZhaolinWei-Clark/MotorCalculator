"""Phase 11A: canonical measurement columns, and what a header is allowed to mean.

The dangerous column in a motor test file is the one labelled ``Voltage``.

On a back-EMF bench that header might be line-to-line RMS off a scope, phase RMS
off a meter, or phase peak from a cursor measurement. The three differ by
sqrt(3) and sqrt(2) -- 73 % between the extremes -- and all three are plausible
for the same machine at the same speed. Guessing produces a Ke that is wrong by
a factor nobody can see, and the comparison against the analytical model will
quietly "validate" or "refute" the wrong thing.

So ambiguous headers are **refused**, by name, with the alternatives listed. The
recognised aliases here are only those that state their basis unambiguously.
``Current`` gets the same treatment for the same reason: RMS, peak and DC are
not interchangeable.

Explicit mapping always wins. A user who knows their file can say
``{"Voltage": "line_voltage_rms_v"}`` and the importer will believe them,
because at that point somebody with knowledge has made the statement rather than
a heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .schema import TestType

COLUMNS_SCHEMA_VERSION = "phase11a.experiment.columns.v1"


class VoltageBasis(str, Enum):
    """Which voltage a number is. Never inferred from magnitude."""

    LINE_RMS = "LINE_RMS"
    PHASE_RMS = "PHASE_RMS"
    PHASE_PEAK = "PHASE_PEAK"


class CurrentBasis(str, Enum):
    PHASE_RMS = "PHASE_RMS"
    PHASE_PEAK = "PHASE_PEAK"
    DC = "DC"


@dataclass(frozen=True)
class CanonicalColumn:
    """One field the analysis layer knows how to read."""

    name: str
    canonical_unit: str
    label_zh: str
    #: Header spellings that unambiguously mean this column. Case- and
    #: separator-insensitive; a unit suffix in the header is stripped first.
    aliases: tuple[str, ...] = ()
    voltage_basis: VoltageBasis | None = None
    current_basis: CurrentBasis | None = None
    #: True when the number is a measurement; False when the file supplies a
    #: value the analysis could also derive. Derived-vs-measured is kept so a
    #: supplied power is never overwritten by a computed one.
    is_measurement: bool = True


CANONICAL_COLUMNS: tuple[CanonicalColumn, ...] = (
    CanonicalColumn(
        "speed_rpm", "rpm", "机械转速",
        ("speed rpm", "motor speed rpm", "rotational speed", "n", "speed", "rpm",
         "motor speed", "shaft speed", "转速"),
    ),
    CanonicalColumn(
        "line_voltage_rms_v", "V", "线电压有效值",
        ("line voltage rms v", "line to line voltage rms", "line line voltage rms",
         "vll rms", "v line rms", "line voltage rms", "ull", "线电压有效值"),
        voltage_basis=VoltageBasis.LINE_RMS,
    ),
    CanonicalColumn(
        "phase_voltage_rms_v", "V", "相电压有效值",
        ("phase voltage rms v", "phase voltage rms", "vph rms", "v phase rms",
         "相电压有效值"),
        voltage_basis=VoltageBasis.PHASE_RMS,
    ),
    CanonicalColumn(
        "phase_voltage_peak_v", "V", "相电压峰值",
        ("phase voltage peak v", "phase voltage peak", "vph peak", "v phase peak",
         "相电压峰值"),
        voltage_basis=VoltageBasis.PHASE_PEAK,
    ),
    CanonicalColumn(
        "line_voltage_peak_v", "V", "线电压峰值",
        ("line voltage peak v", "line voltage peak", "vll peak", "线电压峰值"),
        voltage_basis=VoltageBasis.PHASE_PEAK,
    ),
    CanonicalColumn(
        "phase_current_rms_a", "A", "相电流有效值",
        ("phase current rms a", "phase current rms", "iph rms", "i phase rms",
         "相电流有效值"),
        current_basis=CurrentBasis.PHASE_RMS,
    ),
    CanonicalColumn(
        "phase_current_peak_a", "A", "相电流峰值",
        ("phase current peak a", "phase current peak", "iph peak", "相电流峰值"),
        current_basis=CurrentBasis.PHASE_PEAK,
    ),
    CanonicalColumn("id_a", "A", "d 轴电流", ("id a", "id", "i d", "d axis current")),
    CanonicalColumn("iq_a", "A", "q 轴电流", ("iq a", "iq", "i q", "q axis current")),
    CanonicalColumn("torque_nm", "Nm", "转矩", ("torque nm", "torque", "t", "shaft torque", "转矩")),
    CanonicalColumn("temperature_c", "degC", "温度",
                    ("temperature c", "temperature", "temp", "winding temperature", "温度")),
    CanonicalColumn(
        "dc_bus_voltage_v", "V", "直流母线电压",
        ("dc bus voltage v", "dc bus voltage", "vdc", "v dc", "bus voltage", "母线电压"),
    ),
    CanonicalColumn(
        "dc_bus_current_a", "A", "直流母线电流",
        ("dc bus current a", "dc bus current", "idc", "i dc", "bus current", "母线电流"),
        current_basis=CurrentBasis.DC,
    ),
    CanonicalColumn(
        "input_power_w", "W", "输入功率（实测）",
        ("input power w", "input power", "p in", "pin", "electrical input power"),
    ),
    CanonicalColumn(
        "output_power_w", "W", "输出功率（实测）",
        ("output power w", "output power", "p out", "pout", "shaft power", "mechanical power"),
    ),
    CanonicalColumn(
        "efficiency", "1", "效率（实测）",
        ("efficiency", "eta", "效率"),
    ),
    CanonicalColumn(
        "measured_resistance_ohm", "Ohm", "实测电阻",
        ("measured resistance ohm", "resistance", "r measured", "r", "电阻"),
    ),
    CanonicalColumn(
        "applied_voltage_v", "V", "施加电压（直流）",
        ("applied voltage v", "applied voltage", "v applied", "dc voltage applied"),
    ),
    CanonicalColumn(
        "applied_current_a", "A", "施加电流（直流）",
        ("applied current a", "applied current", "i applied", "dc current applied"),
        current_basis=CurrentBasis.DC,
    ),
)

CANONICAL_BY_NAME = {column.name: column for column in CANONICAL_COLUMNS}


#: Headers that name a quantity without stating its basis. Refused rather than
#: guessed, with the admissible alternatives in the message.
AMBIGUOUS_HEADERS: dict[str, tuple[str, ...]] = {
    "voltage": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "v": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "volt": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "emf": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "back emf": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "bemf": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "u": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "电压": ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    "current": ("phase_current_rms_a", "phase_current_peak_a", "dc_bus_current_a"),
    "i": ("phase_current_rms_a", "phase_current_peak_a", "dc_bus_current_a"),
    "amps": ("phase_current_rms_a", "phase_current_peak_a", "dc_bus_current_a"),
    "电流": ("phase_current_rms_a", "phase_current_peak_a", "dc_bus_current_a"),
    "power": ("input_power_w", "output_power_w"),
    "p": ("input_power_w", "output_power_w"),
    "功率": ("input_power_w", "output_power_w"),
}


class AmbiguousColumnError(ValueError):
    """A header names a quantity without saying which basis it is in."""

    def __init__(self, header: str, candidates: tuple[str, ...]) -> None:
        self.header = header
        self.candidates = candidates
        super().__init__(
            f"column {header!r} does not state its measurement basis. "
            f"Map it explicitly to one of: {', '.join(candidates)}. "
            "This is refused rather than guessed because the candidates differ "
            "by factors of sqrt(2) and sqrt(3), which would silently change the "
            "result instead of failing."
        )


class UnknownColumnError(ValueError):
    """A header matches no canonical field and no explicit mapping."""


def normalize_header(header: str) -> str:
    """Lower-case, strip a parenthesised unit, and collapse separators."""

    text = str(header).strip()
    if "(" in text and text.endswith(")"):
        text = text[: text.index("(")]
    if "[" in text and text.endswith("]"):
        text = text[: text.index("[")]
    text = text.replace("_", " ").replace("-", " ").replace("/", " ").replace(".", " ")
    return " ".join(text.lower().split())


def unit_suffix(header: str) -> str | None:
    """The unit written in the header, if any: ``Torque (mNm)`` -> ``mNm``."""

    text = str(header).strip()
    for opener, closer in (("(", ")"), ("[", "]")):
        if opener in text and text.endswith(closer):
            candidate = text[text.index(opener) + 1 : -1].strip()
            if candidate:
                return candidate
    return None


_ALIAS_INDEX: dict[str, CanonicalColumn] = {}
for _column in CANONICAL_COLUMNS:
    _ALIAS_INDEX[normalize_header(_column.name)] = _column
    for _alias in _column.aliases:
        _ALIAS_INDEX.setdefault(normalize_header(_alias), _column)


def resolve_header(header: str) -> CanonicalColumn:
    """The canonical column a header deterministically means.

    Raises rather than guessing. There is no fuzzy matching and no scoring.
    """

    key = normalize_header(header)
    if key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]
    if key in AMBIGUOUS_HEADERS:
        raise AmbiguousColumnError(header, AMBIGUOUS_HEADERS[key])
    raise UnknownColumnError(
        f"column {header!r} is not recognised. Map it explicitly, or rename it "
        f"to one of: {', '.join(sorted(CANONICAL_BY_NAME))}"
    )


#: Columns each implemented test type needs, and the ones it can use.
REQUIRED_COLUMNS: dict[TestType, tuple[tuple[str, ...], ...]] = {
    # A tuple of alternatives: at least one member of each group must be present.
    TestType.NO_LOAD_BACK_EMF: (
        ("speed_rpm",),
        ("line_voltage_rms_v", "phase_voltage_rms_v", "phase_voltage_peak_v"),
    ),
    TestType.PHASE_RESISTANCE: (
        ("measured_resistance_ohm", "applied_voltage_v"),
    ),
    TestType.TORQUE_CURRENT: (
        ("torque_nm",),
        ("phase_current_rms_a", "iq_a"),
    ),
    TestType.EFFICIENCY: (
        ("speed_rpm",),
        ("torque_nm", "output_power_w"),
        ("dc_bus_voltage_v", "input_power_w"),
    ),
}


def missing_required_columns(
    test_type: TestType, present: frozenset[str] | set[str]
) -> tuple[tuple[str, ...], ...]:
    """Groups of which no member is present. Empty means the file is usable."""

    groups = REQUIRED_COLUMNS.get(TestType(test_type), ())
    return tuple(group for group in groups if not set(group) & set(present))
