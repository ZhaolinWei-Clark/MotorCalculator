"""Phase 11B: deterministic harmonic analysis of a measured waveform.

Written to be checkable by hand rather than fast. The whole value of this module
is that it reproduces a published number from raw data without being tuned to
do so, and that property is only credible if the method is stated exactly.

The method
----------
The waveform is sampled against *rotor angle*, not time, and the samples are not
exactly evenly spaced (the CREATOR back-EMF file steps by 0.040-0.050 mechanical
degrees). A plain FFT would require resampling and would introduce an
interpolation choice into a result that is supposed to be an observation.

So the projection is a direct numerical integral against the basis functions:

    a_k = (2/Theta) * sum_i  y_i * cos(k * p * theta_i) * dtheta_i
    b_k = (2/Theta) * sum_i  y_i * sin(k * p * theta_i) * dtheta_i
    A_k = sqrt(a_k^2 + b_k^2)

where ``theta`` is mechanical angle in radians, ``p`` is the pole-pair count
(so ``k = 1`` is the electrical fundamental), ``dtheta_i`` is the interval to the
next sample, and ``Theta`` is the total span actually integrated. Dividing by the
measured span rather than by an assumed 2*pi means a file covering 360.0076
degrees is normalised by what it really covers.

``A_k`` is an **amplitude (peak)**, not an RMS value and not a peak-to-peak
value. For a sinusoid, RMS = A_k / sqrt(2). This is stated because the single
most common way to get a back-EMF constant wrong by 41 % is to disagree with
yourself about which of those three a number is.

No windowing is applied: the record spans whole periods of the quantity of
interest, so windowing would attenuate the very component being measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

HARMONICS_SCHEMA_VERSION = "phase11b.harmonics.v1"

#: Harmonic orders extracted by default. Even orders are included because their
#: presence is diagnostic: a healthy symmetric machine should show almost none,
#: so a large h2 means an asymmetry or a measurement problem, not a feature.
DEFAULT_ORDERS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 9, 11, 13)

#: Orders entering the THD sum: every extracted order above the fundamental.
THD_ORDERS: tuple[int, ...] = tuple(k for k in DEFAULT_ORDERS if k > 1)


class WaveformError(ValueError):
    """The samples cannot support a harmonic analysis."""


@dataclass(frozen=True)
class Harmonic:
    """One extracted component."""

    order: int
    #: Peak amplitude in the waveform's own unit.
    amplitude: float
    #: Phase in radians, from the cosine reference.
    phase_rad: float
    #: Amplitude as a fraction of the fundamental. ``None`` if no fundamental.
    ratio_to_fundamental: float | None

    @property
    def rms(self) -> float:
        """Only meaningful for a single sinusoidal component."""

        return self.amplitude / math.sqrt(2.0)

    @property
    def percent_of_fundamental(self) -> float | None:
        if self.ratio_to_fundamental is None:
            return None
        return self.ratio_to_fundamental * 100.0


@dataclass(frozen=True)
class WaveformAnalysis:
    """Everything the harmonic projection produced, with its normalisation."""

    schema_version: str
    sample_count: int
    #: Mechanical degrees actually covered by the record.
    angle_span_deg: float
    pole_pairs: int
    #: Electrical periods contained in the record.
    electrical_periods: float
    harmonics: tuple[Harmonic, ...]
    #: Largest and smallest raw sample, before any processing.
    raw_max: float
    raw_min: float
    #: max(|y|) over the raw record.
    raw_peak: float
    #: RMS of the whole record, all harmonics included.
    total_rms: float
    mean: float
    #: Total harmonic distortion over :data:`THD_ORDERS`.
    thd: float | None
    method_note: str

    def order(self, k: int) -> Harmonic | None:
        for harmonic in self.harmonics:
            if harmonic.order == k:
                return harmonic
        return None

    @property
    def fundamental(self) -> Harmonic | None:
        return self.order(1)

    @property
    def fundamental_peak(self) -> float | None:
        harmonic = self.fundamental
        return None if harmonic is None else harmonic.amplitude

    @property
    def fundamental_rms(self) -> float | None:
        """Fundamental peak / sqrt(2). The fundamental alone, not the record."""

        peak = self.fundamental_peak
        return None if peak is None else peak / math.sqrt(2.0)

    @property
    def crest_ratio(self) -> float | None:
        """Raw peak over fundamental peak.

        Above 1 means the waveform is peakier than its fundamental, so reading a
        "peak voltage" straight off the record overstates the fundamental by
        exactly this factor.
        """

        peak = self.fundamental_peak
        return None if not peak else self.raw_peak / peak


def analyze_waveform(
    angles_deg: Sequence[float],
    values: Sequence[float],
    *,
    pole_pairs: int = 1,
    orders: Sequence[int] = DEFAULT_ORDERS,
) -> WaveformAnalysis:
    """Project a measured waveform onto its harmonics.

    ``angles_deg`` are *mechanical* degrees. ``pole_pairs`` converts to the
    electrical basis, so order 1 is the electrical fundamental.
    """

    angle = [float(a) for a in angles_deg]
    y = [float(v) for v in values]
    if len(angle) != len(y):
        raise WaveformError("angle and value arrays must be the same length")
    if len(angle) < 8:
        raise WaveformError(
            f"a harmonic analysis needs a populated record; got {len(angle)} samples"
        )
    if any(not math.isfinite(v) for v in (*angle, *y)):
        raise WaveformError("every sample must be finite")
    if int(pole_pairs) < 1:
        raise WaveformError("pole_pairs must be at least 1")
    pole_pairs = int(pole_pairs)

    span_deg = max(angle) - min(angle)
    if span_deg <= 0.0:
        raise WaveformError("the record covers no angle span")

    # Interval weights: each sample carries the angle to the next one. The last
    # sample takes the mean interval, so a record ending one step short of a
    # full revolution is not silently truncated.
    steps = [angle[i + 1] - angle[i] for i in range(len(angle) - 1)]
    if any(step < 0 for step in steps):
        raise WaveformError(
            "samples must be ordered by increasing angle; this record is not "
            "monotonic and would alias if integrated as-is"
        )
    mean_step = sum(steps) / len(steps) if steps else 0.0
    weights = [*steps, mean_step]
    total = sum(weights)
    if total <= 0.0:
        raise WaveformError("total integration span is zero")

    harmonics: list[Harmonic] = []
    amplitudes: dict[int, float] = {}
    for k in sorted({int(order) for order in orders if int(order) >= 1}):
        a = b = 0.0
        for value, theta, weight in zip(y, angle, weights):
            phase = math.radians(theta) * pole_pairs * k
            a += value * math.cos(phase) * math.radians(weight)
            b += value * math.sin(phase) * math.radians(weight)
        scale = 2.0 / math.radians(total)
        a *= scale
        b *= scale
        amplitudes[k] = math.hypot(a, b)
        harmonics.append(
            Harmonic(
                order=k,
                amplitude=amplitudes[k],
                phase_rad=math.atan2(b, a),
                ratio_to_fundamental=None,
            )
        )

    fundamental = amplitudes.get(1)
    if fundamental:
        harmonics = [
            Harmonic(h.order, h.amplitude, h.phase_rad, h.amplitude / fundamental)
            for h in harmonics
        ]

    thd = None
    if fundamental:
        squares = sum(
            amplitudes[k] ** 2 for k in THD_ORDERS if k in amplitudes
        )
        thd = math.sqrt(squares) / fundamental

    weighted_square = sum(
        value * value * weight for value, weight in zip(y, weights)
    )
    weighted_mean = sum(value * weight for value, weight in zip(y, weights)) / total

    return WaveformAnalysis(
        schema_version=HARMONICS_SCHEMA_VERSION,
        sample_count=len(y),
        angle_span_deg=span_deg,
        pole_pairs=pole_pairs,
        electrical_periods=span_deg / 360.0 * pole_pairs,
        harmonics=tuple(harmonics),
        raw_max=max(y),
        raw_min=min(y),
        raw_peak=max(abs(max(y)), abs(min(y))),
        total_rms=math.sqrt(weighted_square / total),
        mean=weighted_mean,
        thd=thd,
        method_note=(
            "直接数值投影，不重采样、不加窗；按实际角度跨度归一化。"
            "幅值为**峰值**，不是有效值，也不是峰峰值。"
        ),
    )


def describe_analysis_zh(analysis: WaveformAnalysis, unit: str = "") -> str:
    """A readable summary that never leaves the basis implicit."""

    suffix = f" {unit}" if unit else ""
    lines = [
        f"样本数：{analysis.sample_count}",
        f"角度跨度：{analysis.angle_span_deg:.4f}° 机械"
        f"（{analysis.electrical_periods:.4f} 个电周期，极对数 {analysis.pole_pairs}）",
        f"原始最大值：{analysis.raw_max:.6g}{suffix}",
        f"原始最小值：{analysis.raw_min:.6g}{suffix}",
        f"原始峰值 max|y|：{analysis.raw_peak:.6g}{suffix}",
        f"整个记录的有效值（含全部谐波）：{analysis.total_rms:.6g}{suffix}",
        f"平均值：{analysis.mean:.6g}{suffix}",
    ]
    fundamental = analysis.fundamental
    if fundamental is not None:
        lines.extend(
            [
                "",
                f"基波峰值：{fundamental.amplitude:.6g}{suffix}",
                f"基波有效值（= 峰值 / √2）：{analysis.fundamental_rms:.6g}{suffix}",
            ]
        )
        if analysis.crest_ratio is not None:
            lines.append(
                f"原始峰值 / 基波峰值：{analysis.crest_ratio:.4f}"
                + (
                    "　← 波形明显非正弦；直接把原始峰值当作基波会高估"
                    f" {(analysis.crest_ratio - 1.0) * 100.0:.1f} %"
                    if analysis.crest_ratio > 1.02
                    else ""
                )
            )
    if analysis.thd is not None:
        lines.append(f"THD（{min(THD_ORDERS)}–{max(THD_ORDERS)} 次）：{analysis.thd * 100.0:.3f} %")
    lines.extend(["", "谐波（电气次数，峰值）："])
    for harmonic in analysis.harmonics:
        ratio = (
            "" if harmonic.percent_of_fundamental is None
            else f"  ({harmonic.percent_of_fundamental:7.3f} % 基波)"
        )
        lines.append(f"  h{harmonic.order:<3} {harmonic.amplitude:12.6g}{suffix}{ratio}")
    lines.extend(["", f"方法：{analysis.method_note}"])
    return "\n".join(lines)
