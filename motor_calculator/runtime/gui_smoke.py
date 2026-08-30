"""Explicit real-window GUI smoke procedure for source and packaged builds."""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any


def _window_fits_screen(window) -> bool:
    window.update_idletasks()
    return (
        window.winfo_reqwidth() <= window.winfo_screenwidth()
        and window.winfo_reqheight() <= window.winfo_screenheight()
    )


def _widget_fits_window(widget, window) -> bool:
    window.update_idletasks()
    widget.update_idletasks()
    return (
        bool(widget.winfo_ismapped())
        and widget.winfo_rootx() >= window.winfo_rootx()
        and widget.winfo_rooty() >= window.winfo_rooty()
        and widget.winfo_rootx() + widget.winfo_width()
        <= window.winfo_rootx() + window.winfo_width()
        and widget.winfo_rooty() + widget.winfo_height()
        <= window.winfo_rooty() + window.winfo_height()
    )


def _calculation_snapshot(result) -> dict[str, float]:
    return {
        "back_emf_phase_rms_v": float(result.electrical.E_phase_rms),
        "back_emf_line_rms_v": float(result.electrical.E_line_rms),
        "phase_resistance_ohm": float(result.electrical.R_phase),
        "phase_inductance_h": float(result.electrical.L_phase),
        "rated_current_rms_a": float(result.performance.I_phase_rms),
        "efficiency_percent": float(result.performance.Efficiency),
        "required_voltage_v": float(result.performance.V_required),
    }


def _install_nonblocking_messages(main_window_module, legacy_module) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    def recorder(kind: str):
        def record(title: str, message: str, **_kwargs: Any) -> None:
            messages.append({"kind": kind, "title": str(title), "message": str(message)})

        return record

    for module in (main_window_module.messagebox, legacy_module.messagebox):
        module.showinfo = recorder("info")
        module.showwarning = recorder("warning")
        module.showerror = recorder("error")
    return messages


def _submit_smoke_feedback(app, main_window_module) -> tuple[int, int]:
    from motor_calculator.gui.feedback_dialog import FeedbackDialogValues
    from motor_calculator.validation.feedback_models import ValidationEvidenceType
    from motor_calculator.validation.feedback_service import load_feedback_records

    before = len(load_feedback_records(app._feedback_store))
    options = app._feedback_metric_options()
    option = options["phase_resistance_ohm"]
    values = FeedbackDialogValues(
        metric_name=option.metric_name,
        reference_value=option.predicted_value,
        reference_unit=option.unit,
        evidence_type=ValidationEvidenceType.ANALYTICAL_REFERENCE,
        speed_rpm=float(app._get_params()["n_rated"]),
        current_a=None,
        voltage_v=None,
        temperature_c=None,
        source_name="Phase 8A.2 packaged smoke",
        source_reference="local runtime smoke record",
        notes="Runtime persistence verification only; not calibration evidence.",
        reference_semantics=option.semantics,
    )
    original_dialog = main_window_module.ValidationFeedbackDialog

    class SmokeFeedbackDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def show(self):
            return values

    main_window_module.ValidationFeedbackDialog = SmokeFeedbackDialog
    try:
        app._add_validation_feedback()
    finally:
        main_window_module.ValidationFeedbackDialog = original_dialog
    after = len(load_feedback_records(app._feedback_store))
    if after != before + 1:
        raise RuntimeError("feedback record was not appended exactly once")
    return before, after


