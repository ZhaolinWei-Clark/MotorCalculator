"""Explicit real-window GUI smoke procedure for source and packaged builds."""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any


from tkinter import messagebox


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


def _find_all(text, needle):
    start = 0
    while (index := text.find(needle, start)) != -1:
        yield index
        start = index + 1


def _exercise_phase11b_public_reference(root, app, dialog) -> dict[str, Any]:
    """Phase 11B: the CREATOR public-reference view.

    The repository ships no raw measurements, so the state the application must
    handle correctly is "source registered, data absent". That is exercised
    unconditionally. When a developer machine happens to have a local copy, the
    extraction is exercised too.
    """

    import os

    from motor_calculator.experiment import creator_evidence as evidence
    from motor_calculator.experiment import creator_source as creator
    from motor_calculator.experiment.topology import AFPM_NOT_VALIDATED, PIPELINE_VALIDATED

    results: dict[str, Any] = {}

    tab_labels = tuple(
        str(dialog.tabs.tab(index, "text")) for index in range(dialog.tabs.index("end"))
    )
    results["phase11b_public_reference_tab_present"] = "\u516c\u5f00\u53c2\u8003\u6e90" in tab_labels

    # --- The shipped state: registered source, no local data. ---------------
    dialog.creator_root_var.set("")
    report = dialog.refresh_public_reference()
    root.update()
    results["phase11b_no_data_state"] = report.state
    results["phase11b_no_data_is_clean"] = report.state == evidence.DATA_NOT_CONFIGURED
    results["phase11b_no_data_has_no_values"] = (
        report.back_emf is None and report.cogging is None and report.no_load is None
    )
    results["phase11b_metadata_without_data"] = (
        report.summary.doi == creator.DATASET_DOI
        and report.summary.license_name == creator.LICENSE_NAME
    )
    results["phase11b_compatibility"] = report.compatibility.status.value
    results["phase11b_different_machine"] = report.is_different_machine
    results["phase11b_afpm_claim"] = report.afpm_claim
    results["phase11b_afpm_not_validated"] = report.afpm_claim == AFPM_NOT_VALIDATED

    rendered = {
        key: widget.get("1.0", "end") for key, widget in dialog.creator_views.items()
    }
    results["phase11b_source_view_rendered"] = creator.DATASET_DOI in rendered["source"]
    results["phase11b_source_states_topology"] = "RADIAL_FLUX_INSET_PMSM" in rendered["source"]
    results["phase11b_source_states_licence"] = "CC BY-NC 4.0" in rendered["source"]
    results["phase11b_source_states_different_machine"] = (
        "DIFFERENT_MACHINE" in rendered["source"]
    )
    results["phase11b_all_views_render_without_data"] = all(
        text.strip() for text in rendered.values()
    )
    # Parameter origins are metadata and must render with no data present.
    results["phase11b_parameter_origins_rendered"] = (
        "\u6709\u9650\u5143\u8ba1\u7b97" in rendered["parameters"]
        and "\u6765\u6e90\u672a\u77e5" in rendered["parameters"]
    )
    results["phase11b_lambda_flag_rendered"] = (
        "PARAMETER_PROVENANCE_UNRESOLVED" in rendered["parameters"]
    )
    results["phase11b_state_banner"] = dialog.creator_state_var.get()

    # --- Step 19: the topology firewall, through a real production path. -----
    refusal = dialog.create_project_from_public_source()
    root.update()
    results["phase11b_project_construction_refused"] = bool(refusal)
    results["phase11b_refusal_names_topology"] = bool(
        refusal and "RADIAL_FLUX_INSET_PMSM" in refusal
    )
    results["phase11b_refusal_names_axial"] = bool(refusal and "axial-flux" in refusal)

    # --- Optional: a local copy of the dataset, if this machine has one. -----
    configured = str(os.environ.get("MOTORCALC_CREATOR_DATASET_ROOT", "")).strip()
    default_root = r"D:/File/Project/Codex_电机项目/PM_synchronous_motor"
    candidate = configured or default_root
    has_local = (
        Path(candidate) / creator.RELATIVE_PATHS["back_emf"]
    ).is_file()
    results["phase11b_local_dataset_present"] = has_local
    if has_local:
        dialog.creator_root_var.set(candidate)
        loaded = dialog.refresh_public_reference()
        root.update()
        results["phase11b_data_state"] = loaded.state
        results["phase11b_back_emf_fundamental_v"] = (
            None if loaded.back_emf is None else loaded.back_emf.fundamental_peak_v
        )
        results["phase11b_publication_reproduced"] = bool(
            loaded.publication_check and loaded.publication_check.reproduced
        )
        results["phase11b_publication_deviation_percent"] = (
            None if loaded.publication_check is None
            else loaded.publication_check.difference_percent
        )
        results["phase11b_single_speed_ke"] = (
            None if loaded.single_speed_ke is None
            else loaded.single_speed_ke.value_v_per_rad_s
        )
        results["phase11b_ke_has_no_r_squared"] = (
            loaded.single_speed_ke is not None and loaded.single_speed_ke.r_squared is None
        )
        results["phase11b_cogging_max_abs"] = (
            None if loaded.cogging is None else loaded.cogging.max_abs_nm
        )
        results["phase11b_cogging_peak_to_peak"] = (
            None if loaded.cogging is None else loaded.cogging.peak_to_peak_nm
        )
        results["phase11b_cogging_flag"] = (
            None if loaded.cogging is None else loaded.cogging.published_scalar_flag
        )
        results["phase11b_no_load_mean_residual_percent"] = (
            None if loaded.no_load is None else loaded.no_load.mean_abs_residual_percent
        )
        results["phase11b_pipeline_claim"] = loaded.pipeline_claim
        results["phase11b_pipeline_validated"] = loaded.pipeline_claim == PIPELINE_VALIDATED
        # Even with a perfect reproduction, the AFPM claim must not move.
        results["phase11b_afpm_still_not_validated"] = (
            loaded.afpm_claim == AFPM_NOT_VALIDATED and loaded.is_different_machine
        )
        loaded_text = dialog.creator_views["back_emf"].get("1.0", "end")
        results["phase11b_view_shows_fundamental"] = "\u57fa\u6ce2\u5cf0\u503c" in loaded_text
        results["phase11b_view_shows_provenance"] = (
            "MEASUREMENT_DERIVED_SINGLE_SPEED" in loaded_text
        )
        results["phase11b_view_shows_afpm_disclaimer"] = AFPM_NOT_VALIDATED in loaded_text
        cogging_text = dialog.creator_views["cogging"].get("1.0", "end")
        results["phase11b_cogging_view_shows_ambiguity"] = (
            "PUBLISHED_SCALAR_DEFINITION_AMBIGUOUS" in cogging_text
        )
        dialog.creator_root_var.set("")
        dialog.refresh_public_reference()
        root.update()
    return results


