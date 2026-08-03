"""Safe user-oriented entry point for configured dynamic simulations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from .configuration import FallbackPolicy, SimulationConfig, select_simulation_settings
from .integrators import EulerIntegrator, RK4Integrator
from .inverter import DCBusConfig
from .pmsm_model import PMSMDynamicParameters
from .simulation_results import SimulationResult, SimulationStatus
from .simulation_runner import InputProfile, SimulationRunner
from .state import InputState, MotorState

StaticFallbackProvider = Callable[[str], object]


class UserSimulationRunner:
    """Run a preset simulation and make any fallback explicit in the result."""

    def run(
        self,
        initial_state: MotorState,
        motor_parameters: PMSMDynamicParameters,
        input_profile: InputState | InputProfile,
        config: SimulationConfig,
        static_fallback_provider: StaticFallbackProvider | None = None,
        inverter_config: DCBusConfig | None = None,
    ) -> SimulationResult:
        settings = select_simulation_settings(config)
        integrator = EulerIntegrator() if settings.solver_name == "Euler" else RK4Integrator()

        try:
            dynamic_result = SimulationRunner(integrator=integrator).run(
                initial_state=initial_state,
                motor_parameters=motor_parameters,
                input_profile=input_profile,
                simulation_time=config.simulation_time,
                time_step=settings.time_step,
                inverter_config=inverter_config,
            )
        except Exception as exc:
            reason = f"Dynamic simulation failed: {type(exc).__name__}: {exc}"
            return self._handle_failure(
                reason=reason,
                solver_used=settings.solver_name,
                warning_messages=settings.warning_messages,
                fallback_policy=config.fallback_policy,
                static_fallback_provider=static_fallback_provider,
            )

        combined_warnings = tuple(
            dict.fromkeys((*settings.warning_messages, *dynamic_result.warning_messages))
        )
        status = SimulationStatus.WARNING if combined_warnings else SimulationStatus.SUCCESS
        return replace(
            dynamic_result,
            status=status,
            warning_messages=combined_warnings,
            solver_used=settings.solver_name,
            confidence_level=settings.confidence_level,
        )

    @staticmethod
    def _handle_failure(
        *,
        reason: str,
        solver_used: str,
        warning_messages: tuple[str, ...],
        fallback_policy: FallbackPolicy,
        static_fallback_provider: StaticFallbackProvider | None,
    ) -> SimulationResult:
        if fallback_policy is FallbackPolicy.FAIL:
            return SimulationResult.failed(
                reason=reason,
                solver_used=solver_used,
                warning_messages=warning_messages,
            )
        if static_fallback_provider is None:
            return SimulationResult.failed(
                reason=f"{reason}; static fallback was requested but no provider was supplied",
                solver_used=solver_used,
                warning_messages=warning_messages,
            )

        try:
            steady_state_result = static_fallback_provider(reason)
        except Exception as exc:
            return SimulationResult.failed(
                reason=f"{reason}; static fallback provider failed: {type(exc).__name__}: {exc}",
                solver_used=solver_used,
                warning_messages=warning_messages,
            )
        if steady_state_result is None:
            return SimulationResult.failed(
                reason=f"{reason}; static fallback provider returned no result",
                solver_used=solver_used,
                warning_messages=warning_messages,
            )

        return SimulationResult.fallback_static(
            reason=reason,
            steady_state_result=steady_state_result,
            solver_used=solver_used,
            warning_messages=warning_messages,
        )


def run_user_simulation(
    initial_state: MotorState,
    motor_parameters: PMSMDynamicParameters,
    input_profile: InputState | InputProfile,
    config: SimulationConfig,
    static_fallback_provider: StaticFallbackProvider | None = None,
    inverter_config: DCBusConfig | None = None,
) -> SimulationResult:
    """Convenience function for the user-oriented simulation entry point."""

    return UserSimulationRunner().run(
        initial_state=initial_state,
        motor_parameters=motor_parameters,
        input_profile=input_profile,
        config=config,
        static_fallback_provider=static_fallback_provider,
        inverter_config=inverter_config,
    )
