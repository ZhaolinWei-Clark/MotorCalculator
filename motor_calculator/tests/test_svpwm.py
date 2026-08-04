"""Mathematical checks for the Phase 6N average SVPWM foundation."""

from __future__ import annotations

import math

import pytest

from dynamics import SVPWMConfig, SVPWMModulator


@pytest.fixture
def modulator() -> SVPWMModulator:
    return SVPWMModulator()


@pytest.fixture
def config() -> SVPWMConfig:
    return SVPWMConfig(enabled=True, dc_bus_voltage_v=48.0)


def test_zero_voltage_command_has_centered_duties_and_no_division_error(
    modulator, config
):
    result = modulator.modulate_dq(0.0, 0.0, 0.0, config)

    assert result.sector == 1
    assert result.modulation_index == 0.0
    assert result.duties == (0.5, 0.5, 0.5)
    assert result.average_phase_voltages_v == (0.0, 0.0, 0.0)
    assert result.vd_actual_v == 0.0
    assert result.vq_actual_v == 0.0


def test_linear_region_reconstructs_dq_command_and_balanced_phase_voltage(
    modulator, config
):
    result = modulator.modulate_dq(5.0, 8.0, 0.7, config)

    assert result.vd_actual_v == pytest.approx(5.0, abs=1.0e-12)
    assert result.vq_actual_v == pytest.approx(8.0, abs=1.0e-12)
    assert sum(result.average_phase_voltages_v) == pytest.approx(0.0, abs=1.0e-12)
    assert all(0.0 <= duty <= 1.0 for duty in result.duties)
    assert result.voltage_saturated is False


@pytest.mark.parametrize(
    ("angle_deg", "expected_sector"),
    ((30, 1), (90, 2), (150, 3), (210, 4), (270, 5), (330, 6)),
)
def test_six_sector_selection_is_deterministic(modulator, angle_deg, expected_sector):
    angle = math.radians(angle_deg)
    sector = modulator.determine_sector(math.cos(angle), math.sin(angle))
    assert sector == expected_sector


def test_sector_boundary_is_valid_and_average_voltage_is_continuous(modulator, config):
    radius = 10.0
    epsilon = 1.0e-9
    below = modulator.modulate_alpha_beta(
        radius * math.cos(math.pi / 3.0 - epsilon),
        radius * math.sin(math.pi / 3.0 - epsilon),
        0.0,
        config,
    )
    above = modulator.modulate_alpha_beta(
        radius * math.cos(math.pi / 3.0 + epsilon),
        radius * math.sin(math.pi / 3.0 + epsilon),
        0.0,
        config,
    )

    assert below.sector in range(1, 7)
    assert above.sector in range(1, 7)
    assert math.hypot(
        below.alpha_voltage_v - above.alpha_voltage_v,
        below.beta_voltage_v - above.beta_voltage_v,
    ) < 1.0e-6


def test_exact_sector_boundary_belongs_to_following_sector(modulator):
    assert modulator.determine_sector(1.0, 0.0) == 1
    assert modulator.determine_sector(0.5, math.sqrt(3.0) / 2.0) == 2
    assert modulator.determine_sector(-0.5, math.sqrt(3.0) / 2.0) == 3


def test_modulation_index_matches_vdc_over_sqrt_three_linear_limit(
    modulator, config
):
    limit = 48.0 / math.sqrt(3.0)
    result = modulator.modulate_alpha_beta(limit, 0.0, 0.0, config)

    assert config.linear_voltage_limit_v == pytest.approx(limit)
    assert result.modulation_index == pytest.approx(1.0)
    assert result.voltage_saturated is False


def test_overcommand_is_scaled_without_changing_voltage_direction(modulator, config):
    result = modulator.modulate_alpha_beta(30.0, 20.0, 0.0, config)

    assert result.modulation_index > 1.0
    assert result.voltage_saturated is True
    assert result.overmodulation_active is False
    assert result.alpha_voltage_v * 20.0 - result.beta_voltage_v * 30.0 == pytest.approx(
        0.0, abs=1.0e-12
    )
    assert math.hypot(result.alpha_voltage_v, result.beta_voltage_v) == pytest.approx(
        config.linear_voltage_limit_v
    )


def test_optional_overmodulation_uses_hexagon_and_reports_metadata(modulator):
    config = SVPWMConfig(
        enabled=True,
        dc_bus_voltage_v=48.0,
        allow_overmodulation=True,
    )
    result = modulator.modulate_alpha_beta(30.0, 0.0, 0.0, config)

    assert result.modulation_index > 1.0
    assert result.overmodulation_active is True
    assert result.voltage_saturated is False
    assert result.alpha_voltage_v == pytest.approx(30.0)
    assert result.warning_messages


def test_duty_bounds_reduce_available_linear_voltage(modulator):
    config = SVPWMConfig(
        enabled=True,
        dc_bus_voltage_v=48.0,
        minimum_duty=0.1,
        maximum_duty=0.9,
    )
    result = modulator.modulate_alpha_beta(30.0, 0.0, 0.0, config)

    assert config.linear_voltage_limit_v == pytest.approx(0.8 * 48.0 / math.sqrt(3.0))
    assert result.voltage_saturated is True
    assert all(0.1 <= duty <= 0.9 for duty in result.duties)


def test_invalid_configuration_is_rejected_safely():
    with pytest.raises(ValueError, match="minimum_duty"):
        SVPWMConfig(True, 48.0, minimum_duty=0.9, maximum_duty=0.1)