def _exercise_dialogs(root, app, screenshot_base: Path) -> dict[str, Any]:
    from motor_calculator.i18n import tr
    from motor_calculator.gui.feedback_dialog import ValidationFeedbackDialog
    from motor_calculator.gui.uncertainty_dialog import UncertaintyAssumptionDialog
    from motor_calculator.validation.uncertainty_models import load_uncertainty_specification

    feedback = ValidationFeedbackDialog(
        root,
        app._feedback_metric_options(),
        default_speed=float(app._get_params()["n_rated"]),
    )
    feedback.window.update()
    feedback_title_chinese = feedback.window.title() == tr("feedback.add_title")
    feedback_fits = _window_fits_screen(feedback.window)
    feedback_screenshot = screenshot_base.with_name(screenshot_base.stem + "-feedback.png")
    feedback_screenshot_error = _capture_window(feedback.window, feedback_screenshot)
    feedback.window.destroy()

    specification = load_uncertainty_specification(
        app._runtime_paths.resource(
            "validation_data",
            "uncertainty",
            "phase7i_afpm_back_emf_uncertainty.json",
        )
    )
    uncertainty = UncertaintyAssumptionDialog(root, specification.parameters)
    uncertainty.window.update()
    uncertainty_title_chinese = uncertainty.window.title() == tr("uncertainty.title")
    uncertainty_fits = _window_fits_screen(uncertainty.window)
    uncertainty_screenshot = screenshot_base.with_name(screenshot_base.stem + "-uncertainty.png")
    uncertainty_screenshot_error = _capture_window(uncertainty.window, uncertainty_screenshot)
    uncertainty.window.destroy()
    root.update()
    return {
        "feedback_dialog_opened": True,
        "feedback_dialog_title_chinese": feedback_title_chinese,
        "feedback_dialog_fits_screen": feedback_fits,
        "feedback_dialog_screenshot": str(feedback_screenshot),
        "feedback_dialog_screenshot_error": feedback_screenshot_error,
        "uncertainty_dialog_opened": True,
        "uncertainty_dialog_title_chinese": uncertainty_title_chinese,
        "uncertainty_dialog_fits_screen": uncertainty_fits,
        "uncertainty_dialog_screenshot": str(uncertainty_screenshot),
        "uncertainty_dialog_screenshot_error": uncertainty_screenshot_error,
    }


def _exercise_project_workflow(root, app, main_window_module, output: Path) -> dict[str, Any]:
    """Exercise project lifecycle through the real GUI controller methods."""

    from motor_calculator.project import load_project

    primary = output.with_name(output.stem + "-project.motorproj")
    save_as = output.with_name(output.stem + "-project-save-as.motorproj")
    for path in (primary, primary.with_name(primary.name + ".bak"), save_as, save_as.with_name(save_as.name + ".bak")):
        path.unlink(missing_ok=True)

    if not app._new_project():
        raise RuntimeError("new project action was cancelled unexpectedly")
    project_created = app._project_manager.current_path is None and not app._project_manager.is_dirty

    app.vars["n_rated"].set("2375.0")
    root.update()
    dirty_after_edit = app._project_manager.is_dirty and app.root.title().endswith(" *")
    expected_inputs = dict(app._get_params())
    app.run_analysis()
    root.update()
    expected_calculation = _calculation_snapshot(app.calc_results)
    if not app._save_project_to_path(primary, save_as=True):
        raise RuntimeError("direct project save failed")
    clean_after_save = not app._project_manager.is_dirty and primary.is_file()

    if not app._new_project():
        raise RuntimeError("new project reset failed")
    reset_changed_inputs = dict(app._get_params()) != expected_inputs

    original_open_dialog = main_window_module.filedialog.askopenfilename
    main_window_module.filedialog.askopenfilename = lambda **_kwargs: str(primary)
    try:
        opened_through_dialog = app._open_project()
    finally:
        main_window_module.filedialog.askopenfilename = original_open_dialog
    restored_inputs = dict(app._get_params())
    exact_inputs_restored = restored_inputs == expected_inputs
    app.run_analysis()
    root.update()
    restored_calculation = _calculation_snapshot(app.calc_results)
    calculation_reproduced = restored_calculation == expected_calculation

    original_save_dialog = main_window_module.filedialog.asksaveasfilename
    main_window_module.filedialog.asksaveasfilename = lambda **_kwargs: str(save_as)
    try:
        saved_as_through_dialog = app._save_project_as()
    finally:
        main_window_module.filedialog.asksaveasfilename = original_save_dialog
    save_as_document = load_project(save_as)

    app.vars["Br"].set("1.27")
    root.update()
    dirty_before_cancel = app._project_manager.is_dirty
    original_prompt = main_window_module.messagebox.askyesnocancel
    main_window_module.messagebox.askyesnocancel = lambda *_args, **_kwargs: None
    try:
        cancel_protected = not app._confirm_abandon_changes()
    finally:
        main_window_module.messagebox.askyesnocancel = original_prompt
    dirty_after_cancel = app._project_manager.is_dirty

    if not app._open_project_path(save_as, prompt_for_unsaved=False):
        raise RuntimeError("final project restore failed")
    app.run_analysis()
    root.update()
    return {
        "project_file": str(primary),
        "project_file_exists": primary.is_file(),
        "project_save_as_file": str(save_as),
        "project_save_as_exists": save_as.is_file(),
        "project_schema_version": save_as_document.schema_version,
        "project_created": project_created,
        "project_dirty_after_edit": dirty_after_edit,
        "project_clean_after_save": clean_after_save,
        "project_reset_changed_inputs": reset_changed_inputs,
        "project_opened_through_file_dialog": bool(opened_through_dialog),
        "project_saved_as_through_file_dialog": bool(saved_as_through_dialog),
        "project_exact_inputs_restored": exact_inputs_restored,
        "project_calculation_reproduced": calculation_reproduced,
        "project_exit_cancel_protected": cancel_protected and dirty_before_cancel and dirty_after_cancel,
        "project_recent_entry_present": any(
            entry.path == save_as for entry in app._project_manager.recent_store.entries()
        ),
    }