def _exercise_phase12_capability(root, app, output: Path) -> dict[str, Any]:
    """Phase 12: the torque-speed / field-weakening capability view."""

    from motor_calculator.capability.export import CALIBRATION_STATUS, EVIDENCE_STATEMENT
    from motor_calculator.capability.limits import MODULATION_LABELS_ZH, Modulation

    results: dict[str, Any] = {}

    menu = app._project_analysis_menu
    labels = [
        str(menu.entrycget(index, "label"))
        for index in range(menu.index("end") + 1)
        if menu.type(index) == "command"
    ]
    results["phase12_menu_entry_present"] = "\u8f6c\u77e9-\u8f6c\u901f / \u5f31\u78c1\u80fd\u529b..." in labels

    dialog = app._open_capability_view()
    root.update()
    results["phase12_dialog_opened"] = bool(dialog.window.winfo_exists())
    results["phase12_dialog_fits_screen"] = _window_fits_screen(dialog.window)

    headline = dialog.headline_values()
    results["phase12_solved"] = bool(headline.get("available"))
    for key in (
        "base_speed_rpm", "base_speed_resolved", "maximum_speed_rpm",
        "maximum_speed_bounded", "peak_torque_nm", "peak_power_w",
        "dc_bus_voltage_v", "current_limit_peak_a", "voltage_limit_phase_peak_v",
        "modulation", "mtpa_method", "mtpa_id_a", "field_weakening_active",
        "constant_power_exists", "regions", "evidence", "calibration_status",
    ):
        results[f"phase12_{key}"] = headline.get(key)

    results["phase12_evidence_is_model_only"] = headline.get("evidence") == EVIDENCE_STATEMENT
    results["phase12_calibration_none"] = headline.get("calibration_status") == CALIBRATION_STATUS
    results["phase12_spmsm_mtpa_id_is_zero"] = (
        headline.get("mtpa_id_a") is not None and abs(headline["mtpa_id_a"]) < 1e-12
    )

    # Every tab must render, and the figures must actually draw.
    tab_labels = tuple(
        str(dialog.tabs.tab(index, "text")) for index in range(dialog.tabs.index("end"))
    )
    results["phase12_tabs"] = list(tab_labels)
    results["phase12_torque_speed_tab_present"] = "\u8f6c\u77e9-\u8f6c\u901f\u66f2\u7ebf" in tab_labels
    results["phase12_dq_tab_present"] = "dq \u7535\u6d41\u5e73\u9762" in tab_labels
    results["phase12_torque_speed_rendered"] = bool(
        dialog.torque_speed_host.winfo_children()
    )
    results["phase12_dq_rendered"] = bool(dialog.dq_host.winfo_children())

    summary = dialog.summary_text.get("1.0", "end")
    results["phase12_summary_has_base_speed"] = "\u57fa\u901f" in summary
    results["phase12_summary_has_regions"] = "MTPA_CURRENT_LIMITED" in summary
    results["phase12_summary_states_model_only"] = "\u672a\u7ecf\u5b9e\u9a8c\u9a8c\u8bc1" in summary

    provenance = dialog.provenance_text.get("1.0", "end")
    results["phase12_provenance_shows_isotropic"] = "ISOTROPIC_ASSUMPTION" in provenance
    results["phase12_provenance_shows_psi_source"] = "psi_pm" in provenance

    # Operating-point inspector at base speed and deep in field weakening.
    dialog.inspect_speed_var.set(f"{headline['base_speed_rpm']:.0f}")
    at_base = dialog.refresh_inspector()
    results["phase12_inspector_renders"] = "id" in at_base and "iq" in at_base
    results["phase12_inspector_shows_constraints"] = "\u8d77\u4f5c\u7528\u7684\u7ea6\u675f" in at_base
    dialog.inspect_speed_var.set(f"{headline['base_speed_rpm'] * 6.0:.0f}")
    deep = dialog.refresh_inspector()
    results["phase12_inspector_deep_fw_renders"] = "id" in deep

    # Switching modulation must change the voltage limit, and by the known ratio.
    svpwm_limit = headline["voltage_limit_phase_peak_v"]
    dialog.modulation_var.set(MODULATION_LABELS_ZH[Modulation.SPWM])
    dialog.refresh()
    root.update()
    spwm = dialog.headline_values()
    results["phase12_spwm_limit_lower"] = spwm["voltage_limit_phase_peak_v"] < svpwm_limit
    results["phase12_svpwm_advantage_ratio"] = (
        svpwm_limit / spwm["voltage_limit_phase_peak_v"]
    )
    results["phase12_spwm_base_speed_lower"] = spwm["base_speed_rpm"] < headline["base_speed_rpm"]
    dialog.modulation_var.set(MODULATION_LABELS_ZH[Modulation.SVPWM])
    dialog.refresh()
    root.update()

    # Export.
    export_dir = output.parent / "phase12_capability"
    exported = dialog.export(export_dir)
    results["phase12_export_json"] = bool(exported and exported.json_path.is_file())
    results["phase12_export_csv"] = bool(exported and exported.csv_path.is_file())
    if exported:
        text = exported.json_path.read_text(encoding="utf-8")
        results["phase12_export_no_experimental_claim"] = (
            "NOT_EXPERIMENTALLY_VALIDATED" in text
            and "EXPERIMENTALLY_SUPPORTED" not in text
        )
        results["phase12_export_declares_peak_basis"] = "PHASE_PEAK" in text

    # Settings must reach the project's persisted preferences.
    preferences = app._ui_preferences_payload()
    results["phase12_settings_persisted"] = any(
        str(key).startswith("capability.") for key in preferences
    )
    results["phase12_persisted_modulation"] = preferences.get("capability.modulation")
    results["phase12_no_derived_curves_persisted"] = not any(
        "torque" in str(key) or "envelope" in str(key) for key in preferences
    )

    dialog.window.destroy()
    return results


def _exercise_phase11a_validation_data(root, app, output: Path) -> dict[str, Any]:
    """Phase 11A: File -> New authority, the dashboard summary, and the data manager."""

    from motor_calculator.experiment.comparison import NO_EXPERIMENTAL_DATA
    from motor_calculator.experiment.persistence import DatasetAvailability, DatasetStore
    from motor_calculator.experiment.schema import DatasetMetadata, MachineIdentity, TestType
    from motor_calculator.experiment.service import ValidationDataService
    from motor_calculator.experiment.sources import DatasetSourceType
    from motor_calculator.motor_core.winding_factor import (
        WINDING_FACTOR_MODE_LABELS_ZH,
        WindingFactorMode,
    )

    results: dict[str, Any] = {}

    # File -> New prompts when the project is dirty, and the earlier workflows
    # leave it dirty. Discard, the way the other sections that drive this path
    # do, so the smoke never blocks on a modal nobody can click.
    original_prompt = messagebox.askyesnocancel
    messagebox.askyesnocancel = lambda *_args, **_kwargs: False
    try:
        return _phase11a_body(root, app, output, results)
    finally:
        messagebox.askyesnocancel = original_prompt


