"""Phase 6B isolated PMSM time-domain simulation foundation."""

from .configuration import (
    FallbackPolicy,
    ResolvedSimulationSettings,
    SimulationAccuracy,
    SimulationConfig,
    SolverPreference,
    select_simulation_settings,
)
from .controllers import (
    DQCurrentController,
    DQDecouplingFeedforward,
    DQSaturationFeedback,
    DQVoltageCommand,
    PIController,
    compute_pmsm_dq_decoupling_feedforward,
)
from .current_control_runner import (
    CurrentControlSimulationRunner,
    CurrentReferenceProfile,
    DQCurrentReference,
)
from .foc_runner import (
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCSimulationResult,
    FOCStepInput,
    FOCStepOutput,
    ScalarProfile,
    run_foc_current_control_simulation,
)
from .integrators import DerivativeEvaluator, EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig, InverterVoltageLimiter, VoltageLimitResult
from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .simulation_results import SimulationConfidence, SimulationResult, SimulationStatus
from .simulation_runner import InputProfile, SimulationRunner
from .state import DQElectricalDerivatives, InputState, MotorState, StateDerivatives
from .transforms import (
    ABCPhaseValues,
    AlphaBetaValues,
    DQValues,
    clarke_transform,
    electrical_angle,
    inverse_clarke_transform,
    inverse_park_transform,
    park_transform,
    wrap_electrical_angle,
)
from .user_interface import StaticFallbackProvider, UserSimulationRunner, run_user_simulation

__all__ = [
    "ABCPhaseValues",
    "AlphaBetaValues",
    "EulerIntegrator",
    "DerivativeEvaluator",
    "DQElectricalDerivatives",
    "DQCurrentController",
    "DQDecouplingFeedforward",
    "DQCurrentReference",
    "DQVoltageCommand",
    "DQSaturationFeedback",
    "DQValues",
    "DCBusConfig",
    "FallbackPolicy",
    "FOCReference",
    "FOCRunner",
    "FOCRunnerConfig",
    "FOCSimulationResult",
    "FOCStepInput",
    "FOCStepOutput",
    "InputProfile",
    "InputState",
    "InverterVoltageLimiter",
    "MotorState",
    "PMSMDynamicModel",
    "PMSMDynamicParameters",
    "PIController",
    "RK4Integrator",
    "ResolvedSimulationSettings",
    "SimulationAccuracy",
    "SimulationConfidence",
    "SimulationConfig",
    "SimulationResult",
    "SimulationRunner",
    "SimulationStatus",
    "ScalarProfile",
    "SolverPreference",
    "StaticFallbackProvider",
    "StateDerivatives",
    "UserSimulationRunner",
    "VoltageLimitResult",
    "CurrentControlSimulationRunner",
    "CurrentReferenceProfile",
    "clarke_transform",
    "compute_pmsm_dq_decoupling_feedforward",
    "electrical_angle",
    "inverse_clarke_transform",
    "inverse_park_transform",
    "park_transform",
    "run_user_simulation",
    "run_foc_current_control_simulation",
    "select_simulation_settings",
    "wrap_electrical_angle",
]
