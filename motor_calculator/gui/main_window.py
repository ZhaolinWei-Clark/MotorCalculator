"""Legacy GUI wrapper that delegates all electromagnetic calculations to motor_core."""

from __future__ import annotations

import importlib.util
import logging
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict
from tkinter import filedialog, messagebox, simpledialog, ttk

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from motor_calculator.motor_core import (
    LegacyGuiMotorModelBridge,
    MotorCalculationError,
    MotorValidationError,
    parse_legacy_gui_params,
)
from motor_calculator.input_ux import (
    APPLICATION_DEFAULTS,
    BASIC_INPUT_FIELDS,
    INPUT_DEFINITIONS,
    DisplayUnitPreferences,
    canonical_to_display_inputs,
    convert_display_value,
    display_to_canonical_inputs,
    evaluate_input_guidance,
    format_engineering_value,
)
from motor_calculator.presets import apply_preset, default_preset_registry, preview_preset
from motor_calculator.project import (
    PROJECT_FILE_EXTENSION,
    CompatibilityStatus,
    ProjectDocument,
    ProjectManager,
    ProjectSerializationError,
    ProjectValidationError,
    RecentProjectStore,
    RecoveryCandidate,
    RecoveryManager,
    UnsavedChangesDecision,
    create_project_document,
    flatten_project_inputs,
    inspect_project_sources,
    missing_feedback_record_ids,
    project_inputs_hash,
    uncertainty_parameters_from_payload,
    utc_now_iso,
)

from .confidence_panel import ConfidencePanel
from .guided_input_panel import GuidedInputPanel, ToolTip
from .feedback_dialog import (
    FeedbackMetricOption,
    ValidationFeedbackDialog,
    format_feedback_submission_result,
)
from .recovery_dialog import RecoveryBrowserDialog
from .uncertainty_dialog import UncertaintyAssumptionDialog

from motor_calculator.validation.confidence_summary import (
    build_engineering_confidence_summary,
    build_unavailable_confidence_summary,
    export_confidence_summary,
    load_validation_summary_safely,
)
from motor_calculator.validation.feedback_aggregation import compare_feedback_to_uncertainty_envelope
from motor_calculator.validation.feedback_models import (
    FeedbackModelIdentity,
    FeedbackOperatingPoint,
    FeedbackSubmission,
    MetricSemantics,
)
from motor_calculator.validation.feedback_service import load_feedback_records, submit_feedback
from motor_calculator.validation.phase7i_uncertainty_report import run_phase7i_demonstration
from motor_calculator.validation.uncertainty_models import (
    ParameterUncertainty,
    UncertaintyKind,
    UncertaintySpecification,
    load_uncertainty_specification,
)
from motor_calculator.runtime import (
    bounded_window_size,
    check_runtime_health,
    create_runtime_directories,
    dpi_scaled_window_size,
    enable_windows_dpi_awareness,
    format_startup_failure,
    initialize_local_logging,
    resolve_runtime_paths,
    windows_work_area,
)
from motor_calculator.version import application_version_label


_RUNTIME_PATHS = resolve_runtime_paths()
_REPOSITORY_ROOT = _RUNTIME_PATHS.resource_root