def _phase11a_body(root, app, output: Path, results: dict[str, Any]) -> dict[str, Any]:
    from motor_calculator.experiment.comparison import NO_EXPERIMENTAL_DATA
    from motor_calculator.experiment.persistence import DatasetAvailability, DatasetStore
    from motor_calculator.experiment.schema import DatasetMetadata, MachineIdentity, TestType
    from motor_calculator.experiment.service import ValidationDataService
    from motor_calculator.experiment.sources import DatasetSourceType
    from motor_calculator.motor_core.winding_factor import (
        WINDING_FACTOR_MODE_LABELS_ZH,
        WindingFactorMode,
    )

    # --- Step 1: File -> New must be live, not merely library code. ----------
    # Force MANUAL first, so an AUTO result after File -> New can only have come
    # from the new-project path itself rather than from leftover session state.
    app._winding_factor_mode_var.set(WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.MANUAL])
    app._refresh_winding_factor_summary()
    root.update()
    results["phase11a_authority_before_new"] = app._selected_winding_factor_mode().value

    if not app._new_project():
        raise RuntimeError("Phase 11A: File -> New was cancelled unexpectedly")
    root.update()
    results["phase11a_new_project_authority"] = app._selected_winding_factor_mode().value
    results["phase11a_new_project_is_auto"] = (
        app._selected_winding_factor_mode() is WindingFactorMode.AUTO
    )
    resolution = app._latest_winding_factor_resolution()
    results["phase11a_new_project_kw"] = None if resolution is None else resolution.value
    results["phase11a_new_project_kw_is_geometry"] = (
        resolution is not None
        and resolution.value is not None
        and abs(float(resolution.value) - 0.8660254037844386) < 1e-9
    )
    results["phase11a_new_project_declares_authority"] = (
        app._new_project_ui_preferences().get("winding.authority") == "AUTO_FROM_GEOMETRY"
    )

    # --- Step 2: the dashboard manufacturability summary. --------------------
    app.run_analysis()
    root.update()
    summary = app.results_dashboard.winding_summary
    results["phase11a_dashboard_summary_present"] = summary is not None
    if summary is not None:
        results["phase11a_dashboard_authority"] = summary.authority
        results["phase11a_dashboard_kw"] = summary.production_winding_factor
        results["phase11a_dashboard_fill_status"] = summary.fill_status
        results["phase11a_dashboard_envelope_fill"] = summary.usable_envelope_fill
        results["phase11a_dashboard_never_meshed"] = (
            summary.provenance != "MESHED_GEOMETRY_FEA_DIAGNOSTIC_ONLY"
        )
        results["phase11a_dashboard_matches_input_authority"] = (
            summary.authority == "AUTO_FROM_GEOMETRY"
        )
    rendered_summary = app.results_dashboard._winding_summary_var.get()
    results["phase11a_dashboard_summary_rendered"] = "\u751f\u4ea7\u7ed5\u7ec4\u7cfb\u6570" in rendered_summary
    results["phase11a_dashboard_points_at_full_panel"] = "\u7ed5\u7ec4\u5de5\u7a0b" in rendered_summary

    # --- Steps 17-19: the validation data manager. ---------------------------
    menu = app._project_analysis_menu
    labels = [
        str(menu.entrycget(index, "label"))
        for index in range(menu.index("end") + 1)
        if menu.type(index) == "command"
    ]
    results["phase11a_menu_entry_present"] = "\u9a8c\u8bc1\u6570\u636e\u7ba1\u7406..." in labels

    dialog = app._open_validation_data_manager()
    root.update()
    results["phase11a_dialog_opened"] = bool(dialog.window.winfo_exists())
    results["phase11a_dialog_fits_screen"] = _window_fits_screen(dialog.window)

    # Step 19: with no datasets the state must say so, and show no numbers.
    overview = dialog.build_overview()
    results["phase11a_no_data_state"] = overview.state
    results["phase11a_no_data_is_explicit"] = overview.state == NO_EXPERIMENTAL_DATA
    results["phase11a_no_data_has_no_comparisons"] = not overview.comparisons
    results["phase11a_no_data_no_affirmative_claim"] = not overview.has_any_affirmative_claim
    empty_text = dialog.results_text.get("1.0", "end")
    results["phase11a_no_data_text_shown"] = "NO_EXPERIMENTAL_DATA" in empty_text
    results["phase11a_no_data_says_no_pass"] = "\u9a8c\u8bc1\u901a\u8fc7" in empty_text
    results["phase11a_dataset_list_empty"] = dialog.dataset_rows() == ()

    # Step 8: export a template, and prove our own parser accepts it back.
    template_path = output.with_name(output.stem + "-ke-template.csv")
    template_path.unlink(missing_ok=True)
    dialog.export_measurement_template(template_path)
    results["phase11a_template_exported"] = template_path.is_file()

    # Step 5: import a filled-in template through the real dialog action.
    measurement_path = output.with_name(output.stem + "-ke-measurements.csv")
    measurement_path.write_text(
        template_path.read_text(encoding="utf-8")
        + "600,13.856,,24.0\n1200,27.713,,24.5\n1800,41.569,,25.1\n2400,55.426,,25.4\n",
        encoding="utf-8",
    )
    parameters = app._get_params()
    own_machine = MachineIdentity(
        topology="AFPM_DUAL_ROTOR_SINGLE_STATOR",
        pole_count=int(parameters["p"]) * 2,
        slot_count=int(parameters["slots"]),
        phases=3,
        connection="WYE",
        turns_per_phase=int(parameters["N_ph_turns"]),
        rated_speed_rpm=float(parameters["n_rated"]),
        rated_power_w=float(parameters["P_rated"]),
    )
    loaded = dialog.import_dataset(
        measurement_path,
        metadata=DatasetMetadata(
            dataset_id="smoke.ke.1",
            title="GUI smoke Ke run",
            source_type=DatasetSourceType.USER_EXPERIMENT,
            test_type=TestType.NO_LOAD_BACK_EMF,
            machine=own_machine,
        ),
        comparison_config={"connection": "WYE"},
    )
    root.update()
    results["phase11a_csv_imported"] = loaded is not None
    results["phase11a_import_had_no_errors"] = bool(loaded and not loaded.import_errors)
    results["phase11a_imported_sample_count"] = 0 if loaded is None else len(loaded.rows)
    results["phase11a_dataset_listed"] = len(dialog.dataset_rows()) == 1
    results["phase11a_dataset_hash_recorded"] = bool(
        loaded and loaded.metadata.raw_file_hash != "UNKNOWN"
    )

    # Step 18: the comparison view, on one explicit basis.
    comparisons = dialog.build_comparisons()
    results["phase11a_comparison_built"] = len(comparisons) == 1
    if comparisons:
        comparison = comparisons[0]
        results["phase11a_comparison_quantity"] = comparison.quantity
        results["phase11a_comparison_basis"] = comparison.basis_zh
        results["phase11a_comparison_claim"] = comparison.overall_claim.value
        results["phase11a_comparison_samples"] = comparison.measured.sample_count
        results["phase11a_comparison_machine"] = (
            None if comparison.compatibility is None else comparison.compatibility.status.value
        )
        results["phase11a_comparison_evidence_label"] = comparison.measured.evidence_label
        results["phase11a_comparison_has_analytical"] = (
            comparison.analytical is not None and comparison.analytical.value is not None
        )
        results["phase11a_comparison_calibration"] = comparison.calibration_status
        results["phase11a_comparison_residual_count"] = len(comparison.residuals)
    dialog.refresh()
    root.update()
    rendered = dialog.results_text.get("1.0", "end")
    results["phase11a_comparison_rendered"] = "\u53cd\u7535\u52a8\u52bf\u5e38\u6570" in rendered
    results["phase11a_comparison_shows_machine_compatibility"] = "\u673a\u5668\u4e00\u81f4\u6027" in rendered
    results["phase11a_comparison_shows_sample_count"] = "\u6837\u672c\u6570" in rendered

    # A different machine's real data must not validate this design.
    other_path = output.with_name(output.stem + "-other-machine.csv")
    other_path.write_text(
        "speed_rpm,line_voltage_rms_v\n600,13.856\n1200,27.713\n1800,41.569\n",
        encoding="utf-8",
    )
    dialog.import_dataset(
        other_path,
        metadata=DatasetMetadata(
            dataset_id="smoke.ke.other",
            title="published data, different machine",
            source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
            test_type=TestType.NO_LOAD_BACK_EMF,
            machine=MachineIdentity(
                topology="RADIAL_FLUX_INNER_ROTOR", pole_count=20,
                slot_count=24, phases=3, connection="WYE",
            ),
        ),
        comparison_config={"connection": "WYE"},
    )
    root.update()
    claims = {
        comparison.dataset.dataset_id: comparison.overall_claim.value
        for comparison in dialog.build_comparisons()
    }
    results["phase11a_other_machine_claim"] = claims.get("smoke.ke.other")
    results["phase11a_other_machine_not_validated"] = (
        claims.get("smoke.ke.other") == "METHODOLOGY_REFERENCE_ONLY"
    )
    results["phase11a_same_machine_still_supported"] = (
        claims.get("smoke.ke.1") == "EXPERIMENTALLY_SUPPORTED"
    )

    # Phase 11B: the public-reference view lives in the same dialog.
    results.update(_exercise_phase11b_public_reference(root, app, dialog))

    # Step 23: the report export. VALIDATED may only appear as NOT_VALIDATED or
    # inside the affirmative claim for the same-machine dataset.
    report_dir = output.parent / "phase11a_report"
    exported = dialog.export_report(report_dir)
    report_text = exported.text_path.read_text(encoding="utf-8")
    results["phase11a_report_exported"] = exported.json_path.is_file()
    results["phase11a_report_has_citation_block"] = "\u518d\u5206\u53d1\u8bb8\u53ef" in report_text
    results["phase11a_report_marks_other_machine"] = "DIFFERENT_MACHINE" in report_text
    results["phase11a_report_validated_word_is_guarded"] = all(
        report_text[index - 4 : index] == "NOT_"
        for index in _find_all(report_text, "VALIDATED")
    )

    # Step 22: save/load must carry the dataset references.
    project_path = output.with_name(output.stem + "-phase11a.motorproj")
    project_path.unlink(missing_ok=True)
    if not app._save_project_to_path(project_path, save_as=True):
        raise RuntimeError("Phase 11A: saving the project with datasets failed")
    saved_preferences = app._ui_preferences_payload()
    results["phase11a_datasets_persisted"] = "experiment.datasets" in saved_preferences
    results["phase11a_project_holds_reference_not_samples"] = (
        "41.569" not in saved_preferences.get("experiment.datasets", "")
    )
    dialog.window.destroy()

    app._validation_data_service.datasets = []
    if not app._open_project_path(project_path, prompt_for_unsaved=False):
        raise RuntimeError("Phase 11A: reopening the project failed")
    root.update()
    restored_ids = sorted(item.dataset_id for item in app._validation_data_service.datasets)
    results["phase11a_datasets_restored"] = restored_ids == ["smoke.ke.1", "smoke.ke.other"]
    restored = app._validation_data_service.get("smoke.ke.1")
    results["phase11a_restored_samples"] = 0 if restored is None else len(restored.rows)
    results["phase11a_restored_metadata_intact"] = bool(
        restored is not None
        and restored.metadata.machine.pole_count == int(parameters["p"]) * 2
    )

    # A missing data file must degrade, never raise.
    orphan = ValidationDataService(DatasetStore(output.parent / "phase11a_empty_store"))
    orphan.restore(saved_preferences)
    results["phase11a_missing_file_is_reported"] = bool(orphan.datasets) and all(
        item.availability is DatasetAvailability.MISSING for item in orphan.datasets
    )
    results["phase11a_missing_file_keeps_metadata"] = all(
        item.metadata.title for item in orphan.datasets
    )

    # Reopening a project clears the analysis results, and the sections that run
    # after this one expect a calculated session. Leave the app as we found it.
    app.run_analysis()
    root.update()
    results["phase11a_session_restored_for_later_sections"] = (
        getattr(app, "calc_results", None) is not None
    )
    return results


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
    primary_document = load_project(primary)
    snapshot_saved = primary_document.result_snapshot is not None

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
    snapshot_current_on_open = (
        app._latest_result_snapshot is not None
        and "输入哈希与模型版本匹配" in app.results_dashboard._source_var.get()
    )
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
        "project_result_snapshot_saved": snapshot_saved,
        "project_result_snapshot_current_on_open": snapshot_current_on_open,
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
        # Phase 9C: v1 is voltage limited on the authoritative corrected basis,
        # so the feasible reference case is now v2.
        preset_applied = app._apply_preset_by_id("design.manufacturability_start.v2")
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
            app._apply_preset_by_id("design.manufacturability_start.v2")
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
        "phase8g_feasible_legacy_voltage_margin": feasible.legacy_voltage_margin_percent,
        "phase8g_report_shows_engineering_numbers": (
            "当前电流密度" in report and "可用/所需线电压 RMS" in report
        ),
        "phase8g_bad_design_triggers_severe": bad.has_severe_design_risk,
        "phase8g_bad_issue_codes": [issue.code for issue in bad.issues],
    }


