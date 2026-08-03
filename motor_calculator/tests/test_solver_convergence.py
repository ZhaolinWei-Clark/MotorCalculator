"""Numerical convergence and steady-state checks for Phase 6C."""

from __future__ import annotations

from dynamics.solver_validation import (
    calculate_steady_state_consistency,
    collect_power_balance_trend,
    run_solver_convergence_analysis,
)


def _record(solver_name: str, time_step: float):
    return next(
        item
        for item in run_solver_convergence_analysis()
        if item.solver_name == solver_name and item.time_step == time_step
    )


def test_rk4_speed_torque_and_current_converge_as_time_step_decreases():
    coarse = _record("RK4", 1.0e-2)
    medium = _record("RK4", 1.0e-3)

    assert medium.speed_relative_error < coarse.speed_relative_error
    assert medium.torque_relative_error < coarse.torque_relative_error
    assert medium.current_relative_error < coarse.current_relative_error


def test_rk4_is_more_accurate_than_euler_for_identical_coarse_step():
    euler = _record("Euler", 1.0e-2)
    rk4 = _record("RK4", 1.0e-2)

    assert euler.status == "unstable"
    assert rk4.status == "finite"
    assert rk4.speed_relative_error < euler.speed_relative_error
    assert rk4.torque_relative_error < euler.torque_relative_error
    assert rk4.current_relative_error < euler.current_relative_error


def test_dynamic_steady_state_matches_mechanical_torque_relationship():
    comparison = calculate_steady_state_consistency()

    assert abs(comparison.final_domega_dt) < 1.0e-8
    assert comparison.torque_relative_error < 1.0e-10


def test_power_balance_trend_is_recorded_without_imposing_a_loss_model():
    trend = collect_power_balance_trend()

    assert len(trend) == 5
    assert all(record.electrical_power == record.mechanical_power + record.raw_power_difference for record in trend)
    assert trend[-1].time == 5.0
