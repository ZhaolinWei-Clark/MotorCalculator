"""Phase 11A: converting measured units without destroying them.

A measurement is a number *and* the unit it was taken in. A converter that
overwrites ``1800 rpm`` with ``188.4955592153876 rad/s`` has thrown away the
fact that somebody read 1800 off a display, and there is no way back: the
rounding of the original reading is gone, and so is any chance of showing the
user their own data.

So every conversion here produces a :class:`NormalizedValue` that carries the
original number, the original unit, the canonical number, the canonical unit and
the exact factor applied. Nothing in this module mutates a value in place.

Conversions are exact ratios or documented definitions, never fits. Temperature
is the one non-multiplicative case and is handled explicitly rather than being
forced into the same shape: degrees Celsius stay Celsius, because that is what
this project's thermal inputs are in, and a silent conversion to kelvin would
break every comparison against them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

UNITS_SCHEMA_VERSION = "phase11a.experiment.units.v1"


class UnitError(ValueError):
    """An unrecognised unit, or one that does not fit the canonical quantity."""


@dataclass(frozen=True)
class NormalizedValue:
    """One measured number, in both the unit it was taken in and SI."""

    original_value: float
    original_unit: str
    value: float
    unit: str
    #: The multiplicative factor applied, when the conversion is multiplicative.
    #: ``None`` for offset conversions, which name themselves in ``provenance``.
    factor: float | None
    #: How the conversion is defined. Never "fitted" and never "estimated".
    provenance: str

    @property
    def is_identity(self) -> bool:
        return self.original_unit == self.unit


@dataclass(frozen=True)
class UnitDefinition:
    """One recognised source unit and the canonical unit it maps to."""

    symbol: str
    canonical_unit: str
    #: Applied to the source number. Kept separate from ``convert`` so a purely
    #: multiplicative conversion can report its factor.
    factor: float | None
    convert: Callable[[float], float]
    provenance: str
    aliases: tuple[str, ...] = ()


def _scale(factor: float) -> Callable[[float], float]:
    return lambda value: value * factor


_RPM_TO_RAD_PER_S = 2.0 * math.pi / 60.0

#: Every unit the importer recognises. Adding one is a deliberate act: an
#: unrecognised unit is an error, never a guess.
UNIT_DEFINITIONS: tuple[UnitDefinition, ...] = (
    # Angular speed. rpm is kept as a canonical unit of its own because the
    # project's inputs, presets and published observations are all in rpm;
    # rad/s is derived beside it, not instead of it.
    UnitDefinition("rpm", "rpm", 1.0, _scale(1.0), "IDENTITY", ("r/min", "RPM", "min^-1")),
    UnitDefinition("rad/s", "rpm", 1.0 / _RPM_TO_RAD_PER_S, _scale(1.0 / _RPM_TO_RAD_PER_S),
                   "EXACT_DEFINITION rad/s = 2*pi/60 rpm", ("rad_per_s", "rads")),
    UnitDefinition("Hz", "Hz", 1.0, _scale(1.0), "IDENTITY", ("hz",)),
    # Voltage.
    UnitDefinition("V", "V", 1.0, _scale(1.0), "IDENTITY", ("volt", "volts")),
    UnitDefinition("mV", "V", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX", ("millivolt",)),
    UnitDefinition("kV", "V", 1.0e3, _scale(1.0e3), "EXACT_SI_PREFIX", ()),
    # Current.
    UnitDefinition("A", "A", 1.0, _scale(1.0), "IDENTITY", ("amp", "amps", "ampere")),
    UnitDefinition("mA", "A", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX", ()),
    # Resistance.
    UnitDefinition("Ohm", "Ohm", 1.0, _scale(1.0), "IDENTITY", ("ohm", "ohms", "Ω", "R")),
    UnitDefinition("mOhm", "Ohm", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX",
                   ("mohm", "milliohm", "mΩ")),
    UnitDefinition("uOhm", "Ohm", 1.0e-6, _scale(1.0e-6), "EXACT_SI_PREFIX",
                   ("uohm", "µOhm", "microohm")),
    UnitDefinition("kOhm", "Ohm", 1.0e3, _scale(1.0e3), "EXACT_SI_PREFIX", ("kohm",)),
    # Torque.
    UnitDefinition("Nm", "Nm", 1.0, _scale(1.0), "IDENTITY", ("N.m", "N*m", "N-m", "newton_metre")),
    UnitDefinition("mNm", "Nm", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX",
                   ("mN.m", "mN*m", "millinewton_metre")),
    UnitDefinition("kgfcm", "Nm", 0.0980665, _scale(0.0980665),
                   "EXACT_DEFINITION 1 kgf*cm = 0.0980665 N*m (g0 = 9.80665 m/s^2)",
                   ("kgf.cm", "kgf*cm", "kgf-cm")),
    UnitDefinition("ozin", "Nm", 0.00706155183333, _scale(0.00706155183333),
                   "EXACT_DEFINITION 1 ozf*in = 0.00706155183333 N*m",
                   ("oz.in", "oz-in", "ozf.in")),
    # Power.
    UnitDefinition("W", "W", 1.0, _scale(1.0), "IDENTITY", ("watt", "watts")),
    UnitDefinition("kW", "W", 1.0e3, _scale(1.0e3), "EXACT_SI_PREFIX", ()),
    UnitDefinition("mW", "W", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX", ()),
    # Inductance, for the declared-but-unimplemented test type.
    UnitDefinition("H", "H", 1.0, _scale(1.0), "IDENTITY", ("henry",)),
    UnitDefinition("mH", "H", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX", ()),
    UnitDefinition("uH", "H", 1.0e-6, _scale(1.0e-6), "EXACT_SI_PREFIX", ("µH",)),
    # Flux linkage.
    UnitDefinition("Wb", "Wb", 1.0, _scale(1.0), "IDENTITY", ("weber",)),
    UnitDefinition("mWb", "Wb", 1.0e-3, _scale(1.0e-3), "EXACT_SI_PREFIX", ()),
    # Temperature. Celsius is canonical here because every thermal input in this
    # project is in Celsius; converting to kelvin would silently break those
    # comparisons for no benefit.
    UnitDefinition("degC", "degC", 1.0, _scale(1.0), "IDENTITY",
                   ("C", "°C", "celsius", "degc", "deg_c")),
    UnitDefinition("K", "degC", None, lambda value: value - 273.15,
                   "EXACT_DEFINITION degC = K - 273.15", ("kelvin",)),
    UnitDefinition("degF", "degC", None, lambda value: (value - 32.0) * 5.0 / 9.0,
                   "EXACT_DEFINITION degC = (degF - 32) * 5/9", ("F", "°F", "fahrenheit")),
    # Dimensionless.
    UnitDefinition("1", "1", 1.0, _scale(1.0), "IDENTITY", ("", "-", "ratio", "pu")),
    UnitDefinition("%", "1", 0.01, _scale(0.01), "EXACT_DEFINITION 1 % = 0.01",
                   ("percent", "pct")),
)


def _index() -> dict[str, UnitDefinition]:
    table: dict[str, UnitDefinition] = {}
    for definition in UNIT_DEFINITIONS:
        for symbol in (definition.symbol, *definition.aliases):
            table[symbol.strip().lower()] = definition
    return table


_UNIT_INDEX = _index()


def known_units() -> tuple[str, ...]:
    return tuple(definition.symbol for definition in UNIT_DEFINITIONS)


def lookup_unit(symbol: str) -> UnitDefinition:
    """The definition for a unit symbol, or :class:`UnitError`."""

    key = str(symbol).strip().lower()
    if key not in _UNIT_INDEX:
        raise UnitError(
            f"unrecognised unit {symbol!r}. Recognised units: "
            + ", ".join(sorted({d.symbol for d in UNIT_DEFINITIONS}))
        )
    return _UNIT_INDEX[key]


def canonical_unit_for(symbol: str) -> str:
    return lookup_unit(symbol).canonical_unit


def normalize(value: float, unit: str, *, expected_canonical: str | None = None) -> NormalizedValue:
    """Convert one measurement, keeping the original representation intact.

    ``expected_canonical`` lets a caller state the quantity it is reading, so a
    torque column labelled ``rpm`` is rejected rather than silently converted
    into a number that means nothing.
    """

    definition = lookup_unit(unit)
    if expected_canonical is not None and definition.canonical_unit != expected_canonical:
        raise UnitError(
            f"unit {unit!r} measures {definition.canonical_unit}, but this column "
            f"must be in {expected_canonical}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise UnitError(f"{value!r} is not a finite measurement")
    return NormalizedValue(
        original_value=number,
        original_unit=str(unit).strip(),
        value=definition.convert(number),
        unit=definition.canonical_unit,
        factor=definition.factor,
        provenance=definition.provenance,
    )


def rpm_to_rad_per_s(rpm: float) -> float:
    """Mechanical angular speed. Exact by definition, not a fitted constant."""

    return float(rpm) * _RPM_TO_RAD_PER_S


def electrical_rad_per_s(rpm: float, pole_pairs: int) -> float:
    """Electrical angular speed from mechanical rpm."""

    return rpm_to_rad_per_s(rpm) * float(pole_pairs)
