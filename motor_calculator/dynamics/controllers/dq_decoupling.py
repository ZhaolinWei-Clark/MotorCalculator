"""Optional PMSM dq coupling feedforward for the FOC sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..pmsm_model import PMSMDynamicParameters


@dataclass(frozen=True)
class DQDecouplingFeedforward:
    """Calculated d- and q-axis feedforward voltages."""

    vd_ff_v: float
    vq_ff_v: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.vd_ff_v) or not math.isfinite(self.vq_ff_v):
            raise ValueError("dq decoupling voltages must be finite")


def compute_pmsm_dq_decoupling_feedforward(
    omega_e_rad_s: float,
    id_a: float,
    iq_a: float,
    motor_parameters: PMSMDynamicParameters,
    enabled: bool = True,
) -> DQDecouplingFeedforward:
    """Return optional PMSM cross-coupling and magnet-flux compensation."""

    for name, value in (
        ("omega_e_rad_s", omega_e_rad_s),
        ("id_a", id_a),
        ("iq_a", iq_a),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}")
    if not isinstance(motor_parameters, PMSMDynamicParameters):
        raise TypeError("motor_parameters must be PMSMDynamicParameters")
    if not isinstance(enabled, bool):
        raise TypeError("enabled must be a bool")
    if not enabled:
        return DQDecouplingFeedforward(vd_ff_v=0.0, vq_ff_v=0.0)

    return DQDecouplingFeedforward(
        vd_ff_v=-omega_e_rad_s * motor_parameters.Lq * iq_a,
        vq_ff_v=omega_e_rad_s
        * (motor_parameters.Ld * id_a + motor_parameters.psi_f),
    )
