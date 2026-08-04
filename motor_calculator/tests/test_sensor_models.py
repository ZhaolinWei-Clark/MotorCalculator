"""Unit validation for optional current, position, and speed sensors."""

from __future__ import annotations

import math
import random

import pytest

from dynamics import (
    CurrentSensor,
    CurrentSensorConfig,
    PositionSensor,
    PositionSensorConfig,
    SpeedSensor,
    SpeedSensorConfig,
)


def test_disabled_current_sensor_preserves_true_value_exactly():
    result = CurrentSensor(CurrentSensorConfig(enabled=False)).measure(1.2345)

    assert result.measured_value == 1.2345
    assert result.measurement_error == 0.0
    assert result.quantized is False
    assert result.noise_applied is False


def test_current_offset_produces_expected_measurement():
    result = CurrentSensor(
        CurrentSensorConfig(offset_a=0.25, enabled=True)
    ).measure(2.0)

    assert result.measured_value == pytest.approx(2.25)
    assert result.measurement_error == pytest.approx(0.25)


def test_current_gain_error_scales_before_offset():
    result = CurrentSensor(
        CurrentSensorConfig(
            offset_a=0.1,
            gain_error_fraction=0.05,
            enabled=True,
        )
    ).measure(2.0)

    assert result.measured_value == pytest.approx(2.2)


def test_current_quantization_is_deterministic():
    sensor = CurrentSensor(
        CurrentSensorConfig(
            resolution_bits=3,
            full_scale_a=7.0,
            enabled=True,
        )
    )

    first = sensor.measure(1.2)
    second = sensor.measure(1.2)
    assert first == second
    assert first.measured_value == pytest.approx(1.0)
    assert first.quantized is True


def test_encoder_resolution_quantizes_mechanical_angle():
    sensor = PositionSensor(
        PositionSensorConfig(
            resolution_counts_per_rev=8,
            enabled=True,
        )
    )
    result = sensor.measure(theta_m_true_rad=0.6, pole_pairs=2)

    assert result.measured_value == pytest.approx(math.pi / 4.0)
    assert result.quantized is True


def test_mechanical_offset_maps_to_existing_electrical_angle_convention():
    sensor = PositionSensor(
        PositionSensorConfig(mechanical_offset_rad=0.1, enabled=True)
    )
    result = sensor.measure(theta_m_true_rad=0.0, pole_pairs=4)

    assert result.measured_value == pytest.approx(0.1)
    assert result.electrical_angle_rad == pytest.approx(0.4)


def test_seeded_current_noise_is_reproducible_without_global_state():
    sensor = CurrentSensor(
        CurrentSensorConfig(noise_std_a=0.05, enabled=True)
    )
    first = sensor.measure(1.0, random.Random(12345))
    second = sensor.measure(1.0, random.Random(12345))

    assert first == second
    assert first.noise_applied is True
    with pytest.raises(ValueError, match="explicit RNG"):
        sensor.measure(1.0)


def test_speed_sensor_applies_gain_offset_and_seeded_noise_directly():
    sensor = SpeedSensor(
        SpeedSensorConfig(
            offset_rad_s=1.0,
            gain_error_fraction=0.02,
            noise_std_rad_s=0.1,
            sample_period_s=0.001,
            enabled=True,
        )
    )
    first = sensor.measure(100.0, random.Random(7))
    second = sensor.measure(100.0, random.Random(7))

    assert first == second
    assert first.measured_value != 100.0
    assert first.noise_applied is True
