"""RC5.1: the customer-visible winding-factor and slot-fill product gate.

RC5 shipped a production winding-factor authority whose value the input panel
never showed. The panel kept an ordinary editable ``k_w`` field holding whatever
had last been typed or dragged, while the dashboard, the report and the export
all used the geometry-derived number. Two numbers, both on screen, no indication
that only one of them was real.

These tests assert the customer-facing contract rather than the internals: the
same production winding factor in every place a user can read one, a k_w control
that is editable exactly when what is typed in it is used, and a slot-fill card
that either shows its numbers or says which input is missing.

The GUI half needs a display and is skipped without one. The rendering half does
not and always runs.
"""

from __future__ import annotations

import math
import os

import pytest

from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.winding.authority import (
    AUTHORITY_CHOICE_LABELS_ZH,
    AUTHORITY_FIELD_LABELS_ZH,
    SELECTABLE_AUTHORITIES,
    WindingAuthority,
)
from motor_calculator.winding.evaluation import (
    SLOT_FILL_REQUIRED_FIELDS_ZH,
    describe_missing_slot_fill_fields,
    evaluate_winding,
    missing_slot_fill_fields,
)
from motor_calculator.winding.slot_fill_card import (
    CARD_TITLE_ZH,
    build_slot_fill_card,
    detail_rows_zh,
    primary_rows_zh,
    render_slot_fill_card_zh,
)

GEOMETRY_KW = math.sqrt(3.0) / 2.0
LEGACY_KW = 0.93

#: The Phase 10G manufacturability starting example, as the shipped preset
#: leaves it. Recomputed here rather than asserted against frozen constants.
STARTING_EXAMPLE = {
    **APPLICATION_DEFAULTS,
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 1800.0,
    "N_ph_turns": 42,
    "d_wire": 1.2,
    "n_parallel": 3,
    "slot_type": "半闭口槽",
    "coreless": False,
    "coil_span_slots": 1,
}


# ---------------------------------------------------------------------------
# The selector
# ---------------------------------------------------------------------------


def test_unresolved_is_not_something_a_user_can_choose():
    """UNRESOLVED is an outcome. Offering it as a mode would invite nonsense."""

    assert WindingAuthority.UNRESOLVED not in SELECTABLE_AUTHORITIES
    assert set(SELECTABLE_AUTHORITIES) == {
        WindingAuthority.AUTO_FROM_GEOMETRY,
        WindingAuthority.MANUAL_OVERRIDE,
        WindingAuthority.LEGACY_MANUAL,
    }


def test_every_authority_state_has_its_own_field_label():
    """All four states, including UNRESOLVED, name themselves in the field label."""

    labels = {AUTHORITY_FIELD_LABELS_ZH[state] for state in WindingAuthority}
    assert len(labels) == len(WindingAuthority)
    for state in SELECTABLE_AUTHORITIES:
        assert AUTHORITY_CHOICE_LABELS_ZH[state]


# ---------------------------------------------------------------------------
# Step 6: an unavailable slot fill must say which input is missing
# ---------------------------------------------------------------------------


def test_a_complete_design_reports_no_missing_slot_fill_fields():
    assert missing_slot_fill_fields(STARTING_EXAMPLE) == ()


@pytest.mark.parametrize("field", sorted(SLOT_FILL_REQUIRED_FIELDS_ZH))
def test_each_required_slot_fill_input_is_named_when_it_is_absent(field):
    parameters = {key: value for key, value in STARTING_EXAMPLE.items() if key != field}
    assert field in missing_slot_fill_fields(parameters)


def test_a_zero_wire_diameter_counts_as_missing_not_as_zero_copper():
    """A zero is not a measurement of nothing; it is an absent input."""

    parameters = {**STARTING_EXAMPLE, "d_wire": 0.0}
    assert "d_wire" in missing_slot_fill_fields(parameters)


def test_the_missing_field_message_names_the_parameter_in_both_languages():
    message = describe_missing_slot_fill_fields(("d_wire", "h_slot"))
    assert "d_wire" in message and "h_slot" in message
    assert SLOT_FILL_REQUIRED_FIELDS_ZH["d_wire"] in message
    assert SLOT_FILL_REQUIRED_FIELDS_ZH["h_slot"] in message


def test_an_unavailable_card_carries_a_reason_rather_than_only_不可用():
    parameters = {**STARTING_EXAMPLE, "d_wire": 0.0}
    card = build_slot_fill_card(
        evaluate_winding(parameters, authority=WindingAuthority.AUTO_FROM_GEOMETRY)
    )
    assert not card.is_available
    assert card.missing_fields == ("d_wire",)
    assert card.unavailable_reason_zh
    assert "d_wire" in card.unavailable_reason_zh
    rendered = render_slot_fill_card_zh(card)
    assert "原因" in rendered
    assert "d_wire" in rendered


