"""Voltage-envelope validation for the field-weakening foundation."""

from __future__ import annotations

import math

from dynamics import (
    DCBusConfig,
    FieldWeakeningController,
    InverterVoltageLimiter,
    PMSMDynamicParameters,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )


def _evaluate(speed_rad_s: float):
    controller = FieldWeakeningController(current_limit_a=30.0)
    parameters = _parameters()
    voltage = controller.estimate_steady_state_voltage(
        speed_rad_s=speed_rad_s,
        id_reference_a=0.0,
        iq_reference_a=2.0,
        motor_parameters=parameters,
    )
    result = controller.compute_weakening_command(
        speed_rad_s=speed_rad_s,
        vd_command_v=voltage.vd_v,
        vq_command_v=voltage.vq_v,
        dc_bus_voltage_v=48.0,
        motor_parameters=parameters,
    )
    return controller, parameters, voltage, result


def test_low_speed_keeps_field_weakening_inactive():
    _, _, _, result = _evaluate(speed_rad_s=20.0)

    assert result.weakening_active is False
    assert result.id_weakening_command == 0.0
    assert result.voltage_margin > 0.0
    assert result.warning is None


def test_high_speed_generates_negative_d_axis_current():
    _, _, _, result = _evaluate(speed_rad_s=200.0)

    assert result.weakening_active is True
    assert result.id_weakening_command < 0.0
    assert result.voltage_margin < 0.0
    assert result.warning


def test_negative_id_reduces_estimated_voltage_saturation():
    controller, parameters, baseline_voltage, result = _evaluate(speed_rad_s=200.0)
    weakened_voltage = controller.estimate_steady_state_voltage(
        speed_rad_s=200.0,
        id_reference_a=result.id_weakening_command,
        iq_reference_a=2.0,
        motor_parameters=parameters,
    )
    voltage_limit = 48.0 / math.sqrt(3.0)
    dc_bus = DCBusConfig(nominal_voltage_v=48.0)
    baseline_limit = InverterVoltageLimiter.apply_limit(
        baseline_voltage.vd_v,
        baseline_voltage.vq_v,
        dc_bus,
    )
    weakened_limit = InverterVoltageLimiter.apply_limit(
        weakened_voltage.vd_v,
        weakened_voltage.vq_v,
        dc_bus,
    )

    assert baseline_voltage.magnitude_v > voltage_limit
    assert weakened_voltage.magnitude_v < baseline_voltage.magnitude_v
    assert weakened_limit.saturation_ratio < baseline_limit.saturation_ratio