def _exercise_phase8h_dashboard(root, app, output: Path) -> dict[str, Any]:
    """Exercise the real dashboard, opt-in sweep, exports, and visible plot."""

    dashboard = app.results_dashboard
    data = dashboard.data
    if data is None:
        raise RuntimeError("Phase 8H dashboard did not receive calculation data")
    metrics = data.metric_by_key
    dashboard._point_count_var.set("7")
    app.notebook.select(app.dashboard_tab)
    dashboard.tabs.select(dashboard.overview_tab)
    dashboard.overview_canvas.yview_moveto(0.0)
    root.update()
    overview_screenshot = output.with_name(output.stem + "-phase8h-overview.png")
    overview_screenshot_error = _capture_window(root, overview_screenshot)
    card_widgets = tuple(widgets[0] for widgets in dashboard._metric_widgets.values())
    top_cards_fit = all(
        _widget_fits_window(widgets[0], root)
        for widgets in tuple(dashboard._metric_widgets.values())[:8]
    )
    dashboard.overview_canvas.yview_moveto(1.0)
    root.update()
    overview_bottom_screenshot = output.with_name(output.stem + "-phase8h-overview-bottom.png")
    overview_bottom_screenshot_error = _capture_window(root, overview_bottom_screenshot)
    bottom_cards_fit = all(_widget_fits_window(widget, root) for widget in card_widgets[-4:])
    range_bars_fit = all(
        _widget_fits_window(widget, root)
        for widget in (
            dashboard.current_density_bar,
            dashboard.voltage_margin_bar,
            dashboard.slot_fill_bar,
        )
    )
    cards_fit = top_cards_fit and bottom_cards_fit and range_bars_fit
    dashboard.tabs.select(dashboard.performance_tab)
    root.update()
    sweep_ran = dashboard.run_performance_sweep()
    root.update()
    series = {item.key: item for item in dashboard.sweep_series}
    figure_export = output.with_name(output.stem + "-phase8h-performance.png")
    csv_export = output.with_name(output.stem + "-phase8h-performance.csv")
    dashboard_screenshot = output.with_name(output.stem + "-phase8h-dashboard.png")
    exported_figure = dashboard.export_current_figure(figure_export)
    exported_csv = dashboard.export_current_csv(csv_export)
    screenshot_error = _capture_window(root, dashboard_screenshot)
    return {
        "phase8h_dashboard_tab_present": bool(app.notebook.index(app.dashboard_tab) == 0),
        "phase8h_dashboard_data_present": data is not None,
        "phase8h_dashboard_no_severe": data.design_status.severe_count == 0,
        "phase8h_dashboard_no_warning": data.design_status.warning_count == 0,
        "phase8h_torque_nm": metrics["rated_torque_nm"].value,
        "phase8h_power_w": metrics["output_power_w"].value,
        "phase8h_efficiency_percent": metrics["efficiency_percent"].value,
        "phase8h_current_density": metrics["current_density_a_per_mm2"].value,
        "phase8h_slot_fill": metrics["slot_fill_factor"].value,
        "phase8h_voltage_margin": metrics["voltage_margin_percent"].value,
        "phase8h_loss_rows": len(dashboard.loss_tree.get_children()),
        "phase8h_static_thermal_explicit": "无可信温升预测" in dashboard._thermal_var.get(),
        "phase8h_dynamic_not_run_explicit": "尚未运行动态仿真" in dashboard._availability_rows.get("dynamic", ""),
        "phase8h_uncertainty_not_run_explicit": "尚未执行不确定性分析" in dashboard._availability_rows.get("uncertainty", ""),
        "phase8h_sweep_ran": bool(sweep_ran),
        "phase8h_sweep_point_count": 0 if dashboard.last_speed_sweep is None else len(dashboard.last_speed_sweep.points),
        "phase8h_torque_curve_available": series["torque_speed"].availability.value == "AVAILABLE",
        "phase8h_power_curve_available": series["power_speed"].availability.value == "AVAILABLE",
        "phase8h_voltage_margin_curve_available": series["voltage_margin"].availability.value == "AVAILABLE",
        "phase8h_figure_export": str(figure_export),
        "phase8h_figure_exported": exported_figure == figure_export and figure_export.stat().st_size > 1000,
        "phase8h_csv_export": str(csv_export),
        "phase8h_csv_exported": exported_csv == csv_export and csv_export.stat().st_size > 100,
        "phase8h_chinese_font": dashboard.chinese_font_name,
        "phase8h_dashboard_screenshot": str(dashboard_screenshot),
        "phase8h_dashboard_screenshot_error": screenshot_error,
        "phase8h_overview_screenshot": str(overview_screenshot),
        "phase8h_overview_screenshot_error": overview_screenshot_error,
        "phase8h_overview_bottom_screenshot": str(overview_bottom_screenshot),
        "phase8h_overview_bottom_screenshot_error": overview_bottom_screenshot_error,
        "phase8h_top_cards_fit_window": top_cards_fit,
        "phase8h_bottom_cards_fit_window": bottom_cards_fit,
        "phase8h_range_bars_fit_window": range_bars_fit,
        "phase8h_cards_fit_window": cards_fit,
        "phase8h_dashboard_fits_window": _widget_fits_window(dashboard, root),
        "phase8h_initial_render_seconds": dashboard.last_initial_render_seconds,
        "phase8h_plot_render_seconds": dashboard.last_plot_render_seconds,
        "phase8h_sweep_seconds": dashboard.last_speed_sweep.elapsed_seconds,
    }


