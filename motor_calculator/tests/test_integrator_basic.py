"""Unit tests for the Phase 6B Euler integration boundary."""

from __future__ import annotations

import pytest

from dynamics import EulerIntegrator, MotorState, RK4Integrator, StateDerivatives


def test_euler_integrator_applies_x_next_equals_x_plus_dx_dt_times_dt():
    state = MotorState(id=1.0, iq=-2.0, omega_m=3.0, theta=4.0)
    derivatives = StateDerivatives(did_dt=10.0, diq_dt=20.0, domega_dt=-5.0, dtheta_dt=3.0)

    next_state = EulerIntegrator.step(state, derivatives, dt=0.1)

    assert next_state.id == pytest.approx(2.0)
    assert next_state.iq == pytest.approx(0.0)
    assert next_state.omega_m == pytest.approx(2.5)
    assert next_state.theta == pytest.approx(4.3)
    assert state == MotorState(id=1.0, iq=-2.0, omega_m=3.0, theta=4.0)


@pytest.mark.parametrize("dt", [0.0, -0.1, float("nan"), float("inf")])
def test_euler_integrator_rejects_invalid_time_steps(dt: float):
    with pytest.raises(ValueError):
        EulerIntegrator.step(
            MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
            StateDerivatives(did_dt=0.0, diq_dt=0.0, domega_dt=0.0, dtheta_dt=0.0),
            dt,
        )


def test_rk4_recomputes_derivatives_at_intermediate_states():
    state = MotorState(id=1.0, iq=0.0, omega_m=0.0, theta=0.0)
    evaluation_offsets = []

    def exponential_derivatives(candidate: MotorState, time_offset: float) -> StateDerivatives:
        evaluation_offsets.append(time_offset)
        return StateDerivatives(
            did_dt=candidate.id,
            diq_dt=0.0,
            domega_dt=0.0,
            dtheta_dt=0.0,
        )

    next_state = RK4Integrator.step(state, exponential_derivatives, dt=0.1)

    assert next_state.id == pytest.approx(1.1051708333333332)
    assert evaluation_offsets == pytest.approx([0.0, 0.05, 0.05, 0.1])


def test_rk4_accepts_fixed_derivatives_for_constant_slope():
    next_state = RK4Integrator.step(
        MotorState(id=1.0, iq=2.0, omega_m=3.0, theta=4.0),
        StateDerivatives(did_dt=1.0, diq_dt=-1.0, domega_dt=2.0, dtheta_dt=3.0),
        dt=0.25,
    )

    assert next_state == MotorState(id=1.25, iq=1.75, omega_m=3.5, theta=4.75)
