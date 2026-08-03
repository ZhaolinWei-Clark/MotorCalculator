"""Validation for the sandbox-only MTPA current-reference foundation."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from dynamics import MTPAController, PMSMDynamicParameters


def _parameters(*, ld: float, lq: float) -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=0.2,
        Ld=ld,
        Lq=lq,
        psi_f=0.08,
        pole_pairs=4,
        J=0.02,
        B=0.001,
    )


def test_spmsm_mtpa_uses_zero_d_axis_current():
    parameters = _parameters(ld=0.005, lq=0.005)
    result = MTPAController(current_limit_a=30.0).compute_current_reference(
        torque_reference_nm=6.0,
        motor_parameters=parameters,
    )

    expected_iq = 6.0 / (1.5 * parameters.pole_pairs * parameters.psi_f)
    assert result.id_reference == pytest.approx(0.0)
    assert result.iq_reference == pytest.approx(expected_iq)
    assert result.method == "spmsm_id_zero"
    assert result.current_limited is False


def test_ipmsm_negative_id_improves_torque_per_current_for_typical_saliency():
    parameters = _parameters(ld=0.003, lq=0.008)
    torque_reference = 8.0
    result = MTPAController(current_limit_a=40.0).compute_current_reference(
        torque_reference_nm=torque_reference,
        motor_parameters=parameters,
    )

    id_zero_iq = torque_reference / (
        1.5 * parameters.pole_pairs * parameters.psi_f
    )
    assert result.id_reference < 0.0
    assert result.current_magnitude_a < abs(id_zero_iq)
    assert result.estimated_torque_nm == pytest.approx(torque_reference)
    assert result.method == "ipmsm_discrete_mtpa"


def test_mtpa_current_magnitude_limit_is_respected():
    result = MTPAController(current_limit_a=10.0).compute_current_reference(
        torque_reference_nm=1000.0,
        motor_parameters=_parameters(ld=0.003, lq=0.008),
    )

    assert math.hypot(result.id_reference, result.iq_reference) <= 10.0 + 1.0e-12
    assert result.current_limited is True
    assert result.method == "ipmsm_current_limit_boundary"


def test_invalid_inductance_safely_falls_back_to_id_zero_strategy():
    invalid_parameters = SimpleNamespace(
        Ld=float("nan"),
        Lq=0.008,
        psi_f=0.08,
        pole_pairs=4,
    )
    result = MTPAController(current_limit_a=20.0).compute_current_reference(
        torque_reference_nm=4.0,
        motor_parameters=invalid_parameters,
    )

    assert result.id_reference == 0.0
    assert result.method == "fallback_id_zero_invalid_inductance"
    assert result.notes