def _load_legacy_module():
    legacy_path = _RUNTIME_PATHS.resource("motor_calculator", "PMDC_Calculator_claude204.py")
    spec = importlib.util.spec_from_file_location("legacy_motor_calculator_ui", legacy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 legacy GUI 文件: {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PMDCMotorModel = LegacyGuiMotorModelBridge
    return module


_LEGACY_MODULE = None
_REAL_APP_CLASS = None


def _get_legacy_module():
    global _LEGACY_MODULE
    if _LEGACY_MODULE is None:
        _LEGACY_MODULE = _load_legacy_module()
    return _LEGACY_MODULE


def _get_real_app_class():
    global _REAL_APP_CLASS
    if _REAL_APP_CLASS is None:
        legacy_module = _get_legacy_module()

        class _RealMotorCalculatorApp(MotorCalculatorAppMixin, legacy_module.MotorCalculatorApp):
            """Runtime subclass that keeps legacy GUI behavior with refactored parsing."""

        _REAL_APP_CLASS = _RealMotorCalculatorApp
    return _REAL_APP_CLASS


class MotorCalculatorAppMixin:
    """GUI subclass with strict input parsing and non-crashing error handling."""

    def __init__(self, root):
        super().__init__(root)
        self._runtime_paths = create_runtime_directories(_RUNTIME_PATHS)
        self._repository_root = _REPOSITORY_ROOT
        self._feedback_store = self._runtime_paths.feedback_store
        self.root.title(f"Motor Calculator {application_version_label()}")
        self._latest_accuracy_envelope = None
        self._engineering_confidence_summary = None
        self._user_uncertainty_parameters = None
        self._create_confidence_tab()
        self._initialize_guided_input_ux()
        self._initialize_project_support()

    def _initialize_guided_input_ux(self) -> None:
        self._display_unit_preferences = DisplayUnitPreferences()
        self._input_mode = "ADVANCED"
        self._preset_registry = default_preset_registry()
        self._last_preset_id: str | None = None
        self._last_preset_version: int | None = None
        self._guidance_after_id = None
        self._input_row_widgets: dict[str, tuple[tk.Widget, ...]] = {}
        self._input_unit_labels: dict[str, tk.Widget] = {}

        legacy_frame = self.input_frame.scrollable_frame
        for widget in legacy_frame.grid_slaves():
            widget.grid_configure(row=int(widget.grid_info()["row"]) + 1)
        self._index_legacy_input_widgets(legacy_frame)

        # The legacy selector silently changed Br; Phase 8D requires preview/apply.
        self.mag_combo.unbind("<<ComboboxSelected>>")
        self.mag_combo.configure(state="disabled")
        self._guided_input_panel = GuidedInputPanel(
            legacy_frame,
            self.vars,
            self._preset_registry,
            preferences=self._display_unit_preferences,
            on_mode_change=self._set_input_mode,
            on_unit_change=self._change_display_unit,
            on_apply_preset=self._apply_preset_by_id,
            on_preset_details=self._show_preset_details,
            on_reset_field=self._reset_input_field,
            on_reset_guided=self._reset_guided_fields,
            on_help=self._show_input_help,
        )
        self._guided_input_panel.frame.grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 8)
        )
        for name, entry in self.entries.items():
            if name in INPUT_DEFINITIONS:
                ToolTip(entry, INPUT_DEFINITIONS[name].tooltip)
        self._apply_input_mode_visibility()

    def _index_legacy_input_widgets(self, frame) -> None:
        variable_to_field = {str(variable): name for name, variable in self.vars.items()}
        variable_to_field[str(self.coreless_var)] = "coreless"
        row_to_field: dict[int, str] = {}
        for widget in frame.grid_slaves():
            field = None
            if "textvariable" in widget.keys():
                field = variable_to_field.get(str(widget.cget("textvariable")))
            if field is None and "variable" in widget.keys():
                field = variable_to_field.get(str(widget.cget("variable")))
            if field is not None:
                row_to_field[int(widget.grid_info()["row"])] = field
        for row, field in row_to_field.items():
            widgets = tuple(
                widget for widget in frame.grid_slaves()
                if int(widget.grid_info()["row"]) == row
            )
            self._input_row_widgets[field] = widgets
            for widget in widgets:
                if int(widget.grid_info().get("column", -1)) == 2:
                    self._input_unit_labels[field] = widget

    def _set_input_mode(self, mode: str) -> None:
        if mode not in {"BASIC", "ADVANCED"}:
            raise ValueError(f"Unsupported input mode: {mode}")
        if mode == self._input_mode:
            return
        self._input_mode = mode
        self._apply_input_mode_visibility()
        self._mark_ux_preference_changed()

    def _apply_input_mode_visibility(self) -> None:
        for field, widgets in self._input_row_widgets.items():
            visible = self._input_mode == "ADVANCED" or field in BASIC_INPUT_FIELDS
            for widget in widgets:
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()
        if hasattr(self, "_guided_input_panel"):
            self._guided_input_panel.set_mode(self._input_mode)

    @staticmethod
    def _field_quantity(field: str) -> str | None:
        length_fields = {
            "D_out", "D_in", "g_side", "D_stator_out", "D_stator_in", "h_stator",
            "h_coil", "h_yoke", "h_slot", "w_slot_top", "w_slot_bottom",
            "h_slot_opening", "w_slot_opening", "h_wedge", "h_mag", "w_magnet",
            "L_magnet", "d_wire",
        }
        if field in length_fields:
            return "length"
        if field == "n_rated":
            return "speed"
        if field == "Temp_coil":
            return "temperature"
        return None

    def _change_display_unit(self, quantity: str, new_unit: str) -> None:
        old_unit = getattr(self._display_unit_preferences, quantity)
        if old_unit == new_unit:
            return
        updated = replace(self._display_unit_preferences, **{quantity: new_unit})
        converted_values: dict[str, str] = {}
        try:
            for field, variable in self.vars.items():
                if self._field_quantity(field) == quantity:
                    value = convert_display_value(float(variable.get()), quantity, old_unit, new_unit)
                    converted_values[field] = format_engineering_value(value)
        except (TypeError, ValueError) as exc:
            self._guided_input_panel.set_preferences(self._display_unit_preferences)
            messagebox.showwarning(
                "Unit change not applied",
                f"Correct the current numeric input before changing units:\n{exc}",
                parent=self.root,
            )
            return
        suppress = getattr(self, "_project_suppress_dirty", True)
        self._project_suppress_dirty = True
        try:
            for field, displayed in converted_values.items():
                self.vars[field].set(displayed)
            self._display_unit_preferences = updated
            self._update_input_unit_labels()
            self._guided_input_panel.set_preferences(updated)
        finally:
            self._project_suppress_dirty = suppress
        self._mark_ux_preference_changed()
        self._schedule_input_guidance()

    def _update_input_unit_labels(self) -> None:
        units = {
            "length": self._display_unit_preferences.length,
            "speed": self._display_unit_preferences.speed,
            "temperature": "°C" if self._display_unit_preferences.temperature == "degC" else "K",
        }
        for field, label in self._input_unit_labels.items():
            quantity = self._field_quantity(field)
            if quantity is not None:
                label.configure(text=units[quantity])

    def _mark_ux_preference_changed(self) -> None:
        if not hasattr(self, "_project_manager") or self._project_suppress_dirty:
            return
        self._project_manager.mark_dirty()
        self._update_project_title()
        self._schedule_recovery_autosave()

    def _ui_preferences_payload(self) -> dict[str, str | int | None]:
        return {
            "input_mode": self._input_mode,
            "length_unit": self._display_unit_preferences.length,
            "speed_unit": self._display_unit_preferences.speed,
            "temperature_unit": self._display_unit_preferences.temperature,
            "angle_unit": self._display_unit_preferences.angle,
            "preset_id": self._last_preset_id,
            "preset_version": self._last_preset_version,
        }

    def _restore_ui_preferences(self, preferences) -> None:
        try:
            restored = DisplayUnitPreferences(
                length=str(preferences.get("length_unit", "mm")),
                speed=str(preferences.get("speed_unit", "rpm")),
                temperature=str(preferences.get("temperature_unit", "degC")),
                angle=str(preferences.get("angle_unit", "degree")),
            )
        except ValueError:
            restored = DisplayUnitPreferences()
        mode = str(preferences.get("input_mode", "ADVANCED"))
        self._display_unit_preferences = restored
        self._input_mode = mode if mode in {"BASIC", "ADVANCED"} else "ADVANCED"
        self._last_preset_id = preferences.get("preset_id")
        version = preferences.get("preset_version")
        self._last_preset_version = int(version) if version is not None else None
        self._update_input_unit_labels()
        self._guided_input_panel.set_preferences(restored)
        self._apply_input_mode_visibility()

    def _apply_preset_by_id(self, preset_id: str) -> bool:
        preset = self._preset_registry.get(preset_id)
        if not preset.available:
            messagebox.showwarning("Preset unavailable", preset.unavailable_reason, parent=self.root)
            return False
        try:
            current = self._get_params()
            changes = preview_preset(current, preset)
        except (MotorValidationError, TypeError, ValueError) as exc:
            messagebox.showerror(
                "Preset preview", f"Current inputs must be valid before preview:\n{exc}", parent=self.root
            )
            return False
        if not changes:
            messagebox.showinfo("Preset preview", "No input value would change.", parent=self.root)
            return True
        lines = [
            f"{INPUT_DEFINITIONS[item.field_name].gui_label}: {item.current_value} -> {item.preset_value}"
            for item in changes
        ]
        detail = (
            f"{preset.display_name}\nEvidence: {preset.evidence_kind.value}\n"
            f"Provenance: {preset.provenance}\nAssumptions: {'; '.join(preset.assumptions)}\n\n"
            + "\n".join(lines)
            + "\n\nApply only these fields?"
        )
        if not messagebox.askokcancel("Preset preview", detail, parent=self.root):
            return False
        updated = apply_preset(current, preset)
        displayed = canonical_to_display_inputs(updated, self._display_unit_preferences)
        self._project_suppress_dirty = True
        try:
            for change in changes:
                value = displayed[change.field_name]
                if change.field_name == "coreless":
                    self.coreless_var.set(bool(value))
                else:
                    self.vars[change.field_name].set(
                        format_engineering_value(value) if isinstance(value, float) else str(value)
                    )
            self._last_preset_id = preset.preset_id
            self._last_preset_version = preset.version
        finally:
            self._project_suppress_dirty = False
        self._mark_ux_preference_changed()
        self._guided_input_panel.refresh_all()
        self._schedule_input_guidance()
        return True

    def _show_preset_details(self, preset_id: str) -> None:
        preset = self._preset_registry.get(preset_id)
        values = ", ".join(f"{name}={value}" for name, value in preset.values.items()) or "None"
        messagebox.showinfo(
            "Preset details",
            f"{preset.display_name}\nAvailable: {preset.available}\nValues: {values}\n"
            f"Provenance: {preset.provenance}\nAssumptions: {'; '.join(preset.assumptions) or 'None'}\n"
            f"Notes: {'; '.join(preset.notes) or 'None'}",
            parent=self.root,
        )

    def _reset_input_field(self, field: str) -> None:
        value = canonical_to_display_inputs(
            {field: APPLICATION_DEFAULTS[field]}, self._display_unit_preferences
        )[field]
        variable = self.coreless_var if field == "coreless" else self.vars[field]
        if field == "coreless":
            variable.set(bool(value))
        else:
            variable.set(format_engineering_value(value) if isinstance(value, float) else str(value))

    def _reset_guided_fields(self) -> None:
        if messagebox.askokcancel(
            "Reset quick fields",
            "Reset air gap, speed, winding factor and pole pairs to application defaults?",
            parent=self.root,
        ):
            for field in ("g_side", "n_rated", "k_w", "p"):
                self._reset_input_field(field)

    def reset_defaults(self):
        if not messagebox.askokcancel(
            "Reset all inputs", "Restore all 41 inputs to the frozen application defaults?", parent=self.root
        ):
            return False
        displayed = canonical_to_display_inputs(APPLICATION_DEFAULTS, self._display_unit_preferences)
        self._project_suppress_dirty = True
        try:
            for field, value in displayed.items():
                if field == "coreless":
                    self.coreless_var.set(bool(value))
                else:
                    self.vars[field].set(
                        format_engineering_value(value) if isinstance(value, float) else str(value)
                    )
            self._last_preset_id = None
            self._last_preset_version = None
        finally:
            self._project_suppress_dirty = False
        self._mark_ux_preference_changed()
        self._guided_input_panel.refresh_all()
        self._schedule_input_guidance()
        messagebox.showinfo(
            "Reset complete", "All inputs were restored to application defaults.", parent=self.root
        )
        return True

    def _show_input_help(self) -> None:
        messagebox.showinfo(
            "Engineering input help",
            "Presets are transparent starting points, not optimized designs.\n\n"
            "Br depends on supplier and temperature. Winding factor represents pitch/distribution. "
            "Air gap is entered per side for the existing SSDR model. Pole pairs are half the total pole count.\n\n"
            "Ke/Kt, RMS/peak and phase/line semantics depend on the selected PMSM/BLDC waveform. "
            "DSSR cannot be represented by the current production schema. Slider ranges are quick-adjust "
            "ranges only; exact values outside them are preserved.",
            parent=self.root,
        )

    def _schedule_input_guidance(self) -> None:
        if not hasattr(self, "_project_manager"):
            return
        if self._guidance_after_id is not None:
            self.root.after_cancel(self._guidance_after_id)
        self._guidance_after_id = self.root.after(250, self._refresh_input_guidance)

    def _refresh_input_guidance(self) -> None:
        self._guidance_after_id = None
        try:
            issues = evaluate_input_guidance(self._get_params())
            text = " | ".join(
                f"{item.severity.value}/{item.level.value}: {item.message}" for item in issues
            )
        except Exception as exc:
            text = f"ERROR/INVALID: {exc}"
        self._guided_input_panel.set_guidance(text)

    def _initialize_project_support(self) -> None:
        self._project_suppress_dirty = True
        self._project_notes = ""
        self._project_validation_record_ids: list[str] = []
        self._project_default_inputs = dict(self._get_params())
        recent_store = RecentProjectStore(self._runtime_paths.user_data_dir / "recent_projects.json")
        self._project_manager = ProjectManager(recent_store)
        self._recovery_manager = RecoveryManager(self._runtime_paths.user_data_dir / "recovery")
        initial_recovery_scan = self._recovery_manager.scan()
        recovery_startup_warning = None
        try:
            self._recovery_manager.begin_session()
        except (OSError, ProjectSerializationError, ValueError) as exc:
            recovery_startup_warning = f"Recovery protection is unavailable: {exc}"
        self._recovery_after_id = None
        self._recovery_candidates = initial_recovery_scan.candidates
        self._recovery_status_var = tk.StringVar(
            value=recovery_startup_warning or "Recovery protection active"
        )
        document = create_project_document("Untitled", self._project_default_inputs)
        self._project_manager.new_project(document)
        self._create_project_menu()
        self._project_traces = [
            variable.trace_add("write", self._on_project_input_changed)
            for variable in (*self.vars.values(), self.coreless_var)
        ]
        self.root.protocol("WM_DELETE_WINDOW", self._request_exit)
        self._recovery_status_label = ttk.Label(
            self.root, textvariable=self._recovery_status_var, anchor=tk.E, padding=(8, 2)
        )
        packed_children = self.root.pack_slaves()
        pack_options = {"side": tk.BOTTOM, "fill": tk.X}
        if packed_children:
            pack_options["before"] = packed_children[0]
        self._recovery_status_label.pack(**pack_options)
        self._project_suppress_dirty = False
        self._update_project_title()
        if initial_recovery_scan.warnings:
            logging.getLogger(__name__).warning("; ".join(initial_recovery_scan.warnings))
        if recovery_startup_warning:
            logging.getLogger(__name__).warning(recovery_startup_warning)
        elif self._recovery_candidates:
            self._recovery_status_var.set(
                f"Recovered work available ({len(self._recovery_candidates)}); use File > Recover Unsaved Work"
            )

    def _create_project_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="New Project", accelerator="Ctrl+N", command=self._new_project)
        file_menu.add_command(label="Open Project...", accelerator="Ctrl+O", command=self._open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._save_project)
        file_menu.add_command(label="Save As...", command=self._save_project_as)
        self._recent_projects_menu = tk.Menu(file_menu, tearoff=False, postcommand=self._refresh_recent_projects_menu)
        file_menu.add_cascade(label="Recent Projects", menu=self._recent_projects_menu)
        file_menu.add_command(label="Recover Unsaved Work...", command=self._recover_unsaved_work)
        file_menu.add_command(label="Project Notes...", command=self._edit_project_notes)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._request_exit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menu_bar)
        self._project_menu_bar = menu_bar
        self._project_file_menu = file_menu
        self.root.bind_all("<Control-n>", lambda _event: self._new_project())
        self.root.bind_all("<Control-o>", lambda _event: self._open_project())
        self.root.bind_all("<Control-s>", lambda _event: self._save_project())

    def _on_project_input_changed(self, *_args) -> None:
        if self._project_suppress_dirty:
            return
        self._project_manager.mark_dirty()
        self._update_project_title()
        self._schedule_recovery_autosave()
        self._schedule_input_guidance()

    def _schedule_recovery_autosave(self) -> None:
        if self._recovery_after_id is not None:
            self.root.after_cancel(self._recovery_after_id)
        delay_ms = self._recovery_manager.autosave_interval_seconds * 1000
        self._recovery_after_id = self.root.after(delay_ms, self._perform_recovery_autosave)
        self._recovery_status_var.set("Unsaved changes; recovery snapshot scheduled")

    def _perform_recovery_autosave(self) -> bool:
        self._recovery_after_id = None
        if not self._project_manager.is_dirty:
            self._recovery_status_var.set("Project saved; recovery protection active")
            return False
        try:
            document = self._build_project_document()
        except (ProjectValidationError, MotorValidationError, ValueError) as exc:
            self._recovery_status_var.set(f"Recovery waiting for valid inputs: {exc}")
            return False
        current = self._project_manager.current_project
        result = self._recovery_manager.try_write_recovery(
            document,
            original_project_path=self._project_manager.current_path,
            dirty=True,
            last_normal_save_timestamp=None if current is None else current.metadata.modified_at,
        )
        if not result.written:
            self._recovery_status_var.set(result.warning or "Recovery autosave unavailable")
            logging.getLogger(__name__).warning(result.warning)
            return False
        self._recovery_status_var.set(f"Recovery snapshot created {utc_now_iso()}")
        return True

    def _cleanup_project_recovery(self, project_uuid: str, *, saved_input_hash: str | None = None) -> None:
        try:
            self._recovery_manager.cleanup_project(project_uuid, saved_input_hash=saved_input_hash)
        except OSError as exc:
            warning = f"Recovery cleanup could not be completed: {exc}"
            self._recovery_status_var.set(warning)
            logging.getLogger(__name__).warning(warning)

    def _update_project_title(self) -> None:
        document = self._project_manager.current_project
        if document is None:
            display_name = "Untitled"
        elif self._project_manager.current_path is not None:
            display_name = self._project_manager.current_path.name
        else:
            display_name = document.metadata.project_name
        dirty = " *" if self._project_manager.is_dirty else ""
        self.root.title(f"Motor Calculator {application_version_label()} - {display_name}{dirty}")

    def _build_project_document(self, *, project_name: str | None = None) -> ProjectDocument:
        current = self._project_manager.current_project
        name = project_name or (current.metadata.project_name if current else "Untitled")
        return create_project_document(
            name,
            self._get_params(),
            project_uuid=None if current is None else current.metadata.project_uuid,
            created_at=None if current is None else current.metadata.created_at,
            modified_at=utc_now_iso(),
            uncertainty_assumptions=self._user_uncertainty_parameters,
            ui_preferences=self._ui_preferences_payload(),
            notes=self._project_notes,
            validation_record_ids=self._project_validation_record_ids,
        )

    @staticmethod
    def _restore_uncertainty_assumptions(document: ProjectDocument) -> tuple[ParameterUncertainty, ...] | None:
        normalized = uncertainty_parameters_from_payload(document.uncertainty_assumptions)
        if not normalized:
            return None
        return tuple(
            ParameterUncertainty(
                parameter_name=str(item["parameter_name"]),
                nominal_value=float(item["nominal_value"]),
                unit=str(item["unit"]),
                uncertainty_kind=UncertaintyKind(str(item["uncertainty_kind"])),
                lower_bound=item["lower_bound"],
                upper_bound=item["upper_bound"],
                mean=item["mean"],
                standard_deviation=item["standard_deviation"],
                provenance=str(item["provenance"]),
                confidence=str(item["confidence"]),
                notes=tuple(str(note) for note in item["notes"]),
            )
            for item in normalized
        )

    def _clear_project_results(self) -> None:
        self.calc_results = None
        self.result_text.delete("1.0", tk.END)
        for tab, title in (
            (self.curves_tab, "Performance curves"),
            (self.emf_tab, "Back EMF"),
            (self.torque_tab, "Torque analysis"),
            (self.flux_tab, "Flux distribution"),
            (self.geo_tab, "Geometry"),
        ):
            self._set_chart_placeholder(tab, title, "Run the calculation to refresh this project result.")
        self._set_unavailable_current_summary()

    def _apply_project_document(self, document: ProjectDocument) -> None:
        restored = flatten_project_inputs(document.inputs)
        self._project_suppress_dirty = True
        try:
            self._restore_ui_preferences(document.ui_preferences)
            displayed = canonical_to_display_inputs(restored, self._display_unit_preferences)
            for name, value in displayed.items():
                if name == "coreless":
                    self.coreless_var.set(bool(value))
                else:
                    self.vars[name].set(
                        format_engineering_value(value) if isinstance(value, float) else str(value)
                    )
            self._user_uncertainty_parameters = self._restore_uncertainty_assumptions(document)
            self._project_notes = document.notes
            self._project_validation_record_ids = list(document.validation_record_ids)
            self._clear_project_results()
        finally:
            self._project_suppress_dirty = False
        self._project_manager.mark_clean(document)
        self._update_project_title()
        self._guided_input_panel.refresh_all()
        self._schedule_input_guidance()

    def _confirm_abandon_changes(self) -> bool:
        if not self._project_manager.is_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved project changes",
            "Save changes before continuing?",
            parent=self.root,
        )
        if answer is None:
            decision = UnsavedChangesDecision.CANCEL
        elif answer:
            decision = UnsavedChangesDecision.SAVE
        else:
            decision = UnsavedChangesDecision.DISCARD
        return self._project_manager.can_abandon(decision, save_callback=self._save_project)

    def _new_project(self) -> bool:
        previous = self._project_manager.current_project
        if not self._confirm_abandon_changes():
            return False
        if previous is not None:
            self._cleanup_project_recovery(previous.metadata.project_uuid)
        document = create_project_document("Untitled", self._project_default_inputs)
        self._project_manager.new_project(document)
        self._apply_project_document(document)
        return True

    def _open_project(self) -> bool:
        previous = self._project_manager.current_project
        if not self._confirm_abandon_changes():
            return False
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Open MotorCalculator project",
            filetypes=(("MotorCalculator project", f"*{PROJECT_FILE_EXTENSION}"), ("All files", "*.*")),
        )
        if not selected:
            return False
        opened = self._open_project_path(Path(selected), prompt_for_unsaved=False)
        if opened and previous is not None:
            self._cleanup_project_recovery(previous.metadata.project_uuid)
        return opened

    def _open_project_path(self, path: Path, *, prompt_for_unsaved: bool = True) -> bool:
        previous = self._project_manager.current_project if prompt_for_unsaved else None
        if prompt_for_unsaved and not self._confirm_abandon_changes():
            return False
        source_path = path
        sources = inspect_project_sources(path)
        report = sources.official
        if report.status is CompatibilityStatus.NEWER_SCHEMA_UNSUPPORTED:
            messagebox.showerror("Open project", report.message, parent=self.root)
            return False
        if report.status in {CompatibilityStatus.CORRUPT, CompatibilityStatus.INVALID}:
            if sources.backup is not None and sources.backup.status is CompatibilityStatus.COMPATIBLE:
                use_backup = messagebox.askyesno(
                    "Open project backup",
                    f"The official project is invalid or corrupt.\n\n{report.message}\n\nOpen its valid .bak copy without overwriting either file?",
                    parent=self.root,
                )
                if not use_backup:
                    return False
                source_path = sources.backup.path
            else:
                messagebox.showerror("Open project", report.message, parent=self.root)
                return False
        elif report.status is CompatibilityStatus.MIGRATION_AVAILABLE:
            if not messagebox.askokcancel(
                "Project migration",
                f"{report.message}. Open using the approved in-memory migration path?",
                parent=self.root,
            ):
                return False
        try:
            document = self._project_manager.open_project(source_path)
            self._apply_project_document(document)
        except ProjectSerializationError as exc:
            messagebox.showerror("Open project", str(exc), parent=self.root)
            return False
        try:
            available = [record.record_id for record in load_feedback_records(self._feedback_store)]
        except Exception:
            available = []
        missing = missing_feedback_record_ids(document, available)
        if missing:
            messagebox.showwarning(
                "Project validation references",
                f"{len(missing)} linked local validation record(s) are unavailable. The project inputs were loaded normally.",
                parent=self.root,
            )
        if previous is not None:
            self._cleanup_project_recovery(previous.metadata.project_uuid)
        return True

    def _save_project(self) -> bool:
        if self._project_manager.current_path is None:
            return self._save_project_as()
        return self._save_project_to_path(self._project_manager.current_path)

    def _save_project_as(self) -> bool:
        current_path = self._project_manager.current_path
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save MotorCalculator project",
            initialdir=str(current_path.parent if current_path else Path.home()),
            initialfile=current_path.name if current_path else f"Untitled{PROJECT_FILE_EXTENSION}",
            defaultextension=PROJECT_FILE_EXTENSION,
            filetypes=(("MotorCalculator project", f"*{PROJECT_FILE_EXTENSION}"),),
        )
        return False if not selected else self._save_project_to_path(Path(selected), save_as=True)

    def _save_project_to_path(self, path: Path, *, save_as: bool = False) -> bool:
        target = Path(path)
        if target.suffix.lower() != PROJECT_FILE_EXTENSION:
            target = target.with_name(target.name + PROJECT_FILE_EXTENSION)
        name = target.stem if save_as or self._project_manager.current_path is None else None
        try:
            document = self._build_project_document(project_name=name)
            self._project_manager.save_as(document, target)
        except (ProjectSerializationError, ProjectValidationError, MotorValidationError) as exc:
            messagebox.showerror("Save project", str(exc), parent=self.root)
            return False
        self._update_project_title()
        self._cleanup_project_recovery(
            document.metadata.project_uuid,
            saved_input_hash=project_inputs_hash(document.inputs),
        )
        self._recovery_status_var.set("Project saved; recovery protection active")
        return True

    def _refresh_recent_projects_menu(self) -> None:
        self._recent_projects_menu.delete(0, tk.END)
        entries = self._project_manager.recent_store.entries(existing_only=True)
        if not entries:
            self._recent_projects_menu.add_command(label="(No recent projects)", state=tk.DISABLED)
            return
        for entry in entries:
            self._recent_projects_menu.add_command(
                label=f"{entry.project_name} - {entry.path}",
                command=lambda path=entry.path: self._open_project_path(path),
            )

    def _edit_project_notes(self) -> None:
        edited = simpledialog.askstring(
            "Project Notes",
            "Plain-text engineering notes:",
            initialvalue=self._project_notes,
            parent=self.root,
        )
        if edited is not None and edited != self._project_notes:
            self._project_notes = edited
            self._project_manager.mark_dirty()
            self._update_project_title()
            self._schedule_recovery_autosave()

    def _recover_unsaved_work(self):
        scan = self._recovery_manager.scan()
        if scan.warnings:
            logging.getLogger(__name__).warning("; ".join(scan.warnings))
        self._recovery_candidates = scan.candidates
        if not scan.candidates:
            messagebox.showinfo("Recover Unsaved Work", "No meaningful recovery snapshots are available.", parent=self.root)
            return None
        return RecoveryBrowserDialog(
            self.root,
            scan.candidates,
            on_restore=self._restore_recovery_candidate,
            on_discard=self._discard_recovery_candidate,
        )

    def _restore_recovery_candidate(self, candidate: RecoveryCandidate) -> bool:
        if not self._confirm_abandon_changes():
            return False
        document = self._recovery_manager.restore(candidate)
        self._project_manager.new_project(document)
        self._apply_project_document(document)
        self._project_manager.mark_dirty()
        self._update_project_title()
        self._schedule_recovery_autosave()
        self._recovery_status_var.set("Recovered project is unsaved; use Save or Save As")
        return True

    def _discard_recovery_candidate(self, candidate: RecoveryCandidate) -> bool:
        try:
            self._recovery_manager.discard(candidate)
        except OSError as exc:
            messagebox.showerror("Discard recovery", str(exc), parent=self.root)
            return False
        self._recovery_status_var.set("Selected recovery snapshot discarded")
        return True

    def _request_exit(self) -> bool:
        if not self._confirm_abandon_changes():
            return False
        if self._recovery_after_id is not None:
            self.root.after_cancel(self._recovery_after_id)
            self._recovery_after_id = None
        current = self._project_manager.current_project
        if current is not None:
            self._cleanup_project_recovery(current.metadata.project_uuid)
        try:
            self._recovery_manager.mark_session_clean()
        except OSError as exc:
            logging.getLogger(__name__).warning("Clean-shutdown marker could not be written: %s", exc)
        self.root.destroy()
        return True

    def _create_confidence_tab(self) -> None:
        self.confidence_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.confidence_tab, text="Confidence & Validation")
        self.confidence_panel = ConfidencePanel(
            self.confidence_tab,
            on_estimate=self._estimate_controlled_reference_uncertainty,
            on_edit_assumptions=self._edit_uncertainty_assumptions,
            on_add_feedback=self._add_validation_feedback,
            on_export=self._export_confidence_summary,
        )
        self.confidence_panel.pack(fill=tk.BOTH, expand=True)
        self._set_unavailable_current_summary()

    def _load_local_validation_summary(self, *, metric_name: str | None = None, topology: str | None = None):
        return load_validation_summary_safely(
            self._feedback_store,
            metric_name=metric_name,
            topology=topology,
        )

    def _set_unavailable_current_summary(self) -> None:
        result = getattr(self, "calc_results", None)
        nominal = None if result is None else float(result.electrical.E_phase_rms)
        validation_summary, database_warning = self._load_local_validation_summary(
            topology="dual-rotor single-stator dual-air-gap AFPM"
        )
        reason = (
            "Uncertainty estimate not available for this result. Use the explicit controlled-reference action; "
            "its result is not an error bound for this legacy calculation."
        )
        if database_warning:
            reason += f" {database_warning}"
        summary = build_unavailable_confidence_summary(
            metric_name="back_emf_phase_rms_v",
            nominal_value=nominal,
            unit="V",
            validation_summary=validation_summary,
            reason=reason,
        )
        self._engineering_confidence_summary = summary
        self._latest_accuracy_envelope = None
        self.confidence_panel.set_summary(summary)

    def _controlled_uncertainty_specification(self) -> UncertaintySpecification | None:
        if self._user_uncertainty_parameters is None:
            return None
        base = load_uncertainty_specification(
            self._repository_root / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"
        )
        return replace(
            base,
            assumption_label="USER-SPECIFIED LOCAL CONTROLLED-REFERENCE ASSUMPTIONS",
            parameters=self._user_uncertainty_parameters,
            assumptions=base.assumptions + (
                "Phase 7K user-edited assumptions apply only to this local controlled-reference run.",
            ),
        )

    def _estimate_controlled_reference_uncertainty(self) -> None:
        try:
            result = run_phase7i_demonstration(
                self._repository_root,
                specification_override=self._controlled_uncertainty_specification(),
            )
            validation_summary, database_warning = self._load_local_validation_summary(
                metric_name=result.accuracy_envelope.metric_name,
                topology="SSDR controlled AFPM reference",
            )
            summary = build_engineering_confidence_summary(
                result.accuracy_envelope,
                validation_summary,
                source_label="CONTROLLED REFERENCE - not the current production calculation",
            )
            if database_warning:
                summary = replace(
                    summary,
                    warnings=summary.warnings + (database_warning,),
                )
        except Exception as exc:
            messagebox.showwarning(
                "Confidence & Validation",
                f"Uncertainty analysis is unavailable, but the main calculation remains usable.\n\n{exc}",
                parent=self.root,
            )
            return
        self._latest_accuracy_envelope = result.accuracy_envelope
        self._engineering_confidence_summary = summary
        self.confidence_panel.set_summary(summary)
        self.notebook.select(self.confidence_tab)

    def _edit_uncertainty_assumptions(self) -> None:
        try:
            if self._user_uncertainty_parameters is None:
                specification = load_uncertainty_specification(
                    self._repository_root / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"
                )
                parameters = specification.parameters
            else:
                parameters = self._user_uncertainty_parameters
            edited = UncertaintyAssumptionDialog(self.root, parameters).show()
        except Exception as exc:
            messagebox.showwarning("Uncertainty assumptions", str(exc), parent=self.root)
            return
        if edited is not None:
            self._user_uncertainty_parameters = edited
            self._project_manager.mark_dirty()
            self._update_project_title()
            self._schedule_recovery_autosave()
            messagebox.showinfo(
                "Uncertainty assumptions",
                "Local assumptions saved for the next explicit controlled-reference estimate.\nProduction defaults were not changed.",
                parent=self.root,
            )

    def _feedback_metric_options(self) -> dict[str, FeedbackMetricOption]:
        result = self.calc_results
        waveform = "sinusoidal" if str(self._get_params().get("waveform", "")).lower() in {"sinusoidal", "正弦波"} else "trapezoidal"
        return {
            "back_emf_phase_rms_v": FeedbackMetricOption(
                "back_emf_phase_rms_v", float(result.electrical.E_phase_rms), "V",
                MetricSemantics("phase", "rms", waveform, "not_applicable", "not_applicable"),
            ),
            "back_emf_line_rms_v": FeedbackMetricOption(
                "back_emf_line_rms_v", float(result.electrical.E_line_rms), "V",
                MetricSemantics("line", "rms", waveform, "not_applicable", "not_applicable"),
            ),
            "rated_torque_nm": FeedbackMetricOption(
                "rated_torque_nm", float(result.performance.T_rated), "Nm",
                MetricSemantics("motor", "average", "not_applicable", "shaft", "not_applicable"),
            ),
            "phase_resistance_ohm": FeedbackMetricOption(
                "phase_resistance_ohm", float(result.electrical.R_phase), "ohm",
                MetricSemantics("phase", "dc", "not_applicable", "not_applicable", "not_applicable"),
            ),
            "phase_inductance_h": FeedbackMetricOption(
                "phase_inductance_h", float(result.electrical.L_phase), "H",
                MetricSemantics("scalar_phase", "not_applicable", "not_applicable", "not_applicable", "not_applicable"),
            ),
            "efficiency_percent": FeedbackMetricOption(
                "efficiency_percent", float(result.performance.Efficiency), "%",
                MetricSemantics("system", "average", "not_applicable", "shaft_output", "not_applicable"),
            ),
        }

    def _add_validation_feedback(self) -> None:
        if not getattr(self, "calc_results", None):
            messagebox.showinfo("Validation feedback", "Run the calculator before adding a validation result.", parent=self.root)
            return
        options = self._feedback_metric_options()
        values = ValidationFeedbackDialog(
            self.root,
            options,
            default_speed=float(self._get_params()["n_rated"]),
        ).show()
        if values is None:
            return
        option = options[values.metric_name]
        params = dict(self._get_params())
        params.update({
            "topology": "dual-rotor single-stator dual-air-gap AFPM",
            "calculation_origin": "production_legacy_compatible_gui",
        })
        submission = FeedbackSubmission(
            metric_name=option.metric_name,
            predicted_value=option.predicted_value,
            reference_value=values.reference_value,
            predicted_unit=option.unit,
            reference_unit=values.reference_unit,
            predicted_semantics=option.semantics,
            reference_semantics=values.reference_semantics,
            operating_point=FeedbackOperatingPoint(
                speed_rpm=values.speed_rpm,
                current_a=values.current_a,
                voltage_v=values.voltage_v,
                temperature_c=values.temperature_c,
            ),
            evidence_type=values.evidence_type,
            model_identity=FeedbackModelIdentity(
                calculator_version="phase7k-gui",
                model_version=str(self.calc_results.metadata.get("模型版本", "legacy-compatible")),
                model_track="production_legacy_compatible",
                topology="dual-rotor single-stator dual-air-gap AFPM",
                software_version="phase7k",
                git_commit=None,
                model_family="legacy_afpm_calculator",
                calculation_mode="static_gui",
                origin="production",
                formula_version="legacy-frozen",
            ),
            full_input_snapshot=params,
            source_name=values.source_name,
            source_reference=values.source_reference,
            notes=values.notes,
        )
        try:
            result = submit_feedback(submission, self._feedback_store)
            envelope_comparison = (
                None
                if self._latest_accuracy_envelope is None
                else compare_feedback_to_uncertainty_envelope(result.record, self._latest_accuracy_envelope)
            )
            display = format_feedback_submission_result(result.record, envelope_comparison)
        except Exception as exc:
            messagebox.showwarning(
                "Validation feedback",
                f"The local evidence database could not be updated. The main calculation is unchanged.\n\n{exc}",
                parent=self.root,
            )
            return
        messagebox.showinfo("Validation feedback saved locally", display, parent=self.root)
        if result.record.record_id not in self._project_validation_record_ids:
            self._project_validation_record_ids.append(result.record.record_id)
            self._project_manager.mark_dirty()
            self._update_project_title()
            self._schedule_recovery_autosave()
        self._set_unavailable_current_summary()

    def _export_confidence_summary(self) -> None:
        summary = self._engineering_confidence_summary
        if summary is None:
            messagebox.showinfo("Confidence export", "No confidence summary is available.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export confidence summary locally",
            initialdir=str(self._runtime_paths.export_dir),
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("Text", "*.txt")),
        )
        if not path:
            return
        format_name = "json" if Path(path).suffix.lower() == ".json" else "text"
        try:
            export_confidence_summary(summary, Path(path), format_name=format_name)
        except Exception as exc:
            messagebox.showerror("Confidence export", str(exc), parent=self.root)
            return
        messagebox.showinfo("Confidence export", "Summary exported locally. No data was uploaded.", parent=self.root)

    def _collect_raw_params(self) -> Dict[str, Any]:
        raw: Dict[str, Any] = {}
        for key, var in self.vars.items():
            raw[key] = var.get()
        raw["coreless"] = self.coreless_var.get()
        return display_to_canonical_inputs(raw, self._display_unit_preferences)

    def _get_params(self) -> Dict[str, Any]:
        return parse_legacy_gui_params(self._collect_raw_params())

    def _inject_phase3a_report_summary(self) -> None:
        if not getattr(self, "calc_results", None):
            return
        metadata = self.calc_results.metadata
        summary_lines = [
            "",
            "Phase 3A Electrical Semantics",
            f"控制模式: {metadata.get('控制模式', 'N/A')}",
            f"legacy控制模型: {metadata.get('legacy控制模型', 'N/A')}",
            f"机械转速: {metadata.get('机械转速_rpm', 'N/A')} rpm",
            f"电频率: {metadata.get('电频率_Hz', 'N/A')} Hz",
            "-" * 70,
            "",
        ]
        self.result_text.insert("1.0", "\n".join(summary_lines))

    def run_analysis(self):
        try:
            params = self._get_params()
            model = LegacyGuiMotorModelBridge(params)
            self.calc_results = model.run_full_analysis()
            self.calculation_history.append(
                {
                    "timestamp": _get_legacy_module().datetime.now().isoformat(),
                    "params": params,
                    "results": self.calc_results.to_dict(),
                }
            )
            self._display_report()
            self._inject_phase3a_report_summary()
            self._plot_performance_curves()
            self._plot_back_emf()
            self._plot_torque()
            self._plot_flux_distribution()
            self._draw_geometry()
            self._set_unavailable_current_summary()
            self.notebook.select(0)
            messagebox.showinfo("分析完成", "电磁分析计算已完成。\n请查看各选项卡中的结果。")
        except (MotorValidationError, MotorCalculationError) as exc:
            messagebox.showerror("分析错误", str(exc))
        except Exception as exc:
            messagebox.showerror("分析错误", f"计算失败:\n{exc}")


