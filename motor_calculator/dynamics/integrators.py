"""Numerical integrators for the independent dynamics sandbox."""

from __future__ import annotations

from collections.abc import Callable
import math

from .state import MotorState, StateDerivatives

DerivativeEvaluator = Callable[[MotorState, float], StateDerivatives]
DerivativeInput = StateDerivatives | DerivativeEvaluator


def _validate_dt(dt: float) -> None:
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt must be a finite value greater than zero")


def _evaluate_derivatives(
    derivatives: DerivativeInput,
    state: MotorState,
    time_offset: float,
) -> StateDerivatives:
    resolved = derivatives(state, time_offset) if callable(derivatives) else derivatives
    if not isinstance(resolved, StateDerivatives):
        raise TypeError("derivatives must be StateDerivatives or return StateDerivatives")
    return resolved


def _advance_state(state: MotorState, derivatives: StateDerivatives, scale: float) -> MotorState:
    return MotorState(
        id=state.id + derivatives.did_dt * scale,
        iq=state.iq + derivatives.diq_dt * scale,
        omega_m=state.omega_m + derivatives.domega_dt * scale,
        theta=state.theta + derivatives.dtheta_dt * scale,
    )


class EulerIntegrator:
    """Explicit first-order Euler integrator."""

    @staticmethod
    def step(state: MotorState, derivatives: DerivativeInput, dt: float) -> MotorState:
        _validate_dt(dt)
        current_derivatives = _evaluate_derivatives(derivatives, state, 0.0)
        return _advance_state(state, current_derivatives, dt)


class RK4Integrator:
    """Classical fourth-order Runge-Kutta integrator.

    A callable derivative input is reevaluated at each intermediate state.
    Passing a fixed ``StateDerivatives`` record remains valid for constant
    derivatives and preserves the same public step signature as Euler.
    """

    @staticmethod
    def step(state: MotorState, derivatives: DerivativeInput, dt: float) -> MotorState:
        _validate_dt(dt)

        k1 = _evaluate_derivatives(derivatives, state, 0.0)
        k2_state = _advance_state(state, k1, 0.5 * dt)
        k2 = _evaluate_derivatives(derivatives, k2_state, 0.5 * dt)
        k3_state = _advance_state(state, k2, 0.5 * dt)
        k3 = _evaluate_derivatives(derivatives, k3_state, 0.5 * dt)
        k4_state = _advance_state(state, k3, dt)
        k4 = _evaluate_derivatives(derivatives, k4_state, dt)

        one_sixth_dt = dt / 6.0
        return MotorState(
            id=state.id + one_sixth_dt * (k1.did_dt + 2.0 * k2.did_dt + 2.0 * k3.did_dt + k4.did_dt),
            iq=state.iq + one_sixth_dt * (k1.diq_dt + 2.0 * k2.diq_dt + 2.0 * k3.diq_dt + k4.diq_dt),
            omega_m=state.omega_m
            + one_sixth_dt * (k1.domega_dt + 2.0 * k2.domega_dt + 2.0 * k3.domega_dt + k4.domega_dt),
            theta=state.theta
            + one_sixth_dt * (k1.dtheta_dt + 2.0 * k2.dtheta_dt + 2.0 * k3.dtheta_dt + k4.dtheta_dt),
        )
