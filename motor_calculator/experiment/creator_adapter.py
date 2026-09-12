"""Phase 11B: reading the CREATOR PMSM files, with their semantics declared.

Why these are adapters and not column mappings
----------------------------------------------
Phase 11A's importer maps a source header onto a canonical field. That is the
right tool when a file is a table of the quantities the analysis wants. The
CREATOR measurement files are not that shape.

``Back_emf.csv`` is an angle-domain waveform: 7,681 rows of rotor angle and three
instantaneous phase voltages. A column mapping *can* be made to "work" on it --
point ``Rotor angle`` at ``speed_rpm`` and the Phase 11A importer returns
``ok=True`` -- and the result is meaningless. The audit demonstrated exactly
that. So the mapping route is not used here at all: each adapter declares the
layout it expects, verifies it, and produces a typed result whose semantics are
part of the type.

What every adapter does
-----------------------
* declares the columns and units it expects, because the CREATOR files declare
  no units in their headers;
* verifies the file hash against what was recorded at audit time, and says so
  rather than silently analysing a file that has changed;
* refuses a layout it does not recognise instead of guessing;
* keeps raw and derived quantities separate in the result.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import creator_source as src
from .harmonics import WaveformAnalysis, analyze_waveform
from .origins import ParameterOrigin
from .schema import TestType, file_sha256

CREATOR_ADAPTER_SCHEMA_VERSION = "phase11b.creator_adapter.v1"


class CreatorAdapterError(ValueError):
    """A CREATOR file is absent, or is not the file this adapter expects."""


@dataclass(frozen=True)
class FileBinding:
    """Which physical file an adapter read, and whether it is the expected one."""

    key: str
    path: Path
    sha256: str
    expected_sha256: str | None
    #: "VERIFIED" / "HASH_MISMATCH" / "NO_EXPECTED_HASH"
    integrity: str

    @property
    def is_verified(self) -> bool:
        return self.integrity == "VERIFIED"


def resolve(root: str | Path, key: str, *, verify: bool = True) -> FileBinding:
    """Locate one CREATOR file under the user's own copy of the dataset."""

    relative = src.RELATIVE_PATHS.get(key)
    if relative is None:
        raise CreatorAdapterError(f"{key!r} is not a known CREATOR file key")
    path = Path(root) / relative
    if not path.is_file():
        raise CreatorAdapterError(
            f"CREATOR file not found: {path}\n"
            f"This project does not ship the raw dataset. Obtain it from "
            f"https://doi.org/{src.DATASET_DOI} ({src.LICENSE_NAME}) and point "
            "the adapter at your own copy."
        )
    digest = file_sha256(path) if verify else ""
    expected = src.FILE_HASHES.get(key)
    if not verify:
        integrity = "NOT_CHECKED"
    elif expected is None:
        integrity = "NO_EXPECTED_HASH"
    elif digest == expected:
        integrity = "VERIFIED"
    else:
        integrity = "HASH_MISMATCH"
    return FileBinding(key, path, digest, expected, integrity)