def _exercise_phase8i_analysis(root, app, output: Path) -> dict[str, Any]:
    """Run all three new opt-in analysis entries through their real GUI controls."""

    center = app._open_analysis_center("dynamic")
    center.dynamic_time_var.set("0.05")
    center.dynamic_speed_var.set("200")
    center.dynamic_load_var.set("0")
    center.dynamic_accuracy_var.set("FAST")
    dynamic_ran = center.run_dynamic()
    root.update()
    center.window.update()
    dynamic_screenshot = output.with_name(output.stem + "-phase8i-dynamic.png")
    dynamic_screenshot_error = _capture_window(center.window, dynamic_screenshot)

    center.select_analysis("uncertainty")
    center.uncertainty_samples_var.set("100")
    center.uncertainty_seed_var.set("20260830")
    uncertainty_ran = center.run_uncertainty()
    root.update()
    center.window.update()
    uncertainty_screenshot = output.with_name(output.stem + "-phase8i-uncertainty.png")
    uncertainty_screenshot_error = _capture_window(center.window, uncertainty_screenshot)

    center.select_analysis("sensitivity")
    sensitivity_ran = center.run_sensitivity()
    root.update()
    center.window.update()
    sensitivity_screenshot = output.with_name(output.stem + "-phase8i-sensitivity.png")
    sensitivity_screenshot_error = _capture_window(center.window, sensitivity_screenshot)
    window_fits = _window_fits_screen(center.window)
    center.window.destroy()
    app._analysis_center = None
    root.update()

    dynamic_result = None if center.last_dynamic_outcome is None else center.last_dynamic_outcome.result
    uncertainty_result = center.last_uncertainty_result
    sensitivity_summary = center.last_sensitivity_summary
    return {
        "phase8i_analysis_menu_present": app._project_menu_bar.entrycget(2, "label") == "分析",
        "phase8i_dynamic_ran": bool(dynamic_ran),
        "phase8i_dynamic_points": 0 if dynamic_result is None else len(dynamic_result.time),
        "phase8i_dynamic_voltage_series": bool(dynamic_result and dynamic_result.vd_actual and dynamic_result.vq_actual),
        "phase8i_uncertainty_ran": bool(uncertainty_ran),
        "phase8i_uncertainty_valid_samples": 0 if uncertainty_result is None else uncertainty_result.monte_carlo.valid_sample_count,
        "phase8i_uncertainty_dashboard_updated": "参数边界" in app.results_dashboard._uncertainty_var.get(),
        "phase8i_sensitivity_ran": bool(sensitivity_ran),
        "phase8i_sensitivity_run_count": 0 if sensitivity_summary is None else len(sensitivity_summary.run_results),
        "phase8i_analysis_window_fits_screen": window_fits,
        "phase8i_dynamic_screenshot": str(dynamic_screenshot),
        "phase8i_dynamic_screenshot_error": dynamic_screenshot_error,
        "phase8i_uncertainty_screenshot": str(uncertainty_screenshot),
        "phase8i_uncertainty_screenshot_error": uncertainty_screenshot_error,
        "phase8i_sensitivity_screenshot": str(sensitivity_screenshot),
        "phase8i_sensitivity_screenshot_error": sensitivity_screenshot_error,
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


def _exercise_rc3_voltage_authority(root, app) -> dict[str, Any]:
    """Phase 9C: the corrected voltage must be authoritative everywhere."""

    from motor_calculator.plots import build_speed_sweep_series, run_speed_sweep
    from motor_calculator.validation.design_feasibility import evaluate_design_feasibility

    results: dict[str, Any] = {}
    app.run_analysis()
    root.update()
    params = app._get_params()
    assessment = app._latest_feasibility_assessment
    data = app.results_dashboard.data
    report = app.result_text.get("1.0", "end")

    required = data.metric_by_key["required_voltage_v"]
    margin = data.metric_by_key["voltage_margin_percent"]
    results["rc3_dashboard_uses_corrected_voltage"] = (
        required.value is not None
        and abs(required.value - float(app.calc_results.performance.required_voltage_line_rms_v))
        < 1e-9
        and margin.value is not None
        and abs(margin.value - assessment.voltage_margin_percent) < 1e-9
    )
    legacy_keys = {metric.key for metric in data.legacy_diagnostic_metrics}
    results["rc3_dashboard_legacy_group_present"] = {
        "legacy_required_voltage_v",
        "legacy_voltage_margin_percent",
    } <= legacy_keys
    results["rc3_report_shows_corrected_voltage"] = "同基电压裕量" in report
    results["rc3_report_marks_legacy_as_compatibility"] = "兼容值 legacy 电压" in report

    sweep = run_speed_sweep(params, 1400.0, 2400.0, point_count=5)
    series = {item.key: item for item in build_speed_sweep_series(sweep)}
    first = sweep.points[0]
    results["rc3_sweep_uses_corrected_voltage"] = (
        first.required_voltage_line_rms_v is not None
        and first.legacy_required_voltage_line_rms_v is not None
        and first.required_voltage_line_rms_v > first.legacy_required_voltage_line_rms_v
    )
    results["rc3_sweep_legacy_curve_hidden_by_default"] = (
        series["legacy_required_voltage"].default_visible is False
        and series["required_voltage"].default_visible is True
    )

    payload = app.rc2_export_payload()
    results["rc3_export_uses_authoritative_names"] = (
        payload.get("voltage_model_provenance") == "CORRECTED_SAME_BASIS_PMSM"
        and "required_voltage_line_rms_v" in payload
        and "voltage_margin_line_rms_percent" in payload
        and "legacy_required_voltage_v" in payload
    )
    results["rc3_startup_corrected_margin"] = assessment.voltage_margin_percent
    results["rc3_startup_legacy_margin"] = assessment.legacy_voltage_margin_percent

    # A design the legacy basis calls feasible must now be rejected.
    bad = dict(params)
    bad["n_rated"] = 2200.0
    bad["N_ph_turns"] = 50
    bad["n_parallel"] = 2
    from motor_calculator.motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params

    bad_parsed = parse_legacy_gui_params(bad)
    bad_result = LegacyGuiMotorModelBridge(bad_parsed).run_full_analysis()
    bad_assessment = evaluate_design_feasibility(bad_parsed, bad_result)
    results["rc3_bad_design_rejected_on_corrected_basis"] = (
        bad_assessment.voltage_margin_percent < 0.0
        and bad_assessment.legacy_voltage_margin_percent > 0.0
        and bad_assessment.has_severe_design_risk
    )
    return results


def _exercise_rc2_winding_factor_and_occupancy(root, app) -> dict[str, Any]:
    """RC2: slot occupancy and winding-factor provenance must be user-visible."""

    from motor_calculator.motor_core.winding_factor import (
        WINDING_FACTOR_MODE_LABELS_ZH,
        WindingFactorMode,
        WindingFactorProvenance,
    )

    results: dict[str, Any] = {}
    manual_label = WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.MANUAL]
    auto_label = WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.AUTO]

    app._winding_factor_mode_var.set(manual_label)
    app._coil_span_slots_var.set("")
    app._skew_slots_var.set("0")
    root.update()
    app.run_analysis()
    root.update()
    manual_resolution = app._latest_winding_factor_resolution()
    manual_report = app.result_text.get("1.0", "end")
    manual_kw = float(app._get_params()["k_w"])
    results["rc2_manual_provenance"] = manual_resolution.provenance.value
    results["rc2_manual_k_w"] = manual_kw
    results["rc2_manual_matches_input"] = math.isclose(
        manual_kw, float(app.vars["k_w"].get()), rel_tol=1e-12
    )
    results["rc2_manual_label_visible"] = manual_label in manual_report
    results["rc2_report_shows_occupancy"] = "近似裸铜槽占比" in manual_report
    results["rc2_report_shows_same_basis_voltage"] = "同基电压裕量" in manual_report
    results["rc2_report_shows_winding_factor"] = "基波绕组系数 k_w1" in manual_report
    results["rc2_summary_caption_present"] = bool(
        str(app._winding_factor_summary_var.get()).strip()
    )

    # AUTO without a coil span must not invent full pitch.
    app._winding_factor_mode_var.set(auto_label)
    app._coil_span_slots_var.set("")
    root.update()
    app.run_analysis()
    root.update()
    without_span = app._latest_winding_factor_resolution()
    results["rc2_auto_without_span_provenance"] = without_span.provenance.value
    results["rc2_auto_without_span_preserves_manual"] = math.isclose(
        float(app._get_params()["k_w"]), manual_kw, rel_tol=1e-12
    )

    # AUTO with an explicit coil span derives k_w1 and shows k_d / k_p / k_s.
    app._coil_span_slots_var.set("1")
    root.update()
    app.run_analysis()
    root.update()
    auto_resolution = app._latest_winding_factor_resolution()
    auto_report = app.result_text.get("1.0", "end")
    results["rc2_auto_provenance"] = auto_resolution.provenance.value
    results["rc2_auto_k_w"] = auto_resolution.value
    results["rc2_auto_used_in_params"] = math.isclose(
        float(app._get_params()["k_w"]), float(auto_resolution.value), rel_tol=1e-12
    )
    results["rc2_auto_report_shows_kd"] = "分布系数 k_d" in auto_report
    results["rc2_auto_report_shows_kp"] = "节距系数 k_p" in auto_report
    results["rc2_auto_report_shows_ks"] = "偏斜系数 k_s" in auto_report
    results["rc2_auto_label_visible"] = auto_label in auto_report
    results["rc2_auto_breakdown_present"] = auto_resolution.breakdown is not None
    if auto_resolution.breakdown is not None:
        results["rc2_auto_k_d"] = auto_resolution.breakdown.distribution_factor
        results["rc2_auto_k_p"] = auto_resolution.breakdown.pitch_factor
        results["rc2_auto_k_s"] = auto_resolution.breakdown.skew_factor

    # Switching back must restore the manual value exactly.
    app._winding_factor_mode_var.set(manual_label)
    root.update()
    app.run_analysis()
    root.update()
    results["rc2_switch_back_restores_manual"] = math.isclose(
        float(app._get_params()["k_w"]), manual_kw, rel_tol=1e-12
    )
    results["rc2_switch_back_provenance"] = (
        app._latest_winding_factor_resolution().provenance.value
    )
    app._coil_span_slots_var.set("")
    root.update()
    results["rc2_provenance_states_distinct"] = (
        results["rc2_manual_provenance"] == WindingFactorProvenance.MANUAL_USER.value
        and results["rc2_auto_provenance"] == WindingFactorProvenance.AUTO_GEOMETRY.value
        and results["rc2_auto_without_span_provenance"]
        == WindingFactorProvenance.NOT_ENOUGH_GEOMETRY.value
    )
    return results


