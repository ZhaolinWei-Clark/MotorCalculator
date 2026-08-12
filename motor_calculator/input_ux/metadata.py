"""Audited metadata for every canonical legacy GUI input."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InputControlType(str, Enum):
    TEXT_NUMERIC = "TEXT_NUMERIC"
    SLIDER_NUMERIC = "SLIDER_NUMERIC"
    SPINBOX_INTEGER = "SPINBOX_INTEGER"
    DROPDOWN_ENUM = "DROPDOWN_ENUM"
    RADIO_ENUM = "RADIO_ENUM"
    TOGGLE_BOOLEAN = "TOGGLE_BOOLEAN"
    PRESET_SELECTOR = "PRESET_SELECTOR"
    TEXT_FREEFORM = "TEXT_FREEFORM"
    ADVANCED_CUSTOM = "ADVANCED_CUSTOM"


@dataclass(frozen=True)
class InputDefinition:
    field_name: str
    gui_label: str
    meaning: str
    unit: str
    default: str | int | float | bool
    control_type: InputControlType
    group: str
    beginner_visible: bool
    preset_suitable: bool
    tooltip: str


APPLICATION_DEFAULTS: dict[str, str | int | float | bool] = {
    "V_dc": 48.0, "P_rated": 800.0, "n_rated": 2500.0, "Temp_coil": 80.0,
    "D_out": 140.0, "D_in": 70.0, "g_side": 1.0,
    "D_stator_out": 138.0, "D_stator_in": 72.0, "h_stator": 20.0,
    "h_coil": 5.0, "h_yoke": 5.0, "slots": 24, "slot_type": "无槽",
    "h_slot": 15.0, "w_slot_top": 8.0, "w_slot_bottom": 6.0,
    "h_slot_opening": 1.0, "w_slot_opening": 3.0, "h_wedge": 2.0,
    "h_mag": 5.0, "w_magnet": 20.0, "L_magnet": 30.0,
    "magnet_type": "表贴式", "magnetization": "径向充磁", "p": 8,
    "magnet_grade": "N42", "Br": 1.28, "alpha_p": 0.70, "sigma_m": 1.15,
    "mu_r_mag": 1.05, "N_ph_turns": 50, "d_wire": 0.9, "n_parallel": 2,
    "k_w": 0.93, "fill_limit": 0.65, "waveform": "正弦波",
    "k_cogging": 0.02, "k_ripple_6": 0.05, "k_ripple_12": 0.02,
    "coreless": True,
}


def _definition(
    name: str,
    label: str,
    meaning: str,
    unit: str,
    control: InputControlType,
    group: str,
    *,
    basic: bool = False,
    preset: bool = False,
    caution: str = "",
) -> InputDefinition:
    tooltip = f"{meaning} Canonical unit: {unit}."
    if caution:
        tooltip += f" {caution}"
    return InputDefinition(name, label, meaning, unit, APPLICATION_DEFAULTS[name], control, group, basic, preset, tooltip)


INPUT_DEFINITIONS: dict[str, InputDefinition] = {
    item.field_name: item
    for item in (
        _definition("V_dc", "DC bus voltage", "Available DC bus voltage for the legacy operating point.", "V", InputControlType.SLIDER_NUMERIC, "Operating Point", basic=True, preset=True),
        _definition("P_rated", "Rated output power", "Rated shaft-output power used by the static calculator.", "W", InputControlType.TEXT_NUMERIC, "Operating Point", basic=True, preset=True),
        _definition("n_rated", "Rated speed", "Mechanical rotor speed, not electrical frequency.", "rpm", InputControlType.SLIDER_NUMERIC, "Operating Point", basic=True, preset=True),
        _definition("Temp_coil", "Winding temperature", "Winding temperature used for resistance evaluation.", "degC", InputControlType.SLIDER_NUMERIC, "Operating Point", basic=True, preset=True),
        _definition("D_out", "Motor outer diameter", "Overall active motor outer diameter.", "mm", InputControlType.SLIDER_NUMERIC, "Geometry", basic=True, preset=True),
        _definition("D_in", "Motor inner diameter", "Overall active motor inner diameter.", "mm", InputControlType.SLIDER_NUMERIC, "Geometry", basic=True, preset=True, caution="Must remain smaller than the outer diameter."),
        _definition("g_side", "Mechanical air gap per side", "Single-side mechanical air gap; dual-gap topology is handled by the existing model.", "mm", InputControlType.SLIDER_NUMERIC, "Geometry", basic=True, preset=True, caution="Do not enter the sum of both gaps."),
        _definition("D_stator_out", "Stator outer diameter", "Stator active outer diameter.", "mm", InputControlType.TEXT_NUMERIC, "Geometry"),
        _definition("D_stator_in", "Stator inner diameter", "Stator active inner diameter.", "mm", InputControlType.TEXT_NUMERIC, "Geometry"),
        _definition("h_stator", "Stator thickness", "Axial stator stack or body thickness.", "mm", InputControlType.TEXT_NUMERIC, "Geometry"),
        _definition("h_coil", "Coil height", "Axial coil build used by winding geometry.", "mm", InputControlType.TEXT_NUMERIC, "Winding"),
        _definition("h_yoke", "Yoke height", "Stator yoke dimension used by the legacy geometry model.", "mm", InputControlType.TEXT_NUMERIC, "Geometry"),
        _definition("slots", "Slot count", "Total stator slot count.", "count", InputControlType.SPINBOX_INTEGER, "Geometry", preset=True),
        _definition("slot_type", "Slot type", "Finite slot-geometry family supported by the existing calculator.", "enum", InputControlType.DROPDOWN_ENUM, "Geometry", preset=True),
        _definition("h_slot", "Slot depth", "Slot depth for slotted configurations.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("w_slot_top", "Slot top width", "Upper slot width.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("w_slot_bottom", "Slot bottom width", "Lower slot width.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("h_slot_opening", "Slot-opening height", "Slot-mouth opening height.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("w_slot_opening", "Slot-opening width", "Slot-mouth opening width.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("h_wedge", "Wedge height", "Slot wedge height.", "mm", InputControlType.TEXT_NUMERIC, "Advanced"),
        _definition("h_mag", "Magnet thickness", "Magnet dimension along the modeled magnetization direction.", "mm", InputControlType.SLIDER_NUMERIC, "Magnet / Material", basic=True, preset=True),
        _definition("w_magnet", "Magnet tangential width", "Magnet width in the circumferential direction.", "mm", InputControlType.TEXT_NUMERIC, "Magnet / Material"),
        _definition("L_magnet", "Magnet radial length", "Magnet span in the radial direction.", "mm", InputControlType.TEXT_NUMERIC, "Magnet / Material"),
        _definition("magnet_type", "Magnet arrangement", "Supported surface/interior magnet arrangement selector.", "enum", InputControlType.DROPDOWN_ENUM, "Magnet / Material", basic=True, preset=True),
        _definition("magnetization", "Magnetization type", "Finite magnetization option used by the legacy UI.", "enum", InputControlType.DROPDOWN_ENUM, "Magnet / Material", preset=True),
        _definition("p", "Pole pairs", "Number of pole pairs; total pole count is twice this value.", "pole_pairs", InputControlType.SPINBOX_INTEGER, "Geometry", basic=True, preset=True),
        _definition("magnet_grade", "Magnet grade", "Material grade label linked to a partial nominal-property preset.", "enum", InputControlType.DROPDOWN_ENUM, "Magnet / Material", basic=True, preset=True),
        _definition("Br", "Magnet remanence", "Nominal remanent flux density at the stated reference condition.", "T", InputControlType.TEXT_NUMERIC, "Magnet / Material", basic=True, preset=True, caution="Manufacturer and temperature variation must be checked."),
        _definition("alpha_p", "Pole-arc coefficient", "Ratio describing magnet pole-arc coverage.", "ratio", InputControlType.SLIDER_NUMERIC, "Advanced", preset=True),
        _definition("sigma_m", "Leakage factor", "Legacy empirical magnetic leakage factor.", "ratio", InputControlType.ADVANCED_CUSTOM, "Advanced", caution="This is an empirical model input, not a universal material property."),
        _definition("mu_r_mag", "Magnet relative permeability", "Relative recoil permeability used by the magnetic circuit.", "ratio", InputControlType.TEXT_NUMERIC, "Magnet / Material", preset=True),
        _definition("N_ph_turns", "Effective turns per phase", "Effective phase series turns used by the existing winding semantics.", "turns_per_phase", InputControlType.SPINBOX_INTEGER, "Winding", basic=True, preset=True),
        _definition("d_wire", "Wire diameter", "Bare/effective conductor diameter expected by the legacy winding model.", "mm", InputControlType.SLIDER_NUMERIC, "Winding", basic=True),
        _definition("n_parallel", "Parallel paths", "Number of parallel winding paths.", "parallel_paths", InputControlType.SPINBOX_INTEGER, "Winding", basic=True, preset=True),
        _definition("k_w", "Winding factor", "Pitch/distribution effect on effective flux linkage.", "ratio", InputControlType.SLIDER_NUMERIC, "Winding", basic=True, preset=True, caution="Do not use 1.0 unless the winding genuinely supports it."),
        _definition("fill_limit", "Fill-factor limit", "Legacy allowable winding fill ratio.", "ratio", InputControlType.SLIDER_NUMERIC, "Advanced"),
        _definition("waveform", "Back-EMF waveform", "Selects the existing PMSM sinusoidal or BLDC trapezoidal semantic path.", "enum", InputControlType.RADIO_ENUM, "Electrical", basic=True, preset=True, caution="RMS/peak and phase/line meanings depend on this selection."),
        _definition("k_cogging", "Cogging coefficient", "Legacy empirical cogging-torque coefficient.", "ratio", InputControlType.ADVANCED_CUSTOM, "Advanced"),
        _definition("k_ripple_6", "6th torque-ripple coefficient", "Legacy empirical sixth-order ripple coefficient.", "ratio", InputControlType.ADVANCED_CUSTOM, "Advanced"),
        _definition("k_ripple_12", "12th torque-ripple coefficient", "Legacy empirical twelfth-order ripple coefficient.", "ratio", InputControlType.ADVANCED_CUSTOM, "Advanced"),
        _definition("coreless", "Coreless stator", "Enables the existing coreless-stator branch.", "boolean", InputControlType.TOGGLE_BOOLEAN, "Geometry", basic=True, preset=True),
    )
}

BASIC_INPUT_FIELDS = frozenset(
    name for name, definition in INPUT_DEFINITIONS.items() if definition.beginner_visible
)
