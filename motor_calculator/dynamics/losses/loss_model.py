"""Composition of optional dynamic loss monitors."""

from __future__ import annotations

import math

from ..pmsm_model import PMSMDynamicParameters
from ..state import MotorState
from .copper_loss import CopperLossModel
from .iron_loss import IronLossModel, UnavailableIronLossModel
from .loss_results import LossBreakdown, LossModelConfig
from .mechanical_loss import MechanicalLossModel


class DynamicLossModel:
    """Compute monitoring-only losses without changing plant derivatives."""

    def __init__(
        self,
        config: LossModelConfig | None = None,
        iron_loss_model: IronLossModel | None = None,
    ) -> None:
        self.config = config or LossModelConfig()
        self.iron_loss_model = iron_loss_model or UnavailableIronLossModel()

    def compute(
        self,
        state: MotorState,
        parameters: PMSMDynamicParameters,
        winding_temperature_c: float,
        effective_phase_resistance_ohm: float,
        flux_density_proxy: float | None = None,
    ) -> LossBreakdown:
        if not math.isfinite(winding_temperature_c):
            raise ValueError("winding_temperature_c must be finite")
        if (
            not math.isfinite(effective_phase_resistance_ohm)
            or effective_phase_resistance_ohm < 0.0
        ):
            raise ValueError(
                "effective_phase_resistance_ohm must be finite and non-negative"
            )

        assumptions: list[str] = []
        warnings: list[str] = []
        copper_loss = 0.0
        if self.config.enable_copper_loss:
            copper_loss = CopperLossModel.compute_from_dq_peak(
                state.id, state.iq, effective_phase_resistance_ohm
            )
            assumptions.append(
                "Amplitude-invariant dq currents are peak values of a balanced sinusoid."
            )

        iron_loss = 0.0
        if self.config.enable_iron_loss:
            electrical_frequency_hz = (
                abs(parameters.pole_pairs * state.omega_m) / math.tau
            )
            estimate = self.iron_loss_model.compute(
                electrical_frequency_hz,
                flux_density_proxy,
                winding_temperature_c,
            )
            iron_loss = estimate.loss_w
            assumptions.extend(estimate.assumptions)
            warnings.extend(estimate.warning_messages)

        mechanical_loss = 0.0
        if self.config.enable_mechanical_loss:
            mechanical_loss = MechanicalLossModel.compute_viscous_loss(
                state.omega_m, parameters.B
            )
            assumptions.append(
                "Mechanical loss monitors existing viscous damping and is not subtracted twice."
            )

        total_loss = copper_loss + (iron_loss or 0.0) + mechanical_loss
        return LossBreakdown(
            copper_loss_w=copper_loss,
            iron_loss_w=iron_loss,
            mechanical_loss_w=mechanical_loss,
            total_loss_w=total_loss,
            assumptions=tuple(dict.fromkeys(assumptions)),
            warning_messages=tuple(dict.fromkeys(warnings)),
        )
