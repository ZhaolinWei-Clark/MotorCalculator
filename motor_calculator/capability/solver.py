"""Phase 12: the whole capability picture for one design.

Assembles the envelope, samples it adaptively, and answers the questions a user
actually asks: how fast, how much torque, how much power, and where does the
behaviour change.

Adaptive sampling
-----------------
A uniform grid wastes points in the flat constant-torque region and misses the
knee at base speed, which is the one place the curve is not smooth. Sampling is
therefore concentrated where the physics changes: around base speed, around the
maximum speed, and around any point where the active constraint set changes.
The result is deterministic -- the same design always produces the same sample
speeds -- because every refinement is derived from solved quantities, never from
a random or time-dependent source.

Constant power
--------------
Whether a machine exhibits a constant-power region is a *result*, not a target.
The flatness of ``P = T * omega_m`` above base speed is measured and reported.
Nothing forces a plateau, and a machine that does not have one is reported as
not having one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .conventions import mechanical_rad_s_to_rpm, rpm_to_mechanical_rad_s
from .envelope import (
    ENVELOPE_SCHEMA_VERSION,
    BaseSpeed,
    EnvelopePoint,
    MaximumSpeed,
    Region,
    _envelope_point,
    solve_base_speed,
    solve_maximum_speed,
)
from .limits import CurrentLimit, Modulation, VoltageLimit, current_limit_from_rms, voltage_limit
from .parameters import CapabilityParameters
from .steady_state import MTPAPoint, mtpa_locus, mtpa_point

SOLVER_SCHEMA_VERSION = "phase12.capability_solver.v1"

#: A region is called "constant power" when the power over it varies by less
#: than this fraction of its mean. An engineering reporting threshold, declared
#: as such; it decides what we *call* the region, never what we compute.
CONSTANT_POWER_FLATNESS_TOLERANCE = 0.05
CONSTANT_POWER_CLASSIFICATION = "ENGINEERING_REPORTING_THRESHOLD"


@dataclass(frozen=True)
class ConstantPowerAssessment:
    """Whether a constant-power region exists, measured rather than assumed."""

    exists: bool
    start_rpm: float | None
    end_rpm: float | None
    mean_power_w: float | None
    power_spread_percent: float | None
    ratio_to_base_speed: float | None
    tolerance: float
    classification: str
    note_zh: str


@dataclass(frozen=True)
class CapabilityResult:
    """Everything the capability solver determined for one design."""

    schema_version: str
    parameters: CapabilityParameters
    current_limit: CurrentLimit
    voltage_limit: VoltageLimit
    base_speed: BaseSpeed
    maximum_speed: MaximumSpeed
    mtpa_at_limit: MTPAPoint
    mtpa_locus: tuple[MTPAPoint, ...]
    envelope: tuple[EnvelopePoint, ...]
    constant_power: ConstantPowerAssessment
    peak_torque_nm: float
    peak_power_w: float
    peak_power_speed_rpm: float
    warnings_zh: tuple[str, ...] = ()

    @property
    def feasible_points(self) -> tuple[EnvelopePoint, ...]:
        return tuple(point for point in self.envelope if point.feasible)

    def point_at(self, speed_rpm: float) -> EnvelopePoint | None:
        """The solved envelope point nearest a requested speed."""

        feasible = self.feasible_points
        if not feasible:
            return None
        return min(feasible, key=lambda item: abs(item.speed_rpm - speed_rpm))

    def regions_present(self) -> tuple[Region, ...]:
        seen: list[Region] = []
        for point in self.envelope:
            if point.region not in seen:
                seen.append(point.region)
        return tuple(seen)

    @property
    def field_weakening_active(self) -> bool:
        return any(
            point.feasible and point.id_a < -1.0e-9 for point in self.envelope
        )


def _sample_speeds(
    base_speed: BaseSpeed,
    maximum_speed: MaximumSpeed,
    *,
    low_speed_points: int,
    weakening_points: int,
) -> tuple[float, ...]:
    """Deterministic, adaptive speed samples."""

    top = maximum_speed.speed_rpm
    knee = base_speed.speed_rpm if base_speed.resolved else top * 0.25
    knee = max(min(knee, top), 0.0)

    speeds: list[float] = []
    # Constant-torque region: a handful of points is enough, the curve is flat.
    for index in range(low_speed_points):
        speeds.append(knee * index / max(low_speed_points - 1, 1))
    # Dense immediately around the knee, where the constraint set changes.
    for fraction in (0.98, 0.995, 1.005, 1.02, 1.05):
        candidate = knee * fraction
        if 0.0 <= candidate <= top:
            speeds.append(candidate)
    # Field-weakening region: geometric spacing, dense near the knee where the
    # curvature is, sparse where it is nearly hyperbolic.
    if top > knee:
        for index in range(1, weakening_points + 1):
            fraction = index / weakening_points
            speeds.append(knee + (top - knee) * fraction**1.6)
    # The two endpoints that matter most.
    for fraction in (0.995, 0.999, 1.0):
        speeds.append(top * fraction)

    unique = sorted({round(value, 6) for value in speeds if value >= 0.0})
    return tuple(unique)


def _assess_constant_power(
    envelope: tuple[EnvelopePoint, ...], base_speed: BaseSpeed
) -> ConstantPowerAssessment:
    """Measure the flatness of P above base speed. Never force a plateau."""

    if not base_speed.resolved:
        return ConstantPowerAssessment(
            exists=False, start_rpm=None, end_rpm=None, mean_power_w=None,
            power_spread_percent=None, ratio_to_base_speed=None,
            tolerance=CONSTANT_POWER_FLATNESS_TOLERANCE,
            classification=CONSTANT_POWER_CLASSIFICATION,
            note_zh="基速无解，因此不存在可供评估的弱磁区。",
        )

    above = [
        point
        for point in envelope
        if point.feasible and point.speed_rpm > base_speed.speed_rpm * 1.001
    ]
    if len(above) < 3:
        return ConstantPowerAssessment(
            exists=False, start_rpm=None, end_rpm=None, mean_power_w=None,
            power_spread_percent=None, ratio_to_base_speed=None,
            tolerance=CONSTANT_POWER_FLATNESS_TOLERANCE,
            classification=CONSTANT_POWER_CLASSIFICATION,
            note_zh=(
                "基速以上的可行工作点不足三个：该机器/逆变器组合几乎没有弱磁区，"
                "因此不存在恒功率段。**这是如实报告，不是缺陷。**"
            ),
        )

    # The widest contiguous span that is flat within tolerance, rather than the
    # spread over everything above base speed. Immediately above the knee the
    # power is still climbing out of the constant-torque region, and including
    # that ramp would report "no constant power" for a machine that plainly has
    # one. Searching for the widest flat window measures the plateau where it
    # actually is; it does not create one, and a machine without a flat span
    # still returns exists=False.
    powers = [point.mechanical_power_w for point in above]

    def flat(lo: int, hi: int) -> bool:
        window = powers[lo : hi + 1]
        centre = sum(window) / len(window)
        if centre <= 0.0:
            return False
        return (max(window) - min(window)) / centre <= CONSTANT_POWER_FLATNESS_TOLERANCE

    best_span = (0, 0)
    for start_index in range(len(above)):
        end_index = start_index
        while end_index + 1 < len(above) and flat(start_index, end_index + 1):
            end_index += 1
        if end_index - start_index > best_span[1] - best_span[0]:
            best_span = (start_index, end_index)

    lo, hi = best_span
    window = powers[lo : hi + 1]
    mean = sum(window) / len(window)
    spread = (
        (max(window) - min(window)) / mean if mean > 0.0 and len(window) > 1
        else float("inf")
    )
    # A plateau needs to span a real speed range, not two adjacent samples.
    exists = (
        hi > lo
        and spread <= CONSTANT_POWER_FLATNESS_TOLERANCE
        and above[hi].speed_rpm >= above[lo].speed_rpm * 1.2
    )
    start = above[lo].speed_rpm
    end = above[hi].speed_rpm
    ratio = end / start if start else None
    return ConstantPowerAssessment(
        exists=exists,
        start_rpm=start,
        end_rpm=end,
        mean_power_w=mean,
        power_spread_percent=spread * 100.0,
        ratio_to_base_speed=ratio,
        tolerance=CONSTANT_POWER_FLATNESS_TOLERANCE,
        classification=CONSTANT_POWER_CLASSIFICATION,
        note_zh=(
            (
                f"最宽平坦区为 {start:.0f} – {end:.0f} rpm（跨度 {ratio:.2f}×），"
                f"其间功率波动 {spread * 100.0:.2f} %，"
                f"在 {CONSTANT_POWER_FLATNESS_TOLERANCE * 100.0:.0f} % 的报告阈值之内，"
                f"可视为恒功率区，平均功率 {mean:.1f} W。"
                "该区间由实测平坦度搜索得到，不是预先假定的。"
            )
            if exists
            else (
                f"基速以上找不到足够宽的平坦区（最宽候选段波动 {spread * 100.0:.2f} %，"
                f"阈值 {CONSTANT_POWER_FLATNESS_TOLERANCE * 100.0:.0f} %）："
                "该机器/逆变器组合**没有**表现出恒功率平台。"
                "本软件不会为了得到平台而修改任何量。"
            )
        ),
    )


def solve_capability(
    parameters: CapabilityParameters,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
    *,
    low_speed_points: int = 6,
    weakening_points: int = 24,
    search_ceiling_rpm: float = 6.0e4,
) -> CapabilityResult:
    """Solve the full capability envelope for one design."""

    base = solve_base_speed(parameters, current_limit, voltage_limit_obj)
    maximum = solve_maximum_speed(
        parameters, current_limit, voltage_limit_obj,
        search_ceiling_rpm=search_ceiling_rpm,
    )

    speeds = _sample_speeds(
        base, maximum,
        low_speed_points=low_speed_points,
        weakening_points=weakening_points,
    )
    envelope = tuple(
        _envelope_point(
            parameters,
            rpm_to_mechanical_rad_s(rpm) * parameters.pole_pairs,
            current_limit,
            voltage_limit_obj,
        )
        for rpm in speeds
    )

    feasible = [point for point in envelope if point.feasible]
    peak_torque = max((point.torque_nm for point in feasible), default=0.0)
    peak_power_point = (
        max(feasible, key=lambda item: item.mechanical_power_w) if feasible else None
    )

    warnings: list[str] = list(parameters.warnings_zh)
    if not base.resolved:
        warnings.append(base.note_zh)
    if not maximum.bounded:
        warnings.append(maximum.note_zh)

    return CapabilityResult(
        schema_version=SOLVER_SCHEMA_VERSION,
        parameters=parameters,
        current_limit=current_limit,
        voltage_limit=voltage_limit_obj,
        base_speed=base,
        maximum_speed=maximum,
        mtpa_at_limit=mtpa_point(parameters, current_limit.peak_a),
        mtpa_locus=mtpa_locus(parameters, current_limit.peak_a, points=21),
        envelope=envelope,
        constant_power=_assess_constant_power(envelope, base),
        peak_torque_nm=peak_torque,
        peak_power_w=peak_power_point.mechanical_power_w if peak_power_point else 0.0,
        peak_power_speed_rpm=peak_power_point.speed_rpm if peak_power_point else 0.0,
        warnings_zh=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Convenience entry point from a production analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InverterSettings:
    """The inverter inputs a capability study needs. Persisted with a project."""

    dc_bus_voltage_v: float
    modulation: Modulation = Modulation.SVPWM
    voltage_utilization: float = 1.0
    #: Phase RMS, matching how the project stores currents.
    current_limit_rms_a: float | None = None
    low_speed_points: int = 6
    weakening_points: int = 24

    def resolved_current_limit(self, fallback_rms_a: float) -> CurrentLimit:
        return current_limit_from_rms(
            self.current_limit_rms_a
            if self.current_limit_rms_a
            else fallback_rms_a,
            source="project" if self.current_limit_rms_a is None else "user",
        )


def solve_from_analysis(
    result,
    parameters_mapping,
    settings: InverterSettings | None = None,
    **bridge_kwargs,
) -> CapabilityResult:
    """Solve capability straight from a production analysis result."""

    from .parameters import bridge_from_analysis

    capability_parameters = bridge_from_analysis(
        result, parameters_mapping, **bridge_kwargs
    )
    performance = result.performance
    bus = float(
        getattr(result.electrical, "dc_bus_voltage_v", 0.0)
        or parameters_mapping.get("V_dc", 0.0)
    )
    settings = settings or InverterSettings(dc_bus_voltage_v=bus)
    limit = settings.resolved_current_limit(
        float(getattr(performance, "phase_current_rms_a", 0.0))
    )
    return solve_capability(
        capability_parameters,
        limit,
        voltage_limit(
            settings.dc_bus_voltage_v or bus,
            modulation=settings.modulation,
            utilization=settings.voltage_utilization,
        ),
        low_speed_points=settings.low_speed_points,
        weakening_points=settings.weakening_points,
    )
