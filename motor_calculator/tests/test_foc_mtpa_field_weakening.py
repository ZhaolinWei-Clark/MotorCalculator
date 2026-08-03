"""Optional MTPA and field-weakening integration checks for the FOC runner."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from dynamics import (
    DCBusConfig,
    DQCurrentController,
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCStepInput,
    FieldWeakeningController,
    MTPAController,
    MotorState,
    PMSMDynamicParameters,
    run_foc_current_control_simulation,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.2,
        Ld=0.003,
        Lq=0.008,
        psi_f=0.08,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )


def _step_input(speed_rad_s: float = 0.0) -> FOCStepInput:
    return FOCStepInput(
        phase_current_a=0.0,
        phase_current_b=0.0,
        phase_current_c=0.0,
        theta_m_rad=0.0,
        omega_m_rad_s=speed_rad_s,
        load_torque_nm=0.0,
    )


def _runner(*, explicit_disabled_flags: bool) -> FOCRunner:
    config_kwargs = {}
    if explicit_disabled_flags:
        config_kwargs = {
            "enable_mtpa": False,
            "enable_field_weakening": False,
        }
    return FOCRunner(
        controller=DQCurrentController(kp=2.0, ki=50.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.0001,
            use_inverter_limit=False,
            **config_kwargs,
        ),
    )


def test_disabled_optimization_features_preserve_existing_foc_behavior():
    reference = FOCReference(id_ref_a=0.0, iq_ref_a=2.0)
    legacy_default = _runner(explicit_disabled_flags=False).step(
        reference,
        _step_input(),
    )
    explicit_disabled = _runner(explicit_disabled_flags=True).step(
        reference,
        _step_input(),
    )

    assert explicit_disabled == legacy_default
    assert legacy_default.mtpa_method is None
    assert legacy_default.field_weakening_active is False


def test_enabled_mtpa_and_field_weakening_feed_bounded_current_references():
    dc_bus = DCBusConfig(nominal_voltage_v=48.0, current_limit_a=20.0)
    runner = FOCRunner(
        controller=DQCurrentController(kp=2.0, ki=50.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=4,
            control_time_step_s=0.0001,
            use_inverter_limit=True,
            enable_mtpa=True,
            enable_field_weakening=True,
        ),
        inverter_config=dc_bus,
        mtpa_controller=MTPAController(current_limit_a=20.0),
        field_weakening_controller=FieldWeakeningController(current_limit_a=20.0),
    )

    output = runner.step(
        FOCReference(id_ref_a=0.0, iq_ref_a=0.0, torque_reference_nm=4.0),
        _step_input(speed_rad_s=200.0),
    )

    assert output.mtpa_method == "ipmsm_discrete_mtpa"
    assert output.field_weakening_active is True
    assert output.id_reference_a < 0.0
    assert math.hypot(output.id_reference_a, output.iq_reference_a) <= 20.0 + 1.0e-12
    assert all(
        math.isfinite(value)
        for value in (
            output.vd_command_v,
            output.vq_command_v,
            output.vd_actual_v,
            output.vq_actual_v,
            output.torque_nm,
        )
    )


def test_optional_features_run_in_closed_loop_without_touching_production():
    calculations_path = Path(__file__).resolve().parents[1] / "motor_core" / "calculations.py"
    calculations_before = calculations_path.read_bytes()
    result = run_foc_current_control_simulation(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=150.0, theta=0.0),
        id_ref_profile=0.0,
        iq_ref_profile=0.0,
        torque_reference_profile=3.0,
        load_torque_profile=0.0,
        simulation_time_s=0.002,
        control_time_step_s=0.0001,
        motor_parameters=_parameters(),
        controller_kp=2.0,
        controller_ki=50.0,
        inverter_config=DCBusConfig(
            nominal_voltage_v=48.0,
            current_limit_a=20.0,
        ),
        enable_mtpa=True,
        enable_field_weakening=True,
    )

    assert result.mtpa_active_count > 0
    assert result.field_weakening_active_count > 0
    assert all(math.isfinite(value) for series in result.series for value in series)
    assert calculations_path.read_bytes() == calculations_before


def test_field_weakening_requires_a_real_inverter_voltage_envelope():
    with pytest.raises(ValueError, match="inverter voltage limit"):
        FOCRunner(
            controller=DQCurrentController(kp=2.0, ki=50.0),
            motor_parameters=_parameters(),
            config=FOCRunnerConfig(
                pole_pairs=4,
                control_time_step_s=0.0001,
                use_inverter_limit=False,
                enable_field_weakening=True,
            ),
            field_weakening_controller=FieldWeakeningController(
                current_limit_a=20.0
            ),
        )
