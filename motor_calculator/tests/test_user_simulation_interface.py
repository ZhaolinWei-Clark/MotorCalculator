"""User-oriented configuration, solver selection, and fallback tests."""

from __future__ import annotations

import pytest

from dynamics import (
    FallbackPolicy,
    InputState,
    MotorState,
    PMSMDynamicParameters,
    SimulationAccuracy,
    SimulationConfidence,
    SimulationConfig,
    SimulationStatus,
    SolverPreference,
    UserSimulationRunner,
    select_simulation_settings,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.01,
        B=0.002,
    )


def _initial_state() -> MotorState:
    return MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0)


def test_accuracy_presets_select_internal_timesteps_without_user_timestep():
    fast_config = SimulationConfig(simulation_time=1.0, accuracy_level=SimulationAccuracy.FAST)
    balanced_config = SimulationConfig(simulation_time=1.0, accuracy_level=SimulationAccuracy.BALANCED)
    high_config = SimulationConfig(simulation_time=1.0, accuracy_level=SimulationAccuracy.HIGH_ACCURACY)

    fast = select_simulation_settings(fast_config)
    balanced = select_simulation_settings(balanced_config)
    high = select_simulation_settings(high_config)

    assert fast.time_step > balanced.time_step > high.time_step
    assert not hasattr(fast_config, "time_step")


@pytest.mark.parametrize(
    ("accuracy", "expected_solver"),
    [
        (SimulationAccuracy.FAST, "Euler"),
        (SimulationAccuracy.BALANCED, "RK4"),
        (SimulationAccuracy.HIGH_ACCURACY, "RK4"),
    ],
)
def test_automatic_solver_selection(accuracy: SimulationAccuracy, expected_solver: str):
    settings = select_simulation_settings(
        SimulationConfig(
            simulation_time=1.0,
            accuracy_level=accuracy,
            solver_preference=SolverPreference.AUTO,
        )
    )

    assert settings.solver_name == expected_solver


def test_explicit_solver_preference_overrides_automatic_choice_with_warning():
    settings = select_simulation_settings(
        SimulationConfig(
            simulation_time=1.0,
            accuracy_level=SimulationAccuracy.HIGH_ACCURACY,
            solver_preference=SolverPreference.EULER,
        )
    )

    assert settings.solver_name == "Euler"
    assert settings.confidence_level is SimulationConfidence.LOW
    assert settings.warning_messages


def test_balanced_dynamic_simulation_returns_success_without_calling_fallback():
    def unexpected_fallback(_: str) -> object:
        raise AssertionError("fallback must not run after dynamic success")

    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.5),
        config=SimulationConfig(simulation_time=0.05),
        static_fallback_provider=unexpected_fallback,
    )

    assert result.status is SimulationStatus.SUCCESS
    assert result.solver_used == "RK4"
    assert result.confidence_level is SimulationConfidence.MEDIUM
    assert result.transient_response_available is True
    assert result.time[-1] == pytest.approx(0.05)
    assert result.steady_state_result is None


def test_fast_dynamic_simulation_is_explicitly_marked_as_warning():
    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.5),
        config=SimulationConfig(
            simulation_time=0.05,
            accuracy_level=SimulationAccuracy.FAST,
        ),
    )

    assert result.status is SimulationStatus.WARNING
    assert result.solver_used == "Euler"
    assert result.confidence_level is SimulationConfidence.LOW
    assert result.warning_messages


def test_forced_dynamic_failure_returns_explicit_static_fallback():
    static_result = {"rated_torque_nm": 1.25, "source": "caller_supplied_static_result"}

    def failing_input_profile(_: float) -> InputState:
        raise RuntimeError("forced dynamic failure")

    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=failing_input_profile,
        config=SimulationConfig(simulation_time=0.05, fallback_policy=FallbackPolicy.STATIC),
        static_fallback_provider=lambda _: static_result,
    )

    assert result.status is SimulationStatus.FALLBACK_STATIC
    assert result.transient_response_available is False
    assert result.time == ()
    assert result.fallback_reason and "forced dynamic failure" in result.fallback_reason
    assert any("transient response is unavailable" in message for message in result.warning_messages)


def test_static_fallback_result_is_returned_without_conversion_or_mutation():
    static_result = {"speed_rpm": 1500.0, "torque_nm": 2.0}

    def failing_input_profile(_: float) -> InputState:
        raise ValueError("test failure")

    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=failing_input_profile,
        config=SimulationConfig(simulation_time=0.01),
        static_fallback_provider=lambda _: static_result,
    )

    assert result.steady_state_result is static_result
    assert static_result == {"speed_rpm": 1500.0, "torque_nm": 2.0}


def test_failure_without_allowed_static_fallback_returns_failed_status():
    def failing_input_profile(_: float) -> InputState:
        raise RuntimeError("forced failure without fallback")

    result = UserSimulationRunner().run(
        initial_state=_initial_state(),
        motor_parameters=_parameters(),
        input_profile=failing_input_profile,
        config=SimulationConfig(simulation_time=0.01, fallback_policy=FallbackPolicy.FAIL),
    )

    assert result.status is SimulationStatus.FAILED
    assert result.steady_state_result is None
    assert result.transient_response_available is False
