"""First-order lumped thermal dynamics checks."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    LumpedThermalModel,
    ThermalConfig,
    ThermalIntegrationMethod,
    ThermalState,
    run_thermal_foundation_experiments,
)


def _config(initial_temperature_c: float = 25.0) -> ThermalConfig:
    return ThermalConfig(
        ambient_temperature_c=25.0,
        thermal_resistance_c_per_w=2.0,
        thermal_capacitance_j_per_c=100.0,
        initial_temperature_c=initial_temperature_c,
    )


def test_zero_loss_drives_hot_winding_toward_ambient():
    model = LumpedThermalModel()
    config = _config(75.0)
    state = ThermalState(75.0)

    for _ in range(1000):
        state = model.step(state, 0.0, 1.0, config)

    assert 25.0 < state.winding_temperature_c < 26.0


def test_constant_loss_approaches_expected_steady_state_temperature():
    model = LumpedThermalModel()
    config = _config()
    state = ThermalState(config.initial_temperature_c)

    for _ in range(2000):
        state = model.step(state, 10.0, 1.0, config)

    assert config.steady_state_temperature_c(10.0) == 45.0
    assert state.winding_temperature_c == pytest.approx(45.0, abs=0.001)


def test_rk4_thermal_dynamics_remain_finite_and_bounded_at_coarse_step():
    model = LumpedThermalModel()
    config = _config()
    state = ThermalState(25.0)

    for _ in range(20):
        state = model.step(
            state,
            10.0,
            50.0,
            config,
            ThermalIntegrationMethod.RK4,
        )

    assert math.isfinite(state.winding_temperature_c)
    assert 25.0 < state.winding_temperature_c < 45.0


@pytest.mark.parametrize(
    "kwargs",
    (
        {"thermal_resistance_c_per_w": 0.0},
        {"thermal_resistance_c_per_w": -1.0},
        {"thermal_capacitance_j_per_c": 0.0},
        {"thermal_capacitance_j_per_c": float("nan")},
    ),
)
def test_invalid_thermal_parameters_are_rejected_safely(kwargs):
    values = dict(
        ambient_temperature_c=25.0,
        thermal_resistance_c_per_w=2.0,
        thermal_capacitance_j_per_c=100.0,
        initial_temperature_c=25.0,
    )
    values.update(kwargs)
    with pytest.raises(ValueError):
        ThermalConfig(**values)


@pytest.fixture(scope="module")
def thermal_experiments():
    return run_thermal_foundation_experiments()


def test_constant_current_experiment_rises_toward_theoretical_steady_state(
    thermal_experiments,
):
    result = thermal_experiments.constant_current

    assert result.final_temperature_c > result.winding_temperature_c[0]
    assert result.final_temperature_c == pytest.approx(
        result.theoretical_fixed_loss_steady_temperature_c, abs=0.1
    )


def test_higher_current_experiment_has_i_squared_loss_and_larger_rise(
    thermal_experiments,
):
    low = thermal_experiments.constant_current
    high = thermal_experiments.higher_current

    assert high.copper_loss_w[0] / low.copper_loss_w[0] == pytest.approx(4.0)
    assert high.final_temperature_c > low.final_temperature_c


def test_resistance_feedback_experiment_increases_resistance_and_copper_loss(
    thermal_experiments,
):
    disabled = thermal_experiments.resistance_feedback_disabled
    enabled = thermal_experiments.resistance_feedback_enabled

    assert enabled.effective_phase_resistance_ohm[-1] > enabled.effective_phase_resistance_ohm[0]
    assert enabled.copper_loss_w[-1] > disabled.copper_loss_w[-1]
    assert enabled.final_temperature_c > disabled.final_temperature_c


def test_cooling_experiment_decays_toward_ambient(thermal_experiments):
    result = thermal_experiments.cooling
    switch_index = result.time_s.index(150.0)

    assert result.winding_temperature_c[switch_index] > 25.0
    assert result.final_temperature_c < result.winding_temperature_c[switch_index]
    assert result.final_temperature_c == pytest.approx(25.0, abs=0.1)