def test_a_slotless_machine_is_not_reported_as_a_failed_calculation():
    """No slots is a topology fact; it must not read like a missing input."""

    card = build_slot_fill_card(
        evaluate_winding(
            {**STARTING_EXAMPLE, "coreless": True},
            authority=WindingAuthority.AUTO_FROM_GEOMETRY,
        )
    )
    assert not card.is_available
    assert card.missing_fields == ()
    assert "无槽" in card.status_label_zh
    assert "无槽" in card.unavailable_reason_zh


# ---------------------------------------------------------------------------
# Steps 4, 5 and 9: the card shows the numbers, recomputed not hard-coded
# ---------------------------------------------------------------------------


def test_the_card_carries_every_area_and_every_fill_ratio():
    card = build_slot_fill_card(
        evaluate_winding(STARTING_EXAMPLE, authority=WindingAuthority.AUTO_FROM_GEOMETRY)
    )
    assert card.is_available
    for value in (
        card.gross_slot_area_mm2,
        card.usable_slot_area_mm2,
        card.bare_copper_area_mm2,
        card.envelope_area_mm2,
        card.gross_copper_fill,
        card.usable_copper_fill,
        card.gross_envelope_fill,
        card.usable_envelope_fill,
    ):
        assert value is not None and value > 0.0


def test_the_startup_example_still_reproduces_the_phase_10g_slot_fill():
    """Recomputed from the preset, not read back from a stored baseline."""

    card = build_slot_fill_card(
        evaluate_winding(STARTING_EXAMPLE, authority=WindingAuthority.AUTO_FROM_GEOMETRY)
    )
    assert card.gross_slot_area_mm2 == pytest.approx(105.0, abs=5e-3)
    assert card.usable_slot_area_mm2 == pytest.approx(77.490, abs=5e-3)
    assert card.bare_copper_area_mm2 == pytest.approx(35.626, abs=5e-3)
    assert card.envelope_area_mm2 == pytest.approx(41.554, abs=5e-3)
    assert card.gross_copper_fill == pytest.approx(0.3393, abs=5e-5)
    assert card.usable_copper_fill == pytest.approx(0.4597, abs=5e-5)
    assert card.gross_envelope_fill == pytest.approx(0.3958, abs=5e-5)
    assert card.usable_envelope_fill == pytest.approx(0.5362, abs=5e-5)
    assert card.status == "FEASIBLE"
    assert card.status_label_zh == "可行"


def test_the_rendered_card_uses_chinese_findings_not_enum_names():
    card = build_slot_fill_card(
        evaluate_winding(STARTING_EXAMPLE, authority=WindingAuthority.AUTO_FROM_GEOMETRY)
    )
    rendered = render_slot_fill_card_zh(card)
    assert "FEASIBLE" not in rendered
    assert "可行" in rendered
    for label, _value in primary_rows_zh(card) + detail_rows_zh(card):
        assert label in rendered


# ---------------------------------------------------------------------------
# The GUI half
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """A real application window against an isolated user-data directory."""

    tk = pytest.importorskip("tkinter")
    user_data = tmp_path_factory.mktemp("rc51-user-data")

    from motor_calculator.runtime.paths import resolve_runtime_paths

    isolated = resolve_runtime_paths(
        environment={**os.environ, "MOTOR_CALCULATOR_USER_DATA": str(user_data)}
    )

    from motor_calculator.gui import main_window as module

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless machine
        pytest.skip(f"no display available: {exc}")
    root.withdraw()

    previous = module._RUNTIME_PATHS
    module._RUNTIME_PATHS = isolated
    for target in (module.messagebox, module._get_legacy_module().messagebox):
        target.showinfo = lambda *args, **kwargs: None
        target.showwarning = lambda *args, **kwargs: None
        target.showerror = lambda *args, **kwargs: None
    try:
        instance = module._get_real_app_class()(root)
        root.update_idletasks()
        yield instance
    finally:
        module._RUNTIME_PATHS = previous
        try:
            root.destroy()
        except tk.TclError:  # pragma: no cover - already gone
            pass


def _select(app, authority: WindingAuthority) -> None:
    app._winding_authority_var.set(AUTHORITY_CHOICE_LABELS_ZH[authority])
    app._on_winding_authority_selected()