def _exercise_recovery_workflow(root, app, main_window_module) -> dict[str, Any]:
    """Exercise autosave, browser, restore, and selected-record discard."""

    app.vars["n_rated"].set("2412.0")
    app.vars["Br"].set("1.28")
    app.vars["g_side"].set("7.123456789")
    root.update()
    expected = dict(app._get_params())
    autosave_written = app._perform_recovery_autosave()
    scan = app._recovery_manager.scan()
    if len(scan.candidates) != 1:
        raise RuntimeError("recovery autosave did not produce one meaningful candidate")
    candidate = scan.candidates[0]
    recovery_path = candidate.path
    browser = app._recover_unsaved_work()
    browser_opened = browser is not None and bool(browser.window.winfo_exists())
    if browser is not None:
        browser.window.destroy()
    original_prompt = main_window_module.messagebox.askyesnocancel
    main_window_module.messagebox.askyesnocancel = lambda *_args, **_kwargs: False
    try:
        restored = app._restore_recovery_candidate(candidate)
    finally:
        main_window_module.messagebox.askyesnocancel = original_prompt
    root.update()
    restored_inputs = dict(app._get_params())
    restored_dirty = (
        app._project_manager.is_dirty
        and app._project_manager.current_path is None
        and app.root.title().endswith("Recovered Project *")
    )
    app.run_analysis()
    root.update()
    calculation_after_restore = bool(getattr(app, "calc_results", None))
    discarded = app._discard_recovery_candidate(candidate)
    return {
        "recovery_autosave_written": bool(autosave_written and recovery_path.is_file() is False),
        "recovery_browser_opened": browser_opened,
        "recovery_restored": bool(restored),
        "recovery_restored_inputs_exact": restored_inputs == expected,
        "recovery_restored_dirty_without_path": restored_dirty,
        "recovery_calculation_after_restore": calculation_after_restore,
        "recovery_selected_discarded": bool(discarded and not recovery_path.exists()),
        "recovery_path": str(recovery_path),
    }


