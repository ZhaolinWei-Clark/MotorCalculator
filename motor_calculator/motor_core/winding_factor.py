"""Fundamental winding-factor derivation from the slot EMF star.

This module is GUI-independent and contains no legacy compatibility factors.
It answers exactly one question: given the slot/pole/phase combination and an
explicit coil span, what is the fundamental winding factor `k_w1`, and how was
it obtained?

Design rules enforced here:

* The distribution factor is derived from the actual slot EMF phasor star
  (Bianchi/Dai Pre "star of slots"), not from the integer-slot closed form.
  The star handles integer and fractional `q` with the same code path, which is
  required for fractional-slot concentrated AFPM windings.
* Nothing is invented. The coil span is an explicit input. When it is absent,
  the resolution reports NOT_ENOUGH_GEOMETRY instead of assuming full pitch.
* Only the fundamental is used by the production model. Harmonic orders are
  available for inspection but are never collapsed into the production scalar.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


DEFAULT_PHASES = 3


class WindingFactorMode(str, Enum):
    """User-selected policy for obtaining `k_w`."""

    AUTO = "auto"
    MANUAL = "manual"


class WindingFactorProvenance(str, Enum):
    """Where the displayed winding factor actually came from."""

    AUTO_GEOMETRY = "AUTO_GEOMETRY"
    MANUAL_USER = "MANUAL_USER"
    PRESET = "PRESET"
    LEGACY_PROJECT = "LEGACY_PROJECT"
    NOT_ENOUGH_GEOMETRY = "NOT_ENOUGH_GEOMETRY"
    NOT_SUPPORTED_FOR_AUTO_CALCULATION = "NOT_SUPPORTED_FOR_AUTO_CALCULATION"


PROVENANCE_LABELS_ZH = {
    WindingFactorProvenance.AUTO_GEOMETRY: "自动计算",
    WindingFactorProvenance.MANUAL_USER: "手动指定",
    WindingFactorProvenance.PRESET: "预设提供",
    WindingFactorProvenance.LEGACY_PROJECT: "历史项目沿用",
    WindingFactorProvenance.NOT_ENOUGH_GEOMETRY: "几何信息不足",
    WindingFactorProvenance.NOT_SUPPORTED_FOR_AUTO_CALCULATION: "当前拓扑不支持自动计算",
}


WINDING_FACTOR_MODE_LABELS_ZH = {
    WindingFactorMode.AUTO: "自动计算",
    WindingFactorMode.MANUAL: "手动指定",
}

WINDING_FACTOR_TOOLTIP_ZH = (
    "绕组系数反映绕组分布、线圈节距和偏斜等因素对基波电势/磁动势的影响。"
    "若当前模型具有完整绕组几何，则自动计算；否则可由用户手动提供。"
    "自动模式需要槽数、极对数和线圈节距三项同时可用。"
)

COIL_SPAN_TOOLTIP_ZH = (
    "线圈节距，以跨过的槽数表示。整距对应 Q/(2p) 槽。"
    "整距不是几何必然结果，因此不会被自动假设；留空则退回手动指定模式。"
)

SKEW_TOOLTIP_ZH = (
    "斜槽/斜极量，以槽距为单位。0 表示未建模偏斜，此时 k_s = 1.000。"
)


class WindingFactorError(ValueError):
    """Raised when a winding-factor derivation input is structurally invalid."""


@dataclass(frozen=True)
class SlotStarAllocation:
    """Phase-A coil sides of the slot EMF star, with series-connection signs."""

    slots: int
    pole_pairs: int
    phases: int
    slot_electrical_angle_rad: float
    phase_a_slots: tuple[int, ...]
    phase_a_signs: tuple[int, ...]
    balanced: bool


@dataclass(frozen=True)
class WindingFactorBreakdown:
    """Fully traceable fundamental winding-factor derivation."""

    fundamental_winding_factor: float
    distribution_factor: float
    pitch_factor: float
    skew_factor: float
    slots: int
    pole_pairs: int
    pole_count: int
    phases: int
    slots_per_pole_per_phase: float
    slot_electrical_angle_deg: float
    full_pitch_slots: float
    coil_span_slots: int
    coil_span_electrical_deg: float
    skew_slots: float
    skew_electrical_deg: float
    winding_layout: str
    method: str
    assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fundamental_winding_factor": self.fundamental_winding_factor,
            "distribution_factor": self.distribution_factor,
            "pitch_factor": self.pitch_factor,
            "skew_factor": self.skew_factor,
            "slots": self.slots,
            "pole_pairs": self.pole_pairs,
            "pole_count": self.pole_count,
            "phases": self.phases,
            "slots_per_pole_per_phase": self.slots_per_pole_per_phase,
            "slot_electrical_angle_deg": self.slot_electrical_angle_deg,
            "full_pitch_slots": self.full_pitch_slots,
            "coil_span_slots": self.coil_span_slots,
            "coil_span_electrical_deg": self.coil_span_electrical_deg,
            "skew_slots": self.skew_slots,
            "skew_electrical_deg": self.skew_electrical_deg,
            "winding_layout": self.winding_layout,
            "method": self.method,
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True)
class WindingFactorResolution:
    """The winding factor actually used, plus why it is trustworthy or not."""

    value: float | None
    mode: WindingFactorMode
    provenance: WindingFactorProvenance
    breakdown: WindingFactorBreakdown | None
    reason_zh: str
    manual_value: float | None = None

    @property
    def provenance_label_zh(self) -> str:
        return PROVENANCE_LABELS_ZH[self.provenance]

    @property
    def is_auto(self) -> bool:
        return self.provenance is WindingFactorProvenance.AUTO_GEOMETRY

    def to_dict(self) -> dict[str, Any]:
        return {
            "winding_factor": self.value,
            "winding_factor_mode": self.mode.value,
            "winding_factor_provenance": self.provenance.value,
            "winding_factor_provenance_label_zh": self.provenance_label_zh,
            "winding_factor_reason_zh": self.reason_zh,
            "winding_factor_manual_value": self.manual_value,
            "winding_factor_breakdown": None if self.breakdown is None else self.breakdown.to_dict(),
        }


def slot_electrical_angle_rad(slots: int, pole_pairs: int) -> float:
    """Electrical angle between two physically adjacent slots."""

    if slots <= 0 or pole_pairs <= 0:
        raise WindingFactorError("slots and pole_pairs must be positive integers")
    return 2.0 * math.pi * float(pole_pairs) / float(slots)


def full_pitch_slots(slots: int, pole_pairs: int) -> float:
    """Coil span, in slots, that spans exactly 180 electrical degrees."""

    if slots <= 0 or pole_pairs <= 0:
        raise WindingFactorError("slots and pole_pairs must be positive integers")
    return float(slots) / (2.0 * float(pole_pairs))


def slots_per_pole_per_phase(slots: int, pole_pairs: int, phases: int = DEFAULT_PHASES) -> float:
    """`q`, which is deliberately allowed to be fractional."""

    if phases <= 0:
        raise WindingFactorError("phases must be a positive integer")
    return float(slots) / (2.0 * float(pole_pairs) * float(phases))


def build_slot_star(
    slots: int, pole_pairs: int, phases: int = DEFAULT_PHASES
) -> SlotStarAllocation:
    """Allocate slot EMF phasors to phase A using symmetric phase belts.

    Each slot `k` carries an EMF phasor at electrical angle `k * alpha`. Phase A
    owns the belt centred on 0 electrical degrees (positive series sense) and the
    belt centred on 180 electrical degrees (reversed series sense). The belts are
    `180 / phases` electrical degrees wide, which is the standard symmetric
    allocation and is valid for fractional `q`.
    """

    alpha = slot_electrical_angle_rad(slots, pole_pairs)
    belt_count = 2 * phases

    # Belt assignment is done in exact integer arithmetic. The electrical angle
    # of slot k is 2*pi*(k*p mod Q)/Q, and the belt centred on 0 spans a half
    # width of 2*pi/(4m). Evaluating the boundary in floating point puts
    # phasors that land exactly on a belt edge on either side depending on
    # rounding, which silently unbalances integer-slot windings such as
    # Q=24, 2p=4. The integer form below is boundary-exact.
    phase_slots: list[int] = []
    phase_signs: list[int] = []
    phase_population = [0] * phases
    for slot_index in range(slots):
        residue = (slot_index * pole_pairs) % slots
        belt = ((residue * 4 * phases + slots) // (2 * slots)) % belt_count
        phase_population[belt % phases] += 1
        if belt == 0:
            phase_slots.append(slot_index)
            phase_signs.append(1)
        elif belt == phases:
            phase_slots.append(slot_index)
            phase_signs.append(-1)

    # A symmetric three-phase winding requires every phase to own the same
    # number of coil sides. Individual belts may differ for fractional-slot
    # windings (for example Q=9, 2p=8), so belt population is not the criterion.
    expected_per_phase, remainder = divmod(slots, phases)
    balanced = (
        remainder == 0
        and all(count == expected_per_phase for count in phase_population)
        and len(phase_slots) == expected_per_phase
    )

    return SlotStarAllocation(
        slots=slots,
        pole_pairs=pole_pairs,
        phases=phases,
        slot_electrical_angle_rad=alpha,
        phase_a_slots=tuple(phase_slots),
        phase_a_signs=tuple(phase_signs),
        balanced=balanced,
    )


def distribution_factor(
    slots: int, pole_pairs: int, phases: int = DEFAULT_PHASES, harmonic: int = 1
) -> float:
    """`k_d` for the requested harmonic, from the slot EMF star."""

    if harmonic <= 0:
        raise WindingFactorError("harmonic must be a positive integer")
    star = build_slot_star(slots, pole_pairs, phases)
    if not star.phase_a_slots:
        raise WindingFactorError("slot star produced an empty phase belt")
    total = complex(0.0, 0.0)
    for slot_index, sign in zip(star.phase_a_slots, star.phase_a_signs):
        angle = harmonic * slot_index * star.slot_electrical_angle_rad
        total += sign * cmath.exp(1j * angle)
    return abs(total) / float(len(star.phase_a_slots))


def pitch_factor(
    coil_span_slots: int, slots: int, pole_pairs: int, harmonic: int = 1
) -> float:
    """`k_p` for the requested harmonic from an explicit coil span."""

    if harmonic <= 0:
        raise WindingFactorError("harmonic must be a positive integer")
    if coil_span_slots <= 0:
        raise WindingFactorError("coil_span_slots must be a positive integer")
    span_rad = coil_span_slots * slot_electrical_angle_rad(slots, pole_pairs)
    return abs(math.sin(harmonic * span_rad / 2.0))


def skew_factor(
    skew_slots: float, slots: int, pole_pairs: int, harmonic: int = 1
) -> float:
    """`k_s` for the requested harmonic from an explicit skew, in slot pitches."""

    if harmonic <= 0:
        raise WindingFactorError("harmonic must be a positive integer")
    if skew_slots < 0.0:
        raise WindingFactorError("skew_slots must be non-negative")
    if skew_slots == 0.0:
        return 1.0
    skew_rad = skew_slots * slot_electrical_angle_rad(slots, pole_pairs)
    half = harmonic * skew_rad / 2.0
    return abs(math.sin(half) / half)


def compute_fundamental_winding_factor(
    *,
    slots: int,
    pole_pairs: int,
    coil_span_slots: int,
    skew_slots: float = 0.0,
    phases: int = DEFAULT_PHASES,
) -> WindingFactorBreakdown:
    """`k_w1 = k_d1 * k_p1 * k_s1` with a fully explicit derivation record."""

    star = build_slot_star(slots, pole_pairs, phases)
    if not star.balanced:
        raise WindingFactorError(
            f"slot/pole combination Q={slots}, 2p={2 * pole_pairs}, m={phases} does not "
            "produce a balanced symmetric winding"
        )
    alpha = star.slot_electrical_angle_rad
    span_rad = coil_span_slots * alpha
    if not 0.0 < span_rad < 2.0 * math.pi:
        raise WindingFactorError(
            "coil span must be greater than zero and less than one full electrical period"
        )

    k_d = distribution_factor(slots, pole_pairs, phases, harmonic=1)
    k_p = pitch_factor(coil_span_slots, slots, pole_pairs, harmonic=1)
    k_s = skew_factor(skew_slots, slots, pole_pairs, harmonic=1)
    q = slots_per_pole_per_phase(slots, pole_pairs, phases)
    layout = "集中绕组（齿绕）" if q < 1.0 else "分布绕组"

    assumptions = (
        "三相对称绕组，相带按 180/m 电角度对称分配。",
        "每槽线圈边匝数相同，且同相线圈串联。",
        "分布系数由槽电势星形图直接求得，未假设 q 为整数。",
        "节距系数由用户显式给定的线圈节距求得，未假设整距。",
        "仅为基波绕组系数 k_w1，不代表任何谐波次数。",
    )
    if skew_slots == 0.0:
        assumptions = assumptions + ("未建模斜槽/斜极，k_s 取 1.000。",)

    return WindingFactorBreakdown(
        fundamental_winding_factor=k_d * k_p * k_s,
        distribution_factor=k_d,
        pitch_factor=k_p,
        skew_factor=k_s,
        slots=slots,
        pole_pairs=pole_pairs,
        pole_count=2 * pole_pairs,
        phases=phases,
        slots_per_pole_per_phase=q,
        slot_electrical_angle_deg=math.degrees(alpha),
        full_pitch_slots=full_pitch_slots(slots, pole_pairs),
        coil_span_slots=coil_span_slots,
        coil_span_electrical_deg=math.degrees(span_rad),
        skew_slots=float(skew_slots),
        skew_electrical_deg=math.degrees(skew_slots * alpha),
        winding_layout=layout,
        method="slot_emf_star_fundamental",
        assumptions=assumptions,
    )


def harmonic_winding_factors(
    *,
    slots: int,
    pole_pairs: int,
    coil_span_slots: int,
    skew_slots: float = 0.0,
    phases: int = DEFAULT_PHASES,
    harmonics: tuple[int, ...] = (1, 5, 7),
) -> dict[int, float]:
    """Inspection-only harmonic winding factors.

    The production model consumes only `k_w1`. These values exist so that the
    fundamental is never silently presented as if it described all harmonics.
    """

    values: dict[int, float] = {}
    for order in harmonics:
        values[order] = (
            distribution_factor(slots, pole_pairs, phases, harmonic=order)
            * pitch_factor(coil_span_slots, slots, pole_pairs, harmonic=order)
            * skew_factor(skew_slots, slots, pole_pairs, harmonic=order)
        )
    return values


def _coerce_positive_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_non_negative_float(value: Any, default: float = 0.0) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed) or parsed < 0.0:
        return default
    return parsed


def resolve_winding_factor(
    parameters: Mapping[str, Any],
    *,
    mode: WindingFactorMode | str = WindingFactorMode.MANUAL,
    coil_span_slots: Any = None,
    skew_slots: Any = None,
    manual_provenance: WindingFactorProvenance = WindingFactorProvenance.MANUAL_USER,
) -> WindingFactorResolution:
    """Resolve the winding factor to use, without ever inventing geometry.

    `parameters` is a parsed legacy GUI parameter mapping. The manual value in
    `parameters["k_w"]` is preserved verbatim whenever AUTO is not both selected
    and defensible, which is what keeps existing projects stable.
    """

    manual_value = float(parameters["k_w"])
    normalized_mode = (
        mode if isinstance(mode, WindingFactorMode) else WindingFactorMode(str(mode).strip().lower())
    )

    if normalized_mode is not WindingFactorMode.AUTO:
        return WindingFactorResolution(
            value=manual_value,
            mode=WindingFactorMode.MANUAL,
            provenance=manual_provenance,
            breakdown=None,
            reason_zh="当前为手动指定模式，绕组系数直接采用输入值，未由几何推导。",
            manual_value=manual_value,
        )

    slots = _coerce_positive_int(parameters.get("slots"))
    pole_pairs = _coerce_positive_int(parameters.get("p"))
    span = _coerce_positive_int(coil_span_slots)
    skew = _coerce_non_negative_float(skew_slots, 0.0)

    if slots is None or pole_pairs is None:
        return WindingFactorResolution(
            value=manual_value,
            mode=WindingFactorMode.MANUAL,
            provenance=WindingFactorProvenance.NOT_ENOUGH_GEOMETRY,
            breakdown=None,
            reason_zh="缺少有效的槽数或极对数，无法自动计算，已保留手动值。",
            manual_value=manual_value,
        )
    if span is None:
        return WindingFactorResolution(
            value=manual_value,
            mode=WindingFactorMode.MANUAL,
            provenance=WindingFactorProvenance.NOT_ENOUGH_GEOMETRY,
            breakdown=None,
            reason_zh=(
                "缺少线圈节距（跨槽数）。整距不是几何必然结果，因此不会假设，"
                "已保留手动值。"
            ),
            manual_value=manual_value,
        )

    try:
        breakdown = compute_fundamental_winding_factor(
            slots=slots,
            pole_pairs=pole_pairs,
            coil_span_slots=span,
            skew_slots=skew,
        )
    except WindingFactorError as exc:
        return WindingFactorResolution(
            value=manual_value,
            mode=WindingFactorMode.MANUAL,
            provenance=WindingFactorProvenance.NOT_SUPPORTED_FOR_AUTO_CALCULATION,
            breakdown=None,
            reason_zh=f"当前槽极/节距组合不支持自动计算（{exc}），已保留手动值。",
            manual_value=manual_value,
        )

    if not 0.0 < breakdown.fundamental_winding_factor <= 1.0:
        return WindingFactorResolution(
            value=manual_value,
            mode=WindingFactorMode.MANUAL,
            provenance=WindingFactorProvenance.NOT_SUPPORTED_FOR_AUTO_CALCULATION,
            breakdown=None,
            reason_zh="自动计算结果超出 (0, 1] 的有效范围，已保留手动值。",
            manual_value=manual_value,
        )

    return WindingFactorResolution(
        value=breakdown.fundamental_winding_factor,
        mode=WindingFactorMode.AUTO,
        provenance=WindingFactorProvenance.AUTO_GEOMETRY,
        breakdown=breakdown,
        reason_zh=(
            f"根据 Q={breakdown.slots}、2p={breakdown.pole_count}、m={breakdown.phases}、"
            f"线圈节距 {breakdown.coil_span_slots} 槽的槽电势星形图自动计算。"
        ),
        manual_value=manual_value,
    )


def format_winding_factor_summary_zh(resolution: WindingFactorResolution) -> str:
    """Compact Chinese summary suitable for an input-panel caption."""

    if resolution.value is None:
        return f"绕组系数不可用（{resolution.provenance_label_zh}）。{resolution.reason_zh}"
    header = (
        f"基波绕组系数 k_w1 = {resolution.value:.4f}（{resolution.provenance_label_zh}）"
    )
    if resolution.breakdown is None:
        return f"{header}\n{resolution.reason_zh}"
    breakdown = resolution.breakdown
    return (
        f"{header}\n"
        f"k_d = {breakdown.distribution_factor:.4f}  "
        f"k_p = {breakdown.pitch_factor:.4f}  "
        f"k_s = {breakdown.skew_factor:.4f}\n"
        f"Q={breakdown.slots} 2p={breakdown.pole_count} q={breakdown.slots_per_pole_per_phase:.3f} "
        f"节距 {breakdown.coil_span_slots} 槽（整距 {breakdown.full_pitch_slots:.2f} 槽）\n"
        f"{breakdown.winding_layout}；仅为基波，不代表谐波绕组系数。"
    )


def format_winding_factor_report_lines_zh(
    resolution: WindingFactorResolution,
) -> tuple[str, ...]:
    """Detailed engineering-report lines for the winding factor."""

    if resolution.value is None:
        return (
            f"   基波绕组系数 k_w1     : 不可用（{resolution.provenance_label_zh}）",
            f"   来源说明              : {resolution.reason_zh}",
        )
    lines = [
        f"   基波绕组系数 k_w1     : {resolution.value:.6f}（{resolution.provenance_label_zh}）",
        f"   来源说明              : {resolution.reason_zh}",
    ]
    breakdown = resolution.breakdown
    if breakdown is not None:
        lines.extend(
            [
                f"   分布系数 k_d          : {breakdown.distribution_factor:.6f}",
                f"   节距系数 k_p          : {breakdown.pitch_factor:.6f}",
                f"   偏斜系数 k_s          : {breakdown.skew_factor:.6f}",
                f"   槽极配合              : Q={breakdown.slots}, 2p={breakdown.pole_count}, "
                f"m={breakdown.phases}, q={breakdown.slots_per_pole_per_phase:.4f}",
                f"   槽距电角度            : {breakdown.slot_electrical_angle_deg:.3f}°",
                f"   线圈节距              : {breakdown.coil_span_slots} 槽 "
                f"({breakdown.coil_span_electrical_deg:.3f}° 电角度；整距 "
                f"{breakdown.full_pitch_slots:.3f} 槽)",
                f"   偏斜量                : {breakdown.skew_slots:.3f} 槽距 "
                f"({breakdown.skew_electrical_deg:.3f}° 电角度)",
                f"   绕组型式              : {breakdown.winding_layout}",
                f"   计算方法              : {breakdown.method}",
            ]
        )
        if resolution.manual_value is not None:
            lines.append(
                f"   手动输入值(未采用)    : {resolution.manual_value:.6f}"
            )
    return tuple(lines)