def _entry_state(widget) -> str:
    return str(widget.cget("state"))


# --- Step 8: the shipped startup preset ------------------------------------


def test_the_startup_preset_opens_on_the_geometry_derived_authority(app):
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")
    assert app.current_winding_authority() is WindingAuthority.AUTO_FROM_GEOMETRY
    assert app._get_params()["k_w"] == pytest.approx(GEOMETRY_KW, abs=1e-9)


# --- Step 10: one number, everywhere a user can read one -------------------


def test_every_surface_shows_the_same_production_winding_factor(app):
    """Left panel, production parameter, dashboard, winding dialog, export."""

    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")

    left_panel = float(app.vars["k_w"].get())
    production = float(app._get_params()["k_w"])
    dashboard = float(app._winding_dashboard_summary().production_winding_factor)
    dialog = app._open_winding_engineering()
    app.root.update_idletasks()
    dialog_value = float(dialog._production.value)
    app.run_analysis()
    app.root.update_idletasks()
    exported = float(app.rc2_export_payload()["winding_factor"])

    # The panel field is rounded for display; everything else is exact.
    assert left_panel == pytest.approx(GEOMETRY_KW, abs=5e-7)
    for value in (production, dashboard, dialog_value, exported):
        assert value == pytest.approx(GEOMETRY_KW, abs=1e-9)
    assert float(app._winding_factor_value_var.get()) == pytest.approx(left_panel)


def test_the_winding_dialog_opens_on_the_sessions_authority_not_its_own(app):
    """It used to default to LEGACY_MANUAL and mislabel a derived value."""

    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    dialog = app._open_winding_engineering()
    app.root.update_idletasks()
    assert dialog.selected_authority() is WindingAuthority.AUTO_FROM_GEOMETRY
    assert dialog._production.authority is WindingAuthority.AUTO_FROM_GEOMETRY


def test_the_entered_factor_stays_distinct_from_the_derived_one(app):
    """Phase 10H keeps three winding factors apart; AUTO must not merge them."""

    _select(app, WindingAuthority.MANUAL_OVERRIDE)
    app.vars["k_w"].set(str(LEGACY_KW))
    app._refresh_winding_factor_summary()
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)

    dialog = app._open_winding_engineering()
    app.root.update_idletasks()
    factors = dialog._evaluation.report.factors
    assert factors.entered == pytest.approx(LEGACY_KW)
    assert factors.ideal_slot_star == pytest.approx(GEOMETRY_KW, abs=1e-9)


# --- Steps 2, 3 and 7: the field is editable exactly when it is used -------


def test_an_automatic_winding_factor_locks_every_control_that_edits_it(app):
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")

    assert _entry_state(app.entries["k_w"]) == "readonly"
    assert _entry_state(app._guided_input_panel.quick_entries["k_w"]) == "readonly"
    assert _entry_state(app._guided_input_panel.sliders["k_w"]) == "disabled"
    assert app._winding_factor_field_label_var.get() == (
        AUTHORITY_FIELD_LABELS_ZH[WindingAuthority.AUTO_FROM_GEOMETRY]
    )
    assert app._winding_factor_source_var.get()


def test_a_manual_override_unlocks_the_field_and_restores_what_was_typed(app):
    _select(app, WindingAuthority.MANUAL_OVERRIDE)
    app.vars["k_w"].set(str(LEGACY_KW))
    app._refresh_winding_factor_summary()
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    assert float(app.vars["k_w"].get()) == pytest.approx(GEOMETRY_KW, abs=5e-7)

    _select(app, WindingAuthority.MANUAL_OVERRIDE)
    assert float(app.vars["k_w"].get()) == pytest.approx(LEGACY_KW)
    assert _entry_state(app.entries["k_w"]) == "normal"
    assert _entry_state(app._guided_input_panel.sliders["k_w"]) == "normal"
    assert app._winding_factor_field_label_var.get() == (
        AUTHORITY_FIELD_LABELS_ZH[WindingAuthority.MANUAL_OVERRIDE]
    )
    assert app._get_params()["k_w"] == pytest.approx(LEGACY_KW)


def test_resetting_kw_under_auto_does_not_put_a_stale_default_back(app):
    """The reset button must not re-open the hole this release closes."""

    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")
    app._reset_input_field("k_w")

    assert float(app.vars["k_w"].get()) == pytest.approx(GEOMETRY_KW, abs=5e-7)
    assert app._get_params()["k_w"] == pytest.approx(GEOMETRY_KW, abs=1e-9)
    assert _entry_state(app.entries["k_w"]) == "readonly"

    # The stored manual value is what was reset, so manual mode gives the default.
    _select(app, WindingAuthority.MANUAL_OVERRIDE)
    assert float(app.vars["k_w"].get()) == pytest.approx(
        float(APPLICATION_DEFAULTS["k_w"])
    )


