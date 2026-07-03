"""Revised BLDC Ke definition tests."""

from __future__ import annotations

import math

import pytest

from motor_core import MotorControlMode, compare_legacy_and_revised_bldc_ke_kt
from motor_core.validation import MotorCalculationError

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_revised_bldc_ke_definitions_follow_explicit_waveform_units():
    semantics = compare_legacy_and_revised_bldc_ke_kt(
        control_mode=MotorControlMode.BLDC_120_DEGREE,
        legacy_back_emf_phase_rms_v=14.0,
        mechanical_speed_rpm=1000.0,
        legacy_back_emf_constant_line_rms_v_per_krpm=20.0,
    )

    mechanical_angular_speed_rad_s = 1000.0 * 2.0 * math.pi / 60.0

    assert math.isclose(
        semantics.revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s,
        semantics.revised_bldc_phase_flat_top_back_emf_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_back_emf_constant_phase_peak_v_per_rad_s,
        semantics.revised_bldc_phase_peak_back_emf_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_back_emf_constant_phase_rms_v_per_rad_s,
        semantics.revised_bldc_phase_rms_back_emf_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_back_emf_constant_line_rms_v_per_rad_s,
        semantics.revised_bldc_line_to_line_rms_back_emf_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_back_emf_constant_line_rms_v_per_krpm,
        semantics.revised_bldc_line_to_line_rms_back_emf_v,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_revised_bldc_ke_definitions_reject_non_bldc_mode():
    with pytest.raises(MotorCalculationError):
        compare_legacy_and_revised_bldc_ke_kt(
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
            legacy_back_emf_phase_rms_v=14.0,
            mechanical_speed_rpm=1000.0,
            legacy_back_emf_constant_line_rms_v_per_krpm=20.0,
        )


@pytest.mark.parametrize(
    ("legacy_back_emf_phase_rms_v", "mechanical_speed_rpm", "legacy_back_emf_constant_line_rms_v_per_krpm"),
    (
        (0.0, 1000.0, 20.0),
        (-1.0, 1000.0, 20.0),
        (14.0, 0.0, 20.0),
        (14.0, -1.0, 20.0),
        (14.0, 1000.0, 0.0),
        (14.0, 1000.0, -1.0),
    ),
)
def test_revised_bldc_ke_definitions_reject_invalid_inputs(
    legacy_back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
    legacy_back_emf_constant_line_rms_v_per_krpm: float,
):
    with pytest.raises(MotorCalculationError):
        compare_legacy_and_revised_bldc_ke_kt(
            control_mode=MotorControlMode.BLDC_120_DEGREE,
            legacy_back_emf_phase_rms_v=legacy_back_emf_phase_rms_v,
            mechanical_speed_rpm=mechanical_speed_rpm,
            legacy_back_emf_constant_line_rms_v_per_krpm=legacy_back_emf_constant_line_rms_v_per_krpm,
        )