def _exercise_phase8d_input_ux(root, app, main_window_module, output: Path) -> dict[str, Any]:
    """Exercise interaction-first controls without bypassing exact numeric entry."""

    from motor_calculator.input_ux import APPLICATION_DEFAULTS
    from motor_calculator.project import load_project, save_project

    baseline = dict(app._get_params())
    app._set_input_mode("BASIC")
    root.update_idletasks()
    advanced_hidden = not any(
        bool(widget.grid_info()) for widget in app._input_row_widgets["sigma_m"]
    )
    basic_preserved = dict(app._get_params()) == baseline
    app._set_input_mode("ADVANCED")

    recovery_files_before = tuple(app._recovery_manager.root.glob("*.recovery.json"))
    for position in (0.95, 1.05, 1.15, 1.25):
        app._guided_input_panel._slider_moved("g_side", str(position))
    root.update_idletasks()
    slider_synced = app.vars["g_side"].get() == "1.25" and app._get_params()["g_side"] == 1.25
    slider_debounced = (
        app._recovery_after_id is not None
        and tuple(app._recovery_manager.root.glob("*.recovery.json")) == recovery_files_before
    )

    exact_air_gap = 7.123456789
    app.vars["g_side"].set(str(exact_air_gap))
    root.update_idletasks()
    out_of_range_preserved = (
        app._get_params()["g_side"] == exact_air_gap
        and app._guided_input_panel.slider_status_vars["g_side"].get() == "超出快速调节范围"
    )
    app._refresh_input_guidance()
    warning_rendered = "提示/非典型" in app._guided_input_panel.guidance_var.get()
    app._show_input_help()
    help_opened = True
    app._reset_input_field("g_side")
    field_reset_worked = app._get_params()["g_side"] == APPLICATION_DEFAULTS["g_side"]
    app.vars["g_side"].set(str(exact_air_gap))

    app._guided_input_panel.pole_spinbox.set("9")
    app._guided_input_panel.waveform_combo.set("梯形波")
    root.update_idletasks()
    discrete_controls_work = app._get_params()["p"] == 9 and app._get_params()["waveform"] == "梯形波"

    unchanged_diameter = app._get_params()["D_out"]
    original_confirm = main_window_module.messagebox.askokcancel
    main_window_module.messagebox.askokcancel = lambda *_args, **_kwargs: True
    try:
        preset_applied = app._apply_preset_by_id("magnet.n35.v1")
    finally:
        main_window_module.messagebox.askokcancel = original_confirm
    root.update_idletasks()
    preset_is_partial = (
        preset_applied
        and app._get_params()["magnet_grade"] == "N35"
        and app._get_params()["Br"] == 1.17
        and app._get_params()["D_out"] == unchanged_diameter
        and app._project_manager.is_dirty
    )

    canonical_before_units = dict(app._get_params())
    app._change_display_unit("length", "m")
    app._change_display_unit("speed", "rad/s")
    root.update_idletasks()
    unit_display_changed = (
        app._display_unit_preferences.length == "m"
        and app._display_unit_preferences.speed == "rad/s"
        and float(app.vars["g_side"].get()) < 0.01
    )
    unit_canonical_preserved = all(
        math.isclose(float(app._get_params()[name]), float(value), rel_tol=1e-12, abs_tol=1e-12)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else app._get_params()[name] == value
        for name, value in canonical_before_units.items()
    )

    project_path = output.with_name(output.stem + "-phase8d-inputs.motorproj")
    project_path.unlink(missing_ok=True)
    document = app._build_project_document(project_name="Phase 8D Input UX Smoke")
    save_project(document, project_path)
    restored_document = load_project(project_path)
    app.vars["g_side"].set("0.001")
    app._apply_project_document(restored_document)
    root.update_idletasks()
    project_exact_restored = app._get_params()["g_side"] == exact_air_gap
    ui_preferences_restored = (
        app._display_unit_preferences.length == "m"
        and app._display_unit_preferences.speed == "rad/s"
        and restored_document.ui_preferences["preset_id"] == "magnet.n35.v1"
    )

    app._project_suppress_dirty = True
    try:
        app._change_display_unit("length", "mm")
        app._change_display_unit("speed", "rpm")
        app._set_input_mode("ADVANCED")
    finally:
        app._project_suppress_dirty = False
    original_confirm = main_window_module.messagebox.askokcancel
    main_window_module.messagebox.askokcancel = lambda *_args, **_kwargs: True
    try:
        reset_confirmed = bool(app.reset_defaults())
    finally:
        main_window_module.messagebox.askokcancel = original_confirm
    reset_all_worked = reset_confirmed and dict(app._get_params()) == APPLICATION_DEFAULTS
    app._project_manager.mark_clean(app._build_project_document())
    app._update_project_title()
    return {
        "phase8d_basic_advanced_preserves_values": basic_preserved,
        "phase8d_advanced_fields_hidden_in_basic": advanced_hidden,
        "phase8d_slider_exact_entry_synced": slider_synced,
        "phase8d_slider_edits_debounced": slider_debounced,
        "phase8d_out_of_range_preserved": out_of_range_preserved,
        "phase8d_guidance_rendered": warning_rendered,
        "phase8d_help_opened": help_opened,
        "phase8d_field_reset_worked": field_reset_worked,
        "phase8d_reset_all_confirmed": reset_all_worked,
        "phase8d_spinbox_enum_work": discrete_controls_work,
        "phase8d_partial_preset_applied": preset_is_partial,
        "phase8d_unit_display_changed": unit_display_changed,
        "phase8d_unit_canonical_preserved": unit_canonical_preserved,
        "phase8d_project_exact_restored": project_exact_restored,
        "phase8d_ui_preferences_restored": ui_preferences_restored,
        "phase8d_project_file": str(project_path),
    }


