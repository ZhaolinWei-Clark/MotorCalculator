"""Phase 12: the inverter voltage limit and the current limit.

The voltage limit is where peak-versus-RMS confusion does the most damage,
because every plausible convention differs from every other by a factor between
1.15 and 1.73, and all of them are "the voltage limit".

So the derivation is written out rather than asserted.

SVPWM linear limit
------------------
A three-phase inverter's realisable voltage vectors form a hexagon of
circumradius ``2*Vdc/3``. The largest *circle* inscribed in that hexagon has
radius equal to the hexagon's inradius:

    r = (2*Vdc/3) * cos(30 deg) = (2*Vdc/3) * (sqrt(3)/2) = Vdc/sqrt(3)

Within that circle the modulator is linear and the output is undistorted. With
the amplitude-invariant transform this project uses, that radius *is* the
available **phase-voltage peak**:

    V_phase_peak_max = Vdc / sqrt(3)          ~= 0.5774 * Vdc
    V_phase_rms_max  = Vdc / sqrt(6)          ~= 0.4082 * Vdc
    V_line_rms_max   = Vdc / sqrt(2)          ~= 0.7071 * Vdc

``dynamics/modulation/svpwm.py`` already uses ``Vdc/sqrt(3)`` as its linear
envelope, so the capability solver and the switching model agree.

SPWM linear limit
-----------------
Without third-harmonic injection each phase modulates independently about the
mid-point, so the phase peak cannot exceed half the bus:

    V_phase_peak_max = Vdc / 2                = 0.5 * Vdc

SVPWM is larger by ``2/sqrt(3)`` = 1.1547, the familiar 15.47 % advantage.

The utilisation factor
----------------------
Real drives do not run to the edge of the linear region: current regulators need
headroom to act. A factor is supported, defaults to 1.0 (no reserve), and is
labelled ``ENGINEERING_ASSUMPTION`` wherever it appears. It is not a physical
constant and it is never folded silently into a limit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .conventions import (
    SQRT2,
    SQRT3,
    phase_peak_to_line_rms,
    phase_peak_to_rms,
    phase_rms_to_peak,
)

LIMITS_SCHEMA_VERSION = "phase12.limits.v1"


class Modulation(str, Enum):
    """How the inverter synthesises the voltage vector."""

    SVPWM = "SVPWM"
    SPWM = "SPWM"


MODULATION_LABELS_ZH = {
    Modulation.SVPWM: "空间矢量调制 SVPWM",
    Modulation.SPWM: "正弦脉宽调制 SPWM（无三次谐波注入）",
}

#: Phase-peak voltage available per volt of DC bus, in the linear region.
MODULATION_PHASE_PEAK_PER_VDC = {
    Modulation.SVPWM: 1.0 / SQRT3,
    Modulation.SPWM: 0.5,
}

MODULATION_DERIVATION_ZH = {
    Modulation.SVPWM: (
        "逆变器可实现电压矢量构成外接圆半径 2·Vdc/3 的六边形；"
        "其**内切圆**半径为 (2·Vdc/3)·cos30° = Vdc/√3，"
        "圆内调制为线性且输出无畸变。"
        "在幅值不变 Park 变换下，该半径即可用的**相电压峰值**。"
    ),
    Modulation.SPWM: (
        "无三次谐波注入时各相独立围绕中点调制，"
        "相电压峰值不超过母线电压之半：Vdc/2。"
        "较 SVPWM 低 2/√3 = 1.1547 倍（即 15.47 %）。"
    ),
}

#: Default utilisation. 1.0 means "use the whole linear region".
DEFAULT_UTILIZATION = 1.0
UTILIZATION_CLASSIFICATION = "ENGINEERING_ASSUMPTION"
UTILIZATION_NOTE_ZH = (
    "电压利用率是**工程假设**，不是物理常数。"
    "实际驱动器需要留出调节裕度，常取 0.90–0.95；"
    "本软件默认 1.0（用满线性区），且绝不把该系数悄悄并入任何限值。"
)


class LimitError(ValueError):
    """A limit was requested from inputs that cannot define one."""


@dataclass(frozen=True)
class VoltageLimit:
    """The usable inverter voltage, in every basis, with its derivation."""

    schema_version: str
    dc_bus_voltage_v: float
    modulation: Modulation
    utilization: float
    utilization_classification: str
    #: The limit the dq solver uses. Phase peak, matching vd/vq.
    phase_peak_v: float
    phase_rms_v: float
    line_rms_v: float
    derivation_zh: str

    @property
    def phase_peak_per_vdc(self) -> float:
        return self.phase_peak_v / self.dc_bus_voltage_v


def voltage_limit(
    dc_bus_voltage_v: float,
    *,
    modulation: Modulation | str = Modulation.SVPWM,
    utilization: float = DEFAULT_UTILIZATION,
) -> VoltageLimit:
    """Usable phase-peak voltage from the DC bus, derived not asserted."""

    bus = float(dc_bus_voltage_v)
    if not math.isfinite(bus) or bus <= 0.0:
        raise LimitError(f"DC bus voltage must be positive and finite, got {bus!r}")
    strategy = modulation if isinstance(modulation, Modulation) else Modulation(str(modulation).upper())
    factor = float(utilization)
    if not math.isfinite(factor) or not 0.0 < factor <= 1.0:
        raise LimitError(
            f"voltage utilization must lie in (0, 1]; got {factor!r}. "
            "Values above 1 would mean overmodulation, which this steady-state "
            "solver does not model."
        )

    peak = bus * MODULATION_PHASE_PEAK_PER_VDC[strategy] * factor
    return VoltageLimit(
        schema_version=LIMITS_SCHEMA_VERSION,
        dc_bus_voltage_v=bus,
        modulation=strategy,
        utilization=factor,
        utilization_classification=UTILIZATION_CLASSIFICATION,
        phase_peak_v=peak,
        phase_rms_v=phase_peak_to_rms(peak),
        line_rms_v=phase_peak_to_line_rms(peak),
        derivation_zh=(
            f"{MODULATION_DERIVATION_ZH[strategy]}\n"
            f"V_phase_peak = {bus:.4f} V × {MODULATION_PHASE_PEAK_PER_VDC[strategy]:.6f}"
            f" × {factor:.4f}（利用率）= {peak:.6f} V\n"
            f"等价表示：相有效值 {phase_peak_to_rms(peak):.6f} V，"
            f"线有效值 {phase_peak_to_line_rms(peak):.6f} V\n"
            f"{UTILIZATION_NOTE_ZH}"
        ),
    )


@dataclass(frozen=True)
class CurrentLimit:
    """The usable current, stated in both bases so neither is assumed."""

    schema_version: str
    #: The limit the dq solver uses: the dq vector magnitude, a phase peak.
    peak_a: float
    rms_a: float
    source: str
    note_zh: str

    def contains(self, id_a: float, iq_a: float, tolerance: float = 1.0e-9) -> bool:
        return math.hypot(id_a, iq_a) <= self.peak_a * (1.0 + tolerance)


def current_limit_from_rms(phase_current_rms_a: float, *, source: str = "project") -> CurrentLimit:
    """Convert a stored phase-RMS current into the dq magnitude limit.

    The conversion is the whole point of this function existing: the project
    stores RMS, the dq constraint circle is in peak, and the two differ by 41 %.
    """

    rms = float(phase_current_rms_a)
    if not math.isfinite(rms) or rms <= 0.0:
        raise LimitError(f"phase RMS current limit must be positive, got {rms!r}")
    peak = phase_rms_to_peak(rms)
    return CurrentLimit(
        schema_version=LIMITS_SCHEMA_VERSION,
        peak_a=peak,
        rms_a=rms,
        source=source,
        note_zh=(
            f"项目以**相有效值**存储电流（{rms:.6f} A）。"
            f"dq 电流圆的约束是**峰值**，故显式换算 ×√2 得 {peak:.6f} A。"
            "二者相差 41.4 %，因此这一步绝不省略。"
        ),
    )


def current_limit_from_peak(phase_current_peak_a: float, *, source: str = "user") -> CurrentLimit:
    peak = float(phase_current_peak_a)
    if not math.isfinite(peak) or peak <= 0.0:
        raise LimitError(f"phase peak current limit must be positive, got {peak!r}")
    return CurrentLimit(
        schema_version=LIMITS_SCHEMA_VERSION,
        peak_a=peak,
        rms_a=phase_peak_to_rms(peak),
        source=source,
        note_zh="电流上限以相电流**峰值**直接给出，与 dq 约定一致。",
    )