def _exercise_phase10a_fea_validation(root, app, output: Path) -> dict[str, Any]:
    """Phase 10A: the FEA validation entry must open, state solver availability
    honestly, generate a case, and never show a fabricated FEA number."""

    from motor_calculator.fea.models import FEASupportability, FEAValidationTarget

    results: dict[str, Any] = {}
    menu = app._project_analysis_menu
    labels = [
        str(menu.entrycget(index, "label"))
        for index in range(menu.index("end") + 1)
        if menu.type(index) == "command"
    ]
    results["phase10a_menu_entry_present"] = "FEA 验证..." in labels

    dialog = app._open_fea_validation()
    root.update()
    results["phase10a_dialog_opened"] = bool(dialog.window.winfo_exists())
    results["phase10a_dialog_fits_screen"] = _window_fits_screen(dialog.window)

    model = dialog.view_model
    results["phase10a_view_model_built"] = model is not None
    if model is None:
        dialog.window.destroy()
        return results

    availability = model.availability
    results["phase10a_femm_available"] = bool(availability.is_available)
    results["phase10a_availability_probe_version"] = availability.probe_version
    # Before the FEA-only parameters are confirmed the case must be unbuildable.
    results["phase10a_blocked_before_parameters"] = (
        model.modelling is None and not model.can_generate_case
    )
    review_before = dialog.review_text.get("1.0", "end").strip()
    results["phase10a_missing_geometry_explained"] = "rotor back-iron" in review_before

    suggested_back_iron_m, suggested_span = model.suggested_values()
    dialog.back_iron_var.set(f"{suggested_back_iron_m * 1000.0:.3f}")
    dialog.coil_span_var.set(str(suggested_span))
    dialog._confirm_parameters()
    root.update()

    results["phase10a_case_generated"] = bool(model.can_generate_case)
    preview = model.preview()
    results["phase10a_supportability"] = preview.supportability.state.value
    results["phase10a_fidelity_tier"] = preview.supportability.fidelity_tier
    results["phase10a_case_id"] = preview.case.case_id if preview.case else None
    review_after = dialog.review_text.get("1.0", "end")
    results["phase10a_review_states_tier"] = "FEA_TIER_3" in review_after
    results["phase10a_review_states_approximations"] = "近似与已知遗漏" in review_after
    results["phase10a_review_states_no_convergence_claim"] = "不作收敛声明" in review_after
    # Phase 10B: only no-load back-EMF has been validated against a real solver.
    # The screen must say so for the other two targets rather than implying
    # they carry the same standing.
    results["phase10b_ke_marked_validated"] = (
        "Phase 10B" in dialog.target_status_var.get()
    )
    model.set_target(FEAValidationTarget.AVERAGE_TORQUE)
    dialog.refresh()
    root.update()
    results["phase10b_torque_marked_not_validated"] = (
        "NOT_YET_VALIDATED" in dialog.target_status_var.get()
    )
    model.set_target(FEAValidationTarget.COGGING_TORQUE)
    dialog.refresh()
    root.update()
    results["phase10b_cogging_marked_not_validated"] = (
        "NOT_YET_VALIDATED" in dialog.target_status_var.get()
    )
    model.set_target(FEAValidationTarget.NO_LOAD_BACK_EMF)
    dialog.refresh()
    root.update()

    # The run button must track real solver availability, with no fake result.
    run_state = str(dialog.run_button.cget("state"))
    results["phase10a_run_button_matches_availability"] = (
        (run_state == "normal") if availability.is_available else (run_state == "disabled")
    )
    results["phase10a_unavailable_message_shown"] = (
        availability.is_available
        or "未检测到 FEMM" in dialog.solver_status_var.get()
    )
    results["phase10a_no_fake_results_shown"] = not model.has_results

    # Phase 10E: the engineering diagnostics tab must exist, must render, and
    # with no solver run must say so rather than showing an empty comparison.
    from motor_calculator.fea.diagnostics import CALIBRATION_STATUS, EvidenceLabel

    tab_labels = tuple(
        str(dialog.tabs.tab(index, "text")) for index in range(dialog.tabs.index("end"))
    )
    results["phase10e_diagnostics_tab_present"] = "工程诊断" in tab_labels
    diagnostics_rendered = dialog.diagnostics_text.get("1.0", "end")
    results["phase10e_diagnostics_rendered"] = len(diagnostics_rendered.strip()) > 0
    results["phase10e_calibration_status_shown"] = CALIBRATION_STATUS in diagnostics_rendered
    results["phase10e_no_corrected_analytical_value"] = (
        "已修正" not in diagnostics_rendered and "修正后" not in diagnostics_rendered
    )
    diagnostics = model.validation_diagnostics()
    results["phase10e_diagnostics_unavailable_without_a_run"] = not diagnostics.available
    results["phase10e_evidence_type"] = diagnostics.evidence_type
    results["phase10e_calibration_status"] = diagnostics.calibration_status
    results["phase10e_numerical_fea_is_not_affirmative"] = (
        EvidenceLabel.NUMERICAL_FEA not in EvidenceLabel.AFFIRMATIVE
    )

    # Phase 10F: a back-EMF run must not display torque or cogging rows. An
    # empty table would read as "measured and found to be nothing".
    results["phase10f_no_torque_rows_on_a_back_emf_target"] = not diagnostics.torque
    results["phase10f_no_cogging_rows_on_a_back_emf_target"] = not diagnostics.cogging
    results["phase10f_torque_section_declared"] = "转矩验证" in dict(diagnostics.sections)
    results["phase10f_cogging_section_declared"] = "齿槽转矩" in dict(diagnostics.sections)
    # Phase 10G: the winding engineering view must open from the analysis menu,
    # render, and label every value with where it came from.
    from motor_calculator.winding.slot_fill import Provenance

    winding_dialog = app._open_winding_engineering()
    root.update()
    results["phase10g_winding_dialog_opened"] = bool(winding_dialog.window.winfo_exists())
    results["phase10g_winding_dialog_fits_screen"] = _window_fits_screen(winding_dialog.window)
    sections, winding_warnings, winding_notes = winding_dialog.build_sections()
    section_titles = [title for title, _rows in sections]
    results["phase10g_winding_sections"] = section_titles
    results["phase10g_winding_factor_section_present"] = "绕组系数" in section_titles
    rendered_winding = winding_dialog.text.get("1.0", "end")
    results["phase10g_winding_rendered"] = len(rendered_winding.strip()) > 0
    every_row = [row for _title, rows in sections for row in rows]
    results["phase10g_every_row_has_provenance"] = all(
        row.provenance is not None for row in every_row
    )
    # Either the slot utilisation is computed, or the panel says why it is not.
    # Never neither, and never both: a slotless machine must not be shown an
    # invented slot fill, and a slotted one must not silently lose it.
    has_slot_section = "槽利用率" in section_titles
    declined_for_slotless = any("无槽" in message for message in winding_warnings)
    results["phase10g_slot_fill_present_or_explained"] = (
        has_slot_section != declined_for_slotless
    )
    results["phase10g_slot_fill_computed"] = has_slot_section
    results["phase10g_slot_fill_declined_for_slotless"] = declined_for_slotless
    results["phase10g_assumptions_are_labelled"] = any(
        row.provenance == Provenance.ENGINEERING_ASSUMPTION for row in every_row
    ) or not any(title == "槽利用率" for title in section_titles)
    # Phase 10H: authority mode must be explicit, switchable, and never silent.
    from motor_calculator.winding.authority import AUTHORITY_LABELS_ZH, WindingAuthority

    results["phase10h_authority_control_present"] = hasattr(winding_dialog, "authority_combo")
    results["phase10h_default_authority"] = winding_dialog.selected_authority().value
    winding_dialog.authority_var.set(AUTHORITY_LABELS_ZH[WindingAuthority.AUTO_FROM_GEOMETRY])
    winding_dialog._on_authority_changed()
    root.update()
    auto_state = winding_dialog._production
    results["phase10h_auto_authority"] = auto_state.authority.value
    results["phase10h_auto_uses_geometry"] = (
        auto_state.value is not None
        and auto_state.geometry_value is not None
        and abs(auto_state.value - auto_state.geometry_value) < 1e-12
    )
    results["phase10h_auto_disables_manual_entry"] = (
        str(winding_dialog.manual_kw_entry.cget("state")) == "disabled"
    )
    results["phase10h_switch_warns"] = "重新计算" in winding_dialog.authority_status_var.get()
    winding_dialog.authority_var.set(AUTHORITY_LABELS_ZH[WindingAuthority.MANUAL_OVERRIDE])
    winding_dialog._on_authority_changed()
    root.update()
    results["phase10h_manual_enables_entry"] = (
        str(winding_dialog.manual_kw_entry.cget("state")) == "normal"
    )
    results["phase10h_manual_authority"] = winding_dialog._production.authority.value
    results["phase10h_production_never_meshed"] = (
        winding_dialog._production.provenance != "MESHED_GEOMETRY_FEA_DIAGNOSTIC_ONLY"
    )
    winding_dialog.window.destroy()

    results["phase10f_new_labels_are_not_affirmative"] = all(
        label not in EvidenceLabel.AFFIRMATIVE
        for label in (
            EvidenceLabel.NOT_EXPERIMENTALLY_VALIDATED,
            EvidenceLabel.EMPIRICAL_INPUT,
            EvidenceLabel.NO_ANALYTICAL_MODEL,
            EvidenceLabel.MORE_VALIDATION_REQUIRED,
            EvidenceLabel.NOT_AN_INDEPENDENT_PREDICTION,
        )
    )
    results["phase10a_no_fea_curves_without_data"] = (
        model.has_real_fea_data is False and not model.has_results
    )

    # Script generation must work with no solver installed.
    script_dir = output.parent / "phase10a_scripts"
    scripts = model.export_scripts(script_dir)
    results["phase10a_scripts_generated"] = len(scripts)
    results["phase10a_scripts_need_no_solver"] = bool(scripts) and not availability.is_available

    bundle_dir = output.parent / "phase10a_export"
    written = model.export_results(bundle_dir)
    results["phase10a_case_exported"] = [path.name for path in written] == ["fea_case.json"]

    # Switching target must re-derive the sampling plan, not reuse the old one.
    model.set_target(FEAValidationTarget.COGGING_TORQUE)
    cogging_case = model.preview().case
    results["phase10a_cogging_span_is_cogging_period"] = (
        cogging_case is not None
        and cogging_case.operating_point.rotor_angle_span_mech_deg
        < preview.case.operating_point.rotor_angle_span_mech_deg
    )
    results["phase10a_cogging_zero_current"] = (
        cogging_case is not None and cogging_case.operating_point.phase_current_rms_a == 0.0
    )

    dialog.window.destroy()
    root.update()
    return results


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
        # RC2 first-launch policy: the application must open on the audited
        # manufacturability starting example, not on a design that trips every
        # feasibility gate before the user has changed anything.
        from motor_calculator.validation.design_feasibility import (
            FeasibilitySeverity,
            evaluate_design_feasibility,
        )

        first_launch_params = app._get_params()
        first_launch_result = main_window_module.LegacyGuiMotorModelBridge(
            first_launch_params
        ).run_full_analysis()
        first_launch_assessment = evaluate_design_feasibility(
            first_launch_params, first_launch_result
        )
        payload["rc2_first_launch_preset_id"] = app._last_preset_id
        # Phase 9C: startup must now open on the corrected-basis v2 example and
        # the authoritative voltage must be the corrected one.
        # Phase 10H.1: the startup example is now v3, which declares
        # AUTO_FROM_GEOMETRY. v2 stays reproducible and is checked separately.
        payload["phase10h1_startup_preset_id"] = app._last_preset_id
        payload["phase10h1_startup_is_v3"] = (
            app._last_preset_id == "design.manufacturability_start.v3"
        )
        payload["phase10h1_startup_authority"] = app._selected_winding_factor_mode().value
        _startup_resolution = app._latest_winding_factor_resolution()
        payload["phase10h1_startup_kw"] = (
            None if _startup_resolution is None else _startup_resolution.value
        )
        payload["phase10h1_startup_kw_is_geometry"] = (
            _startup_resolution is not None
            and abs(float(_startup_resolution.value) - 0.8660254037844386) < 1e-9
        )
        payload["phase10h1_startup_kw_is_not_legacy_manual"] = (
            _startup_resolution is not None
            and abs(float(_startup_resolution.value) - 0.93) > 1e-6
        )
        payload["rc3_startup_preset_is_v2"] = (
            app._last_preset_id == "design.manufacturability_start.v2"
        )
        payload["rc3_corrected_voltage_v"] = (
            first_launch_result.performance.required_voltage_line_rms_v
        )
        payload["rc3_legacy_voltage_v"] = float(
            first_launch_result.performance.legacy_required_voltage_v
        )
        payload["rc3_voltage_authority"] = first_launch_result.performance.voltage_authority
        payload["rc3_corrected_margin_percent"] = first_launch_assessment.voltage_margin_percent
        payload["rc3_legacy_margin_percent"] = (
            first_launch_assessment.legacy_voltage_margin_percent
        )
        payload["rc3_voltage_provenance"] = first_launch_assessment.voltage_model_provenance
        # Phase 10H.1 moved the startup example from v2 to v3, which declares
        # AUTO_FROM_GEOMETRY. The guard now protects the CURRENT startup preset;
        # v2 is not abandoned, it is checked for reproducibility below.
        if not payload["phase10h1_startup_is_v3"]:
            raise RuntimeError(
                "startup must use design.manufacturability_start.v3; "
                f"got {app._last_preset_id!r}"
            )
        if not payload["phase10h1_startup_kw_is_geometry"]:
            raise RuntimeError(
                "the v3 startup example must resolve its winding factor from geometry"
            )
        if payload["rc3_voltage_authority"] != "CORRECTED_SAME_BASIS_PMSM":
            raise RuntimeError("RC3 voltage authority must be the corrected same-basis path")
        payload["rc2_first_launch_no_severe"] = not any(
            issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK
            for issue in first_launch_assessment.issues
        )
        payload["rc2_first_launch_no_error"] = not first_launch_assessment.has_error
        payload["rc2_first_launch_voltage_margin"] = (
            first_launch_assessment.voltage_margin_percent
        )
        payload["rc2_first_launch_slot_occupancy"] = first_launch_assessment.slot_fill_factor
        payload["rc2_first_launch_current_density"] = (
            first_launch_assessment.current_density_a_per_mm2
        )
        if not (payload["rc2_first_launch_no_severe"] and payload["rc2_first_launch_no_error"]):
            raise RuntimeError(
                "RC2 first-launch state must not present a severely infeasible design"
            )

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
        phase8h_results = _exercise_phase8h_dashboard(root, app, output)
        if not all(
            phase8h_results[name]
            for name in (
                "phase8h_dashboard_tab_present",
                "phase8h_dashboard_data_present",
                "phase8h_dashboard_no_severe",
                "phase8h_dashboard_no_warning",
                "phase8h_static_thermal_explicit",
                "phase8h_dynamic_not_run_explicit",
                "phase8h_uncertainty_not_run_explicit",
                "phase8h_sweep_ran",
                "phase8h_torque_curve_available",
                "phase8h_power_curve_available",
                "phase8h_voltage_margin_curve_available",
                "phase8h_figure_exported",
                "phase8h_csv_exported",
                "phase8h_dashboard_fits_window",
                "phase8h_cards_fit_window",
            )
        ):
            raise RuntimeError("Phase 8H dashboard GUI smoke did not pass every gate")
        payload.update(phase8h_results)
        phase8i_results = _exercise_phase8i_analysis(root, app, output)
        payload.update(phase8i_results)
        if not all(
            phase8i_results[name]
            for name in (
                "phase8i_analysis_menu_present",
                "phase8i_dynamic_ran",
                "phase8i_dynamic_voltage_series",
                "phase8i_uncertainty_ran",
                "phase8i_uncertainty_dashboard_updated",
                "phase8i_sensitivity_ran",
                "phase8i_analysis_window_fits_screen",
            )
        ):
            raise RuntimeError("Phase 8I analysis GUI smoke did not pass every gate")
        rc3_results = _exercise_rc3_voltage_authority(root, app)
        payload.update(rc3_results)
        if not all(
            rc3_results[name]
            for name in (
                "rc3_dashboard_uses_corrected_voltage",
                "rc3_dashboard_legacy_group_present",
                "rc3_report_shows_corrected_voltage",
                "rc3_report_marks_legacy_as_compatibility",
                "rc3_sweep_uses_corrected_voltage",
                "rc3_sweep_legacy_curve_hidden_by_default",
                "rc3_export_uses_authoritative_names",
                "rc3_bad_design_rejected_on_corrected_basis",
            )
        ):
            raise RuntimeError("RC3 voltage authority GUI smoke did not pass every gate")
        rc2_results = _exercise_rc2_winding_factor_and_occupancy(root, app)
        payload.update(rc2_results)
        if not all(
            rc2_results[name]
            for name in (
                "rc2_manual_matches_input",
                "rc2_manual_label_visible",
                "rc2_report_shows_occupancy",
                "rc2_report_shows_same_basis_voltage",
                "rc2_report_shows_winding_factor",
                "rc2_summary_caption_present",
                "rc2_auto_without_span_preserves_manual",
                "rc2_auto_used_in_params",
                "rc2_auto_report_shows_kd",
                "rc2_auto_report_shows_kp",
                "rc2_auto_report_shows_ks",
                "rc2_auto_label_visible",
                "rc2_auto_breakdown_present",
                "rc2_switch_back_restores_manual",
                "rc2_provenance_states_distinct",
            )
        ):
            raise RuntimeError("RC2 winding-factor / slot-occupancy GUI smoke did not pass every gate")
        phase10a_results = _exercise_phase10a_fea_validation(root, app, output)
        payload.update(phase10a_results)
        if not all(
            phase10a_results[name]
            for name in (
                "phase10a_menu_entry_present",
                "phase10a_dialog_opened",
                "phase10a_view_model_built",
                "phase10a_blocked_before_parameters",
                "phase10a_missing_geometry_explained",
                "phase10a_case_generated",
                "phase10a_review_states_tier",
                "phase10a_review_states_approximations",
                "phase10a_review_states_no_convergence_claim",
                "phase10a_run_button_matches_availability",
                "phase10a_unavailable_message_shown",
                "phase10a_no_fake_results_shown",
                "phase10a_no_fea_curves_without_data",
                "phase10a_scripts_generated",
                "phase10a_case_exported",
                "phase10a_cogging_span_is_cogging_period",
                "phase10a_cogging_zero_current",
                "phase10b_ke_marked_validated",
                "phase10b_torque_marked_not_validated",
                "phase10b_cogging_marked_not_validated",
            )
        ):
            raise RuntimeError("Phase 10A FEA validation GUI smoke did not pass every gate")
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
                "project_result_snapshot_saved",
                "project_result_snapshot_current_on_open",
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
        phase11a_results = _exercise_phase11a_validation_data(root, app, output)
        payload.update(phase11a_results)
        phase12_results = _exercise_phase12_capability(root, app, output)
        payload.update(phase12_results)
        if not all(
            phase12_results[name]
            for name in (
                "phase12_menu_entry_present",
                "phase12_dialog_opened",
                "phase12_dialog_fits_screen",
                "phase12_solved",
                "phase12_base_speed_resolved",
                "phase12_evidence_is_model_only",
                "phase12_calibration_none",
                "phase12_spmsm_mtpa_id_is_zero",
                "phase12_torque_speed_tab_present",
                "phase12_dq_tab_present",
                "phase12_torque_speed_rendered",
                "phase12_dq_rendered",
                "phase12_summary_has_base_speed",
                "phase12_summary_has_regions",
                "phase12_summary_states_model_only",
                "phase12_provenance_shows_isotropic",
                "phase12_provenance_shows_psi_source",
                "phase12_inspector_renders",
                "phase12_inspector_shows_constraints",
                "phase12_inspector_deep_fw_renders",
                "phase12_field_weakening_active",
                "phase12_spwm_limit_lower",
                "phase12_spwm_base_speed_lower",
                "phase12_export_json",
                "phase12_export_csv",
                "phase12_export_no_experimental_claim",
                "phase12_export_declares_peak_basis",
                "phase12_settings_persisted",
                "phase12_no_derived_curves_persisted",
            )
        ):
            raise RuntimeError("Phase 12 capability GUI smoke did not pass every gate")
        if abs(payload["phase12_svpwm_advantage_ratio"] - 2.0 / 3.0**0.5) > 1e-9:
            raise RuntimeError(
                "Phase 12: SVPWM must exceed SPWM by exactly 2/sqrt(3); got "
                f"{payload['phase12_svpwm_advantage_ratio']}"
            )
        if not all(
            phase11a_results[name]
            for name in (
                "phase11a_new_project_is_auto",
                "phase11a_new_project_kw_is_geometry",
                "phase11a_new_project_declares_authority",
                "phase11a_dashboard_summary_present",
                "phase11a_dashboard_summary_rendered",
                "phase11a_dashboard_points_at_full_panel",
                "phase11a_dashboard_never_meshed",
                "phase11a_dashboard_matches_input_authority",
                "phase11a_menu_entry_present",
                "phase11a_dialog_opened",
                "phase11a_dialog_fits_screen",
                "phase11a_no_data_is_explicit",
                "phase11a_no_data_has_no_comparisons",
                "phase11a_no_data_no_affirmative_claim",
                "phase11a_no_data_text_shown",
                "phase11a_no_data_says_no_pass",
                "phase11a_dataset_list_empty",
                "phase11a_template_exported",
                "phase11a_csv_imported",
                "phase11a_import_had_no_errors",
                "phase11a_dataset_listed",
                "phase11a_dataset_hash_recorded",
                "phase11a_comparison_built",
                "phase11a_comparison_has_analytical",
                "phase11a_comparison_rendered",
                "phase11a_comparison_shows_machine_compatibility",
                "phase11a_comparison_shows_sample_count",
                "phase11a_other_machine_not_validated",
                "phase11a_same_machine_still_supported",
                "phase11a_report_exported",
                "phase11a_report_has_citation_block",
                "phase11a_report_marks_other_machine",
                "phase11a_report_validated_word_is_guarded",
                "phase11a_datasets_persisted",
                "phase11a_project_holds_reference_not_samples",
                "phase11a_datasets_restored",
                "phase11a_restored_metadata_intact",
                "phase11a_missing_file_is_reported",
                "phase11a_missing_file_keeps_metadata",
                "phase11a_session_restored_for_later_sections",
                "phase11b_public_reference_tab_present",
                "phase11b_no_data_is_clean",
                "phase11b_no_data_has_no_values",
                "phase11b_metadata_without_data",
                "phase11b_different_machine",
                "phase11b_afpm_not_validated",
                "phase11b_source_view_rendered",
                "phase11b_source_states_topology",
                "phase11b_source_states_licence",
                "phase11b_source_states_different_machine",
                "phase11b_all_views_render_without_data",
                "phase11b_parameter_origins_rendered",
                "phase11b_lambda_flag_rendered",
                "phase11b_project_construction_refused",
                "phase11b_refusal_names_topology",
                "phase11b_refusal_names_axial",
            )
        ):
            raise RuntimeError("Phase 11A validation-data GUI smoke did not pass every gate")
        if payload["phase11a_authority_before_new"] != "manual":
            raise RuntimeError(
                "Phase 11A: the File -> New check must start from MANUAL, otherwise "
                "an AUTO result proves nothing about the new-project path"
            )
        if payload["phase11a_imported_sample_count"] != 4:
            raise RuntimeError(
                "Phase 11A: the imported Ke dataset must keep all four speed points"
            )
        if payload["phase11a_comparison_evidence_label"] != "EXPERIMENTAL_MEASUREMENT":
            raise RuntimeError(
                "Phase 11A: a same-machine user experiment must carry the "
                "EXPERIMENTAL_MEASUREMENT label"
            )
        if payload["phase11a_comparison_calibration"] != "NONE":
            raise RuntimeError("Phase 11A: the calibration status must remain NONE")
        if payload.get("phase11b_local_dataset_present"):
            for name in (
                "phase11b_publication_reproduced",
                "phase11b_pipeline_validated",
                "phase11b_afpm_still_not_validated",
                "phase11b_ke_has_no_r_squared",
                "phase11b_view_shows_fundamental",
                "phase11b_view_shows_provenance",
                "phase11b_view_shows_afpm_disclaimer",
                "phase11b_cogging_view_shows_ambiguity",
            ):
                if not payload[name]:
                    raise RuntimeError(
                        f"Phase 11B public-reference GUI smoke gate failed: {name}"
                    )
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
                **phase8h_results,
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
