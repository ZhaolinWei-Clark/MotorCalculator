"""Phase 8D input metadata, presets, units, controls, and guidance tests."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from motor_calculator.input_ux import (
    APPLICATION_DEFAULTS,
    BASIC_INPUT_FIELDS,
    INPUT_DEFINITIONS,
    SLIDER_SPECS,
    DisplayUnitPreferences,
    GuidanceLevel,
    GuidanceSeverity,
    InputControlType,
    canonical_to_display_inputs,
    convert_display_value,
    display_to_canonical_inputs,
    evaluate_input_guidance,
    format_engineering_value,
    parse_spinbox_integer,
    slider_from_numeric_text,
    slider_range_for_units,
    slider_to_numeric_text,
)
from motor_calculator.presets import (
    PresetCategory,
    PresetEvidenceKind,
    PresetLoadError,
    apply_preset,
    default_preset_registry,
    load_preset_payload,
    preview_preset,
)
from motor_calculator.gui.main_window import MotorCalculatorAppMixin
from motor_calculator.project import (
    PROJECT_INPUT_SPECS,
    RecoveryManager,
    create_project_document,
    flatten_project_inputs,
    load_project,
    load_recovery,
    save_project,
)


ROOT = Path(__file__).resolve().parents[2]


def test_every_project_input_has_one_ux_definition_and_default():
    assert set(INPUT_DEFINITIONS) == set(PROJECT_INPUT_SPECS)
    assert set(APPLICATION_DEFAULTS) == set(PROJECT_INPUT_SPECS)
    assert len(INPUT_DEFINITIONS) == 41


def test_every_input_control_type_is_explicit():
    assert all(isinstance(item.control_type, InputControlType) for item in INPUT_DEFINITIONS.values())
    assert INPUT_DEFINITIONS["g_side"].control_type is InputControlType.SLIDER_NUMERIC
    assert INPUT_DEFINITIONS["p"].control_type is InputControlType.SPINBOX_INTEGER
    assert INPUT_DEFINITIONS["waveform"].control_type is InputControlType.RADIO_ENUM
    assert INPUT_DEFINITIONS["coreless"].control_type is InputControlType.TOGGLE_BOOLEAN


def test_basic_mode_is_a_nonempty_subset_and_advanced_preserves_every_field():
    assert BASIC_INPUT_FIELDS
    assert BASIC_INPUT_FIELDS < set(INPUT_DEFINITIONS)
    assert {"g_side", "p", "magnet_grade", "k_w", "waveform"} <= BASIC_INPUT_FIELDS


def test_registry_loads_with_unique_ids_and_all_categories():
    registry = default_preset_registry()
    ids = [preset.preset_id for preset in registry.presets]
    assert len(ids) == len(set(ids))
    assert {preset.category for preset in registry.presets} == set(PresetCategory)


def test_dssr_is_not_faked_when_schema_cannot_represent_it():
    preset = default_preset_registry().get("template.afpm_dssr.unavailable.v1")
    assert not preset.available
    assert preset.values == {}
    assert "cannot represent" in preset.unavailable_reason
    with pytest.raises(ValueError, match="cannot represent"):
        apply_preset(APPLICATION_DEFAULTS, preset)


def test_partial_magnet_preset_changes_no_unrelated_field():
    preset = default_preset_registry().get("magnet.n35.v1")
    current = dict(APPLICATION_DEFAULTS, D_out=166.75, n_rated=3210.5)
    applied = apply_preset(current, preset)
    assert applied["magnet_grade"] == "N35"
    assert applied["Br"] == 1.17
    assert applied["D_out"] == 166.75
    assert applied["n_rated"] == 3210.5


def test_pmsm_and_bldc_templates_only_change_waveform():
    registry = default_preset_registry()
    for preset_id, expected in (("template.pmsm.v1", "正弦波"), ("template.bldc.v1", "梯形波")):
        preset = registry.get(preset_id)
        assert set(preset.values) == {"waveform"}
        assert apply_preset(APPLICATION_DEFAULTS, preset)["waveform"] == expected


def test_preset_preview_lists_only_actual_changes():
    preset = default_preset_registry().get("operating.application_reference.v1")
    current = dict(APPLICATION_DEFAULTS, V_dc=72.0, n_rated=3000.0)
    changes = preview_preset(current, preset)
    assert {change.field_name for change in changes} == {"V_dc", "n_rated"}


def test_every_available_preset_retains_provenance_and_assumptions():
    for preset in default_preset_registry().presets:
        assert preset.provenance.strip()
        assert isinstance(preset.evidence_kind, PresetEvidenceKind)
        if preset.available:
            assert preset.assumptions


def test_loader_rejects_unknown_fields_and_duplicate_ids():
    with pytest.raises(PresetLoadError, match="unsupported fields"):
        load_preset_payload({
            "schema_version": 1,
            "presets": [{
                "preset_id": "bad", "version": 1, "display_name": "Bad",
                "category": "design_example", "evidence_kind": "demonstration",
                "values": {"not_a_field": 1}, "provenance": "test",
            }],
        })
    item = {
        "preset_id": "same", "version": 1, "display_name": "Same",
        "category": "design_example", "evidence_kind": "demonstration",
        "values": {}, "provenance": "test", "assumptions": ["test"],
    }
    with pytest.raises(PresetLoadError, match="unique"):
        load_preset_payload({"schema_version": 1, "presets": [item, item]})


def test_mm_m_conversion_round_trip():
    assert convert_display_value(1.2, "length", "mm", "m") == pytest.approx(0.0012)
    assert convert_display_value(0.0012, "length", "m", "mm") == pytest.approx(1.2)


def test_mm_m_conversion_preserves_exact_entered_decimal():
    original = 7.123456789
    displayed = convert_display_value(original, "length", "mm", "m")
    assert convert_display_value(displayed, "length", "m", "mm") == original


def test_rpm_rad_s_conversion_round_trip():
    rad_s = convert_display_value(2500.0, "speed", "rpm", "rad/s")
    assert rad_s == pytest.approx(2500.0 * 2.0 * math.pi / 60.0)
    assert convert_display_value(rad_s, "speed", "rad/s", "rpm") == pytest.approx(2500.0)


def test_degree_radian_and_celsius_kelvin_conversion():
    assert convert_display_value(180.0, "angle", "degree", "rad") == pytest.approx(math.pi)
    assert convert_display_value(math.pi, "angle", "rad", "degree") == pytest.approx(180.0)
    assert convert_display_value(80.0, "temperature", "degC", "K") == pytest.approx(353.15)
    assert convert_display_value(353.15, "temperature", "K", "degC") == pytest.approx(80.0)


def test_all_display_conversions_preserve_canonical_values():
    preferences = DisplayUnitPreferences(length="m", speed="rad/s", temperature="K", angle="rad")
    displayed = canonical_to_display_inputs(APPLICATION_DEFAULTS, preferences)
    restored = display_to_canonical_inputs(displayed, preferences)
    for name, expected in APPLICATION_DEFAULTS.items():
        if isinstance(expected, float):
            assert restored[name] == pytest.approx(expected)
        else:
            assert restored[name] == expected


def test_slider_motion_formats_clean_numeric_text():
    result = slider_to_numeric_text(1.1999999997, SLIDER_SPECS["g_side"], DisplayUnitPreferences())
    assert result.numeric_text == "1.2"
    assert result.slider_value == pytest.approx(1.2)


def test_numeric_entry_updates_slider_when_representable():
    result = slider_from_numeric_text("1.25", SLIDER_SPECS["g_side"], DisplayUnitPreferences())
    assert result.within_display_range
    assert result.slider_value == pytest.approx(1.25)


def test_manual_value_outside_slider_range_is_preserved_without_clamping():
    result = slider_from_numeric_text("7.123456789", SLIDER_SPECS["g_side"], DisplayUnitPreferences())
    assert not result.within_display_range
    assert result.slider_value is None
    assert result.numeric_text == "7.123456789"
    assert result.guidance == "Outside quick-adjust range"


def test_slider_range_and_step_follow_display_units():
    preferences = DisplayUnitPreferences(length="m")
    minimum, maximum, step = slider_range_for_units(SLIDER_SPECS["g_side"], preferences)
    assert (minimum, maximum, step) == pytest.approx((0.0002, 0.005, 0.00005))


def test_spinbox_integer_accepts_manual_integer_and_rejects_fraction():
    assert parse_spinbox_integer("17") == 17
    assert parse_spinbox_integer("+17") == 17
    with pytest.raises(ValueError, match="integer"):
        parse_spinbox_integer("17.5")
    with pytest.raises(ValueError, match="at least"):
        parse_spinbox_integer("0")


def test_engineering_formatting_avoids_binary_noise():
    assert format_engineering_value(0.0011999999999997) == "0.0012"


def test_engineering_formatting_retains_meaningful_custom_precision():
    assert format_engineering_value(7.123456789012345) == "7.123456789012345"


def test_invalid_geometry_is_error_and_blocks_calculation():
    issues = evaluate_input_guidance(dict(APPLICATION_DEFAULTS, D_in=150.0, D_out=140.0))
    assert issues[0].level is GuidanceLevel.INVALID
    assert issues[0].severity is GuidanceSeverity.ERROR
    assert issues[0].blocks_calculation


def test_unusual_valid_air_gap_is_info_and_does_not_block():
    issues = evaluate_input_guidance(dict(APPLICATION_DEFAULTS, g_side=7.0))
    issue = next(item for item in issues if item.field_names == ("g_side",))
    assert issue.level is GuidanceLevel.UNUSUAL
    assert issue.severity is GuidanceSeverity.INFO
    assert not issue.blocks_calculation


def test_high_speed_warning_does_not_block():
    issues = evaluate_input_guidance(dict(APPLICATION_DEFAULTS, n_rated=12000.0))
    issue = next(item for item in issues if item.field_names == ("n_rated",))
    assert issue.severity is GuidanceSeverity.WARNING
    assert not issue.blocks_calculation


def test_preset_values_round_trip_through_project_without_registry_dependency(tmp_path):
    preset = default_preset_registry().get("design.application_reference.v1")
    values = apply_preset(dict(APPLICATION_DEFAULTS, D_out=180.25), preset)
    document = create_project_document(
        "Preset project", values,
        ui_preferences={"preset_id": preset.preset_id, "preset_version": preset.version},
    )
    path = tmp_path / "preset.motorproj"
    save_project(document, path)
    restored = load_project(path)
    assert flatten_project_inputs(restored.inputs) == values
    assert restored.ui_preferences["preset_id"] == preset.preset_id


def test_recovery_preserves_exact_manual_outside_range_value(tmp_path):
    values = dict(APPLICATION_DEFAULTS, g_side=7.123456789)
    document = create_project_document("Exact recovery", values)
    manager = RecoveryManager(tmp_path / "recovery")
    manager.begin_session("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
    path = manager.write_recovery(document, original_project_path=None, dirty=True)
    restored = load_recovery(path).project
    assert flatten_project_inputs(restored.inputs)["g_side"] == pytest.approx(7.123456789)


def test_preset_json_is_packaged_data_not_generated_code():
    path = ROOT / "motor_calculator" / "presets" / "data" / "presets.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert isinstance(payload["presets"], list)


def test_packaging_spec_includes_data_driven_preset_registry():
    content = (ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    assert '"presets" / "data" / "presets.json"' in content
    assert '"motor_calculator/presets/data"' in content


def test_rapid_interactive_changes_debounce_recovery_schedule():
    class FakeRoot:
        def __init__(self):
            self.cancelled = []
            self.scheduled = []

        def after_cancel(self, identifier):
            self.cancelled.append(identifier)

        def after(self, delay, callback):
            identifier = f"after-{len(self.scheduled)}"
            self.scheduled.append((identifier, delay, callback))
            return identifier

    class FakeRecoveryManager:
        autosave_interval_seconds = 60

    class FakeStatus:
        def set(self, value):
            self.value = value

    app = object.__new__(MotorCalculatorAppMixin)
    app.root = FakeRoot()
    app._recovery_manager = FakeRecoveryManager()
    app._recovery_status_var = FakeStatus()
    app._recovery_after_id = None
    for _ in range(20):
        app._schedule_recovery_autosave()
    assert len(app.root.scheduled) == 20
    assert len(app.root.cancelled) == 19
    assert app._recovery_after_id == "after-19"
    assert app._recovery_status_var.value == "存在未保存修改；已安排恢复快照"
