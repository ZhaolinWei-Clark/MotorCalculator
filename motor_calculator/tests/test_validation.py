"""Pytest-style validation tests."""

from __future__ import annotations

from motor_core import MotorValidationError, legacy_params_to_model_input, parse_legacy_gui_params
from motor_core.validation import validate_motor_input


def _expect_raises(exc_type, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exc_type as exc:  # pragma: no cover - helper branch
        return exc
    raise AssertionError(f"Expected {exc_type.__name__} to be raised")


def test_invalid_text_numeric_input_is_not_silently_replaced():
    exc = _expect_raises(
        MotorValidationError,
        parse_legacy_gui_params,
        {
            "V_dc": "abc",
            "P_rated": "800",
            "n_rated": "2500",
            "Temp_coil": "80",
            "D_out": "140",
            "D_in": "70",
            "g_side": "1",
            "D_stator_out": "138",
            "D_stator_in": "72",
            "h_stator": "20",
            "h_coil": "5",
            "h_yoke": "5",
            "slots": "24",
            "h_slot": "15",
            "w_slot_top": "8",
            "w_slot_bottom": "6",
            "h_slot_opening": "1",
            "w_slot_opening": "3",
            "h_wedge": "2",
            "h_mag": "5",
            "w_magnet": "20",
            "L_magnet": "30",
            "p": "8",
            "Br": "1.28",
            "alpha_p": "0.7",
            "sigma_m": "1.15",
            "mu_r_mag": "1.05",
            "N_ph_turns": "50",
            "d_wire": "0.9",
            "n_parallel": "2",
            "k_w": "0.93",
            "fill_limit": "0.65",
            "k_cogging": "0.02",
            "k_ripple_6": "0.05",
            "k_ripple_12": "0.02",
        },
    )
    message = str(exc)
    assert "直流母线电压" in message
    assert "abc" in message
    assert "建议" in message


def test_outer_diameter_must_be_larger_than_inner_diameter():
    parsed = parse_legacy_gui_params(
        {
            "V_dc": "48",
            "P_rated": "800",
            "n_rated": "2500",
            "Temp_coil": "80",
            "D_out": "70",
            "D_in": "70",
            "g_side": "1",
            "D_stator_out": "138",
            "D_stator_in": "72",
            "h_stator": "20",
            "h_coil": "5",
            "h_yoke": "5",
            "slots": "24",
            "h_slot": "15",
            "w_slot_top": "8",
            "w_slot_bottom": "6",
            "h_slot_opening": "1",
            "w_slot_opening": "3",
            "h_wedge": "2",
            "h_mag": "5",
            "w_magnet": "20",
            "L_magnet": "30",
            "p": "8",
            "Br": "1.28",
            "alpha_p": "0.7",
            "sigma_m": "1.15",
            "mu_r_mag": "1.05",
            "N_ph_turns": "50",
            "d_wire": "0.9",
            "n_parallel": "2",
            "k_w": "0.93",
            "fill_limit": "0.65",
            "k_cogging": "0.02",
            "k_ripple_6": "0.05",
            "k_ripple_12": "0.02",
        }
    )
    motor_input = legacy_params_to_model_input(parsed)
    exc = _expect_raises(MotorValidationError, validate_motor_input, motor_input)
    assert "外径必须大于内径" in str(exc)


def test_winding_factor_must_stay_within_range():
    exc = _expect_raises(
        MotorValidationError,
        parse_legacy_gui_params,
        {
            "V_dc": "48",
            "P_rated": "800",
            "n_rated": "2500",
            "Temp_coil": "80",
            "D_out": "140",
            "D_in": "70",
            "g_side": "1",
            "D_stator_out": "138",
            "D_stator_in": "72",
            "h_stator": "20",
            "h_coil": "5",
            "h_yoke": "5",
            "slots": "24",
            "h_slot": "15",
            "w_slot_top": "8",
            "w_slot_bottom": "6",
            "h_slot_opening": "1",
            "w_slot_opening": "3",
            "h_wedge": "2",
            "h_mag": "5",
            "w_magnet": "20",
            "L_magnet": "30",
            "p": "8",
            "Br": "1.28",
            "alpha_p": "0.7",
            "sigma_m": "1.15",
            "mu_r_mag": "1.05",
            "N_ph_turns": "50",
            "d_wire": "0.9",
            "n_parallel": "2",
            "k_w": "1.2",
            "fill_limit": "0.65",
            "k_cogging": "0.02",
            "k_ripple_6": "0.05",
            "k_ripple_12": "0.02",
        },
    )
    message = str(exc)
    assert "绕组系数" in message
    assert "超出上限" in message
