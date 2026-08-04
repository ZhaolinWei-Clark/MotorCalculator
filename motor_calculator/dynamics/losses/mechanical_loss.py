"""Mechanical loss monitor consistent with existing viscous damping."""

from __future__ import annotations

import math


class MechanicalLossModel:
    @staticmethod
    def compute_viscous_loss(
        omega_m_rad_s: float,
        viscous_damping_nms: float,
    ) -> float:
        for name, value in (
            ("omega_m_rad_s", omega_m_rad_s),
            ("viscous_damping_nms", viscous_damping_nms),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if viscous_damping_nms < 0.0:
            raise ValueError("viscous_damping_nms must be non-negative")
        return viscous_damping_nms * omega_m_rad_s**2
