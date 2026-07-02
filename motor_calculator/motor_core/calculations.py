"""Pure calculation kernel for the AFPM PMSM/BLDC model."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from math import gcd, sqrt
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np

from .assumptions import DEFAULT_CONNECTION_ZH, DEFAULT_TOPOLOGY_ZH
from .constants import (
    AFPM_MUTUAL_REDUCTION_FACTOR,
    AIR_DENSITY,
    BALANCED_THREE_PHASE_MUTUAL_RATIO,
    BEARING_LOSS_RATED_POWER_RATIO,
    BEARING_LOSS_REFERENCE_SPEED_RPM,
    CORE_LOSS_RATED_POWER_RATIO,
    DEFAULT_SLOT_COUNT_PER_POLE_PAIR,
    END_WINDING_INDUCTANCE_RATIO,
    END_WINDING_LENGTH_FACTOR,
    LEGACY_POWER_SPEED_TO_TORQUE_FACTOR,
    LEGACY_SINE_EMF_FACTOR,
    LEGACY_TRAPEZOIDAL_EMF_FACTOR,
    MODE_TO_LEGACY_WAVEFORM,
    MU0,
    PI,
    RHO_CU_20,
    RHO_CU_TEMP_COEFF,
    SLOT_TYPES,
    VOLTAGE_REQUIREMENT_MARGIN_FACTOR,
    WINDAGE_COEFFICIENT,
)
from .models import (
    AnalysisResult,
    ElectricalResult,
    MagneticCircuitResult,
    MagnetGeometry,
    MotorAnalysisInput,
    MotorGeometry,
    PerformanceResult,
    SlotGeometry,
    StatorGeometry,
)
from .units import legacy_params_to_model_input
from .validation import validate_finite_result, validate_motor_input, validate_result_object_finite


class MotorAnalysisEngine:
    """Pure calculation engine without any GUI dependencies."""

    def __init__(self, motor_input: MotorAnalysisInput):
        self.motor_input = motor_input
        self.results: Optional[AnalysisResult] = None
        validate_motor_input(self.motor_input)

    def calculate_magnetic_circuit(self) -> MagneticCircuitResult:
        i = self.motor_input

        air_gap_effective_m = i.coil_height_m + 2.0 * i.air_gap_per_side_m
        pole_area_m2 = (
            (PI / (2.0 * i.pole_pairs))
            * ((i.outer_diameter_m / 2.0) ** 2 - (i.inner_diameter_m / 2.0) ** 2)
            * i.pole_arc_coefficient
        )
        carter_factor = SLOT_TYPES.get(i.slot_type, {"carter_factor": 1.0})["carter_factor"]

        air_gap_reluctance = (air_gap_effective_m * carter_factor) / (MU0 * pole_area_m2)
        magnet_reluctance = (2.0 * i.magnet_thickness_m) / (MU0 * i.magnet_relative_permeability * pole_area_m2)
        magnetomotive_force = 2.0 * (i.remanence_t / MU0) * i.magnet_thickness_m / i.magnet_relative_permeability
        pole_flux = magnetomotive_force / (air_gap_reluctance + i.leakage_factor * magnet_reluctance)
        air_gap_flux_density_peak = pole_flux / pole_area_m2
        air_gap_flux_density_average = air_gap_flux_density_peak * i.pole_arc_coefficient
        air_gap_flux_density_rms = air_gap_flux_density_peak * sqrt(i.pole_arc_coefficient)
        permeance_coefficient = (i.magnet_thickness_m * 2.0) / (air_gap_effective_m * i.leakage_factor)

        result = MagneticCircuitResult(
            air_gap_flux_density_peak_t=air_gap_flux_density_peak,
            air_gap_flux_density_average_t=air_gap_flux_density_average,
            air_gap_flux_density_rms_t=air_gap_flux_density_rms,
            pole_flux_wb=pole_flux,
            permeance_coefficient=permeance_coefficient,
            air_gap_reluctance_a_per_wb=air_gap_reluctance,
            magnet_reluctance_a_per_wb=magnet_reluctance,
            magnetomotive_force_a=magnetomotive_force,
        )
        validate_result_object_finite(result)
        return result

    def calculate_electrical_parameters(self, magnetic_result: MagneticCircuitResult) -> ElectricalResult:
        i = self.motor_input

        electrical_frequency_hz = i.rated_speed_rpm * i.pole_pairs / 60.0
        if i.operating_mode == "pmsm":
            back_emf_phase_rms = LEGACY_SINE_EMF_FACTOR * electrical_frequency_hz * i.turns_per_phase * magnetic_result.pole_flux_wb * i.winding_factor
        else:
            back_emf_phase_rms = LEGACY_TRAPEZOIDAL_EMF_FACTOR * electrical_frequency_hz * i.turns_per_phase * magnetic_result.pole_flux_wb * i.winding_factor

        back_emf_line_rms = sqrt(3.0) * back_emf_phase_rms
        back_emf_constant = back_emf_line_rms / (i.rated_speed_rpm / 1000.0)

        mechanical_speed_rad_s = i.rated_speed_rpm * 2.0 * PI / 60.0
        torque_constant_peak = (3.0 * back_emf_phase_rms) / (sqrt(2.0) * mechanical_speed_rad_s)
        torque_constant_rms = torque_constant_peak * sqrt(2.0)

        average_diameter_m = (i.outer_diameter_m + i.inner_diameter_m) / 2.0
        effective_radial_length_m = (i.outer_diameter_m - i.inner_diameter_m) / 2.0
        pole_pitch_m = PI * average_diameter_m / (2.0 * i.pole_pairs)
        end_winding_length_m = pole_pitch_m * END_WINDING_LENGTH_FACTOR
        turn_length_m = 2.0 * effective_radial_length_m + 2.0 * end_winding_length_m
        phase_conductor_length_m = turn_length_m * i.turns_per_phase
        copper_area_m2 = PI * (i.wire_diameter_m / 2.0) ** 2 * i.parallel_paths
        resistivity = RHO_CU_20 * (1.0 + RHO_CU_TEMP_COEFF * (i.coil_temperature_c - 20.0))
        phase_resistance = resistivity * phase_conductor_length_m / copper_area_m2
        line_resistance = 2.0 * phase_resistance

        air_gap_effective_m = i.coil_height_m + 2.0 * i.air_gap_per_side_m
        phase_effective_area_m2 = PI * ((i.outer_diameter_m / 2.0) ** 2 - (i.inner_diameter_m / 2.0) ** 2) / 6.0
        air_gap_inductance = MU0 * i.turns_per_phase**2 * phase_effective_area_m2 / air_gap_effective_m
        end_winding_inductance = END_WINDING_INDUCTANCE_RATIO * air_gap_inductance
        phase_inductance = air_gap_inductance + end_winding_inductance
        mutual_inductance = BALANCED_THREE_PHASE_MUTUAL_RATIO * phase_inductance * AFPM_MUTUAL_REDUCTION_FACTOR
        line_inductance = phase_inductance - mutual_inductance

        result = ElectricalResult(
            phase_resistance_ohm=phase_resistance,
            line_resistance_ohm=line_resistance,
            phase_inductance_h=phase_inductance,
            line_inductance_h=line_inductance,
            mutual_inductance_h=mutual_inductance,
            back_emf_phase_rms_v=back_emf_phase_rms,
            back_emf_line_rms_v=back_emf_line_rms,
            back_emf_constant_v_per_krpm=back_emf_constant,
            torque_constant_nm_per_a_rms=torque_constant_rms,
        )
        validate_result_object_finite(result)
        return result

    def calculate_losses(self, electrical_result: ElectricalResult, phase_current_rms_a: float, magnetic_result: MagneticCircuitResult) -> Tuple[float, float, float, float]:
        i = self.motor_input
        electrical_frequency_hz = i.rated_speed_rpm * i.pole_pairs / 60.0
        copper_loss_w = 3.0 * phase_current_rms_a**2 * electrical_result.phase_resistance_ohm

        resistivity = RHO_CU_20 * (1.0 + RHO_CU_TEMP_COEFF * (i.coil_temperature_c - 20.0))
        local_flux_density_t = magnetic_result.air_gap_flux_density_peak_t
        average_diameter_m = (i.outer_diameter_m + i.inner_diameter_m) / 2.0
        pole_pitch_m = PI * average_diameter_m / (2.0 * i.pole_pairs)
        effective_radial_length_m = (i.outer_diameter_m - i.inner_diameter_m) / 2.0
        turn_length_m = 2.0 * effective_radial_length_m + 2.0 * pole_pitch_m * END_WINDING_LENGTH_FACTOR
        copper_area_m2 = PI * (i.wire_diameter_m / 2.0) ** 2 * i.parallel_paths
        copper_volume_m3 = 3.0 * i.turns_per_phase * turn_length_m * copper_area_m2
        skin_depth_m = sqrt(2.0 * resistivity / (MU0 * 2.0 * PI * electrical_frequency_hz))
        skin_factor = 1.0 if i.wire_diameter_m < 2.0 * skin_depth_m else (i.wire_diameter_m / (2.0 * skin_depth_m))
        eddy_loss_w = (PI**2 / 24.0) * (electrical_frequency_hz * local_flux_density_t * i.wire_diameter_m) ** 2 / resistivity * copper_volume_m3 * skin_factor

        core_loss_w = CORE_LOSS_RATED_POWER_RATIO * i.rated_output_power_w
        mechanical_speed_rad_s = i.rated_speed_rpm * 2.0 * PI / 60.0
        windage_loss_w = 0.5 * WINDAGE_COEFFICIENT * AIR_DENSITY * mechanical_speed_rad_s**3 * ((i.outer_diameter_m / 2.0) ** 5 - (i.inner_diameter_m / 2.0) ** 5) * 2.0
        bearing_loss_w = BEARING_LOSS_RATED_POWER_RATIO * i.rated_output_power_w * (i.rated_speed_rpm / BEARING_LOSS_REFERENCE_SPEED_RPM)
        mechanical_loss_w = windage_loss_w + bearing_loss_w

        for name, value in {
            "铜损": copper_loss_w,
            "涡流损耗": eddy_loss_w,
            "铁损": core_loss_w,
            "机械损耗": mechanical_loss_w,
        }.items():
            validate_finite_result(name, value)

        return copper_loss_w, eddy_loss_w, core_loss_w, mechanical_loss_w

    def calculate_cogging_torque(self) -> Tuple[np.ndarray, np.ndarray]:
        i = self.motor_input
        pole_count = i.pole_count
        slot_count = i.slot_count if i.slot_count else pole_count * 3
        least_common_multiple = (pole_count * slot_count) // gcd(pole_count, slot_count)
        rotor_position_rad = np.linspace(0.0, 2.0 * PI, 360)

        if i.is_coreless:
            return rotor_position_rad, np.zeros_like(rotor_position_rad)

        rated_torque_nm = LEGACY_POWER_SPEED_TO_TORQUE_FACTOR * i.rated_output_power_w / i.rated_speed_rpm
        cogging_peak_nm = i.cogging_factor * rated_torque_nm
        cogging_waveform = cogging_peak_nm * (
            np.sin(least_common_multiple * rotor_position_rad)
            + 0.3 * np.sin(2.0 * least_common_multiple * rotor_position_rad)
            + 0.1 * np.sin(3.0 * least_common_multiple * rotor_position_rad)
        )
        return rotor_position_rad, cogging_waveform

    def calculate_back_emf_waveform(self, magnetic_result: MagneticCircuitResult) -> Dict[str, Any]:
        i = self.motor_input
        electrical_frequency_hz = i.rated_speed_rpm * i.pole_pairs / 60.0
        electrical_period_s = 1.0 / electrical_frequency_hz
        time_s = np.linspace(0.0, 2.0 * electrical_period_s, 720)
        electrical_angle_rad = 2.0 * PI * electrical_frequency_hz * time_s
        mechanical_angle_rad = electrical_angle_rad / i.pole_pairs
        peak_back_emf_v = 2.0 * PI * electrical_frequency_hz * i.turns_per_phase * magnetic_result.pole_flux_wb * i.winding_factor

        if i.operating_mode == "pmsm":
            phase_a = peak_back_emf_v * np.sin(electrical_angle_rad)
            phase_b = peak_back_emf_v * np.sin(electrical_angle_rad - 2.0 * PI / 3.0)
            phase_c = peak_back_emf_v * np.sin(electrical_angle_rad - 4.0 * PI / 3.0)
        else:
            phase_a = self._trapezoidal_back_emf(electrical_angle_rad, peak_back_emf_v, i.pole_arc_coefficient)
            phase_b = self._trapezoidal_back_emf(electrical_angle_rad - 2.0 * PI / 3.0, peak_back_emf_v, i.pole_arc_coefficient)
            phase_c = self._trapezoidal_back_emf(electrical_angle_rad - 4.0 * PI / 3.0, peak_back_emf_v, i.pole_arc_coefficient)

        return {
            "time": time_s,
            "theta_e": electrical_angle_rad,
            "theta_m": np.degrees(mechanical_angle_rad),
            "E_a": phase_a,
            "E_b": phase_b,
            "E_c": phase_c,
            "E_ab": phase_a - phase_b,
            "E_bc": phase_b - phase_c,
            "E_ca": phase_c - phase_a,
            "E_ideal": peak_back_emf_v * np.sin(electrical_angle_rad),
            "E_peak": peak_back_emf_v,
            "E_rms": peak_back_emf_v / sqrt(2.0),
        }

    @staticmethod
    def _trapezoidal_back_emf(angle_rad: np.ndarray, peak_back_emf_v: float, pole_arc_coefficient: float) -> np.ndarray:
        angle_rad = np.mod(angle_rad, 2.0 * PI)
        waveform = np.zeros_like(angle_rad)
        flat_angle = PI * pole_arc_coefficient
        rise_angle = PI * (1.0 - pole_arc_coefficient) / 2.0

        for index, angle in enumerate(angle_rad):
            angle_mod = angle % (2.0 * PI)
            if angle_mod < rise_angle:
                waveform[index] = peak_back_emf_v * angle_mod / rise_angle
            elif angle_mod < rise_angle + flat_angle:
                waveform[index] = peak_back_emf_v
            elif angle_mod < PI:
                waveform[index] = peak_back_emf_v * (PI - angle_mod) / rise_angle
            elif angle_mod < PI + rise_angle:
                waveform[index] = -peak_back_emf_v * (angle_mod - PI) / rise_angle
            elif angle_mod < PI + rise_angle + flat_angle:
                waveform[index] = -peak_back_emf_v
            else:
                waveform[index] = -peak_back_emf_v * (2.0 * PI - angle_mod) / rise_angle

        return waveform

    def calculate_torque_waveform(self) -> Dict[str, Any]:
        i = self.motor_input
        rated_torque_nm = LEGACY_POWER_SPEED_TO_TORQUE_FACTOR * i.rated_output_power_w / i.rated_speed_rpm
        electrical_angle_rad = np.linspace(0.0, 4.0 * PI, 720)
        ripple = i.torque_ripple_6th * np.cos(6.0 * electrical_angle_rad) + i.torque_ripple_12th * np.cos(12.0 * electrical_angle_rad)
        instantaneous_torque = rated_torque_nm * (1.0 + ripple)
        torque_ripple_percent = (np.max(instantaneous_torque) - np.min(instantaneous_torque)) / rated_torque_nm * 100.0

        return {
            "theta_e": np.degrees(electrical_angle_rad),
            "T_inst": instantaneous_torque,
            "T_avg": rated_torque_nm,
            "T_ripple_pct": torque_ripple_percent,
            "T_max": np.max(instantaneous_torque),
            "T_min": np.min(instantaneous_torque),
        }

    def calculate_flux_distribution(self, magnetic_result: MagneticCircuitResult) -> Dict[str, Any]:
        i = self.motor_input
        pole_count = i.pole_count
        mechanical_angle_deg = np.linspace(0.0, 360.0, 720)
        pole_pitch_deg = 360.0 / pole_count
        air_gap_flux_density = np.zeros_like(mechanical_angle_deg)

        for index, angle_deg in enumerate(mechanical_angle_deg):
            angle_in_pole_pair = angle_deg % (2.0 * pole_pitch_deg)
            if angle_in_pole_pair < pole_pitch_deg * i.pole_arc_coefficient:
                air_gap_flux_density[index] = magnetic_result.air_gap_flux_density_peak_t
            elif angle_in_pole_pair < pole_pitch_deg:
                air_gap_flux_density[index] = 0.0
            elif angle_in_pole_pair < pole_pitch_deg * (1.0 + i.pole_arc_coefficient):
                air_gap_flux_density[index] = -magnetic_result.air_gap_flux_density_peak_t
            else:
                air_gap_flux_density[index] = 0.0

        air_gap_flux_density_average = np.mean(np.abs(air_gap_flux_density))
        air_gap_flux_density_rms = np.sqrt(np.mean(air_gap_flux_density**2))
        spectrum = np.abs(np.fft.fft(air_gap_flux_density)[: len(air_gap_flux_density) // 2]) / len(air_gap_flux_density) * 2.0
        harmonics = np.arange(len(spectrum)) * pole_count / 2.0

        return {
            "theta_m": mechanical_angle_deg,
            "Bg": air_gap_flux_density,
            "Bg_peak": magnetic_result.air_gap_flux_density_peak_t,
            "Bg_avg": air_gap_flux_density_average,
            "Bg_rms": air_gap_flux_density_rms,
            "harmonics": harmonics[:50],
            "spectrum": spectrum[:50],
        }

    def run_full_analysis(self) -> AnalysisResult:
        i = self.motor_input

        geometry = MotorGeometry(
            outer_diameter_m=i.outer_diameter_m,
            inner_diameter_m=i.inner_diameter_m,
            magnet_thickness_m=i.magnet_thickness_m,
            coil_height_m=i.coil_height_m,
            air_gap_per_side_m=i.air_gap_per_side_m,
        )
        stator_geometry = StatorGeometry(
            stator_outer_diameter_m=i.stator_outer_diameter_m,
            stator_inner_diameter_m=i.stator_inner_diameter_m,
            stator_thickness_m=i.stator_thickness_m,
            yoke_height_m=i.yoke_height_m,
            slot_count=i.slot_count,
            slot_type=i.slot_type,
        )
        slot_geometry = SlotGeometry(
            slot_height_m=i.slot_height_m,
            slot_top_width_m=i.slot_top_width_m,
            slot_bottom_width_m=i.slot_bottom_width_m,
            slot_opening_height_m=i.slot_opening_height_m,
            slot_opening_width_m=i.slot_opening_width_m,
            wedge_height_m=i.wedge_height_m,
        )
        magnet_geometry = MagnetGeometry(
            magnet_thickness_m=i.magnet_thickness_m,
            magnet_width_m=i.magnet_width_m,
            magnet_length_m=i.magnet_length_m,
            magnet_type=i.magnet_type,
            magnetization_type=i.magnetization_type,
        )

        magnetic_result = self.calculate_magnetic_circuit()
        electrical_result = self.calculate_electrical_parameters(magnetic_result)
        rated_torque_nm = LEGACY_POWER_SPEED_TO_TORQUE_FACTOR * i.rated_output_power_w / i.rated_speed_rpm
        phase_current_rms_a = rated_torque_nm / electrical_result.torque_constant_nm_per_a_rms
        copper_loss_w, eddy_loss_w, core_loss_w, mechanical_loss_w = self.calculate_losses(
            electrical_result, phase_current_rms_a, magnetic_result
        )
        total_loss_w = copper_loss_w + eddy_loss_w + core_loss_w + mechanical_loss_w
        input_power_w = i.rated_output_power_w + total_loss_w
        efficiency_percent = i.rated_output_power_w / input_power_w * 100.0

        resistive_voltage_drop_v = phase_current_rms_a * electrical_result.line_resistance_ohm
        inductive_voltage_drop_v = 2.0 * PI * (i.rated_speed_rpm * i.pole_pairs / 60.0) * electrical_result.line_inductance_h * phase_current_rms_a
        required_voltage_v = sqrt(
            electrical_result.back_emf_line_rms_v**2 + resistive_voltage_drop_v**2 + inductive_voltage_drop_v**2
        ) * VOLTAGE_REQUIREMENT_MARGIN_FACTOR
        voltage_margin_percent = (i.dc_bus_voltage_v - required_voltage_v) / i.dc_bus_voltage_v * 100.0

        copper_area_m2 = PI * (i.wire_diameter_m / 2.0) ** 2 * i.parallel_paths
        current_density_a_per_mm2 = phase_current_rms_a / (copper_area_m2 * 1e6)
        fill_factor = (3.0 * i.turns_per_phase * 2.0 * i.parallel_paths * i.wire_diameter_m) / (PI * i.inner_diameter_m)

        torque_waveform = self.calculate_torque_waveform()
        cogging_theta_rad, cogging_torque_nm = self.calculate_cogging_torque()

        performance_result = PerformanceResult(
            rated_torque_nm=rated_torque_nm,
            average_torque_nm=torque_waveform["T_avg"],
            torque_ripple_percent=torque_waveform["T_ripple_pct"],
            cogging_torque_peak_nm=np.max(np.abs(cogging_torque_nm)),
            phase_current_rms_a=phase_current_rms_a,
            line_current_rms_a=phase_current_rms_a,
            current_density_a_per_mm2=current_density_a_per_mm2,
            output_power_w=i.rated_output_power_w,
            input_power_w=input_power_w,
            copper_loss_w=copper_loss_w,
            eddy_loss_w=eddy_loss_w,
            mechanical_loss_w=mechanical_loss_w,
            core_loss_w=core_loss_w,
            efficiency_percent=efficiency_percent,
            required_voltage_v=required_voltage_v,
            voltage_margin_percent=voltage_margin_percent,
            fill_factor=fill_factor,
        )
        validate_result_object_finite(performance_result)

        waveforms = {
            "back_emf": self.calculate_back_emf_waveform(magnetic_result),
            "torque": torque_waveform,
            "flux": self.calculate_flux_distribution(magnetic_result),
            "cogging": {"theta": cogging_theta_rad, "T_cog": cogging_torque_nm},
        }
        metadata = {
            "计算时间": datetime.now().isoformat(),
            "模型版本": "6.0-refactor",
            "波形类型": MODE_TO_LEGACY_WAVEFORM.get(i.operating_mode, i.operating_mode),
            "默认拓扑": DEFAULT_TOPOLOGY_ZH,
            "默认连接": DEFAULT_CONNECTION_ZH,
            "极对数": i.pole_pairs,
            "总极数": i.pole_count,
        }

        self.results = AnalysisResult(
            geometry=geometry,
            stator_geo=stator_geometry,
            slot_geo=slot_geometry,
            magnet_geo=magnet_geometry,
            magnetic=magnetic_result,
            electrical=electrical_result,
            performance=performance_result,
            waveforms=waveforms,
            metadata=metadata,
        )
        return self.results


class LegacyGuiMotorModelBridge:
    """Adapter that preserves the legacy GUI contract while using the new core."""

    def __init__(self, params: Mapping[str, Any]):
        self.params = dict(params)
        self.input_data = legacy_params_to_model_input(self.params)
        self.engine = MotorAnalysisEngine(self.input_data)
        self.results: Optional[AnalysisResult] = None

    def run_full_analysis(self) -> AnalysisResult:
        self.results = self.engine.run_full_analysis()
        return self.results


def calculate_from_legacy_params(params: Mapping[str, Any]) -> AnalysisResult:
    return LegacyGuiMotorModelBridge(params).run_full_analysis()
