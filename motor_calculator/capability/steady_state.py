"""Phase 12: the steady-state dq equations and the MTPA locus.

The equations are the steady state of ``dynamics/pmsm_model.py`` -- its
derivatives set to zero -- so the capability solver and the time-domain
simulation describe the same machine rather than two similar ones.

MTPA is solved in closed form, not searched. For a fixed current magnitude the
condition comes out of one derivative:

    T / (1.5 p) = (psi + (Ld - Lq) id) * sqrt(Is^2 - id^2)

    d/d id = 0
        =>  2 dL id^2 - psi id - dL Is^2 = 0,     dL = Lq - Ld
        =>  id = [psi - sqrt(psi^2 + 8 dL^2 Is^2)] / (4 dL)

the negative root being the one that produces positive reluctance torque for a
normal interior-PM machine. When ``dL`` vanishes the quadratic degenerates and
the answer is ``id = 0`` exactly, which is the non-salient result and is
returned as such rather than as the limit of a division.

:func:`mtpa_condition_residual` evaluates the analytical derivative directly, so
the closed form is checked against the condition it was derived from rather than
being trusted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .parameters import CapabilityParameters, MachineType

STEADY_STATE_SCHEMA_VERSION = "phase12.steady_state.v1"


@dataclass(frozen=True)
class OperatingPoint:
    """One dq operating point with everything it implies, bases declared."""

    id_a: float
    iq_a: float
    vd_v: float
    vq_v: float
    omega_e_rad_s: float
    omega_m_rad_s: float
    torque_nm: float

    @property
    def current_magnitude_a(self) -> float:
        """Phase-current peak, the dq vector magnitude."""

        return math.hypot(self.id_a, self.iq_a)

    @property
    def voltage_magnitude_v(self) -> float:
        """Phase-voltage peak, the dq vector magnitude."""

        return math.hypot(self.vd_v, self.vq_v)

    @property
    def mechanical_power_w(self) -> float:
        """``T_em * omega_m``. Electromagnetic, not shaft output."""

        return self.torque_nm * self.omega_m_rad_s

    @property
    def current_angle_deg(self) -> float:
        """Angle from the q axis, positive toward negative id (weakening)."""

        return math.degrees(math.atan2(-self.id_a, self.iq_a))


def torque_nm(parameters: CapabilityParameters, id_a: float, iq_a: float) -> float:
    """``T = 1.5 p (psi iq + (Ld - Lq) id iq)``, amplitude-invariant basis."""

    return 1.5 * parameters.pole_pairs * (
        parameters.psi_pm * iq_a + (parameters.Ld - parameters.Lq) * id_a * iq_a
    )


def dq_voltages(
    parameters: CapabilityParameters, id_a: float, iq_a: float, omega_e_rad_s: float
) -> tuple[float, float]:
    """Steady-state ``(vd, vq)``, phase peak."""

    vd = parameters.Rs * id_a - omega_e_rad_s * parameters.Lq * iq_a
    vq = parameters.Rs * iq_a + omega_e_rad_s * (parameters.Ld * id_a + parameters.psi_pm)
    return vd, vq


def voltage_magnitude(
    parameters: CapabilityParameters, id_a: float, iq_a: float, omega_e_rad_s: float
) -> float:
    vd, vq = dq_voltages(parameters, id_a, iq_a, omega_e_rad_s)
    return math.hypot(vd, vq)


def operating_point(
    parameters: CapabilityParameters, id_a: float, iq_a: float, omega_e_rad_s: float
) -> OperatingPoint:
    vd, vq = dq_voltages(parameters, id_a, iq_a, omega_e_rad_s)
    return OperatingPoint(
        id_a=id_a,
        iq_a=iq_a,
        vd_v=vd,
        vq_v=vq,
        omega_e_rad_s=omega_e_rad_s,
        omega_m_rad_s=omega_e_rad_s / parameters.pole_pairs,
        torque_nm=torque_nm(parameters, id_a, iq_a),
    )


# ---------------------------------------------------------------------------
# MTPA
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MTPAPoint:
    """The MTPA solution for one current magnitude."""

    current_magnitude_a: float
    id_a: float
    iq_a: float
    torque_nm: float
    method: str
    #: Residual of the analytical stationarity condition. Should be ~0.
    condition_residual: float

    @property
    def torque_per_amp_nm_per_a(self) -> float:
        """Per peak amp. Stated because per-RMS-amp differs by sqrt(2)."""

        return (
            self.torque_nm / self.current_magnitude_a
            if self.current_magnitude_a
            else 0.0
        )


def mtpa_condition_residual(
    parameters: CapabilityParameters, id_a: float, current_magnitude_a: float
) -> float:
    """``2 dL id^2 - psi id - dL Is^2``, the stationarity condition itself.

    Zero at the MTPA point. Evaluated independently of the closed form so the
    closed form can be checked rather than assumed.
    """

    dL = parameters.saliency_h
    return (
        2.0 * dL * id_a * id_a
        - parameters.psi_pm * id_a
        - dL * current_magnitude_a * current_magnitude_a
    )


def mtpa_point(parameters: CapabilityParameters, current_magnitude_a: float) -> MTPAPoint:
    """The maximum-torque-per-ampere point for a given current magnitude.

    Non-salient machines return ``id = 0`` exactly -- not approximately, and not
    as a numerical limit -- because with ``Ld == Lq`` the d-axis current
    contributes no torque at all and only costs current.
    """

    magnitude = float(current_magnitude_a)
    if magnitude < 0.0:
        raise ValueError("current magnitude must be non-negative")
    if magnitude == 0.0:
        return MTPAPoint(0.0, 0.0, 0.0, 0.0, "zero_current", 0.0)

    if not parameters.is_salient:
        return MTPAPoint(
            current_magnitude_a=magnitude,
            id_a=0.0,
            iq_a=magnitude,
            torque_nm=torque_nm(parameters, 0.0, magnitude),
            method="NON_SALIENT_ID_ZERO",
            condition_residual=0.0,
        )

    dL = parameters.saliency_h
    psi = parameters.psi_pm
    # 2 dL id^2 - psi id - dL Is^2 = 0
    discriminant = psi * psi + 8.0 * dL * dL * magnitude * magnitude
    root = math.sqrt(discriminant)
    # For Lq > Ld (dL > 0) the physical root is the one giving id < 0.
    # For Ld > Lq (dL < 0) the same expression yields id > 0, which is the
    # correct inverse-salient behaviour and is not forced negative.
    id_a = (psi - root) / (4.0 * dL)
    if abs(id_a) > magnitude:
        id_a = math.copysign(magnitude, id_a)
    iq_a = math.sqrt(max(magnitude * magnitude - id_a * id_a, 0.0))

    return MTPAPoint(
        current_magnitude_a=magnitude,
        id_a=id_a,
        iq_a=iq_a,
        torque_nm=torque_nm(parameters, id_a, iq_a),
        method="SALIENT_CLOSED_FORM",
        condition_residual=mtpa_condition_residual(parameters, id_a, magnitude),
    )


def mtpa_locus(
    parameters: CapabilityParameters, max_current_a: float, points: int = 41
) -> tuple[MTPAPoint, ...]:
    """The MTPA locus from zero up to a current magnitude."""

    if points < 2:
        raise ValueError("a locus needs at least two points")
    return tuple(
        mtpa_point(parameters, max_current_a * index / (points - 1))
        for index in range(points)
    )


def verify_mtpa_numerically(
    parameters: CapabilityParameters,
    current_magnitude_a: float,
    *,
    samples: int = 20001,
) -> tuple[float, float]:
    """Brute-force the MTPA point for cross-checking the closed form.

    Used by tests, not by the solver. Scans ``id`` across the current circle and
    returns the best ``(id, torque)`` found, so the analytical answer can be
    compared against an independent method.
    """

    best_id = 0.0
    best_torque = -math.inf
    for index in range(samples):
        fraction = index / (samples - 1)
        id_a = -current_magnitude_a + 2.0 * current_magnitude_a * fraction
        iq_a = math.sqrt(max(current_magnitude_a**2 - id_a * id_a, 0.0))
        value = torque_nm(parameters, id_a, iq_a)
        if value > best_torque:
            best_torque = value
            best_id = id_a
    return best_id, best_torque