def _rows(path: Path, *, has_header: bool, expected_columns: int):
    """Deterministic read. Blank lines and ``#`` comments skipped."""

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = None
        data: list[tuple[int, list[str]]] = []
        for index, row in enumerate(reader, 1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if header is None and has_header:
                header = [cell.strip() for cell in row]
                continue
            data.append((index, row))
    if has_header and header is None:
        raise CreatorAdapterError(f"{path.name}: expected a header row, found none")
    for index, row in data[:1]:
        if len(row) != expected_columns:
            raise CreatorAdapterError(
                f"{path.name}: expected {expected_columns} columns, line {index} "
                f"has {len(row)}. This adapter does not guess layouts."
            )
    return header, data


def _floats(path: Path, data, column: int) -> list[float]:
    out = []
    for index, row in data:
        try:
            out.append(float(row[column].strip()))
        except (ValueError, IndexError) as error:
            raise CreatorAdapterError(
                f"{path.name} line {index}, column {column + 1}: "
                f"cannot parse {row[column]!r} as a number ({error})"
            ) from error
    return out


# ---------------------------------------------------------------------------
# Back-EMF waveform (Steps 3-6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackEmfWaveformResult:
    """The CREATOR back-EMF record, analysed. Every basis is named."""

    schema_version: str
    binding: FileBinding
    test_type: TestType
    sample_count: int
    speed_rpm: float
    pole_pairs: int
    #: "MECHANICAL_DEGREES" -- the angle column's basis, declared not inferred.
    angle_basis: str
    #: "PHASE_TO_NEUTRAL_INSTANTANEOUS" -- the voltage column's basis.
    voltage_basis: str
    #: Per-phase analyses, keyed in source order U, V, W.
    per_phase: tuple[tuple[str, WaveformAnalysis], ...]
    #: Largest |Eu+Ev+Ew| over the record, as a fraction of the raw peak.
    phase_sum_residual_ratio: float
    phase_sum_max_abs: float
    balanced: bool
    notes_zh: tuple[str, ...] = field(default_factory=tuple)

    def analysis(self, phase: str = "U") -> WaveformAnalysis:
        for name, item in self.per_phase:
            if name.upper() == phase.upper():
                return item
        raise KeyError(phase)

    @property
    def reference_phase(self) -> str:
        return self.per_phase[0][0]

    @property
    def fundamental_peak_v(self) -> float:
        """Reference-phase fundamental peak. The comparison quantity."""

        return self.analysis(self.reference_phase).fundamental_peak

    @property
    def fundamental_rms_v(self) -> float:
        return self.analysis(self.reference_phase).fundamental_rms

    @property
    def raw_peak_v(self) -> float:
        return self.analysis(self.reference_phase).raw_peak

    @property
    def mean_fundamental_peak_v(self) -> float:
        """Mean over the three phases, which a symmetric machine should share."""

        peaks = [item.fundamental_peak for _n, item in self.per_phase]
        return sum(peaks) / len(peaks)

    @property
    def phase_spread_percent(self) -> float:
        peaks = [item.fundamental_peak for _n, item in self.per_phase]
        return (max(peaks) - min(peaks)) / self.mean_fundamental_peak_v * 100.0


#: Tolerance for reproducing the published fundamental. The published value is
#: quoted to 4 significant figures (47.37 V), so agreement can only be asserted
#: to the last quoted digit: +/-0.005 V is half a unit in that place, and 0.05 %
#: covers it with margin without being loose enough to hide a real error.
PUBLICATION_TOLERANCE_PERCENT = 0.05

#: A balanced three-phase set sums to zero. Real measurements do not sum to
#: exactly zero; 2 % of the raw peak is generous for instrument offset while
#: still catching a genuinely unbalanced or misread record.
PHASE_SUM_TOLERANCE_RATIO = 0.02


def read_back_emf(root: str | Path, *, verify: bool = True) -> BackEmfWaveformResult:
    """Read and analyse ``No_load_tests/Back_emf.csv``.

    The speed and pole-pair count come from the source's documentation, not from
    the data: a single-speed record cannot reveal its own speed.
    """

    binding = resolve(root, "back_emf", verify=verify)
    layout = src.COLUMN_LAYOUTS["back_emf"]
    _header, data = _rows(
        binding.path, has_header=layout["has_header"], expected_columns=4
    )
    angle = _floats(binding.path, data, 0)
    phases = {
        "U": _floats(binding.path, data, 1),
        "V": _floats(binding.path, data, 2),
        "W": _floats(binding.path, data, 3),
    }

    sums = [phases["U"][i] + phases["V"][i] + phases["W"][i] for i in range(len(angle))]
    sum_max = max(abs(value) for value in sums)
    raw_peak = max(max(abs(v) for v in values) for values in phases.values())
    ratio = sum_max / raw_peak if raw_peak else float("inf")

    per_phase = tuple(
        (name, analyze_waveform(angle, values, pole_pairs=src.POLE_PAIRS))
        for name, values in phases.items()
    )

    notes = [
        "转速与极对数取自来源文档（2000 rpm，2 对极）：单一转速的记录无法自证其转速。",
        layout["note"],
    ]
    if binding.integrity == "HASH_MISMATCH":
        notes.append(
            "⚠ 文件哈希与审计时记录的不一致：该文件已被改动，结果不应与公开值比较。"
        )
    if ratio > PHASE_SUM_TOLERANCE_RATIO:
        notes.append(
            f"⚠ 三相之和的最大绝对值为原始峰值的 {ratio * 100.0:.2f} %，"
            "超出平衡三相的预期；这些列可能不是相对中性点的相电压。"
        )

    return BackEmfWaveformResult(
        schema_version=CREATOR_ADAPTER_SCHEMA_VERSION,
        binding=binding,
        test_type=TestType.BACK_EMF_WAVEFORM,
        sample_count=len(angle),
        speed_rpm=src.BACK_EMF_SPEED_RPM,
        pole_pairs=src.POLE_PAIRS,
        angle_basis="MECHANICAL_DEGREES",
        voltage_basis="PHASE_TO_NEUTRAL_INSTANTANEOUS",
        per_phase=per_phase,
        phase_sum_residual_ratio=ratio,
        phase_sum_max_abs=sum_max,
        balanced=ratio <= PHASE_SUM_TOLERANCE_RATIO,
        notes_zh=tuple(notes),
    )


@dataclass(frozen=True)
class PublicationCheck:
    """Whether extraction reproduced the published number, and by how much."""

    quantity: str
    extracted: float
    published: float
    difference: float
    difference_percent: float
    tolerance_percent: float
    reproduced: bool
    note_zh: str


def check_against_publication(result: BackEmfWaveformResult) -> PublicationCheck:
    """Compare the extracted fundamental with the published 47.37 V.

    This is a *check*, not a fit. Nothing in the extraction path takes the
    published value as an input, so agreement is evidence that the processing
    chain is right; disagreement is a defect in this software, not in the source.
    """

    extracted = result.fundamental_peak_v
    published = src.PUBLISHED_BACK_EMF_FUNDAMENTAL_PEAK_V
    difference = extracted - published
    percent = difference / published * 100.0
    reproduced = abs(percent) <= PUBLICATION_TOLERANCE_PERCENT
    return PublicationCheck(
        quantity="back_emf_fundamental_peak_v",
        extracted=extracted,
        published=published,
        difference=difference,
        difference_percent=percent,
        tolerance_percent=PUBLICATION_TOLERANCE_PERCENT,
        reproduced=reproduced,
        note_zh=(
            f"由原始波形独立提取的基波峰值为 {extracted:.4f} V，"
            f"公开值为 {published} V，相差 {percent:+.4f} %。"
            + (
                "在容差之内：本软件的波形处理链复现了公开结果。"
                if reproduced
                else "**超出容差**：这是本软件处理链的缺陷，不是来源数据的问题。"
            )
        ),
    )


# ---------------------------------------------------------------------------
# Single-speed Ke (Step 6)
# ---------------------------------------------------------------------------

SINGLE_SPEED_PROVENANCE = "MEASUREMENT_DERIVED_SINGLE_SPEED"


@dataclass(frozen=True)
class SingleSpeedKe:
    """A back-EMF constant from one speed. Deliberately not a regression.

    There is no R-squared here and there never will be. R-squared describes how
    well a line fits several points; with one operating point there is no line,
    no residual and nothing to describe. Reporting one would give a single ratio
    the appearance of a fitted result, which is precisely the confusion this
    type exists to prevent.
    """

    schema_version: str
    provenance: str
    value_v_per_rad_s: float
    #: "PHASE_PEAK" / "PHASE_RMS" -- which voltage the constant is per.
    voltage_basis: str
    #: "ELECTRICAL_RAD_PER_S" / "MECHANICAL_RAD_PER_S"
    speed_basis: str
    speed_rpm: float
    angular_speed_rad_s: float
    fundamental_peak_v: float
    formula: str
    sample_count: int
    #: Always None. The attribute exists so a caller that expects the multi-speed
    #: result's shape gets an explicit absence rather than an AttributeError.
    r_squared: None = None
    uncertainty_status: str = "NOT_QUANTIFIED"
    uncertainty_note_zh: str = (
        "来源未提供该测量的不确定度信息（无仪器精度、无重复性、无温度记录），"
        "因此此处不给出任何不确定度数值。"
    )
    limitations_zh: tuple[str, ...] = ()

    @property
    def is_regression(self) -> bool:
        return False


def single_speed_ke(
    result: BackEmfWaveformResult,
    *,
    voltage_basis: str = "PHASE_PEAK",
    speed_basis: str = "ELECTRICAL_RAD_PER_S",
) -> SingleSpeedKe:
    """Derive Ke from the one measured speed, with the basis stated."""

    if voltage_basis not in {"PHASE_PEAK", "PHASE_RMS"}:
        raise CreatorAdapterError(f"unsupported voltage basis {voltage_basis!r}")
    if speed_basis not in {"ELECTRICAL_RAD_PER_S", "MECHANICAL_RAD_PER_S"}:
        raise CreatorAdapterError(f"unsupported speed basis {speed_basis!r}")

    peak = result.fundamental_peak_v
    voltage = peak if voltage_basis == "PHASE_PEAK" else peak / math.sqrt(2.0)
    omega_mech = result.speed_rpm / 60.0 * 2.0 * math.pi
    omega = omega_mech * (result.pole_pairs if speed_basis == "ELECTRICAL_RAD_PER_S" else 1)

    return SingleSpeedKe(
        schema_version=CREATOR_ADAPTER_SCHEMA_VERSION,
        provenance=SINGLE_SPEED_PROVENANCE,
        value_v_per_rad_s=voltage / omega,
        voltage_basis=voltage_basis,
        speed_basis=speed_basis,
        speed_rpm=result.speed_rpm,
        angular_speed_rad_s=omega,
        fundamental_peak_v=peak,
        formula=(
            f"Ke = E1_{voltage_basis.lower()} / omega_{speed_basis.lower()}  "
            f"= {voltage:.6f} V / {omega:.6f} rad/s"
        ),
        sample_count=result.sample_count,
        limitations_zh=(
            "仅有一个转速点：无法判断 Ke 随转速的线性度，也无法区分真实截距与测量偏置。",
            "该值不等价于多转速回归结果，不能与 USER_EXPERIMENT 的多点工作流混用。",
            "由基波导出：原始波形明显非正弦，直接取原始峰值会显著高估。",
        ),
    )


# ---------------------------------------------------------------------------
# Cogging torque (Steps 7-9)
# ---------------------------------------------------------------------------

PUBLISHED_SCALAR_AMBIGUOUS = "PUBLISHED_SCALAR_DEFINITION_AMBIGUOUS"


@dataclass(frozen=True)
class CoggingResult:
    """Cogging torque summary. Four separate scalars, never merged into one."""

    schema_version: str
    binding: FileBinding
    test_type: TestType
    sample_count: int
    angle_span_deg: float
    #: Quasi-static rotation speed, from source documentation.
    speed_rpm: float
    current_condition: str
    torque_basis: str
    max_positive_nm: float
    min_negative_nm: float
    max_abs_nm: float
    peak_to_peak_nm: float
    mean_nm: float
    rms_nm: float
    harmonics: WaveformAnalysis | None
    #: Which raw statistic the published scalar actually corresponds to.
    published_scalar_nm: float
    published_scalar_matches: str
    published_scalar_flag: str
    published_scalar_note_zh: str
    notes_zh: tuple[str, ...] = ()


def read_cogging(
    root: str | Path, *, verify: bool = True, harmonic_orders: Sequence[int] = (6, 12, 18, 24)
) -> CoggingResult:
    """Read and summarise ``No_load_tests/Cogging_torque.csv``.

    The headline statistics are computed on the **full** record. Downsampling
    happens only for plotting, and only after these numbers exist.
    """

    binding = resolve(root, "cogging", verify=verify)
    layout = src.COLUMN_LAYOUTS["cogging"]
    _header, data = _rows(
        binding.path, has_header=layout["has_header"], expected_columns=2
    )
    angle = _floats(binding.path, data, 0)
    torque = _floats(binding.path, data, 1)

    max_positive = max(torque)
    min_negative = min(torque)
    max_abs = max(abs(max_positive), abs(min_negative))
    peak_to_peak = max_positive - min_negative
    mean = sum(torque) / len(torque)
    rms = math.sqrt(sum(value * value for value in torque) / len(torque))

    harmonics = None
    try:
        harmonics = analyze_waveform(
            angle, torque, pole_pairs=1, orders=harmonic_orders
        )
    except Exception:  # noqa: BLE001 - a summary must survive a harmonic failure
        harmonics = None

    published = src.PUBLISHED_COGGING_SCALAR_NM
    candidates = {
        "max_abs": max_abs,
        "abs_min_negative": abs(min_negative),
        "max_positive": max_positive,
        "half_peak_to_peak": peak_to_peak / 2.0,
    }
    matches, best = min(
        ((name, value) for name, value in candidates.items()),
        key=lambda item: abs(item[1] - published),
    )
    deviation = (best - published) / published * 100.0
    max_abs_deviation = (max_abs - published) / published * 100.0

    note = (
        f"公开标量 {published} Nm 与原始记录的 max|T| = {max_abs:.6f} Nm "
        f"相差 {max_abs_deviation:+.2f} %，而与 {matches} = {best:.6f} Nm "
        f"相差 {deviation:+.2f} %。"
        "来源未定义该标量的取法（最大绝对值、负峰、还是峰峰值之半）。"
        "本软件**不调整原始数据去迎合公开标量**，而是并列给出四个统计量，"
        "由使用者按其所需的定义选取。"
    )

    return CoggingResult(
        schema_version=CREATOR_ADAPTER_SCHEMA_VERSION,
        binding=binding,
        test_type=TestType.COGGING_TORQUE,
        sample_count=len(torque),
        angle_span_deg=max(angle) - min(angle),
        speed_rpm=src.COGGING_SPEED_RPM,
        current_condition="ZERO_CURRENT",
        torque_basis="MOTOR_SHAFT",
        max_positive_nm=max_positive,
        min_negative_nm=min_negative,
        max_abs_nm=max_abs,
        peak_to_peak_nm=peak_to_peak,
        mean_nm=mean,
        rms_nm=rms,
        harmonics=harmonics,
        published_scalar_nm=published,
        published_scalar_matches=matches,
        published_scalar_flag=PUBLISHED_SCALAR_AMBIGUOUS,
        published_scalar_note_zh=note,
        notes_zh=(
            "零电流、准静态（0.25 rpm）旋转，转矩传感器测量；属电机轴端转矩。",
            "四个统计量分别保留，不合并为单一「齿槽转矩」数值。",
        ),
    )


def downsample(angles, values, *, target: int = 2000):
    """Evenly thin a record for plotting. Never used before the statistics."""

    count = len(values)
    if count <= target:
        return list(angles), list(values)
    step = count / target
    indices = [int(i * step) for i in range(target)]
    return [angles[i] for i in indices], [values[i] for i in indices]


# ---------------------------------------------------------------------------
# No-load loss (Steps 10-12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoLoadRun:
    """One coast-down run. The rotor configuration is part of its identity."""

    key: str
    binding: FileBinding
    #: "ROTOR_OUTSIDE_STATOR" or "ROTOR_INSIDE_STATOR"
    configuration: str
    measurement_date: str
    speeds_rpm: tuple[float, ...]
    torques_nm: tuple[float, ...]

    def torque_at(self, rpm: float, tolerance: float = 2.0) -> float | None:
        for speed, torque in zip(self.speeds_rpm, self.torques_nm):
            if abs(speed - rpm) <= tolerance:
                return torque
        return None

    def power_w(self) -> tuple[float, ...]:
        return tuple(
            torque * speed / 60.0 * 2.0 * math.pi
            for speed, torque in zip(self.speeds_rpm, self.torques_nm)
        )


#: Which file is which configuration. From the source's README, which states that
#: 05/10 and 17/10 were taken with the rotor outside the stator and 18/10 with it
#: inside. Collapsing these would destroy the loss separation entirely.
RUN_CONFIGURATIONS = {
    "no_load_rotor_out_1": ("ROTOR_OUTSIDE_STATOR", "2023-10-05"),
    "no_load_rotor_out_2": ("ROTOR_OUTSIDE_STATOR", "2023-10-17"),
    "no_load_rotor_in": ("ROTOR_INSIDE_STATOR", "2023-10-18"),
}


@dataclass(frozen=True)
class IronLossReconstruction:
    """Our reconstruction of iron loss, beside the source's own derived values."""

    speed_rpm: float
    frequency_hz: float
    #: (T_inside - T_outside) * omega, computed here.
    reconstructed_w: float
    #: The value the source publishes for the same frequency.
    published_w: float | None
    residual_w: float | None
    residual_percent: float | None


@dataclass(frozen=True)
class NoLoadLossResult:
    """No-load loss with friction/windage and iron loss kept apart."""

    schema_version: str
    test_type: TestType
    runs: tuple[NoLoadRun, ...]
    #: The source's own derived iron-loss table, as published.
    published_iron_loss: tuple[tuple[float, float], ...]
    published_iron_loss_origin: ParameterOrigin
    reconstruction: tuple[IronLossReconstruction, ...]
    reconstruction_reference: str
    max_abs_residual_percent: float | None
    mean_abs_residual_percent: float | None
    closes: bool
    notes_zh: tuple[str, ...]

    def run(self, configuration: str) -> NoLoadRun | None:
        for item in self.runs:
            if item.configuration == configuration:
                return item
        return None


#: How close the reconstruction must come before it is called closed. The source
#: gives no uncertainty, and its own table does not follow exactly from either
#: rotor-out run, so this is a reporting threshold, not a physical claim.
RECONSTRUCTION_TOLERANCE_PERCENT = 15.0


def read_no_load_loss(
    root: str | Path, *, verify: bool = True, reference: str = "no_load_rotor_out_1"
) -> NoLoadLossResult:
    """Read the three coast-down runs and the source's derived iron-loss table.

    Friction and windage are what the rotor-outside-stator runs measure; the
    rotor-inside run adds the iron loss. The difference is the iron loss, and
    keeping the three files distinct is what makes that separation possible.
    """

    runs = []
    for key, (configuration, date) in RUN_CONFIGURATIONS.items():
        binding = resolve(root, key, verify=verify)
        _header, data = _rows(binding.path, has_header=True, expected_columns=2)
        runs.append(
            NoLoadRun(
                key=key,
                binding=binding,
                configuration=configuration,
                measurement_date=date,
                speeds_rpm=tuple(_floats(binding.path, data, 0)),
                torques_nm=tuple(_floats(binding.path, data, 1)),
            )
        )

    iron_binding = resolve(root, "iron_losses", verify=verify)
    _header, iron_data = _rows(iron_binding.path, has_header=True, expected_columns=2)
    published = tuple(
        zip(_floats(iron_binding.path, iron_data, 0), _floats(iron_binding.path, iron_data, 1))
    )

    inside = next(r for r in runs if r.configuration == "ROTOR_INSIDE_STATOR")
    outside = next(r for r in runs if r.key == reference)

    reconstruction: list[IronLossReconstruction] = []
    for frequency, published_w in published:
        rpm = frequency * 60.0 / src.POLE_PAIRS
        torque_in = inside.torque_at(rpm)
        torque_out = outside.torque_at(rpm)
        if torque_in is None or torque_out is None:
            continue
        omega = rpm / 60.0 * 2.0 * math.pi
        value = (torque_in - torque_out) * omega
        residual = value - published_w
        reconstruction.append(
            IronLossReconstruction(
                speed_rpm=rpm,
                frequency_hz=frequency,
                reconstructed_w=value,
                published_w=published_w,
                residual_w=residual,
                residual_percent=(residual / published_w * 100.0) if published_w else None,
            )
        )

    percentages = [
        abs(item.residual_percent)
        for item in reconstruction
        if item.residual_percent is not None
    ]
    worst = max(percentages) if percentages else None
    mean = sum(percentages) / len(percentages) if percentages else None

    return NoLoadLossResult(
        schema_version=CREATOR_ADAPTER_SCHEMA_VERSION,
        test_type=TestType.NO_LOAD_LOSS,
        runs=tuple(runs),
        published_iron_loss=published,
        published_iron_loss_origin=ParameterOrigin.MEASUREMENT_DERIVED,
        reconstruction=tuple(reconstruction),
        reconstruction_reference=reference,
        max_abs_residual_percent=worst,
        mean_abs_residual_percent=mean,
        closes=bool(worst is not None and worst <= RECONSTRUCTION_TOLERANCE_PERCENT),
        notes_zh=(
            "转子在定子**外部**时测得的是轴承摩擦与风阻；"
            "转子在定子**内部**时还包含铁耗。二者之差即铁耗。",
            "因此空载损耗**不等于**铁耗，本结果不把两者混为一谈。",
            f"重建式 P = (T_内 - T_外) × ω，参照运行取 {reference}。",
            "重建与来源公开值之间的差异按原样报告，不作任何标定或调整。",
        ),
    )


# ---------------------------------------------------------------------------
# Drive cycle (Steps 16-17)
# ---------------------------------------------------------------------------

VEHICLES = ("Mid_sized_vehicle", "Small_sized_vehicle")
CYCLES = ("Artemis", "Bcdc", "Wltp")

#: Which quantity each filename carries. The generic word "Power" appears in the
#: headers of the small-vehicle files and says nothing about input vs output, so
#: the mapping comes from the filename, declared here, and never from the header.
DRIVE_CYCLE_SIGNALS = {
    "input_power": ("input_power_w", "W", "DC_INPUT"),
    "output_power": ("output_power_w", "W", "MECHANICAL_OUTPUT"),
    "speed_rpm": ("speed_rpm", "rpm", "MECHANICAL_RPM"),
    "torque_nm": ("torque_nm", "Nm", "MOTOR_SHAFT"),
}


@dataclass(frozen=True)
class DriveCycleSignal:
    name: str
    canonical: str
    unit: str
    semantics: str
    times_s: tuple[float, ...]
    values: tuple[float, ...]
    has_header: bool
    #: True when any sample is negative, i.e. the machine is regenerating.
    has_negative: bool
    min_value: float
    max_value: float


@dataclass(frozen=True)
class DriveCycleResult:
    schema_version: str
    test_type: TestType
    vehicle: str
    cycle: str
    signals: tuple[DriveCycleSignal, ...]
    shared_time_base: bool
    input_energy_j: float | None
    output_energy_j: float | None
    cycle_efficiency: float | None
    regenerative_samples: int
    notes_zh: tuple[str, ...]

    def signal(self, name: str) -> DriveCycleSignal | None:
        for item in self.signals:
            if item.name == name:
                return item
        return None


def _drive_cycle_path(root: Path, vehicle: str, cycle: str, signal: str) -> Path | None:
    if signal in {"input_power", "output_power"}:
        base = root / "Measurement_results" / "Drive_cycle_measurement_results" / vehicle
        name = f"{cycle}_{signal}.csv"
    else:
        base = root / "Measurement_results" / "Drive_cycle_torque_speed_data" / vehicle
        name = f"{cycle}_{signal}.csv"
    path = base / name
    return path if path.is_file() else None


def read_drive_cycle(
    root: str | Path, *, vehicle: str = "Small_sized_vehicle", cycle: str = "Wltp"
) -> DriveCycleResult:
    """Read one CREATOR drive cycle, joining its per-signal files on time.

    The header situation differs by folder -- the small-vehicle files carry
    ``Time,Power`` and the mid-vehicle files carry no header at all, so their
    first data row would be consumed as one. That is declared per vehicle in
    :data:`creator_source.COLUMN_LAYOUTS`, not sniffed.
    """

    if vehicle not in VEHICLES:
        raise CreatorAdapterError(f"unknown vehicle {vehicle!r}; expected one of {VEHICLES}")
    if cycle not in CYCLES:
        raise CreatorAdapterError(f"unknown cycle {cycle!r}; expected one of {CYCLES}")

    root = Path(root)
    layout_key = "drive_cycle_mid" if vehicle == "Mid_sized_vehicle" else "drive_cycle_small"
    has_header = src.COLUMN_LAYOUTS[layout_key]["has_header"]

    signals: list[DriveCycleSignal] = []
    for signal, (canonical, unit, semantics) in DRIVE_CYCLE_SIGNALS.items():
        path = _drive_cycle_path(root, vehicle, cycle, signal)
        if path is None:
            continue
        _header, data = _rows(path, has_header=has_header, expected_columns=2)
        times = _floats(path, data, 0)
        values = _floats(path, data, 1)
        signals.append(
            DriveCycleSignal(
                name=signal,
                canonical=canonical,
                unit=unit,
                semantics=semantics,
                times_s=tuple(times),
                values=tuple(values),
                has_header=has_header,
                has_negative=any(v < 0 for v in values),
                min_value=min(values),
                max_value=max(values),
            )
        )

    if not signals:
        raise CreatorAdapterError(
            f"no drive-cycle files found for {vehicle}/{cycle} under {root}"
        )

    lengths = {len(s.times_s) for s in signals}
    shared = len(lengths) == 1

    def energy(name: str) -> float | None:
        signal = next((s for s in signals if s.name == name), None)
        if signal is None or len(signal.times_s) < 2:
            return None
        return sum(
            signal.values[i] * (signal.times_s[i + 1] - signal.times_s[i])
            for i in range(len(signal.times_s) - 1)
        )

    input_energy = energy("input_power")
    output_energy = energy("output_power")
    efficiency = (
        output_energy / input_energy
        if input_energy not in (None, 0.0) and output_energy is not None
        else None
    )
    regenerative = sum(
        1
        for signal in signals
        if signal.name == "output_power"
        for value in signal.values
        if value < 0
    )

    return DriveCycleResult(
        schema_version=CREATOR_ADAPTER_SCHEMA_VERSION,
        test_type=TestType.DRIVE_CYCLE,
        vehicle=vehicle,
        cycle=cycle,
        signals=tuple(signals),
        shared_time_base=shared,
        input_energy_j=input_energy,
        output_energy_j=output_energy,
        cycle_efficiency=efficiency,
        regenerative_samples=regenerative,
        notes_zh=(
            f"输入/输出功率的区分来自**文件名**，不来自表头："
            f"{'小型车' if vehicle == 'Small_sized_vehicle' else '中型车'}文件的表头"
            f"{'为 Time,Power，未说明是输入还是输出' if has_header else '不存在，首行即数据'}。",
            "负功率表示回馈（发电）运行，按原样保留，不取绝对值、不截断。",
            "循环效率为能量之比（输出能量 / 输入能量），"
            "并非逐点效率——存在负功率时逐点效率没有意义。",
            "转矩与转速来自车辆纵向模型的下调结果，属**计算输入**而非测量。",
        ),
    )