def test_the_locked_slider_says_why_it_cannot_be_dragged(app):
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")
    assert "自动推导" in app._guided_input_panel.slider_status_vars["k_w"].get()


def test_auto_without_enough_geometry_says_unresolved_and_keeps_the_field_usable(app):
    """The entered value is what production falls back to, so it stays editable."""

    _select(app, WindingAuthority.MANUAL_OVERRIDE)
    app.vars["k_w"].set(str(LEGACY_KW))
    app._refresh_winding_factor_summary()
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("")
    try:
        assert app._winding_factor_field_label_var.get() == (
            AUTHORITY_FIELD_LABELS_ZH[WindingAuthority.UNRESOLVED]
        )
        assert _entry_state(app.entries["k_w"]) == "normal"
        assert float(app.vars["k_w"].get()) == pytest.approx(LEGACY_KW)
        assert app._get_params()["k_w"] == pytest.approx(LEGACY_KW)
    finally:
        app._coil_span_slots_var.set("1")


# --- Step 12: a legacy project keeps its number and says so ----------------


def test_a_legacy_project_keeps_its_stored_winding_factor_and_is_labelled(app, tmp_path):
    """An RC4-style document has no winding metadata and must not be re-derived."""

    from motor_calculator.project import create_project_document, load_project, save_project

    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    inputs = dict(app._get_params())
    inputs["k_w"] = LEGACY_KW

    legacy_path = tmp_path / "legacy_rc4.mcproj"
    document = create_project_document(
        "Legacy RC4",
        {key: inputs[key] for key in APPLICATION_DEFAULTS},
        ui_preferences={"input_mode": "ADVANCED"},
    )
    save_project(document, legacy_path)
    assert "winding_factor_mode" not in load_project(legacy_path).ui_preferences

    app._apply_project_document(load_project(legacy_path))
    app.root.update_idletasks()

    assert float(app.vars["k_w"].get()) == pytest.approx(LEGACY_KW)
    assert app._get_params()["k_w"] == pytest.approx(LEGACY_KW)
    assert app.current_winding_authority() is WindingAuthority.LEGACY_MANUAL
    assert app._winding_factor_field_label_var.get() == (
        AUTHORITY_FIELD_LABELS_ZH[WindingAuthority.LEGACY_MANUAL]
    )
    assert "旧项目" in app._winding_factor_source_var.get()
    assert _entry_state(app.entries["k_w"]) == "normal"

    summary = app._winding_dashboard_summary()
    assert summary.authority == WindingAuthority.LEGACY_MANUAL.value
    assert summary.production_winding_factor == pytest.approx(LEGACY_KW)


# --- Step 11: the slot-fill card is on the dashboard a user actually sees ---


def test_the_slot_fill_card_is_laid_out_on_the_results_dashboard(app):
    dashboard = app.results_dashboard
    label = dashboard._slot_fill_label
    assert label.winfo_manager() == "pack"
    assert str(label.master.cget("text")) == CARD_TITLE_ZH


def test_the_dashboard_card_shows_both_fills_and_the_finding(app):
    _select(app, WindingAuthority.AUTO_FROM_GEOMETRY)
    app._coil_span_slots_var.set("1")
    app.run_analysis()
    app.root.update_idletasks()

    text = app.results_dashboard._slot_fill_var.get()
    assert "铜填充率（可用槽面积）" in text
    assert "绝缘包络填充率（可用槽面积）" in text
    assert "状态" in text
    assert "可行" in text
    for label in (
        "总槽面积",
        "可用槽面积",
        "裸铜面积",
        "绝缘后导体包络面积",
        "总槽面积铜填充率",
        "总槽面积包络填充率",
        "可用槽面积包络填充率",
    ):
        assert label in text


def test_the_dashboard_card_explains_an_unavailable_fill(app):
    card = build_slot_fill_card(
        evaluate_winding(
            {**app._get_params(), "d_wire": 0.0},
            authority=WindingAuthority.AUTO_FROM_GEOMETRY,
        )
    )
    app.results_dashboard.set_slot_fill_card(card)
    app.root.update_idletasks()
    text = app.results_dashboard._slot_fill_var.get()
    assert "原因" in text
    assert "d_wire" in text
    assert text.strip() != "不可用"