def _exercise_phase8g_feasibility(root, app, main_window_module) -> dict[str, Any]:
    from motor_calculator.input_ux import APPLICATION_DEFAULTS

    original_confirm = main_window_module.messagebox.askokcancel
    main_window_module.messagebox.askokcancel = lambda *_args, **_kwargs: True
    try:
        preset_applied = app._apply_preset_by_id("design.manufacturability_start.v1")
    finally:
        main_window_module.messagebox.askokcancel = original_confirm
    app.run_analysis()
    root.update()
    feasible = app._latest_feasibility_assessment
    if feasible is None:
        raise RuntimeError("Phase 8G feasible assessment was not produced")
    report = app.result_text.get("1.0", "end")

    bad_values = {
        "V_dc": 48.0,
        "P_rated": 10000.0,
        "n_rated": 2500.0,
        "N_ph_turns": 200,
        "d_wire": 1.2,
        "slot_type": "半闭口槽",
    }
    for name, value in bad_values.items():
        app.vars[name].set(str(value))
    app.coreless_var.set(False)
    app.run_analysis()
    root.update()
    bad = app._latest_feasibility_assessment
    if bad is None:
        raise RuntimeError("Phase 8G bad-design assessment was not produced")

    app._project_suppress_dirty = True
    try:
        for name, value in APPLICATION_DEFAULTS.items():
            if name == "coreless":
                app.coreless_var.set(bool(value))
            else:
                app.vars[name].set(str(value))
        original_confirm = main_window_module.messagebox.askokcancel
        main_window_module.messagebox.askokcancel = lambda *_args, **_kwargs: True
        try:
            app._apply_preset_by_id("design.manufacturability_start.v1")
        finally:
            main_window_module.messagebox.askokcancel = original_confirm
    finally:
        app._project_suppress_dirty = False
    app.run_analysis()
    root.update()
    app._project_manager.mark_clean(app._build_project_document())
    app._update_project_title()

    return {
        "phase8g_feasible_preset_applied": bool(preset_applied),
        "phase8g_feasible_no_error": not feasible.has_error,
        "phase8g_feasible_no_severe": not feasible.has_severe_design_risk,
        "phase8g_feasible_current_density": feasible.current_density_a_per_mm2,
        "phase8g_feasible_slot_fill": feasible.slot_fill_factor,
        "phase8g_feasible_voltage_margin": feasible.voltage_margin_percent,
        "phase8g_report_shows_engineering_numbers": (
            "当前电流密度" in report and "可用/所需线电压 RMS" in report
        ),
        "phase8g_bad_design_triggers_severe": bad.has_severe_design_risk,
        "phase8g_bad_issue_codes": [issue.code for issue in bad.issues],
    }


