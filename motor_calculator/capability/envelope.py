"""Phase 12: the capability envelope -- base speed, field weakening, max speed.

The solver is deterministic and closed-form at its core, not a black-box
optimiser. The structure comes from one observation:

    For a fixed ``id`` and a fixed speed, ``|V|^2`` is a *quadratic in iq*.

Writing ``vd = A + B iq`` and ``vq = C + D iq`` with

    A = Rs id,  B = -omega_e Lq,  C = omega_e (Ld id + psi),  D = Rs

gives ``|V|^2 = (B^2 + D^2) iq^2 + 2(AB + CD) iq + (A^2 + C^2)``, so the largest
``iq`` the voltage limit permits at that ``id`` has a closed-form solution. The
current limit gives another bound, ``iq <= sqrt(Imax^2 - id^2)``. And torque is
monotonic in ``iq`` for fixed ``id`` whenever

    dT/diq = 1.5 p (psi + (Ld - Lq) id) > 0

so the best ``iq`` is simply the smaller of the two bounds. The two-dimensional
constrained maximisation therefore collapses to a one-dimensional scan over
``id`` with an exact answer at every step -- refined by golden section, which is
a bracketing method on a scalar, not an optimiser over the physics.

Where ``dT/diq <= 0`` the extra ``iq`` no longer buys torque, and that is the
condition itself telling us we have passed the maximum-torque-per-volt locus.
It is honoured rather than clamped away.

Regions are classified from **which constraints are active**, never from speed
thresholds, because a speed threshold is a consequence and not a cause.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .conventions import mechanical_rad_s_to_rpm, rpm_to_mechanical_rad_s
from .limits import CurrentLimit, VoltageLimit
from .parameters import CapabilityParameters
from .steady_state import (
    OperatingPoint,
    mtpa_point,
    operating_point,
    torque_nm,
    voltage_magnitude,
)

ENVELOPE_SCHEMA_VERSION = "phase12.envelope.v1"

#: Relative tolerance for calling a constraint active.
CONSTRAINT_TOLERANCE = 1.0e-6


class Region(str, Enum):
    """Which constraints are binding at an operating point."""

    #: Region I. On the MTPA locus at the current limit; voltage has margin.
    MTPA_CURRENT_LIMITED = "MTPA_CURRENT_LIMITED"
    #: Region II. Both the current circle and the voltage ellipse are active.
    CURRENT_AND_VOLTAGE_LIMITED = "CURRENT_AND_VOLTAGE_LIMITED"
    #: Region III. Voltage-limited inside the current circle (MTPV-like).
    VOLTAGE_LIMITED_FIELD_WEAKENING = "VOLTAGE_LIMITED_FIELD_WEAKENING"
    #: No point satisfies both constraints with positive torque.
    NO_FEASIBLE_OPERATING_POINT = "NO_FEASIBLE_OPERATING_POINT"


REGION_LABELS_ZH = {
    Region.MTPA_CURRENT_LIMITED: "MTPA / 电流受限（恒转矩区）",
    Region.CURRENT_AND_VOLTAGE_LIMITED: "电流与电压同时受限（弱磁区）",
    Region.VOLTAGE_LIMITED_FIELD_WEAKENING: "仅电压受限（深度弱磁 / MTPV）",
    Region.NO_FEASIBLE_OPERATING_POINT: "无可行工作点",
}


@dataclass(frozen=True)
class EnvelopePoint:
    """One speed on the capability envelope."""

    speed_rpm: float
    omega_m_rad_s: float
    omega_e_rad_s: float
    id_a: float
    iq_a: float
    vd_v: float
    vq_v: float
    current_magnitude_a: float
    voltage_magnitude_v: float
    torque_nm: float
    mechanical_power_w: float
    current_utilization: float
    voltage_utilization: float
    region: Region
    feasible: bool
    active_constraints: tuple[str, ...]

    @property
    def region_label_zh(self) -> str:
        return REGION_LABELS_ZH[self.region]


def _max_iq_for_voltage(
    parameters: CapabilityParameters,
    id_a: float,
    omega_e: float,
    voltage_peak_limit: float,
) -> float | None:
    """Largest non-negative ``iq`` satisfying the voltage limit, closed form.

    Returns ``None`` when no ``iq >= 0`` satisfies it at this ``id``.
    """

    A = parameters.Rs * id_a
    B = -omega_e * parameters.Lq
    C = omega_e * (parameters.Ld * id_a + parameters.psi_pm)
    D = parameters.Rs

    a = B * B + D * D
    b = 2.0 * (A * B + C * D)
    c = A * A + C * C - voltage_peak_limit * voltage_peak_limit

    if a <= 0.0:
        # Rs == 0 and omega_e == 0: voltage is independent of iq.
        return math.inf if c <= 0.0 else None
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return None
    root = math.sqrt(discriminant)
    upper = (-b + root) / (2.0 * a)
    lower = (-b - root) / (2.0 * a)
    if upper < 0.0:
        return None
    # The feasible interval is [lower, upper]; we want the largest iq >= 0 in it.
    return upper if lower <= 0.0 or upper >= lower else None


def _best_iq_at_id(
    parameters: CapabilityParameters,
    id_a: float,
    omega_e: float,
    current_limit: CurrentLimit,
    voltage_peak_limit: float,
) -> tuple[float, float] | None:
    """The torque-maximising ``iq`` at this ``id``, and the torque it gives."""

    circle = current_limit.peak_a * current_limit.peak_a - id_a * id_a
    if circle < 0.0:
        return None
    iq_current = math.sqrt(circle)

    iq_voltage = _max_iq_for_voltage(parameters, id_a, omega_e, voltage_peak_limit)
    if iq_voltage is None:
        return None

    slope = parameters.psi_pm + (parameters.Ld - parameters.Lq) * id_a
    if slope <= 0.0:
        # More iq no longer increases torque at this id. The stationary point
        # is iq = 0, which produces no torque: this id is simply not useful.
        return None

    iq = min(iq_current, iq_voltage)
    if iq < 0.0:
        return None
    return iq, torque_nm(parameters, id_a, iq)


def solve_max_torque_at_speed(
    parameters: CapabilityParameters,
    omega_e_rad_s: float,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
    *,
    scan_points: int = 401,
    refine_iterations: int = 60,
) -> OperatingPoint | None:
    """Maximum torque at one speed under both constraints.

    A scan over ``id`` with an exact ``iq`` at each point, then golden-section
    refinement around the best bracket. Deterministic: the same inputs always
    give the same output, to the last bit.
    """

    limit_peak = voltage_limit_obj.phase_peak_v
    imax = current_limit.peak_a

    # id is searched from -Imax to 0 for a machine with psi > 0: positive id
    # both costs current and (for Lq > Ld) reduces torque. Inverse-salient
    # machines are handled by extending the range to the positive side.
    lower_id = -imax
    upper_id = imax if parameters.saliency_h < 0.0 else 0.0

    best: tuple[float, float, float] | None = None  # (torque, id, iq)
    samples: list[tuple[float, float | None]] = []
    for index in range(scan_points):
        fraction = index / (scan_points - 1)
        id_a = lower_id + (upper_id - lower_id) * fraction
        found = _best_iq_at_id(parameters, id_a, omega_e_rad_s, current_limit, limit_peak)
        samples.append((id_a, None if found is None else found[1]))
        if found is None:
            continue
        iq, value = found
        if best is None or value > best[0]:
            best = (value, id_a, iq)

    if best is None:
        return None

    # Golden-section refinement on id, bracketed by the neighbours of the best
    # scan sample. This refines a scalar within a known bracket; it does not
    # search the physics.
    step = (upper_id - lower_id) / (scan_points - 1)
    left = max(lower_id, best[1] - step)
    right = min(upper_id, best[1] + step)
    golden = (math.sqrt(5.0) - 1.0) / 2.0

    def evaluate(id_a: float) -> float:
        found = _best_iq_at_id(parameters, id_a, omega_e_rad_s, current_limit, limit_peak)
        return -math.inf if found is None else found[1]

    a_point, b_point = left, right
    c_point = b_point - golden * (b_point - a_point)
    d_point = a_point + golden * (b_point - a_point)
    for _ in range(refine_iterations):
        if evaluate(c_point) > evaluate(d_point):
            b_point = d_point
        else:
            a_point = c_point
        c_point = b_point - golden * (b_point - a_point)
        d_point = a_point + golden * (b_point - a_point)
    candidate_id = 0.5 * (a_point + b_point)
    refined = _best_iq_at_id(parameters, candidate_id, omega_e_rad_s, current_limit, limit_peak)
    if refined is not None and refined[1] > best[0]:
        best = (refined[1], candidate_id, refined[0])

    return operating_point(parameters, best[1], best[2], omega_e_rad_s)


def classify_region(
    point: OperatingPoint,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
    parameters: CapabilityParameters,
) -> tuple[Region, tuple[str, ...]]:
    """Classify by which constraints are active, not by speed."""

    current_active = (
        point.current_magnitude_a >= current_limit.peak_a * (1.0 - CONSTRAINT_TOLERANCE)
    )
    voltage_active = (
        point.voltage_magnitude_v
        >= voltage_limit_obj.phase_peak_v * (1.0 - CONSTRAINT_TOLERANCE)
    )
    active: list[str] = []
    if current_active:
        active.append("CURRENT_LIMIT")
    if voltage_active:
        active.append("VOLTAGE_LIMIT")

    # On the MTPA locus the d-axis current is the unconstrained optimum for the
    # current magnitude in use; checking that is what distinguishes region I
    # from a coincidence of magnitudes.
    if current_active and not voltage_active:
        active.append("MTPA_LOCUS")
        return Region.MTPA_CURRENT_LIMITED, tuple(active)
    if current_active and voltage_active:
        return Region.CURRENT_AND_VOLTAGE_LIMITED, tuple(active)
    if voltage_active:
        return Region.VOLTAGE_LIMITED_FIELD_WEAKENING, tuple(active)
    return Region.MTPA_CURRENT_LIMITED, tuple(active or ("NONE",))


def _envelope_point(
    parameters: CapabilityParameters,
    omega_e: float,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
) -> EnvelopePoint:
    omega_m = omega_e / parameters.pole_pairs
    solved = solve_max_torque_at_speed(
        parameters, omega_e, current_limit, voltage_limit_obj
    )
    if solved is None:
        return EnvelopePoint(
            speed_rpm=mechanical_rad_s_to_rpm(omega_m),
            omega_m_rad_s=omega_m,
            omega_e_rad_s=omega_e,
            id_a=float("nan"), iq_a=float("nan"),
            vd_v=float("nan"), vq_v=float("nan"),
            current_magnitude_a=float("nan"),
            voltage_magnitude_v=float("nan"),
            torque_nm=0.0,
            mechanical_power_w=0.0,
            current_utilization=float("nan"),
            voltage_utilization=float("nan"),
            region=Region.NO_FEASIBLE_OPERATING_POINT,
            feasible=False,
            active_constraints=("INFEASIBLE",),
        )
    region, active = classify_region(solved, current_limit, voltage_limit_obj, parameters)
    return EnvelopePoint(
        speed_rpm=mechanical_rad_s_to_rpm(omega_m),
        omega_m_rad_s=omega_m,
        omega_e_rad_s=omega_e,
        id_a=solved.id_a,
        iq_a=solved.iq_a,
        vd_v=solved.vd_v,
        vq_v=solved.vq_v,
        current_magnitude_a=solved.current_magnitude_a,
        voltage_magnitude_v=solved.voltage_magnitude_v,
        torque_nm=solved.torque_nm,
        mechanical_power_w=solved.mechanical_power_w,
        current_utilization=solved.current_magnitude_a / current_limit.peak_a,
        voltage_utilization=solved.voltage_magnitude_v / voltage_limit_obj.phase_peak_v,
        region=region,
        feasible=True,
        active_constraints=active,
    )


# ---------------------------------------------------------------------------
# Base speed (Step 9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaseSpeed:
    """The speed at which the unconstrained MTPA point first hits the voltage limit."""

    schema_version: str
    speed_rpm: float
    omega_m_rad_s: float
    omega_e_rad_s: float
    id_a: float
    iq_a: float
    torque_nm: float
    voltage_magnitude_v: float
    current_utilization: float
    voltage_utilization: float
    resolved: bool
    note_zh: str


def solve_base_speed(
    parameters: CapabilityParameters,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
    *,
    max_speed_rpm: float = 1.0e6,
    iterations: int = 200,
) -> BaseSpeed:
    """Find where the MTPA point at full current reaches the voltage limit.

    Base speed is **not** rated speed. It is a property of the machine and the
    inverter together, and the two coincide only by chance.
    """

    mtpa = mtpa_point(parameters, current_limit.peak_a)
    limit = voltage_limit_obj.phase_peak_v

    def excess(omega_e: float) -> float:
        return voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, omega_e) - limit

    omega_e_max = rpm_to_mechanical_rad_s(max_speed_rpm) * parameters.pole_pairs
    if excess(0.0) > 0.0:
        # Even at standstill the resistive drop exceeds the inverter voltage.
        return BaseSpeed(
            schema_version=ENVELOPE_SCHEMA_VERSION,
            speed_rpm=0.0, omega_m_rad_s=0.0, omega_e_rad_s=0.0,
            id_a=mtpa.id_a, iq_a=mtpa.iq_a, torque_nm=mtpa.torque_nm,
            voltage_magnitude_v=voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, 0.0),
            current_utilization=1.0,
            voltage_utilization=voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, 0.0) / limit,
            resolved=False,
            note_zh=(
                "在零转速下，满电流 MTPA 点所需电压已超过逆变器可用电压："
                "该电流上限在此母线电压下无法建立。基速无解。"
            ),
        )
    if excess(omega_e_max) < 0.0:
        return BaseSpeed(
            schema_version=ENVELOPE_SCHEMA_VERSION,
            speed_rpm=max_speed_rpm,
            omega_m_rad_s=rpm_to_mechanical_rad_s(max_speed_rpm),
            omega_e_rad_s=omega_e_max,
            id_a=mtpa.id_a, iq_a=mtpa.iq_a, torque_nm=mtpa.torque_nm,
            voltage_magnitude_v=voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, omega_e_max),
            current_utilization=1.0,
            voltage_utilization=voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, omega_e_max) / limit,
            resolved=False,
            note_zh=(
                f"直到 {max_speed_rpm:.0f} rpm，满电流 MTPA 点仍未触及电压上限："
                "在所检查的转速范围内不存在基速。"
            ),
        )

    low, high = 0.0, omega_e_max
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        if excess(middle) < 0.0:
            low = middle
        else:
            high = middle
    omega_e = 0.5 * (low + high)
    omega_m = omega_e / parameters.pole_pairs
    magnitude = voltage_magnitude(parameters, mtpa.id_a, mtpa.iq_a, omega_e)
    return BaseSpeed(
        schema_version=ENVELOPE_SCHEMA_VERSION,
        speed_rpm=mechanical_rad_s_to_rpm(omega_m),
        omega_m_rad_s=omega_m,
        omega_e_rad_s=omega_e,
        id_a=mtpa.id_a,
        iq_a=mtpa.iq_a,
        torque_nm=mtpa.torque_nm,
        voltage_magnitude_v=magnitude,
        current_utilization=1.0,
        voltage_utilization=magnitude / limit,
        resolved=True,
        note_zh=(
            "基速定义为**满电流 MTPA 工作点首次触及电压上限**的转速。"
            "它由机器与逆变器共同决定，与额定转速没有必然关系。"
        ),
    )


# ---------------------------------------------------------------------------
# Maximum speed (Step 12)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaximumSpeed:
    schema_version: str
    speed_rpm: float
    omega_m_rad_s: float
    omega_e_rad_s: float
    id_a: float
    iq_a: float
    torque_nm: float
    mechanical_power_w: float
    active_constraints: tuple[str, ...]
    bounded: bool
    note_zh: str


#: Torque below which an operating point is treated as no longer useful. The
#: envelope asymptotically approaches zero torque, so "maximum speed" needs a
#: stated threshold rather than a limit nobody wrote down.
MINIMUM_USEFUL_TORQUE_NM = 1.0e-6


def solve_maximum_speed(
    parameters: CapabilityParameters,
    current_limit: CurrentLimit,
    voltage_limit_obj: VoltageLimit,
    *,
    search_ceiling_rpm: float = 6.0e4,
    iterations: int = 120,
) -> MaximumSpeed:
    """The highest speed with a feasible, torque-producing operating point.

    Never extrapolated: the answer is always a speed at which a point was
    actually solved.
    """

    def feasible(rpm: float) -> OperatingPoint | None:
        omega_e = rpm_to_mechanical_rad_s(rpm) * parameters.pole_pairs
        found = solve_max_torque_at_speed(
            parameters, omega_e, current_limit, voltage_limit_obj
        )
        if found is None or found.torque_nm <= MINIMUM_USEFUL_TORQUE_NM:
            return None
        return found

    if feasible(search_ceiling_rpm) is not None:
        point = feasible(search_ceiling_rpm)
        return MaximumSpeed(
            schema_version=ENVELOPE_SCHEMA_VERSION,
            speed_rpm=search_ceiling_rpm,
            omega_m_rad_s=point.omega_m_rad_s,
            omega_e_rad_s=point.omega_e_rad_s,
            id_a=point.id_a, iq_a=point.iq_a,
            torque_nm=point.torque_nm,
            mechanical_power_w=point.mechanical_power_w,
            active_constraints=("SEARCH_CEILING",),
            bounded=False,
            note_zh=(
                f"在搜索上限 {search_ceiling_rpm:.0f} rpm 处仍存在可行工作点："
                "该机器/逆变器组合在本模型下不存在有限最高转速"
                f"（特征电流 {parameters.characteristic_current_a:.3f} A 不大于电流上限 "
                f"{current_limit.peak_a:.3f} A）。此处报告的是搜索上限，不是外推值。"
            ),
        )

    low, high = 0.0, search_ceiling_rpm
    if feasible(low + 1.0e-6) is None:
        return MaximumSpeed(
            schema_version=ENVELOPE_SCHEMA_VERSION,
            speed_rpm=0.0, omega_m_rad_s=0.0, omega_e_rad_s=0.0,
            id_a=float("nan"), iq_a=float("nan"),
            torque_nm=0.0, mechanical_power_w=0.0,
            active_constraints=("INFEASIBLE",),
            bounded=True,
            note_zh="在任何转速下都不存在可行工作点。",
        )
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        if feasible(middle) is not None:
            low = middle
        else:
            high = middle
    point = feasible(low)
    if point is None:  # pragma: no cover - low is feasible by construction
        point = feasible(low * 0.999999)
    return MaximumSpeed(
        schema_version=ENVELOPE_SCHEMA_VERSION,
        speed_rpm=mechanical_rad_s_to_rpm(point.omega_m_rad_s),
        omega_m_rad_s=point.omega_m_rad_s,
        omega_e_rad_s=point.omega_e_rad_s,
        id_a=point.id_a,
        iq_a=point.iq_a,
        torque_nm=point.torque_nm,
        mechanical_power_w=point.mechanical_power_w,
        active_constraints=("VOLTAGE_LIMIT",),
        bounded=True,
        note_zh=(
            "最高转速由电压上限决定：再高的转速下，两个约束的交集中"
            "不再存在产生正转矩的工作点。该值由实际求解得到，未作外推。"
        ),
    )