class MotorCalculatorApp:
    """Lazy wrapper so GUI modules can import without loading optional chart dependencies."""

    def __new__(cls, *args, **kwargs):
        real_app_class = _get_real_app_class()
        return real_app_class(*args, **kwargs)


def _create_root_or_exit(runtime_paths, logger):
    try:
        return tk.Tk()
    except tk.TclError as exc:
        logger.exception("Tkinter runtime initialization failed")
        health = check_runtime_health(runtime_paths)
        raise SystemExit(format_startup_failure(exc, runtime_paths, report=health)) from None


def _smoke_output_argument(arguments: list[str]) -> Path | None:
    if "--smoke-output" not in arguments:
        return None
    index = arguments.index("--smoke-output")
    if index + 1 >= len(arguments) or not arguments[index + 1].strip():
        raise SystemExit("--smoke-output requires a JSON destination path")
    return Path(arguments[index + 1])


def main():
    user_data_error = None
    try:
        runtime_paths = create_runtime_directories(_RUNTIME_PATHS)
        logger = initialize_local_logging(runtime_paths)
    except OSError as exc:
        user_data_error = exc
        runtime_paths = _RUNTIME_PATHS
        logger = logging.getLogger("motor_calculator.startup")
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
    dpi_status = enable_windows_dpi_awareness()
    logger.info("Application startup requested; mode=%s dpi=%s", runtime_paths.mode, dpi_status)
    root = _create_root_or_exit(runtime_paths, logger)
    if user_data_error is not None:
        root.destroy()
        raise SystemExit(
            "Motor Calculator could not initialize its writable user-data directory.\n"
            f"Target: {runtime_paths.user_data_dir}\n"
            f"Reason: {user_data_error}\n"
            "Check Windows folder permissions or set MOTOR_CALCULATOR_USER_DATA to a writable directory."
        ) from None
    try:
        root.iconbitmap("motor_icon.ico")
    except Exception:
        pass

    try:
        app = MotorCalculatorApp(root)
    except Exception:
        logger.exception("Main application initialization failed")
        root.destroy()
        raise
    root.update_idletasks()
    work_left, work_top, work_right, work_bottom = windows_work_area(
        root.winfo_screenwidth(),
        root.winfo_screenheight(),
    )
    work_width = work_right - work_left
    work_height = work_bottom - work_top
    requested_width, requested_height = dpi_scaled_window_size(
        root.winfo_width(),
        root.winfo_height(),
        float(root.tk.call("tk", "scaling")),
    )
    width, height = bounded_window_size(
        requested_width,
        requested_height,
        work_width,
        work_height,
    )
    x_pos = work_left + (work_width - width) // 2
    y_pos = work_top + (work_height - height) // 2
    root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
    logger.info("Main window initialized at %sx%s", width, height)
    smoke_output = _smoke_output_argument(sys.argv[1:])
    if smoke_output is not None:
        from motor_calculator.runtime.gui_smoke import run_real_gui_smoke

        root.after(300, run_real_gui_smoke, root, app, smoke_output)
    root.mainloop()
