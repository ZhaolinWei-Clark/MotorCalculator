"""Centralized unit conversions and legacy-to-core input mapping."""

from __future__ import annotations

from typing import Any, Mapping

from .constants import (
    DEFAULT_COGGING_FACTOR,
    DEFAULT_FILL_LIMIT,
    DEFAULT_RIPPLE_6TH,
    DEFAULT_RIPPLE_12TH,
)
from .electrical_semantics import (
    MotorControlMode,
    mechanical_angular_speed_rad_s_to_mechanical_speed_rpm,
    mechanical_speed_rpm_to_mechanical_angular_speed_rad_s,
    normalize_motor_control_mode,
)
from .models import MotorAnalysisInput


def mm_to_m(value_mm: float) -> float:
    return value_mm * 1e-3


def m_to_mm(value_m: float) -> float:
    return value_m * 1e3


def mm2_to_m2(value_mm2: float) -> float:
    return value_mm2 * 1e-6


def m2_to_mm2(value_m2: float) -> float:
    return value_m2 * 1e6


def rpm_to_mechanical_angular_speed_rad_s(speed_rpm: float) -> float:
    return mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(speed_rpm)


def mechanical_angular_speed_rad_s_to_rpm(speed_rad_s: float) -> float:
    return mechanical_angular_speed_rad_s_to_mechanical_speed_rpm(speed_rad_s)


def legacy_waveform_to_control_mode(waveform: str) -> MotorControlMode:
    try:
        return normalize_motor_control_mode(waveform)
    except Exception:
        # Legacy compatibility: the original implementation treated unknown
        # waveform labels as the non-sinusoidal branch.
        return MotorControlMode.BLDC_120_DEGREE


def control_mode_to_legacy_waveform(control_mode: MotorControlMode | str) -> str:
    normalized_mode = normalize_motor_control_mode(control_mode)
    if normalized_mode is MotorControlMode.PMSM_SINUSOIDAL:
        return "正弦波"
    if normalized_mode is MotorControlMode.BLDC_120_DEGREE:
        return "梯形波"
    return str(control_mode)


def legacy_params_to_model_input(params: Mapping[str, Any]) -> MotorAnalysisInput:
    return MotorAnalysisInput(
        dc_bus_voltage_v=float(params["V_dc"]),
        rated_output_power_w=float(params["P_rated"]),
        mechanical_speed_rpm=float(params["n_rated"]),
        coil_temperature_c=float(params["Temp_coil"]),
        outer_diameter_m=mm_to_m(float(params["D_out"])),
        inner_diameter_m=mm_to_m(float(params["D_in"])),
        stator_outer_diameter_m=mm_to_m(float(params.get("D_stator_out", params["D_out"]))),
        stator_inner_diameter_m=mm_to_m(float(params.get("D_stator_in", params["D_in"]))),
        stator_thickness_m=mm_to_m(float(params.get("h_stator", params["h_coil"]))),
        coil_height_m=mm_to_m(float(params["h_coil"])),
        yoke_height_m=mm_to_m(float(params.get("h_yoke", 5.0))),
        air_gap_per_side_m=mm_to_m(float(params["g_side"])),
        slot_count=int(params.get("slots", int(params["p"]) * 6)),
        slot_type=str(params.get("slot_type", "无槽")),
        slot_height_m=mm_to_m(float(params.get("h_slot", 15.0))),
        slot_top_width_m=mm_to_m(float(params.get("w_slot_top", 8.0))),
        slot_bottom_width_m=mm_to_m(float(params.get("w_slot_bottom", 6.0))),
        slot_opening_height_m=mm_to_m(float(params.get("h_slot_opening", 1.0))),
        slot_opening_width_m=mm_to_m(float(params.get("w_slot_opening", 3.0))),
        wedge_height_m=mm_to_m(float(params.get("h_wedge", 2.0))),
        magnet_thickness_m=mm_to_m(float(params["h_mag"])),
        magnet_width_m=mm_to_m(float(params.get("w_magnet", 20.0))),
        magnet_length_m=mm_to_m(float(params.get("L_magnet", 30.0))),
        magnet_type=str(params.get("magnet_type", "表贴式")),
        magnetization_type=str(params.get("magnetization", "径向充磁")),
        pole_pairs=int(params["p"]),
        magnet_grade=str(params.get("magnet_grade", "N42")),
        remanence_t=float(params["Br"]),
        pole_arc_coefficient=float(params["alpha_p"]),
        leakage_factor=float(params.get("sigma_m", 1.15)),
        magnet_relative_permeability=float(params.get("mu_r_mag", 1.05)),
        turns_per_phase=int(params["N_ph_turns"]),
        wire_diameter_m=mm_to_m(float(params["d_wire"])),
        parallel_paths=int(params["n_parallel"]),
        winding_factor=float(params["k_w"]),
        fill_limit=float(params.get("fill_limit", DEFAULT_FILL_LIMIT)),
        control_mode=legacy_waveform_to_control_mode(str(params.get("waveform", "正弦波"))),
        cogging_factor=float(params.get("k_cogging", DEFAULT_COGGING_FACTOR)),
        torque_ripple_6th=float(params.get("k_ripple_6", DEFAULT_RIPPLE_6TH)),
        torque_ripple_12th=float(params.get("k_ripple_12", DEFAULT_RIPPLE_12TH)),
        is_coreless=bool(params.get("coreless", True)),
    )
