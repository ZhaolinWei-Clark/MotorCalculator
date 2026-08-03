"""Outer speed-loop behavior and cascaded-runner checks for Phase 6K."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    SpeedControlRunnerConfig,
    SpeedController,
    SpeedControllerConfig,
    SpeedControllerOutput,
    run_speed_load_step_example,
    run_speed_startup_example,
    run_unreachable_speed_example,
)


def _controller(*, anti_windup_gain: float = 0.0) -> SpeedController:
    return SpeedController(
        SpeedControllerConfig(
            kp=0.5,
            ki=1.0,
            iq_min_a=-5.0,
            iq_max_a=5.0,
            anti_windup_gain=anti_windup_gain,
        )
    )


@pytest.fixture(scope="module")
def startup_result():
    return run_speed_startup_example()


@pytest.fixture(scope="module")
def load_step_result():
    return run_speed_load_step_example()


@pytest.fixture(scope="module")
def unreachable_result():
    return run_unreachable_speed_example()


def test_zero_speed_error_produces_no_q_current_demand():
    output = _controller().update(
        omega_ref_rad_s=20.0,
        omega_measured_rad_s=20.0,
        dt=0.01,
    )

    assert output.speed_error_rad_s == 0.0
    assert output.iq_ref_unsaturated_a == 0.0
    assert output.iq_ref_actual_a == 0.0
    assert output.id_ref_a == 0.0


def test_positive_speed_error_generates_positive_iq_reference():
    output = _controller().update(omega_ref_rad_s=10.0, omega_measured_rad_s=0.0, dt=0.01)

    assert output.iq_ref_actual_a > 0.0


def test_negative_speed_error_generates_negative_iq_reference_when_permitted():
    output = _controller().update(omega_ref_rad_s=0.0, omega_measured_rad_s=10.0, dt=0.01)

    assert output.iq_ref_actual_a < 0.0


def test_iq_reference_limit_and_saturation_metadata_are_explicit():
    output = _controller().update(
        omega_ref_rad_s=100.0,
        omega_measured_rad_s=0.0,
        dt=0.01,
    )

    assert output.iq_ref_unsaturated_a > 5.0
    assert output.iq_ref_actual_a == 5.0
    assert output.current_limit_active is True
    assert output.saturation_error_a == pytest.approx(
        output.iq_ref_actual_a - output.iq_ref_unsaturated_a
    )


def test_speed_anti_windup_reduces_integral_accumulation_and_reset_works():
    baseline = SpeedController(
        SpeedControllerConfig(0.0, 1.0, -1.0, 1.0, 0.0)
    )
    robust = SpeedController(
        SpeedControllerConfig(0.0, 1.0, -1.0, 1.0, 5.0)
    )

    for _ in range(20):
        baseline.update(100.0, 0.0, 0.01)
        robust.update(100.0, 0.0, 0.01)

    assert abs(robust.state.integral_error) < abs(baseline.state.integral_error)
    robust.reset()
    assert robust.state.integral_error == 0.0


def test_speed_controller_outputs_only_current_references_not_voltage():
    output_fields = set(SpeedControllerOutput.__dataclass_fields__)

    assert {"id_ref_a", "iq_ref_actual_a"}.issubset(output_fields)
    assert not any("voltage" in field or field.startswith(("vd", "vq")) for field in output_fields)


def test_default_multi_rate_configuration_runs_current_loop_faster_than_speed_loop():
    config = SpeedControlRunnerConfig()

    assert config.plant_time_step_s < config.current_control_period_s
    assert config.current_control_period_s < config.speed_control_period_s
    assert config.current_steps == 5
    assert config.speed_steps == 50


def test_cascaded_speed_and_current_loop_runs_successfully(startup_result):
    assert all(len(series) == len(startup_result.time) for series in startup_result.all_series)
    assert startup_result.speed[0] == 0.0
    assert startup_result.speed[-1] == pytest.approx(40.0, abs=1.0)
    assert max(startup_result.speed) < 42.0
    assert all(id_ref == 0.0 for id_ref in startup_result.id_ref)
    assert all(math.isfinite(value) for series in startup_result.numeric_series for value in series)


def test_load_step_increases_current_and_torque_demand_and_speed_recovers(load_step_result):
    step_index = min(
        range(len(load_step_result.time)),
        key=lambda index: abs(load_step_result.time[index] - 1.0),
    )
    minimum_speed_after_step = min(load_step_result.speed[step_index:])

    assert max(load_step_result.iq_ref[step_index:]) > load_step_result.iq_ref[step_index] + 1.0
    assert max(load_step_result.torque[step_index:]) > load_step_result.torque[step_index] + 0.5
    assert load_step_result.speed[-1] > minimum_speed_after_step + 2.0
    assert load_step_result.speed[-1] == pytest.approx(30.0, abs=1.0)


def test_unreachable_speed_remains_bounded_and_records_saturation(unreachable_result):
    assert all(
        math.isfinite(value)
        for series in unreachable_result.numeric_series
        for value in series
    )
    assert max(abs(value) for value in unreachable_result.iq_ref) <= 3.0
    assert max(abs(value) for value in unreachable_result.speed) < 100.0
    assert unreachable_result.speed[-1] < 300.0
    assert unreachable_result.current_limit_count > 0
    assert unreachable_result.voltage_saturation_count > 0
    assert len(unreachable_result.warning_messages) >= 2
