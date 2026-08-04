"""Loss-model physics and explicit availability checks for Phase 6O."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    CopperLossModel,
    DynamicLossModel,
    LossModelConfig,
    MechanicalLossModel,
    MotorState,
    PMSMDynamicParameters,
    ProvisionalIronLossModel,
    ResistanceTemperatureConfig,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(0.5, 0.005, 0.005, 0.1, 4, 0.02, 0.002)


def test_copper_loss_follows_expected_current_squared_relationship():
    low = CopperLossModel.compute_from_phase_rms(5.0, 0.5)
    high = CopperLossModel.compute_from_phase_rms(10.0, 0.5)

    assert low == pytest.approx(37.5)
    assert high == pytest.approx(150.0)
    assert high / low == pytest.approx(4.0)


def test_amplitude_invariant_dq_peak_semantics_match_three_phase_rms_loss():
    dq_loss = CopperLossModel.compute_from_dq_peak(6.0, 8.0, 0.5)
    phase_rms = math.hypot(6.0, 8.0) / math.sqrt(2.0)

    assert dq_loss == pytest.approx(
        CopperLossModel.compute_from_phase_rms(phase_rms, 0.5)
    )
    assert dq_loss == pytest.approx(75.0)


def test_resistance_increases_with_temperature_using_explicit_copper_alpha():
    config = ResistanceTemperatureConfig(0.5, 20.0, 0.00393)

    assert config.resistance_at_temperature(20.0) == pytest.approx(0.5)
    assert config.resistance_at_temperature(100.0) == pytest.approx(0.6572)


def test_mechanical_loss_matches_existing_viscous_damping_power():
    assert MechanicalLossModel.compute_viscous_loss(100.0, 0.002) == pytest.approx(
        20.0
    )


def test_enabled_iron_loss_without_coefficients_is_explicitly_unavailable():
    model = DynamicLossModel(
        LossModelConfig(enable_iron_loss=True, enable_mechanical_loss=False)
    )
    result = model.compute(MotorState(0.0, 2.0, 100.0, 0.0), _parameters(), 25.0, 0.5)

    assert result.iron_loss_w is None
    assert result.total_loss_w == pytest.approx(result.copper_loss_w)
    assert any("unavailable" in warning for warning in result.warning_messages)


def test_provisional_iron_loss_requires_explicit_coefficients_and_flux_proxy():
    model = DynamicLossModel(
        LossModelConfig(
            enable_copper_loss=False,
            enable_iron_loss=True,
            enable_mechanical_loss=False,
        ),
        ProvisionalIronLossModel(0.1, 0.001),
    )
    result = model.compute(
        MotorState(0.0, 0.0, math.tau * 10.0 / 4.0, 0.0),
        _parameters(),
        25.0,
        0.5,
        flux_density_proxy=1.0,
    )

    assert result.iron_loss_w == pytest.approx(1.1)
    assert any("provisional" in warning for warning in result.warning_messages)
