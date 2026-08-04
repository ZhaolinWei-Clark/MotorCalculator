"""Optional, non-mutating thermal/electrical coupling checks."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    DynamicLossModel,
    InputState,
    MotorState,
    LossModelConfig,
    PMSMDynamicParameters,
    ResistanceTemperatureConfig,
    SimulationRunner,
    ThermalConfig,
    ThermalElectricalCouplingConfig,
    ThermalElectricalSimulationRunner,
    ThermalSimulationResult,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(0.5, 0.01, 0.01, 0.1, 2, 10.0, 0.0)


def _thermal_config() -> ThermalConfig:
    return ThermalConfig(25.0, 2.0, 20.0, 25.0, warning_temperature_c=30.0)


def _resistance_config() -> ResistanceTemperatureConfig:
    return ResistanceTemperatureConfig(0.5, 25.0, 0.00393)


def test_disabled_thermal_wrapper_preserves_exact_existing_simulation_result():
    initial = MotorState(0.0, 0.0, 0.0, 0.0)
    parameters = _parameters()
    input_state = InputState(0.0, 5.0, 0.0)
    baseline = SimulationRunner(integrator=None).run(
        initial, parameters, input_state, 0.01, 0.001
    )
    wrapped = ThermalElectricalSimulationRunner(integrator=None).run(
        initial,
        parameters,
        input_state,
        0.01,
        0.001,
        coupling_config=ThermalElectricalCouplingConfig(enabled=False),
    )

    assert wrapped == baseline


def test_thermal_coupling_uses_temporary_effective_resistance_only():
    parameters = _parameters()
    original_parameters = parameters
    result = ThermalElectricalSimulationRunner().run(
        MotorState(0.0, 0.0, 0.0, 0.0),
        parameters,
        InputState(0.0, 10.0, 0.0),
        simulation_time=1.0,
        time_step=0.001,
        coupling_config=ThermalElectricalCouplingConfig(
            enabled=True,
            enable_resistance_feedback=True,
            thermal_update_period_s=0.1,
        ),
        thermal_config=_thermal_config(),
        resistance_config=_resistance_config(),
    )

    assert isinstance(result, ThermalSimulationResult)
    assert parameters is original_parameters
    assert parameters.Rs == 0.5
    assert result.effective_phase_resistance_ohm[-1] > result.effective_phase_resistance_ohm[0]
    assert result.final_temperature_c > 25.0
    assert result.thermal_update_count == 10
    assert any("warning threshold" in warning for warning in result.thermal_warning_messages)


def test_disabled_resistance_feedback_keeps_original_rs_while_monitoring_heat():
    parameters = _parameters()
    result = ThermalElectricalSimulationRunner().run(
        MotorState(0.0, 0.0, 0.0, 0.0),
        parameters,
        InputState(0.0, 10.0, 0.0),
        0.2,
        0.001,
        ThermalElectricalCouplingConfig(
            enabled=True,
            enable_resistance_feedback=False,
            thermal_update_period_s=0.05,
        ),
        _thermal_config(),
        _resistance_config(),
    )

    assert isinstance(result, ThermalSimulationResult)
    assert set(result.effective_phase_resistance_ohm) == {parameters.Rs}
    assert result.final_temperature_c > 25.0


def test_coupled_and_uncoupled_runs_produce_distinct_sandbox_current_response():
    common = dict(
        initial_state=MotorState(0.0, 0.0, 0.0, 0.0),
        motor_parameters=_parameters(),
        input_profile=InputState(0.0, 10.0, 0.0),
        simulation_time=1.0,
        time_step=0.001,
        thermal_config=_thermal_config(),
        resistance_config=_resistance_config(),
    )
    uncoupled = ThermalElectricalSimulationRunner().run(
        **common,
        coupling_config=ThermalElectricalCouplingConfig(
            enabled=True,
            enable_resistance_feedback=False,
            thermal_update_period_s=0.1,
        ),
    )
    coupled = ThermalElectricalSimulationRunner().run(
        **common,
        coupling_config=ThermalElectricalCouplingConfig(
            enabled=True,
            enable_resistance_feedback=True,
            thermal_update_period_s=0.1,
        ),
    )

    assert coupled.electrical_result.iq[-1] != pytest.approx(
        uncoupled.electrical_result.iq[-1], rel=1.0e-6
    )
    assert coupled.effective_phase_resistance_ohm[-1] > uncoupled.effective_phase_resistance_ohm[-1]
    assert all(
        math.isfinite(value)
        for series in (
            coupled.winding_temperature_c,
            coupled.effective_phase_resistance_ohm,
            coupled.total_loss_w,
        )
        for value in series
    )


def test_thermal_update_period_cannot_be_faster_than_plant_step():
    with pytest.raises(ValueError, match="must not be faster"):
        ThermalElectricalSimulationRunner().run(
            MotorState(0.0, 0.0, 0.0, 0.0),
            _parameters(),
            InputState(0.0, 1.0, 0.0),
            0.1,
            0.01,
            ThermalElectricalCouplingConfig(
                enabled=True, thermal_update_period_s=0.001
            ),
            _thermal_config(),
            _resistance_config(),
        )


def test_unavailable_iron_loss_is_recorded_as_none_with_warning():
    runner = ThermalElectricalSimulationRunner(
        loss_model=DynamicLossModel(LossModelConfig(enable_iron_loss=True))
    )
    result = runner.run(
        MotorState(0.0, 0.0, 10.0, 0.0),
        _parameters(),
        InputState(0.0, 1.0, 0.0),
        0.01,
        0.001,
        ThermalElectricalCouplingConfig(
            enabled=True, thermal_update_period_s=0.01
        ),
        _thermal_config(),
        _resistance_config(),
    )

    assert set(result.iron_loss_w) == {None}
    assert any("Iron loss is unavailable" in warning for warning in result.thermal_warning_messages)
