"""Core data models with explicit units and legacy compatibility aliases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

import numpy as np

from .electrical_semantics import MotorControlMode, pole_pairs_to_pole_count


@dataclass(frozen=True)
class MotorAnalysisInput:
    """Normalized motor analysis input values.

    Lengths use meters, voltages use volts, power uses watts, and public speed
    quantities use explicit mechanical/electrical naming.
    """

    dc_bus_voltage_v: float
    rated_output_power_w: float
    mechanical_speed_rpm: float
    coil_temperature_c: float
    outer_diameter_m: float
    inner_diameter_m: float
    stator_outer_diameter_m: float
    stator_inner_diameter_m: float
    stator_thickness_m: float
    coil_height_m: float
    yoke_height_m: float
    air_gap_per_side_m: float
    slot_count: int
    slot_type: str
    slot_height_m: float
    slot_top_width_m: float
    slot_bottom_width_m: float
    slot_opening_height_m: float
    slot_opening_width_m: float
    wedge_height_m: float
    magnet_thickness_m: float
    magnet_width_m: float
    magnet_length_m: float
    magnet_type: str
    magnetization_type: str
    pole_pairs: int
    magnet_grade: str
    remanence_t: float
    pole_arc_coefficient: float
    leakage_factor: float
    magnet_relative_permeability: float
    turns_per_phase: int
    wire_diameter_m: float
    parallel_paths: int
    winding_factor: float
    fill_limit: float
    control_mode: MotorControlMode
    cogging_factor: float
    torque_ripple_6th: float
    torque_ripple_12th: float
    is_coreless: bool

    @property
    def pole_count(self) -> int:
        return pole_pairs_to_pole_count(self.pole_pairs)

    @property
    def rated_speed_rpm(self) -> float:
        return self.mechanical_speed_rpm

    @property
    def operating_mode(self) -> str:
        if self.control_mode is MotorControlMode.PMSM_SINUSOIDAL:
            return "pmsm"
        return "bldc"


@dataclass
class MotorGeometry:
    """Motor geometric values in meters."""

    outer_diameter_m: float
    inner_diameter_m: float
    magnet_thickness_m: float
    coil_height_m: float
    air_gap_per_side_m: float

    @property
    def average_diameter_m(self) -> float:
        return (self.outer_diameter_m + self.inner_diameter_m) / 2.0

    @property
    def effective_radial_length_m(self) -> float:
        return (self.outer_diameter_m - self.inner_diameter_m) / 2.0

    @property
    def effective_air_gap_m(self) -> float:
        return self.coil_height_m + 2.0 * self.air_gap_per_side_m

    @property
    def active_area_m2(self) -> float:
        return 3.141592653589793 * (self.outer_diameter_m**2 - self.inner_diameter_m**2) / 4.0

    @property
    def D_out(self) -> float:
        return self.outer_diameter_m

    @property
    def D_in(self) -> float:
        return self.inner_diameter_m

    @property
    def h_mag(self) -> float:
        return self.magnet_thickness_m

    @property
    def h_coil(self) -> float:
        return self.coil_height_m

    @property
    def g_side(self) -> float:
        return self.air_gap_per_side_m

    @property
    def D_avg(self) -> float:
        return self.average_diameter_m

    @property
    def L_eff(self) -> float:
        return self.effective_radial_length_m

    @property
    def g_eff(self) -> float:
        return self.effective_air_gap_m

    @property
    def active_area(self) -> float:
        return self.active_area_m2


@dataclass
class StatorGeometry:
    """Stator geometric values in meters."""

    stator_outer_diameter_m: float
    stator_inner_diameter_m: float
    stator_thickness_m: float
    yoke_height_m: float
    slot_count: int
    slot_type: str

    @property
    def slot_pitch_m(self) -> float:
        return 3.141592653589793 * (self.stator_outer_diameter_m + self.stator_inner_diameter_m) / 2.0 / self.slot_count

    @property
    def D_stator_out(self) -> float:
        return self.stator_outer_diameter_m

    @property
    def D_stator_in(self) -> float:
        return self.stator_inner_diameter_m

    @property
    def h_stator(self) -> float:
        return self.stator_thickness_m

    @property
    def h_yoke(self) -> float:
        return self.yoke_height_m

    @property
    def slots(self) -> int:
        return self.slot_count

    @property
    def slot_pitch(self) -> float:
        return self.slot_pitch_m


@dataclass
class SlotGeometry:
    """Slot geometric values in meters."""

    slot_height_m: float
    slot_top_width_m: float
    slot_bottom_width_m: float
    slot_opening_height_m: float
    slot_opening_width_m: float
    wedge_height_m: float

    @property
    def slot_area_m2(self) -> float:
        return (self.slot_top_width_m + self.slot_bottom_width_m) / 2.0 * self.slot_height_m

    @property
    def h_slot(self) -> float:
        return self.slot_height_m

    @property
    def w_slot_top(self) -> float:
        return self.slot_top_width_m

    @property
    def w_slot_bottom(self) -> float:
        return self.slot_bottom_width_m

    @property
    def h_slot_opening(self) -> float:
        return self.slot_opening_height_m

    @property
    def w_slot_opening(self) -> float:
        return self.slot_opening_width_m

    @property
    def h_wedge(self) -> float:
        return self.wedge_height_m

    @property
    def slot_area(self) -> float:
        return self.slot_area_m2


@dataclass
class MagnetGeometry:
    """Magnet geometric values in meters."""

    magnet_thickness_m: float
    magnet_width_m: float
    magnet_length_m: float
    magnet_type: str
    magnetization_type: str

    @property
    def magnet_volume_m3(self) -> float:
        return self.magnet_thickness_m * self.magnet_width_m * self.magnet_length_m

    @property
    def h_magnet(self) -> float:
        return self.magnet_thickness_m

    @property
    def w_magnet(self) -> float:
        return self.magnet_width_m

    @property
    def L_magnet(self) -> float:
        return self.magnet_length_m

    @property
    def magnetization(self) -> str:
        return self.magnetization_type

    @property
    def magnet_volume(self) -> float:
        return self.magnet_volume_m3


@dataclass
class MagneticCircuitResult:
    """Magnetic circuit outputs."""

    air_gap_flux_density_peak_t: float
    air_gap_flux_density_average_t: float
    air_gap_flux_density_rms_t: float
    pole_flux_wb: float
    permeance_coefficient: float
    air_gap_reluctance_a_per_wb: float
    magnet_reluctance_a_per_wb: float
    magnetomotive_force_a: float

    @property
    def Bg_peak(self) -> float:
        return self.air_gap_flux_density_peak_t

    @property
    def Bg_avg(self) -> float:
        return self.air_gap_flux_density_average_t

    @property
    def Bg_rms(self) -> float:
        return self.air_gap_flux_density_rms_t

    @property
    def Phi_pole(self) -> float:
        return self.pole_flux_wb

    @property
    def PC(self) -> float:
        return self.permeance_coefficient

    @property
    def R_gap(self) -> float:
        return self.air_gap_reluctance_a_per_wb

    @property
    def R_mag(self) -> float:
        return self.magnet_reluctance_a_per_wb

    @property
    def Fm(self) -> float:
        return self.magnetomotive_force_a


@dataclass
class ElectricalResult:
    """Electrical outputs."""

    control_mode: MotorControlMode
    legacy_control_model_name: str
    phase_resistance_ohm: float
    line_resistance_ohm: float
    phase_inductance_h: float
    line_inductance_h: float
    mutual_inductance_h: float
    dc_bus_voltage_v: float
    back_emf_phase_rms_v: float
    back_emf_phase_peak_v: float | None
    back_emf_line_rms_v: float
    back_emf_line_peak_v: float | None
    legacy_back_emf_constant_line_rms_v_per_krpm: float
    legacy_torque_constant_nm_per_phase_rms_a: float
    legacy_bldc_back_emf_constant_line_rms_v_per_krpm: float | None
    legacy_bldc_torque_constant_nm_per_phase_rms_a: float | None
    revised_back_emf_constant_phase_peak_v_per_rad_s: float | None
    revised_back_emf_constant_phase_rms_v_per_rad_s: float | None
    revised_back_emf_constant_line_rms_v_per_rad_s: float | None
    revised_back_emf_constant_line_rms_v_per_krpm: float | None
    revised_torque_constant_nm_per_phase_peak_a: float | None
    revised_torque_constant_nm_per_phase_rms_a: float | None
    revised_bldc_phase_flat_top_back_emf_v: float | None
    revised_bldc_phase_peak_back_emf_v: float | None
    revised_bldc_phase_rms_back_emf_v: float | None
    revised_bldc_line_to_line_peak_back_emf_v: float | None
    revised_bldc_line_to_line_rms_back_emf_v: float | None
    revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s: float | None
    revised_bldc_back_emf_constant_phase_peak_v_per_rad_s: float | None
    revised_bldc_back_emf_constant_phase_rms_v_per_rad_s: float | None
    revised_bldc_back_emf_constant_line_rms_v_per_rad_s: float | None
    revised_bldc_back_emf_constant_line_rms_v_per_krpm: float | None
    revised_bldc_torque_constant_nm_per_conduction_a: float | None
    revised_bldc_torque_constant_nm_per_phase_rms_a: float | None
    ke_legacy_revised_relative_difference: float | None
    kt_legacy_revised_relative_difference: float | None
    voltage_semantics_status: str
    ke_model_status: str
    kt_model_status: str
    pmsm_power_consistency_status: str
    bldc_waveform_semantics_status: str
    bldc_power_balance_status: str
    bldc_ke_semantics_status: str
    bldc_kt_semantics_status: str
    back_emf_constant_phase_peak_v_per_rad_s: float | None
    back_emf_constant_phase_rms_v_per_rad_s: float | None
    back_emf_constant_line_rms_v_per_rad_s: float | None
    back_emf_constant_line_rms_v_per_krpm: float | None
    torque_constant_nm_per_phase_peak_a: float | None
    torque_constant_nm_per_phase_rms_a: float | None

    @property
    def R_phase(self) -> float:
        return self.phase_resistance_ohm

    @property
    def R_line(self) -> float:
        return self.line_resistance_ohm

    @property
    def L_phase(self) -> float:
        return self.phase_inductance_h

    @property
    def L_line(self) -> float:
        return self.line_inductance_h

    @property
    def M_mutual(self) -> float:
        return self.mutual_inductance_h

    @property
    def E_phase_rms(self) -> float:
        return self.back_emf_phase_rms_v

    @property
    def E_line_rms(self) -> float:
        return self.back_emf_line_rms_v

    @property
    def Ke(self) -> float:
        return self.legacy_back_emf_constant_line_rms_v_per_krpm

    @property
    def Kt(self) -> float:
        return self.legacy_torque_constant_nm_per_phase_rms_a

    @property
    def ke_semantics_status(self) -> str:
        return self.ke_model_status

    @property
    def kt_semantics_status(self) -> str:
        return self.kt_model_status


@dataclass
class PerformanceResult:
    """Performance outputs."""

    control_mode: MotorControlMode
    legacy_control_model_name: str
    mechanical_speed_rpm: float
    mechanical_angular_speed_rad_s: float
    electrical_frequency_hz: float
    electrical_angular_speed_rad_s: float
    rated_torque_nm: float
    legacy_rated_torque_nm: float
    revised_rated_torque_nm: float
    rated_torque_absolute_difference_nm: float
    rated_torque_relative_difference: float
    rated_torque_model_status: str
    average_torque_nm: float
    torque_ripple_percent: float
    cogging_torque_peak_nm: float
    phase_current_rms_a: float
    phase_current_peak_a: float | None
    line_current_rms_a: float
    line_current_peak_a: float | None
    dc_bus_current_a: float
    current_density_a_per_mm2: float
    output_power_w: float
    input_power_w: float
    copper_loss_w: float
    eddy_loss_w: float
    mechanical_loss_w: float
    core_loss_w: float
    efficiency_percent: float
    required_voltage_v: float
    voltage_margin_percent: float
    fill_factor: float
    current_semantics_status: str
    required_voltage_semantics_status: str

    @property
    def T_rated(self) -> float:
        return self.rated_torque_nm

    @property
    def T_avg(self) -> float:
        return self.average_torque_nm

    @property
    def T_ripple(self) -> float:
        return self.torque_ripple_percent

    @property
    def T_cogging_peak(self) -> float:
        return self.cogging_torque_peak_nm

    @property
    def I_phase_rms(self) -> float:
        return self.phase_current_rms_a

    @property
    def I_line_rms(self) -> float:
        return self.line_current_rms_a

    @property
    def J_current(self) -> float:
        return self.current_density_a_per_mm2

    @property
    def P_out(self) -> float:
        return self.output_power_w

    @property
    def P_in(self) -> float:
        return self.input_power_w

    @property
    def P_cu(self) -> float:
        return self.copper_loss_w

    @property
    def P_eddy(self) -> float:
        return self.eddy_loss_w

    @property
    def P_mech(self) -> float:
        return self.mechanical_loss_w

    @property
    def P_core(self) -> float:
        return self.core_loss_w

    @property
    def Efficiency(self) -> float:
        return self.efficiency_percent

    @property
    def V_required(self) -> float:
        return self.required_voltage_v

    @property
    def V_margin(self) -> float:
        return self.voltage_margin_percent

    @property
    def K_fill(self) -> float:
        return self.fill_factor


@dataclass
class AnalysisResult:
    """Full motor analysis result."""

    geometry: MotorGeometry
    stator_geo: StatorGeometry
    slot_geo: SlotGeometry
    magnet_geo: MagnetGeometry
    magnetic: MagneticCircuitResult
    electrical: ElectricalResult
    performance: PerformanceResult
    waveforms: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "基本几何参数": asdict(self.geometry),
            "定子几何参数": asdict(self.stator_geo),
            "槽形几何参数": asdict(self.slot_geo),
            "永磁体几何参数": asdict(self.magnet_geo),
            "磁路计算结果": asdict(self.magnetic),
            "电气参数": asdict(self.electrical),
            "性能指标": asdict(self.performance),
            "元数据": self.metadata,
        }


def convert_waveform_arrays_to_lists(waveforms: Dict[str, Any]) -> Dict[str, Any]:
    converted: Dict[str, Any] = {}
    for key, value in waveforms.items():
        if isinstance(value, np.ndarray):
            converted[key] = value.tolist()
        elif isinstance(value, dict):
            converted[key] = convert_waveform_arrays_to_lists(value)
        else:
            converted[key] = value
    return converted
