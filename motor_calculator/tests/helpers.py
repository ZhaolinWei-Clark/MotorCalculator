"""Shared test helpers for the motor calculator suite."""

from __future__ import annotations

from typing import Any, Dict


def build_sample_legacy_params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
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
    params.update(overrides)
    return params
