"""Pytest-style unit conversion tests."""

from __future__ import annotations

import math

from motor_core.units import legacy_params_to_model_input, mm_to_m, rpm_to_mechanical_angular_speed_rad_s


def test_mm_to_m_conversion():
    assert math.isclose(mm_to_m(140.0), 0.14, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(mm_to_m(0.9), 0.0009, rel_tol=1e-12, abs_tol=1e-12)


def test_rpm_to_mechanical_angular_speed_conversion():
    value = rpm_to_mechanical_angular_speed_rad_s(3000.0)
    assert abs(value - 314.1592653589793) < 1e-12


def test_legacy_params_to_model_input_maps_pole_pairs_and_lengths():
    params = {
        "V_dc": 48.0,
        "P_rated": 800.0,
        "n_rated": 2500.0,
        "Temp_coil": 80.0,
        "D_out": 140.0,
        "D_in": 70.0,
        "g_side": 1.0,
        "D_stator_out": 138.0,
        "D_stator_in": 72.0,
        "h_stator": 20.0,
        "h_coil": 5.0,
        "h_yoke": 5.0,
        "slots": 24,
        "slot_type": "无槽",
        "h_slot": 15.0,
        "w_slot_top": 8.0,
        "w_slot_bottom": 6.0,
        "h_slot_opening": 1.0,
        "w_slot_opening": 3.0,
        "h_wedge": 2.0,
        "h_mag": 5.0,
        "w_magnet": 20.0,
        "L_magnet": 30.0,
        "magnet_type": "表贴式",
        "magnetization": "径向充磁",
        "p": 8,
        "magnet_grade": "N42",
        "Br": 1.28,
        "alpha_p": 0.70,
        "sigma_m": 1.15,
        "mu_r_mag": 1.05,
        "N_ph_turns": 50,
        "d_wire": 0.9,
        "n_parallel": 2,
        "k_w": 0.93,
        "fill_limit": 0.65,
        "waveform": "正弦波",
        "k_cogging": 0.02,
        "k_ripple_6": 0.05,
        "k_ripple_12": 0.02,
        "coreless": True,
    }
    motor_input = legacy_params_to_model_input(params)
    assert motor_input.pole_pairs == 8
    assert motor_input.pole_count == 16
    assert math.isclose(motor_input.outer_diameter_m, 0.14, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(motor_input.wire_diameter_m, 0.0009, rel_tol=1e-12, abs_tol=1e-12)
    assert motor_input.operating_mode == "pmsm"
