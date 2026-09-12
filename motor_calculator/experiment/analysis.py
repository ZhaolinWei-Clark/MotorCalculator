"""Phase 11A: turning measured rows into the four quantities we can compare.

Each analysis here answers one question and refuses to answer the others. The
recurring theme is that a number is meaningless without its basis, so every
result states the basis it is on, and conversions between bases are explicit,
named, and carry their assumption.

The Ke analysis is the one that matters most, because back-EMF is where the
analytical model, FEMM and a bench test can all three meet. The others are
implemented to the same standard but have weaker claims, and say so: a
torque-current slope is not an independent Kt unless the current semantics are
known, and an efficiency number derived from DC bus power is an inverter-plus-
motor efficiency unless the source says otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .columns import VoltageBasis
from .csv_import import MeasurementRow
from .regression import LinearFit, RegressionError, fit_line
from .units import rpm_to_rad_per_s

ANALYSIS_SCHEMA_VERSION = "phase11a.experiment.analysis.v1"

#: sqrt(3): line-to-line to phase for a balanced Y connection.
_SQRT3 = math.sqrt(3.0)
#: sqrt(2): peak to RMS for a sinusoid. Only valid for a sinusoid, and the
#: assumption is recorded wherever it is used.
_SQRT2 = math.sqrt(2.0)


class SpeedBasis(str, Enum):
    """Which angular speed a constant is expressed per."""

    MECHANICAL_RAD_PER_S = "MECHANICAL_RAD_PER_S"
    ELECTRICAL_RAD_PER_S = "ELECTRICAL_RAD_PER_S"


class Connection(str, Enum):
    WYE = "WYE"
    DELTA = "DELTA"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Voltage semantics (Step 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoltageConversion:
    """One conversion between voltage bases, with its assumption attached."""

    from_basis: VoltageBasis
    to_basis: VoltageBasis
    factor: float
    assumption_zh: str
    is_exact: bool


def voltage_conversion(
    from_basis: VoltageBasis,
    to_basis: VoltageBasis,
    *,
    connection: Connection = Connection.WYE,
) -> VoltageConversion:
    """The factor taking one voltage basis to another.

    Refuses the line/phase conversion when the connection is unknown, because
    the answer differs by sqrt(3) between Y and delta and there is no way to
    tell from the numbers.
    """

    if from_basis is to_basis:
        return VoltageConversion(from_basis, to_basis, 1.0, "同一基准，无需换算。", True)

    peak_rms = {
        (VoltageBasis.PHASE_PEAK, VoltageBasis.PHASE_RMS): (
            1.0 / _SQRT2,
            "假设波形为正弦：峰值/有效值 = sqrt(2)。非正弦波形下该换算不成立。",
            False,
        ),
        (VoltageBasis.PHASE_RMS, VoltageBasis.PHASE_PEAK): (
            _SQRT2,
            "假设波形为正弦：峰值/有效值 = sqrt(2)。非正弦波形下该换算不成立。",
            False,
        ),
    }
    if (from_basis, to_basis) in peak_rms:
        factor, assumption, exact = peak_rms[(from_basis, to_basis)]
        return VoltageConversion(from_basis, to_basis, factor, assumption, exact)

    if connection is Connection.UNKNOWN:
        raise ValueError(
            "converting between line and phase voltage requires the winding "
            "connection: Y gives V_line = sqrt(3) * V_phase, delta gives "
            "V_line = V_phase. The connection is UNKNOWN for this dataset, so "
            "the conversion is refused rather than guessed."
        )

    line_phase_factor = _SQRT3 if connection is Connection.WYE else 1.0
    assumption = (
        "Y 接：线电压 = sqrt(3) × 相电压（假设三相平衡）。"
        if connection is Connection.WYE
        else "角接：线电压 = 相电压。"
    )
    if (from_basis, to_basis) == (VoltageBasis.LINE_RMS, VoltageBasis.PHASE_RMS):
        return VoltageConversion(from_basis, to_basis, 1.0 / line_phase_factor, assumption, True)
    if (from_basis, to_basis) == (VoltageBasis.PHASE_RMS, VoltageBasis.LINE_RMS):
        return VoltageConversion(from_basis, to_basis, line_phase_factor, assumption, True)
    if (from_basis, to_basis) == (VoltageBasis.LINE_RMS, VoltageBasis.PHASE_PEAK):
        return VoltageConversion(
            from_basis, to_basis, _SQRT2 / line_phase_factor,
            assumption + " 并假设波形为正弦。", False,
        )
    if (from_basis, to_basis) == (VoltageBasis.PHASE_PEAK, VoltageBasis.LINE_RMS):
        return VoltageConversion(
            from_basis, to_basis, line_phase_factor / _SQRT2,
            assumption + " 并假设波形为正弦。", False,
        )
    raise ValueError(f"no defined conversion from {from_basis} to {to_basis}")


#: Which canonical column carries which voltage basis.
_VOLTAGE_COLUMNS: tuple[tuple[str, VoltageBasis], ...] = (
    ("line_voltage_rms_v", VoltageBasis.LINE_RMS),
    ("phase_voltage_rms_v", VoltageBasis.PHASE_RMS),
    ("phase_voltage_peak_v", VoltageBasis.PHASE_PEAK),
)


# ---------------------------------------------------------------------------
# Back-EMF / Ke (Steps 9, 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackEmfResult:
    """A Ke determined from one or more measured speed points."""

    schema_version: str
    #: The basis the fit was performed on. Always stated, never implied.
    voltage_basis: VoltageBasis
    speed_basis: SpeedBasis
    #: V per (rad/s) on the stated bases. This is the comparison quantity.
    ke_v_per_rad_s: float
    #: The same constant per 1000 rpm, which is how data sheets quote it.
    ke_v_per_krpm: float
    fit: LinearFit
    source_column: str
    used_sample_count: int
    excluded_rows: tuple[tuple[int, str], ...]
    conversions: tuple[VoltageConversion, ...]
    connection: Connection
    temperature_range_c: tuple[float, float] | None
    warnings_zh: tuple[str, ...] = ()

    @property
    def intercept_v(self) -> float:
        return self.fit.intercept

    @property
    def r_squared(self) -> float | None:
        return self.fit.r_squared


class AnalysisError(ValueError):
    """The data cannot support the requested analysis."""


def _speed_of(row: MeasurementRow) -> float | None:
    value = row.get("speed_rpm")
    return None if value is None else float(value)


def analyze_back_emf(
    rows: Sequence[MeasurementRow],
    *,
    target_voltage_basis: VoltageBasis = VoltageBasis.PHASE_RMS,
    speed_basis: SpeedBasis = SpeedBasis.MECHANICAL_RAD_PER_S,
    pole_pairs: int | None = None,
    connection: Connection = Connection.WYE,
    force_zero_intercept: bool = False,
    force_reason_zh: str = "",
) -> BackEmfResult:
    """Fit ``E = Ke * omega + offset`` across every usable speed point.

    Whichever voltage column the file supplies is used and converted once, to
    the requested basis, with the conversion recorded. A file supplying both
    line and phase voltage uses phase, because it needs no connection
    assumption -- and says which it used.

    Rows lacking a speed or a voltage are excluded *by row number and reason*,
    never dropped silently.
    """

    if speed_basis is SpeedBasis.ELECTRICAL_RAD_PER_S and not pole_pairs:
        raise AnalysisError(
            "an electrical-speed basis needs the pole-pair count; it is not "
            "recoverable from the measurements"
        )

    available = [
        (name, basis) for name, basis in _VOLTAGE_COLUMNS
        if any(name in row.values for row in rows)
    ]
    if not available:
        raise AnalysisError(
            "no voltage column is present. A back-EMF dataset needs one of "
            + ", ".join(name for name, _ in _VOLTAGE_COLUMNS)
        )
    # Prefer the column needing the fewest assumptions to reach the target.
    def _cost(item: tuple[str, VoltageBasis]) -> tuple[int, int]:
        _name, basis = item
        if basis is target_voltage_basis:
            return (0, 0)
        try:
            conversion = voltage_conversion(basis, target_voltage_basis, connection=connection)
        except ValueError:
            return (3, 0)
        return (1 if conversion.is_exact else 2, 0)

    source_column, source_basis = sorted(available, key=_cost)[0]

    conversions: list[VoltageConversion] = []
    factor = 1.0
    if source_basis is not target_voltage_basis:
        conversion = voltage_conversion(
            source_basis, target_voltage_basis, connection=connection
        )
        conversions.append(conversion)
        factor = conversion.factor

    speeds: list[float] = []
    voltages: list[float] = []
    excluded: list[tuple[int, str]] = []
    temperatures: list[float] = []

    for row in rows:
        speed = _speed_of(row)
        voltage = row.get(source_column)
        if speed is None:
            excluded.append((row.line, "缺少转速"))
            continue
        if voltage is None:
            excluded.append((row.line, f"缺少 {source_column}"))
            continue
        if speed == 0.0:
            excluded.append((row.line, "转速为 0，对 Ke 的斜率没有贡献且会影响截距解释"))
            continue
        omega = rpm_to_rad_per_s(speed)
        if speed_basis is SpeedBasis.ELECTRICAL_RAD_PER_S:
            omega *= float(pole_pairs)
        speeds.append(omega)
        voltages.append(float(voltage) * factor)
        temperature = row.get("temperature_c")
        if temperature is not None:
            temperatures.append(float(temperature))

    if not speeds:
        raise AnalysisError(
            "no usable speed/voltage pair remains: "
            + "; ".join(f"line {line}: {reason}" for line, reason in excluded)
        )

    try:
        fit = fit_line(
            speeds, voltages,
            force_zero_intercept=force_zero_intercept,
            force_reason_zh=force_reason_zh,
        )
    except RegressionError as error:
        raise AnalysisError(str(error)) from error

    warnings: list[str] = []
    if fit.is_single_point:
        warnings.append(
            "只有一个可用测点：Ke 由单点比值给出，不能判断线性度，"
            "也无法区分真实截距与测量偏置。"
        )
    elif not fit.is_well_conditioned:
        warnings.append(
            "测点数量或转速跨度不足，该拟合不足以支撑关于线性度的结论。"
        )
    if not force_zero_intercept and fit.sample_count > 1 and fit.slope != 0.0:
        # A large intercept relative to the fitted range is a measurement
        # problem, not a motor property. Say so rather than absorbing it.
        span_voltage = abs(fit.slope) * max(fit.x_max, 1e-12)
        if span_voltage > 0 and abs(fit.intercept) / span_voltage > 0.02:
            warnings.append(
                f"截距 {fit.intercept:.4g} V 相对量程偏大"
                f"（约 {abs(fit.intercept) / span_voltage * 100.0:.1f} %）。"
                "这通常来自仪器零点、探头偏置或剩磁，而不是电机常数；"
                "本软件不会把它并入 Ke。"
            )
    if conversions and not all(conversion.is_exact for conversion in conversions):
        warnings.append(
            "本次换算依赖正弦波形假设；若实测波形明显非正弦，该 Ke 的基准需重新确认。"
        )
    if source_basis is VoltageBasis.LINE_RMS and connection is Connection.UNKNOWN:
        warnings.append("绕组接法未知，线电压无法换算为相电压。")

    ke = fit.slope
    per_krpm_factor = rpm_to_rad_per_s(1000.0)
    if speed_basis is SpeedBasis.ELECTRICAL_RAD_PER_S:
        per_krpm_factor *= float(pole_pairs)

    return BackEmfResult(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        voltage_basis=target_voltage_basis,
        speed_basis=speed_basis,
        ke_v_per_rad_s=ke,
        ke_v_per_krpm=ke * per_krpm_factor,
        fit=fit,
        source_column=source_column,
        used_sample_count=fit.sample_count,
        excluded_rows=tuple(excluded),
        conversions=tuple(conversions),
        connection=connection,
        temperature_range_c=(min(temperatures), max(temperatures)) if temperatures else None,
        warnings_zh=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Phase resistance (Step 12)
# ---------------------------------------------------------------------------

#: Copper's temperature coefficient at 20 degC, 1/K. A material property, and
#: the only correction this module can apply -- on request, never by default.
COPPER_ALPHA_PER_K = 0.00393
COPPER_REFERENCE_TEMPERATURE_C = 20.0


@dataclass(frozen=True)
class ResistanceResult:
    """A phase resistance and the connection argument that produced it."""

    schema_version: str
    connection: Connection
    #: What the meter read, terminal to terminal.
    measured_terminal_resistance_ohm: float
    #: The per-phase resistance implied by the connection.
    phase_resistance_ohm: float | None
    #: How the phase value follows from the terminal value.
    derivation_zh: str
    measurement_temperature_c: float | None
    #: Present only when the caller explicitly asked for normalisation.
    normalized_to_temperature_c: float | None
    normalized_phase_resistance_ohm: float | None
    normalization_provenance: str
    sample_count: int
    source_zh: str
    warnings_zh: tuple[str, ...] = ()


def analyze_phase_resistance(
    rows: Sequence[MeasurementRow],
    *,
    connection: Connection,
    normalize_to_temperature_c: float | None = None,
    temperature_coefficient_per_k: float = COPPER_ALPHA_PER_K,
    reference_temperature_c: float = COPPER_REFERENCE_TEMPERATURE_C,
) -> ResistanceResult:
    """Terminal-to-terminal resistance, and the phase value it implies.

    A meter across two terminals of a Y machine reads two phases in series, and
    of a delta machine reads one phase in parallel with two in series. These are
    factors of 2 and 2/3, and they are applied only when the connection is
    stated. ``UNKNOWN`` yields a terminal resistance and no phase value, which
    is the honest answer.

    Temperature normalisation never happens on its own. It is applied only when
    a target temperature is passed and a measurement temperature exists, and the
    result records the coefficient used.
    """

    resistances: list[float] = []
    temperatures: list[float] = []
    source = "measured_resistance_ohm"
    warnings: list[str] = []

    for row in rows:
        value = row.get("measured_resistance_ohm")
        if value is None:
            voltage = row.get("applied_voltage_v")
            current = row.get("applied_current_a")
            if voltage is not None and current not in (None, 0.0):
                value = float(voltage) / float(current)
                source = "applied_voltage_v / applied_current_a"
            elif voltage is not None and current == 0.0:
                warnings.append(f"第 {row.line} 行施加电流为 0，无法求电阻。")
                continue
        if value is None:
            continue
        if value <= 0.0:
            warnings.append(f"第 {row.line} 行电阻为非正值 {value}，已排除。")
            continue
        resistances.append(float(value))
        temperature = row.get("temperature_c")
        if temperature is not None:
            temperatures.append(float(temperature))

    if not resistances:
        raise AnalysisError(
            "no resistance measurement found: supply measured_resistance_ohm, "
            "or applied_voltage_v with applied_current_a"
        )

    terminal = sum(resistances) / len(resistances)
    if len(resistances) > 1:
        spread = (max(resistances) - min(resistances)) / terminal
        if spread > 0.05:
            warnings.append(
                f"各次测量之间相差 {spread * 100.0:.1f} %，已取算术平均；"
                "差异较大时建议检查接触电阻与引线电阻。"
            )

    if connection is Connection.WYE:
        phase = terminal / 2.0
        derivation = (
            "Y 接：端子间读数为两相串联，相电阻 = 端子电阻 / 2。"
            "该式假设三相对称且中性点未引出。"
        )
    elif connection is Connection.DELTA:
        phase = terminal * 1.5
        derivation = (
            "角接：端子间读数为一相与另两相串联的并联，"
            "相电阻 = 端子电阻 × 3/2。"
        )
    else:
        phase = None
        derivation = (
            "绕组接法未知：端子间读数无法折算为相电阻"
            "（Y 接为 /2，角接为 ×3/2，相差 3 倍）。此处不作猜测。"
        )
        warnings.append("绕组接法未知，未给出相电阻。")

    measurement_temperature = (
        sum(temperatures) / len(temperatures) if temperatures else None
    )

    normalized = None
    normalization_provenance = "NONE"
    if normalize_to_temperature_c is not None:
        if measurement_temperature is None:
            warnings.append(
                "请求了温度归一化，但数据中没有测量温度；未作任何温度修正。"
            )
            normalization_provenance = "REQUESTED_BUT_NO_MEASUREMENT_TEMPERATURE"
        elif phase is None:
            normalization_provenance = "REQUESTED_BUT_NO_PHASE_RESISTANCE"
        else:
            denominator = 1.0 + temperature_coefficient_per_k * (
                measurement_temperature - reference_temperature_c
            )
            numerator = 1.0 + temperature_coefficient_per_k * (
                normalize_to_temperature_c - reference_temperature_c
            )
            normalized = phase * numerator / denominator
            normalization_provenance = (
                f"EXPLICIT_REQUEST alpha={temperature_coefficient_per_k} /K at "
                f"{reference_temperature_c} degC (copper, material property)"
            )

    return ResistanceResult(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        connection=connection,
        measured_terminal_resistance_ohm=terminal,
        phase_resistance_ohm=phase,
        derivation_zh=derivation,
        measurement_temperature_c=measurement_temperature,
        normalized_to_temperature_c=normalize_to_temperature_c,
        normalized_phase_resistance_ohm=normalized,
        normalization_provenance=normalization_provenance,
        sample_count=len(resistances),
        source_zh=source,
        warnings_zh=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Torque vs current (Step 13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TorqueCurrentResult:
    """A torque-current slope, and an explicit account of what it is not."""

    schema_version: str
    fit: LinearFit
    current_column: str
    #: Nm per amp on the stated current basis.
    slope_nm_per_a: float
    used_sample_count: int
    excluded_rows: tuple[tuple[int, str], ...]
    speed_range_rpm: tuple[float, float] | None
    temperature_range_c: tuple[float, float] | None
    #: The semantic gaps that stop this from being an independent Kt.
    limitations_zh: tuple[str, ...]
    #: True only when every semantic needed to call this Kt is actually known.
    supports_kt_claim: bool
    warnings_zh: tuple[str, ...] = ()


def analyze_torque_current(
    rows: Sequence[MeasurementRow],
    *,
    current_semantics_known: bool = False,
    operating_point_known: bool = False,
    force_zero_intercept: bool = False,
    force_reason_zh: str = "",
) -> TorqueCurrentResult:
    """Fit torque against current, and state what the slope does not prove.

    A torque-per-amp slope is only a torque constant if you know what the amps
    were: phase RMS at unity power factor on the q axis is one thing, a drive's
    reported "current" is another, and a slope fitted across an unknown control
    strategy is a third. Those are not detectable from the numbers, so the
    caller must assert them, and the result records whether they were asserted.
    """

    current_column = "phase_current_rms_a"
    if not any("phase_current_rms_a" in row.values for row in rows):
        if any("iq_a" in row.values for row in rows):
            current_column = "iq_a"
        else:
            raise AnalysisError(
                "no current column: supply phase_current_rms_a or iq_a"
            )

    currents: list[float] = []
    torques: list[float] = []
    excluded: list[tuple[int, str]] = []
    speeds: list[float] = []
    temperatures: list[float] = []

    for row in rows:
        current = row.get(current_column)
        torque = row.get("torque_nm")
        if current is None:
            excluded.append((row.line, f"缺少 {current_column}"))
            continue
        if torque is None:
            excluded.append((row.line, "缺少 torque_nm"))
            continue
        currents.append(float(current))
        torques.append(float(torque))
        speed = row.get("speed_rpm")
        if speed is not None:
            speeds.append(float(speed))
        temperature = row.get("temperature_c")
        if temperature is not None:
            temperatures.append(float(temperature))

    if not currents:
        raise AnalysisError(
            "no usable torque/current pair: "
            + "; ".join(f"line {line}: {reason}" for line, reason in excluded)
        )

    try:
        fit = fit_line(
            currents, torques,
            force_zero_intercept=force_zero_intercept,
            force_reason_zh=force_reason_zh,
        )
    except RegressionError as error:
        raise AnalysisError(str(error)) from error

    limitations: list[str] = []
    if not current_semantics_known:
        limitations.append(
            "电流语义未声明：不清楚该电流是相有效值、峰值、q 轴分量还是驱动器上报值。"
            "这些定义之间相差 sqrt(2) 乃至更多，因此该斜率不能作为 Kt。"
        )
    if current_column == "iq_a" and not operating_point_known:
        limitations.append(
            "使用了 q 轴电流，但未声明 d 轴电流与控制策略；"
            "若存在磁阻转矩或 id ≠ 0，转矩并非只由 iq 决定。"
        )
    if not operating_point_known:
        limitations.append(
            "工作点未声明：温度、转速与控制方式都会改变转矩-电流关系，"
            "拟合斜率本身无法区分这些影响。"
        )
    if not speeds:
        limitations.append("数据中没有转速列，无法确认这些点是否属于同一工作点。")
    elif len(set(round(value, 6) for value in speeds)) > 1:
        limitations.append(
            f"这些测点跨越多个转速（{min(speeds):.0f} … {max(speeds):.0f} rpm），"
            "斜率是跨工作点的综合结果。"
        )
    if abs(fit.intercept) > 1e-9 and not force_zero_intercept:
        limitations.append(
            f"拟合截距为 {fit.intercept:.4g} N·m（零电流时的转矩）。"
            "这通常来自摩擦、齿槽或测量偏置，不属于电磁转矩常数。"
        )

    return TorqueCurrentResult(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        fit=fit,
        current_column=current_column,
        slope_nm_per_a=fit.slope,
        used_sample_count=fit.sample_count,
        excluded_rows=tuple(excluded),
        speed_range_rpm=(min(speeds), max(speeds)) if speeds else None,
        temperature_range_c=(min(temperatures), max(temperatures)) if temperatures else None,
        limitations_zh=tuple(limitations),
        supports_kt_claim=bool(current_semantics_known and operating_point_known and not limitations),
        warnings_zh=(),
    )


# ---------------------------------------------------------------------------
# Efficiency (Step 14)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EfficiencyPoint:
    """One operating point. Measured and derived values stay separate."""

    line: int
    speed_rpm: float | None
    torque_nm: float | None
    #: Straight from the file, when the file supplied it.
    measured_input_power_w: float | None
    measured_output_power_w: float | None
    measured_efficiency: float | None
    #: Computed here, only when not supplied.
    derived_input_power_w: float | None
    derived_output_power_w: float | None
    derived_efficiency: float | None
    #: Which of the two each reported number came from.
    input_power_source: str
    output_power_source: str
    efficiency_source: str

    @property
    def input_power_w(self) -> float | None:
        return (
            self.measured_input_power_w
            if self.measured_input_power_w is not None
            else self.derived_input_power_w
        )

    @property
    def output_power_w(self) -> float | None:
        return (
            self.measured_output_power_w
            if self.measured_output_power_w is not None
            else self.derived_output_power_w
        )

    @property
    def efficiency(self) -> float | None:
        return (
            self.measured_efficiency
            if self.measured_efficiency is not None
            else self.derived_efficiency
        )


@dataclass(frozen=True)
class EfficiencyResult:
    schema_version: str
    points: tuple[EfficiencyPoint, ...]
    peak_efficiency: float | None
    peak_efficiency_line: int | None
    #: True when input power came from the DC bus, which includes the inverter.
    includes_inverter_losses: bool
    boundary_zh: str
    excluded_rows: tuple[tuple[int, str], ...]
    warnings_zh: tuple[str, ...] = ()


def analyze_efficiency(rows: Sequence[MeasurementRow]) -> EfficiencyResult:
    """Efficiency per operating point, keeping measured and derived apart.

    A supplied power is never overwritten by a computed one. When both exist,
    both are kept and the reported value is the measured one, because the file's
    own instrument is closer to the truth than this project's arithmetic.

    When input power comes from the DC bus, the efficiency measured is the
    inverter *and* motor together. Reporting that as motor efficiency would
    understate the motor by the inverter's losses, so the boundary is stated.
    """

    points: list[EfficiencyPoint] = []
    excluded: list[tuple[int, str]] = []
    warnings: list[str] = []
    any_dc_bus = False

    for row in rows:
        speed = row.get("speed_rpm")
        torque = row.get("torque_nm")
        measured_in = row.get("input_power_w")
        measured_out = row.get("output_power_w")
        measured_eta = row.get("efficiency")

        derived_in = None
        input_source = "NONE"
        if measured_in is not None:
            input_source = "MEASURED"
        else:
            bus_v = row.get("dc_bus_voltage_v")
            bus_a = row.get("dc_bus_current_a")
            if bus_v is not None and bus_a is not None:
                derived_in = float(bus_v) * float(bus_a)
                input_source = "DERIVED_FROM_DC_BUS"
                any_dc_bus = True

        derived_out = None
        output_source = "NONE"
        if measured_out is not None:
            output_source = "MEASURED"
        elif speed is not None and torque is not None:
            derived_out = float(torque) * rpm_to_rad_per_s(float(speed))
            output_source = "DERIVED_FROM_TORQUE_AND_SPEED"

        derived_eta = None
        efficiency_source = "NONE"
        if measured_eta is not None:
            efficiency_source = "MEASURED"
        else:
            total_in = measured_in if measured_in is not None else derived_in
            total_out = measured_out if measured_out is not None else derived_out
            if total_in is not None and total_out is not None:
                if total_in == 0.0:
                    excluded.append((row.line, "输入功率为 0，效率无定义"))
                    continue
                derived_eta = float(total_out) / float(total_in)
                efficiency_source = "DERIVED"

        if efficiency_source == "NONE":
            excluded.append(
                (row.line, "既没有实测效率，也没有足够的功率/转矩数据可以导出效率")
            )
            continue

        point = EfficiencyPoint(
            line=row.line,
            speed_rpm=None if speed is None else float(speed),
            torque_nm=None if torque is None else float(torque),
            measured_input_power_w=None if measured_in is None else float(measured_in),
            measured_output_power_w=None if measured_out is None else float(measured_out),
            measured_efficiency=None if measured_eta is None else float(measured_eta),
            derived_input_power_w=derived_in,
            derived_output_power_w=derived_out,
            derived_efficiency=derived_eta,
            input_power_source=input_source,
            output_power_source=output_source,
            efficiency_source=efficiency_source,
        )
        if point.efficiency is not None and point.efficiency > 1.0:
            warnings.append(
                f"第 {row.line} 行效率大于 1（{point.efficiency:.4f}）。"
                "该值按原样保留，不作截断；通常意味着功率测量的符号或基准有问题。"
            )
        points.append(point)

    if not points:
        raise AnalysisError(
            "no usable efficiency point: "
            + "; ".join(f"line {line}: {reason}" for line, reason in excluded)
        )

    ranked = [point for point in points if point.efficiency is not None]
    best = max(ranked, key=lambda point: point.efficiency) if ranked else None

    boundary = (
        "输入功率取自直流母线，因此该效率是**逆变器 + 电机**的整体效率，"
        "不是电机本身的效率。与本项目的电机模型比较时必须考虑这一边界差异。"
        if any_dc_bus
        else "输入功率由数据源直接给出；请确认其测量边界后再与电机模型比较。"
    )

    return EfficiencyResult(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        points=tuple(points),
        peak_efficiency=None if best is None else best.efficiency,
        peak_efficiency_line=None if best is None else best.line,
        includes_inverter_losses=any_dc_bus,
        boundary_zh=boundary,
        excluded_rows=tuple(excluded),
        warnings_zh=tuple(warnings),
    )
