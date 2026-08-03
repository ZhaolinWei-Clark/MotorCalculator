"""Current-control components for the isolated dynamics sandbox."""

from .dq_current_controller import (
    DQCurrentController,
    DQSaturationFeedback,
    DQVoltageCommand,
)
from .dq_decoupling import (
    DQDecouplingFeedforward,
    compute_pmsm_dq_decoupling_feedforward,
)
from .field_weakening import (
    FieldWeakeningController,
    FieldWeakeningResult,
    FieldWeakeningVoltageEstimate,
)
from .mtpa import MTPAController, MTPACurrentReference
from .pi_controller import PIController
from .speed_controller import (
    SpeedController,
    SpeedControllerConfig,
    SpeedControllerOutput,
    SpeedControllerState,
)

__all__ = [
    "DQCurrentController",
    "DQDecouplingFeedforward",
    "DQSaturationFeedback",
    "DQVoltageCommand",
    "FieldWeakeningController",
    "FieldWeakeningResult",
    "FieldWeakeningVoltageEstimate",
    "MTPAController",
    "MTPACurrentReference",
    "PIController",
    "SpeedController",
    "SpeedControllerConfig",
    "SpeedControllerOutput",
    "SpeedControllerState",
    "compute_pmsm_dq_decoupling_feedforward",
]