def _capture_window(root, destination: Path) -> str | None:
    try:
        from PIL import ImageGrab

        root.update()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            image = ImageGrab.grab(
                window=root.winfo_id(),
                include_layered_windows=True,
                all_screens=True,
            )
        else:
            left = root.winfo_rootx()
            top = root.winfo_rooty()
            right = left + root.winfo_width()
            bottom = top + root.winfo_height()
            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        image.save(destination)
    except Exception:
        return traceback.format_exc()
    return None


def run_real_gui_smoke(root, app, output_path: Path) -> None:
    """Exercise the real GUI, persist evidence/export, write JSON, then exit."""

    from motor_calculator.gui import main_window as main_window_module
    from motor_calculator.i18n import get_locale, tr
    from motor_calculator.validation.confidence_summary import export_confidence_summary
    from motor_calculator.validation.feedback_service import load_feedback_records
    from motor_calculator.runtime.display import windows_work_area
    from motor_calculator.version import APPLICATION_VERSION

    output = Path(output_path).resolve()
    screenshot = output.with_suffix(".png")
    payload: dict[str, Any] = {
        "status": "FAILED",
        "mode": app._runtime_paths.mode,
        "user_data_dir": str(app._runtime_paths.user_data_dir),
        "feedback_store": str(app._feedback_store),
        "log_file": str(app._runtime_paths.log_file),
        "screenshot": str(screenshot),
    }
    try:
        legacy_module = main_window_module._get_legacy_module()
        messages = _install_nonblocking_messages(main_window_module, legacy_module)
        root.deiconify()
        root.update()
        tab_names = tuple(
            str(app.notebook.tab(index, "text")) for index in range(app.notebook.index("end"))
        )
        if tr("confidence.tab") not in tab_names:
            raise RuntimeError("localized confidence tab is missing")
        chinese_ui = {
            "default_locale": get_locale(),
            "main_title_chinese": tr("app.title") in root.title(),
            "confidence_tab_chinese": tr("confidence.tab") in tab_names,
            "file_menu_chinese": app._project_menu_bar.entrycget(1, "label") == tr("menu.file"),
            "guided_title_chinese": app._guided_input_panel.frame.cget("text") == tr("guided.title"),
        }
        app.run_analysis()
        root.update()
        if not getattr(app, "calc_results", None):
            raise RuntimeError("GUI calculation did not produce results")
        calculation = _calculation_snapshot(app.calc_results)
        if not all(math.isfinite(value) for value in calculation.values()):
            raise RuntimeError("GUI calculation produced non-finite output")
        app._show_about()
        diagnostic_export = output.with_name(output.stem + "-diagnostics.json")
        original_diagnostic_dialog = main_window_module.filedialog.asksaveasfilename
        main_window_module.filedialog.asksaveasfilename = lambda **_kwargs: str(diagnostic_export)
        try:
            diagnostic_exported = app._export_runtime_diagnostics()
        finally:
            main_window_module.filedialog.asksaveasfilename = original_diagnostic_dialog
        diagnostic_payload = json.loads(diagnostic_export.read_text(encoding="utf-8"))
        if not diagnostic_exported or diagnostic_payload["application_version"] != APPLICATION_VERSION:
            raise RuntimeError("versioned local diagnostic export failed")
        phase8d_results = _exercise_phase8d_input_ux(root, app, main_window_module, output)
        payload.update(phase8d_results)
        if not all(value for name, value in phase8d_results.items() if name != "phase8d_project_file"):
            raise RuntimeError("Phase 8D guided input smoke did not pass every interaction gate")
        phase8g_results = _exercise_phase8g_feasibility(root, app, main_window_module)
        if not all(
            phase8g_results[name]
            for name in (
                "phase8g_feasible_preset_applied",
                "phase8g_feasible_no_error",
                "phase8g_feasible_no_severe",
                "phase8g_report_shows_engineering_numbers",
                "phase8g_bad_design_triggers_severe",
            )
        ):
            raise RuntimeError("Phase 8G feasibility GUI smoke did not pass every gate")
        payload.update(phase8g_results)
        project_results = _exercise_project_workflow(root, app, main_window_module, output)
        if not all(
            project_results[name]
            for name in (
                "project_created",
                "project_dirty_after_edit",
                "project_clean_after_save",
                "project_reset_changed_inputs",
                "project_opened_through_file_dialog",
                "project_saved_as_through_file_dialog",
                "project_exact_inputs_restored",
                "project_calculation_reproduced",
                "project_exit_cancel_protected",
                "project_recent_entry_present",
            )
        ):
            raise RuntimeError("project save/load GUI smoke did not pass every lifecycle gate")
        recovery_results = _exercise_recovery_workflow(root, app, main_window_module)
        if not all(
            recovery_results[name]
            for name in (
                "recovery_autosave_written",
                "recovery_browser_opened",
                "recovery_restored",
                "recovery_restored_inputs_exact",
                "recovery_restored_dirty_without_path",
                "recovery_calculation_after_restore",
                "recovery_selected_discarded",
            )
        ):
            raise RuntimeError("recovery GUI smoke did not pass every recovery gate")
        dialog_results = _exercise_dialogs(root, app, screenshot)
        records_before, records_after = _submit_smoke_feedback(app, main_window_module)
        confidence_export = app._runtime_paths.export_dir / "phase8a2_smoke_confidence.json"
        export_confidence_summary(
            app._engineering_confidence_summary,
            confidence_export,
            format_name="json",
        )
        if not confidence_export.is_file():
            raise RuntimeError("confidence export was not created")
        app.notebook.select(app.confidence_tab)
        app.input_frame.canvas.yview_moveto(0.0)
        root.deiconify()
        root.lift()
        root.update_idletasks()
        root.update()
        chinese_ui["confidence_actions_visible"] = _widget_fits_window(
            app.confidence_panel.actions, root
        )
        time.sleep(0.2)
        root.update()
        screenshot_error = _capture_window(root, screenshot)
        payload.update(
            {
                "status": "PASS",
                "tabs": tab_names,
                "calculation": calculation,
                "about_dialog_opened": True,
                "diagnostic_export": str(diagnostic_export),
                "diagnostic_export_exists": diagnostic_export.is_file(),
                "diagnostic_application_version": diagnostic_payload["application_version"],
                "root_size": [root.winfo_width(), root.winfo_height()],
                "screen_size": [root.winfo_screenwidth(), root.winfo_screenheight()],
                "work_area": list(
                    windows_work_area(root.winfo_screenwidth(), root.winfo_screenheight())
                ),
                "screen_dpi": float(root.winfo_fpixels("1i")),
                "tk_scaling": float(root.tk.call("tk", "scaling")),
                "root_fits_screen": _window_fits_screen(root),
                "matplotlib_available": bool(legacy_module.MATPLOTLIB_AVAILABLE),
                "messages": messages,
                "feedback_records_before": records_before,
                "feedback_records_after": records_after,
                "feedback_records_reloaded": len(load_feedback_records(app._feedback_store)),
                "confidence_export": str(confidence_export),
                "confidence_export_exists": confidence_export.is_file(),
                "screenshot_error": screenshot_error,
                **phase8d_results,
                **phase8g_results,
                **project_results,
                **recovery_results,
                **dialog_results,
                **chinese_ui,
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()
    finally:
        try:
            current = app._project_manager.current_project
            if current is not None:
                app._recovery_manager.cleanup_project(current.metadata.project_uuid)
            app._recovery_manager.mark_session_clean()
        except Exception:
            payload["recovery_cleanup_error"] = traceback.format_exc()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        root.after_idle(root.destroy)
