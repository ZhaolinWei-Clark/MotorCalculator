"""Legacy GUI wrapper that delegates all electromagnetic calculations to motor_core."""

from __future__ import annotations

import importlib.util
import logging
import math
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
from motor_calculator.motor_core.loss_semantics import (
    loss_limitation_report_lines_zh,
    loss_model_status_payload,
)
from motor_calculator.motor_core.voltage_semantics import CORRECTED_VOLTAGE_BASIS
from motor_calculator.motor_core.winding_factor import (
    COIL_SPAN_TOOLTIP_ZH,
    SKEW_TOOLTIP_ZH,
    WINDING_FACTOR_MODE_LABELS_ZH,
    WINDING_FACTOR_TOOLTIP_ZH,
    WindingFactorMode,
    WindingFactorProvenance,
    format_winding_factor_report_lines_zh,
    format_winding_factor_summary_zh,
    resolve_winding_factor,
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
from motor_calculator.i18n import (
    input_label,
    input_tooltip,
    localize_message,
    localize_status,
    preset_name,
    tr,
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
    build_project_inputs,
    flatten_project_inputs,
    inspect_project_sources,
    missing_feedback_record_ids,
    project_inputs_hash,
    uncertainty_parameters_from_payload,
    utc_now_iso,
)

from motor_calculator.plots import (
    assess_result_snapshot,
    build_dashboard_data,
    build_result_snapshot,
)

from .confidence_panel import ConfidencePanel
from .guided_input_panel import GuidedInputPanel, ToolTip
from .results_dashboard import ResultsDashboard
from .feedback_dialog import (
    FeedbackMetricOption,
    ValidationFeedbackDialog,
    format_feedback_submission_result,
)
from .recovery_dialog import RecoveryBrowserDialog
from .uncertainty_dialog import UncertaintyAssumptionDialog
from .analysis_dialogs import AnalysisCenterDialog

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
from motor_calculator.validation.design_feasibility import (
    evaluate_design_feasibility,
    format_feasibility_messages_zh,
)
from motor_calculator.runtime import (
    bounded_window_size,
    build_diagnostics,
    check_runtime_health,
    create_runtime_directories,
    dpi_scaled_window_size,
    enable_windows_dpi_awareness,
    export_diagnostics,
    format_startup_failure,
    initialize_local_logging,
    resolve_runtime_paths,
    windows_work_area,
)
from motor_calculator.version import APPLICATION_VERSION, application_version_label


_RUNTIME_PATHS = resolve_runtime_paths()
_REPOSITORY_ROOT = _RUNTIME_PATHS.resource_root


def _load_legacy_module():
    legacy_path = _RUNTIME_PATHS.resource("motor_calculator", "PMDC_Calculator_claude204.py")
    spec = importlib.util.spec_from_file_location("legacy_motor_calculator_ui", legacy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Legacy GUI module could not be loaded: {legacy_path}")
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
        self.root.title(f"{tr('app.title')} {application_version_label()}")
        self._latest_accuracy_envelope = None
        self._latest_feasibility_assessment = None
        self._latest_result_snapshot = None
        self._engineering_confidence_summary = None
        self._user_uncertainty_parameters = None
        self._analysis_center = None
        self._create_results_dashboard()
        self._create_confidence_tab()
        self._initialize_guided_input_ux()
        self._apply_startup_example()
        self._initialize_project_support()

    STARTUP_EXAMPLE_PRESET_ID = "design.manufacturability_start.v1"

    def _apply_startup_example(self) -> bool:
        """RC2: open on the audited manufacturability starting example.

        The frozen `APPLICATION_DEFAULTS` and `legacy_baseline.json` are
        unchanged; only the initial GUI field values differ. The previous
        first-launch state simultaneously tripped current density, the
        same-basis voltage envelope and the legacy occupancy proxy, which made
        it impossible for a new user to tell a bad design from a broken tool.
        """

        preset = self._preset_registry.get(self.STARTUP_EXAMPLE_PRESET_ID)
        if not preset.available:
            return False
        self._project_suppress_dirty = True
        try:
            displayed = canonical_to_display_inputs(
                apply_preset(parse_legacy_gui_params(self._collect_raw_params()), preset),
                self._display_unit_preferences,
            )
            for field_name in preset.values:
                value = displayed[field_name]
                if field_name == "coreless":
                    self.coreless_var.set(bool(value))
                elif field_name in self.vars:
                    self.vars[field_name].set(
                        format_engineering_value(value) if isinstance(value, float) else str(value)
                    )
            self._last_preset_id = preset.preset_id
            self._last_preset_version = preset.version
        except (MotorValidationError, MotorCalculationError, KeyError, TypeError, ValueError):
            logging.getLogger(__name__).warning(
                "Startup example could not be applied; keeping frozen application defaults",
                exc_info=True,
            )
            return False
        finally:
            self._project_suppress_dirty = False
        self._guided_input_panel.refresh_all()
        self._refresh_winding_factor_summary()
        return True

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
        self._configure_legacy_input_grid(legacy_frame)

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
                ToolTip(entry, input_tooltip(name))
        self._initialize_winding_factor_ux(legacy_frame)
        self._apply_input_mode_visibility()

    # ------------------------------------------------------------------
    # RC2: winding-factor auto/manual provenance
    # ------------------------------------------------------------------

    def _initialize_winding_factor_ux(self, legacy_frame) -> None:
        self._winding_factor_mode_var = tk.StringVar(value=WINDING_FACTOR_MODE_LABELS_ZH[
            WindingFactorMode.MANUAL
        ])
        self._coil_span_slots_var = tk.StringVar(value="")
        self._skew_slots_var = tk.StringVar(value="0")
        self._winding_factor_resolution = None
        self._winding_factor_manual_provenance = WindingFactorProvenance.MANUAL_USER

        used_rows = [
            int(widget.grid_info().get("row", 0)) for widget in legacy_frame.grid_slaves()
        ]
        target_row = (max(used_rows) + 1) if used_rows else 1

        panel = ttk.LabelFrame(legacy_frame, text="绕组系数 k_w1", padding=(6, 4))
        panel.grid(row=target_row, column=0, columnspan=3, sticky="ew", padx=4, pady=(8, 4))
        panel.columnconfigure(1, weight=1)
        self._winding_factor_panel = panel

        ttk.Label(panel, text="模式").grid(row=0, column=0, sticky="w", padx=(0, 4))
        mode_combo = ttk.Combobox(
            panel,
            textvariable=self._winding_factor_mode_var,
            values=list(WINDING_FACTOR_MODE_LABELS_ZH.values()),
            state="readonly",
            width=10,
        )
        mode_combo.grid(row=0, column=1, sticky="ew")
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_winding_factor_summary())
        self._winding_factor_mode_combo = mode_combo

        ttk.Label(panel, text="线圈节距 (槽)").grid(row=1, column=0, sticky="w", padx=(0, 4))
        span_entry = ttk.Entry(panel, textvariable=self._coil_span_slots_var, width=10)
        span_entry.grid(row=1, column=1, sticky="ew")
        self._coil_span_entry = span_entry

        ttk.Label(panel, text="斜槽 (槽距)").grid(row=2, column=0, sticky="w", padx=(0, 4))
        skew_entry = ttk.Entry(panel, textvariable=self._skew_slots_var, width=10)
        skew_entry.grid(row=2, column=1, sticky="ew")
        self._skew_slots_entry = skew_entry

        self._winding_factor_summary_var = tk.StringVar(value="尚未解析")
        summary = ttk.Label(
            panel,
            textvariable=self._winding_factor_summary_var,
            wraplength=250,
            justify=tk.LEFT,
            foreground="#333333",
        )
        summary.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._winding_factor_summary_label = summary

        ToolTip(mode_combo, WINDING_FACTOR_TOOLTIP_ZH)
        ToolTip(span_entry, COIL_SPAN_TOOLTIP_ZH)
        ToolTip(skew_entry, SKEW_TOOLTIP_ZH)
        for variable in (self._coil_span_slots_var, self._skew_slots_var):
            variable.trace_add("write", lambda *_args: self._refresh_winding_factor_summary())
        self._refresh_winding_factor_summary()

    def _selected_winding_factor_mode(self) -> WindingFactorMode:
        label = str(self._winding_factor_mode_var.get()).strip()
        for mode, mode_label in WINDING_FACTOR_MODE_LABELS_ZH.items():
            if mode_label == label:
                return mode
        return WindingFactorMode.MANUAL

    def _resolve_winding_factor_for(self, parsed_params) -> object:
        return resolve_winding_factor(
            parsed_params,
            mode=self._selected_winding_factor_mode(),
            coil_span_slots=self._coil_span_slots_var.get(),
            skew_slots=self._skew_slots_var.get(),
            manual_provenance=self._winding_factor_manual_provenance,
        )

    def _refresh_winding_factor_summary(self) -> None:
        try:
            parsed = parse_legacy_gui_params(self._collect_raw_params())
        except (MotorValidationError, MotorCalculationError, KeyError, ValueError):
            self._winding_factor_summary_var.set("当前输入无效，暂时无法解析绕组系数。")
            return
        resolution = self._resolve_winding_factor_for(parsed)
        self._winding_factor_resolution = resolution
        self._winding_factor_summary_var.set(format_winding_factor_summary_zh(resolution))

    def _latest_winding_factor_resolution(self):
        # The panel does not exist while the legacy base class is still being
        # constructed, and export paths must never depend on widget lifetime.
        if not hasattr(self, "_winding_factor_mode_var"):
            return None
        if getattr(self, "_winding_factor_resolution", None) is None:
            self._refresh_winding_factor_summary()
        return getattr(self, "_winding_factor_resolution", None)

    def _restore_winding_factor_preferences(self, preferences) -> None:
        """Restore winding-factor settings without reinterpreting old projects.

        A project saved before RC2 carries no winding-factor metadata. Such a
        project keeps its stored `k_w` verbatim and is marked LEGACY_PROJECT, so
        a manually chosen value is never presented as model-derived.
        """

        if not hasattr(self, "_winding_factor_mode_var"):
            return
        stored_mode = preferences.get("winding_factor_mode")
        if stored_mode is None:
            self._winding_factor_mode_var.set(
                WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.MANUAL]
            )
            self._coil_span_slots_var.set("")
            self._skew_slots_var.set("0")
            self._winding_factor_manual_provenance = WindingFactorProvenance.LEGACY_PROJECT
            self._refresh_winding_factor_summary()
            return
        try:
            mode = WindingFactorMode(str(stored_mode).strip().lower())
        except ValueError:
            mode = WindingFactorMode.MANUAL
        self._winding_factor_mode_var.set(WINDING_FACTOR_MODE_LABELS_ZH[mode])
        self._coil_span_slots_var.set(str(preferences.get("coil_span_slots", "") or ""))
        self._skew_slots_var.set(str(preferences.get("skew_slots", "0") or "0"))
        self._winding_factor_manual_provenance = WindingFactorProvenance.MANUAL_USER
        self._refresh_winding_factor_summary()

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

    def _configure_legacy_input_grid(self, frame) -> None:
        """Keep older input labels readable without changing control behavior."""

        frame.columnconfigure(0, weight=3, minsize=145)
        frame.columnconfigure(1, weight=2, minsize=105)
        frame.columnconfigure(2, weight=0, minsize=52)
        self._legacy_input_labels = tuple(
            widget
            for widget in frame.grid_slaves()
            if isinstance(widget, ttk.Label)
            and int(widget.grid_info().get("column", -1)) == 0
        )
        for label in self._legacy_input_labels:
            label.configure(justify=tk.LEFT, anchor=tk.W)
            label.grid_configure(sticky="ew", padx=(2, 6))

        def update_wrap(event) -> None:
            wraplength = max(130, min(230, int(event.width * 0.46)))
            for label in self._legacy_input_labels:
                label.configure(wraplength=wraplength)

        frame.bind("<Configure>", update_wrap, add="+")

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
            logging.getLogger(__name__).warning("Display unit conversion rejected: %s", exc)
            messagebox.showwarning(
                tr("unit.change_failed_title"),
                tr("unit.change_failed"),
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
            # RC2 winding-factor provenance metadata. These live in the optional
            # schema v1 ui_preferences map on purpose: `k_w` remains the single
            # authoritative physics input, so no PROJECT_INPUT_SPECS change and
            # no project-hash change is required, and older projects still load.
            "winding_factor_mode": self._selected_winding_factor_mode().value,
            "coil_span_slots": str(self._coil_span_slots_var.get()).strip(),
            "skew_slots": str(self._skew_slots_var.get()).strip(),
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
        self._restore_winding_factor_preferences(preferences)
        self._update_input_unit_labels()
        self._guided_input_panel.set_preferences(restored)
        self._apply_input_mode_visibility()

    def _apply_preset_by_id(self, preset_id: str) -> bool:
        preset = self._preset_registry.get(preset_id)
        if not preset.available:
            messagebox.showwarning(
                tr("preset.unavailable_title"),
                tr("preset.schema_unavailable"),
                parent=self.root,
            )
            return False
        try:
            current = self._get_params()
            changes = preview_preset(current, preset)
        except (MotorValidationError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Preset preview rejected invalid current inputs: %s", exc)
            messagebox.showerror(
                tr("preset.preview_title"), tr("preset.invalid_current"), parent=self.root
            )
            return False
        if not changes:
            messagebox.showinfo(tr("preset.preview_title"), tr("preset.no_changes"), parent=self.root)
            return True
        lines = [
            f"{input_label(item.field_name)}：{item.current_value} -> {item.preset_value}"
            for item in changes
        ]
        detail = (
            f"{preset_name(preset.preset_id, preset.display_name)}\n"
            f"{tr('preset.evidence')}：{localize_status(preset.evidence_kind.value)}\n"
            f"{tr('preset.provenance')}：{localize_message(preset.provenance)}\n"
            f"{tr('preset.assumptions')}：{'; '.join(localize_message(item) for item in preset.assumptions)}\n\n"
            + "\n".join(lines)
            + f"\n\n{tr('preset.apply_question')}"
        )
        if not messagebox.askokcancel(tr("preset.preview_title"), detail, parent=self.root):
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
        values = ", ".join(
            f"{input_label(name)}={value}" for name, value in preset.values.items()
        ) or tr("common.none")
        messagebox.showinfo(
            tr("preset.details_title"),
            f"{preset_name(preset.preset_id, preset.display_name)}\n"
            f"{tr('preset.available')}：{tr('common.yes') if preset.available else tr('common.no')}\n"
            f"{tr('preset.values')}：{values}\n"
            f"{tr('preset.provenance')}：{localize_message(preset.provenance)}\n"
            f"{tr('preset.assumptions')}：{'; '.join(localize_message(item) for item in preset.assumptions) or tr('common.none')}\n"
            f"{tr('preset.notes')}：{'; '.join(localize_message(item) for item in preset.notes) or tr('common.none')}",
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
            tr("reset.quick_title"),
            tr("reset.quick_question"),
            parent=self.root,
        ):
            for field in ("g_side", "n_rated", "k_w", "p"):
                self._reset_input_field(field)

    def reset_defaults(self):
        if not messagebox.askokcancel(
            tr("reset.all_title"), tr("reset.all_question"), parent=self.root
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
            tr("reset.complete_title"), tr("reset.complete"), parent=self.root
        )
        return True

    def _show_input_help(self) -> None:
        messagebox.showinfo(
            tr("help.title"),
            tr("help.body"),
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
                f"{localize_status(item.severity)}/{localize_status(item.level)}：{localize_message(item.message)}"
                for item in issues
            )
        except Exception as exc:
            logging.getLogger(__name__).warning("Input guidance evaluation failed: %s", exc)
            text = (
                f"{localize_status('ERROR')}/{localize_status('INVALID')}："
                f"{tr('guidance.evaluation_failed')}"
            )
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
            recovery_startup_warning = tr("status.recovery_unavailable")
            logging.getLogger(__name__).warning("Recovery protection unavailable: %s", exc)
        self._recovery_after_id = None
        self._recovery_candidates = initial_recovery_scan.candidates
        self._recovery_status_var = tk.StringVar(
            value=recovery_startup_warning or tr("status.recovery_active")
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
                tr("status.recovered_available", count=len(self._recovery_candidates))
            )

    def _create_project_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label=tr("menu.new"), accelerator="Ctrl+N", command=self._new_project)
        file_menu.add_command(label=tr("menu.open"), accelerator="Ctrl+O", command=self._open_project)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.save"), accelerator="Ctrl+S", command=self._save_project)
        file_menu.add_command(label=tr("menu.save_as"), command=self._save_project_as)
        self._recent_projects_menu = tk.Menu(file_menu, tearoff=False, postcommand=self._refresh_recent_projects_menu)
        file_menu.add_cascade(label=tr("menu.recent"), menu=self._recent_projects_menu)
        file_menu.add_command(label=tr("menu.recover"), command=self._recover_unsaved_work)
        file_menu.add_command(label=tr("menu.notes"), command=self._edit_project_notes)
        file_menu.add_separator()
        file_menu.add_command(label=tr("menu.exit"), command=self._request_exit)
        menu_bar.add_cascade(label=tr("menu.file"), menu=file_menu)
        analysis_menu = tk.Menu(menu_bar, tearoff=False)
        analysis_menu.add_command(
            label="动态仿真...", command=lambda: self._open_analysis_center("dynamic")
        )
        analysis_menu.add_command(
            label="不确定性分析...", command=lambda: self._open_analysis_center("uncertainty")
        )
        analysis_menu.add_command(
            label="敏感性分析...", command=lambda: self._open_analysis_center("sensitivity")
        )
        menu_bar.add_cascade(label="分析", menu=analysis_menu)
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label=tr("menu.diagnostics"), command=self._export_runtime_diagnostics)
        help_menu.add_separator()
        help_menu.add_command(label=tr("menu.about"), command=self._show_about)
        menu_bar.add_cascade(label=tr("menu.help"), menu=help_menu)
        self.root.configure(menu=menu_bar)
        self._project_menu_bar = menu_bar
        self._project_file_menu = file_menu
        self._project_help_menu = help_menu
        self._project_analysis_menu = analysis_menu
        self.root.bind_all("<Control-n>", lambda _event: self._new_project())
        self.root.bind_all("<Control-o>", lambda _event: self._open_project())
        self.root.bind_all("<Control-s>", lambda _event: self._save_project())

    def _show_about(self) -> None:
        diagnostics = build_diagnostics(self._runtime_paths)
        commit = diagnostics.get("build_commit") or tr("common.unavailable")
        messagebox.showinfo(
            tr("about.title"),
            tr(
                "about.body",
                version=application_version_label(),
                commit=commit,
                locale_name=diagnostics["locale"],
                runtime=diagnostics["runtime_mode"],
            ),
            parent=self.root,
        )

    def _open_analysis_center(self, analysis_name: str) -> AnalysisCenterDialog:
        if self._analysis_center is None or not self._analysis_center.window.winfo_exists():
            self._analysis_center = AnalysisCenterDialog(
                self.root,
                inputs_provider=self._get_params,
                result_provider=self._current_analysis_result,
                repository_root=self._repository_root,
                uncertainty_specification_provider=self._controlled_uncertainty_specification,
                on_uncertainty_complete=self._apply_uncertainty_analysis_result,
            )
        self._analysis_center.select_analysis(analysis_name)
        return self._analysis_center

    def _current_analysis_result(self):
        result = getattr(self, "calc_results", None)
        snapshot = self._latest_result_snapshot
        if result is None or snapshot is None:
            return None
        try:
            project_inputs = build_project_inputs(self._get_params())
            assessment = assess_result_snapshot(snapshot, project_inputs, APPLICATION_VERSION)
        except (TypeError, ValueError):
            return None
        return result if assessment.is_current else None

    def _export_runtime_diagnostics(self) -> bool:
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title=tr("diagnostics.export_title"),
            defaultextension=".json",
            filetypes=((tr("diagnostics.file_type"), "*.json"),),
            initialdir=str(self._runtime_paths.export_dir),
            initialfile="MotorCalculator-diagnostics.json",
        )
        if not destination:
            return False
        try:
            export_diagnostics(destination, self._runtime_paths)
        except OSError as exc:
            logging.getLogger(__name__).exception("Diagnostic export failed: %s", exc)
            messagebox.showerror(
                tr("diagnostics.error_title"),
                tr("diagnostics.export_failed"),
                parent=self.root,
            )
            return False
        messagebox.showinfo(
            tr("diagnostics.complete_title"),
            tr("diagnostics.export_complete"),
            parent=self.root,
        )
        return True

    def _on_project_input_changed(self, *_args) -> None:
        if self._project_suppress_dirty:
            return
        self.results_dashboard.mark_input_stale()
        self._project_manager.mark_dirty()
        self._update_project_title()
        self._schedule_recovery_autosave()
        self._schedule_input_guidance()

    def _schedule_recovery_autosave(self) -> None:
        if self._recovery_after_id is not None:
            self.root.after_cancel(self._recovery_after_id)
        delay_ms = self._recovery_manager.autosave_interval_seconds * 1000
        self._recovery_after_id = self.root.after(delay_ms, self._perform_recovery_autosave)
        self._recovery_status_var.set(tr("status.unsaved_scheduled"))

    def _perform_recovery_autosave(self) -> bool:
        self._recovery_after_id = None
        if not self._project_manager.is_dirty:
            self._recovery_status_var.set(tr("status.project_saved"))
            return False
        try:
            document = self._build_project_document()
        except (ProjectValidationError, MotorValidationError, ValueError) as exc:
            logging.getLogger(__name__).warning("Recovery waiting for valid inputs: %s", exc)
            self._recovery_status_var.set(tr("status.recovery_waiting"))
            return False
        current = self._project_manager.current_project
        result = self._recovery_manager.try_write_recovery(
            document,
            original_project_path=self._project_manager.current_path,
            dirty=True,
            last_normal_save_timestamp=None if current is None else current.metadata.modified_at,
        )
        if not result.written:
            self._recovery_status_var.set(tr("status.recovery_autosave_unavailable"))
            logging.getLogger(__name__).warning(result.warning)
            return False
        self._recovery_status_var.set(tr("status.recovery_created", timestamp=utc_now_iso()))
        return True

    def _cleanup_project_recovery(self, project_uuid: str, *, saved_input_hash: str | None = None) -> None:
        try:
            self._recovery_manager.cleanup_project(project_uuid, saved_input_hash=saved_input_hash)
        except OSError as exc:
            warning = tr("status.recovery_cleanup_failed")
            self._recovery_status_var.set(warning)
            logging.getLogger(__name__).warning(warning)

    def _update_project_title(self) -> None:
        document = self._project_manager.current_project
        if document is None:
            display_name = tr("project.untitled")
        elif self._project_manager.current_path is not None:
            display_name = self._project_manager.current_path.name
        else:
            display_name = (
                tr("project.untitled")
                if document.metadata.project_name == "Untitled"
                else document.metadata.project_name
            )
        dirty = " *" if self._project_manager.is_dirty else ""
        self.root.title(f"{tr('app.title')} {application_version_label()} - {display_name}{dirty}")

    def _build_project_document(self, *, project_name: str | None = None) -> ProjectDocument:
        current = self._project_manager.current_project
        name = project_name or (current.metadata.project_name if current else "Untitled")
        parameters = self._get_params()
        snapshot = self._latest_result_snapshot
        if snapshot is not None:
            snapshot_state = assess_result_snapshot(
                snapshot,
                build_project_inputs(parameters),
                snapshot.result_model_version,
            )
            if not snapshot_state.is_current:
                snapshot = None
        return create_project_document(
            name,
            parameters,
            project_uuid=None if current is None else current.metadata.project_uuid,
            created_at=None if current is None else current.metadata.created_at,
            modified_at=utc_now_iso(),
            uncertainty_assumptions=self._user_uncertainty_parameters,
            ui_preferences=self._ui_preferences_payload(),
            notes=self._project_notes,
            validation_record_ids=self._project_validation_record_ids,
            result_snapshot=snapshot,
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
        self._latest_result_snapshot = None
        self.results_dashboard.clear()
        self.result_text.delete("1.0", tk.END)
        for tab, title in (
            (self.curves_tab, tr("chart.performance")),
            (self.emf_tab, tr("chart.back_emf")),
            (self.torque_tab, tr("chart.torque")),
            (self.flux_tab, tr("chart.flux")),
            (self.geo_tab, tr("chart.geometry")),
        ):
            self._set_chart_placeholder(tab, title, tr("chart.refresh"))
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
            self._latest_result_snapshot = document.result_snapshot
            snapshot_state = assess_result_snapshot(
                document.result_snapshot,
                document.inputs,
                APPLICATION_VERSION,
            )
            if document.result_snapshot is not None:
                self.results_dashboard.show_snapshot(snapshot_state)
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
            tr("project.unsaved_title"),
            tr("project.unsaved_question"),
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
            title=tr("project.open_title"),
            filetypes=((tr("project.file_type"), f"*{PROJECT_FILE_EXTENSION}"), (tr("project.all_files"), "*.*")),
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
            logging.getLogger(__name__).warning("Project open blocked: %s", report.message)
            messagebox.showerror(tr("project.open_error"), tr("project.open_failed"), parent=self.root)
            return False
        if report.status in {CompatibilityStatus.CORRUPT, CompatibilityStatus.INVALID}:
            if sources.backup is not None and sources.backup.status is CompatibilityStatus.COMPATIBLE:
                use_backup = messagebox.askyesno(
                    tr("project.backup_title"),
                    tr("project.backup_question"),
                    parent=self.root,
                )
                if not use_backup:
                    return False
                source_path = sources.backup.path
            else:
                logging.getLogger(__name__).warning("Project open invalid/corrupt: %s", report.message)
                messagebox.showerror(tr("project.open_error"), tr("project.open_failed"), parent=self.root)
                return False
        elif report.status is CompatibilityStatus.MIGRATION_AVAILABLE:
            if not messagebox.askokcancel(
                tr("project.migration_title"),
                tr("project.migration_question"),
                parent=self.root,
            ):
                return False
        try:
            document = self._project_manager.open_project(source_path)
            self._apply_project_document(document)
        except ProjectSerializationError as exc:
            logging.getLogger(__name__).warning("Project serialization failed: %s", exc)
            messagebox.showerror(tr("project.open_error"), tr("project.open_failed"), parent=self.root)
            return False
        try:
            available = [record.record_id for record in load_feedback_records(self._feedback_store)]
        except Exception:
            available = []
        missing = missing_feedback_record_ids(document, available)
        if missing:
            messagebox.showwarning(
                tr("project.references_title"),
                tr("project.references_missing", count=len(missing)),
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
            title=tr("project.save_title"),
            initialdir=str(current_path.parent if current_path else Path.home()),
            initialfile=current_path.name if current_path else f"{tr('project.untitled')}{PROJECT_FILE_EXTENSION}",
            defaultextension=PROJECT_FILE_EXTENSION,
            filetypes=((tr("project.file_type"), f"*{PROJECT_FILE_EXTENSION}"),),
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
            logging.getLogger(__name__).warning("Project save failed: %s", exc)
            messagebox.showerror(tr("project.save_error"), tr("project.save_failed"), parent=self.root)
            return False
        self._update_project_title()
        self._cleanup_project_recovery(
            document.metadata.project_uuid,
            saved_input_hash=project_inputs_hash(document.inputs),
        )
        self._recovery_status_var.set(tr("status.project_saved"))
        return True

    def _refresh_recent_projects_menu(self) -> None:
        self._recent_projects_menu.delete(0, tk.END)
        entries = self._project_manager.recent_store.entries(existing_only=True)
        if not entries:
            self._recent_projects_menu.add_command(label=tr("project.no_recent"), state=tk.DISABLED)
            return
        for entry in entries:
            self._recent_projects_menu.add_command(
                label=f"{entry.project_name} - {entry.path}",
                command=lambda path=entry.path: self._open_project_path(path),
            )

    def _edit_project_notes(self) -> None:
        edited = simpledialog.askstring(
            tr("project.notes_title"),
            tr("project.notes_prompt"),
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
            messagebox.showinfo(tr("recovery.none_title"), tr("recovery.none"), parent=self.root)
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
        self._recovery_status_var.set(tr("status.recovered_unsaved"))
        return True

    def _discard_recovery_candidate(self, candidate: RecoveryCandidate) -> bool:
        try:
            self._recovery_manager.discard(candidate)
        except OSError as exc:
            logging.getLogger(__name__).warning("Recovery discard failed: %s", exc)
            messagebox.showerror(
                tr("recovery.discard_title"), tr("recovery.discard_failed"), parent=self.root
            )
            return False
        self._recovery_status_var.set(tr("status.recovery_discarded"))
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
        self.notebook.add(self.confidence_tab, text=tr("confidence.tab"))
        self.confidence_panel = ConfidencePanel(
            self.confidence_tab,
            on_estimate=self._estimate_controlled_reference_uncertainty,
            on_edit_assumptions=self._edit_uncertainty_assumptions,
            on_add_feedback=self._add_validation_feedback,
            on_export=self._export_confidence_summary,
        )
        self.confidence_panel.pack(fill=tk.BOTH, expand=True)
        self._set_unavailable_current_summary()

    def _create_results_dashboard(self) -> None:
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.insert(0, self.dashboard_tab, text="结果仪表板")
        self.results_dashboard = ResultsDashboard(
            self.dashboard_tab,
            input_provider=self._get_params,
            export_directory=self._runtime_paths.export_dir,
        )
        self.results_dashboard.pack(fill=tk.BOTH, expand=True)

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
        reason = tr("confidence.unavailable_reason")
        if database_warning:
            logging.getLogger(__name__).warning(database_warning)
            reason += tr("confidence.database_unavailable")
        summary = build_unavailable_confidence_summary(
            metric_name="back_emf_phase_rms_v",
            nominal_value=nominal,
            unit="V",
            validation_summary=validation_summary,
            reason=reason,
            source_label=tr("confidence.current_source"),
        )
        self._engineering_confidence_summary = summary
        self._latest_accuracy_envelope = None
        self.confidence_panel.set_summary(summary)
        if hasattr(self, "results_dashboard"):
            self.results_dashboard.set_uncertainty_result(None)

    def _controlled_uncertainty_specification(self) -> UncertaintySpecification | None:
        if self._user_uncertainty_parameters is None:
            return None
        base = load_uncertainty_specification(
            self._repository_root / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"
        )
        return replace(
            base,
            assumption_label=tr("confidence.user_assumption"),
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
                source_label=tr("confidence.controlled_source"),
            )
            if database_warning:
                summary = replace(
                    summary,
                    warnings=summary.warnings + (database_warning,),
                )
        except Exception as exc:
            logging.getLogger(__name__).warning("Controlled-reference uncertainty unavailable: %s", exc)
            messagebox.showwarning(
                tr("confidence.tab"),
                tr("confidence.analysis_unavailable"),
                parent=self.root,
            )
            return
        self._apply_uncertainty_analysis_result(result, summary=summary)
        self.notebook.select(self.confidence_tab)

    def _apply_uncertainty_analysis_result(self, result, *, summary=None) -> None:
        if summary is None:
            validation_summary, database_warning = self._load_local_validation_summary(
                metric_name=result.accuracy_envelope.metric_name,
                topology="SSDR controlled AFPM reference",
            )
            summary = build_engineering_confidence_summary(
                result.accuracy_envelope,
                validation_summary,
                source_label=tr("confidence.controlled_source"),
            )
            if database_warning:
                summary = replace(summary, warnings=summary.warnings + (database_warning,))
        self._latest_accuracy_envelope = result.accuracy_envelope
        self._engineering_confidence_summary = summary
        self.confidence_panel.set_summary(summary)
        self.results_dashboard.set_uncertainty_result(result.accuracy_envelope)

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
            logging.getLogger(__name__).warning("Uncertainty assumptions unavailable: %s", exc)
            messagebox.showwarning(
                tr("uncertainty.error_title"), tr("uncertainty.load_failed"), parent=self.root
            )
            return
        if edited is not None:
            self._user_uncertainty_parameters = edited
            self._project_manager.mark_dirty()
            self._update_project_title()
            self._schedule_recovery_autosave()
            messagebox.showinfo(
                tr("uncertainty.error_title"),
                tr("uncertainty.saved"),
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
            messagebox.showinfo(tr("feedback.error_title"), tr("feedback.run_first"), parent=self.root)
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
            logging.getLogger(__name__).warning("Local validation feedback save failed: %s", exc)
            messagebox.showwarning(
                tr("feedback.error_title"),
                tr("feedback.save_failed"),
                parent=self.root,
            )
            return
        messagebox.showinfo(tr("feedback.saved_title"), display, parent=self.root)
        if result.record.record_id not in self._project_validation_record_ids:
            self._project_validation_record_ids.append(result.record.record_id)
            self._project_manager.mark_dirty()
            self._update_project_title()
            self._schedule_recovery_autosave()
        self._set_unavailable_current_summary()

    def _export_confidence_summary(self) -> None:
        summary = self._engineering_confidence_summary
        if summary is None:
            messagebox.showinfo(tr("confidence.export_title"), tr("confidence.export_none"), parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title=tr("confidence.export_dialog"),
            initialdir=str(self._runtime_paths.export_dir),
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), (tr("project.text_file_type"), "*.txt")),
        )
        if not path:
            return
        format_name = "json" if Path(path).suffix.lower() == ".json" else "text"
        try:
            export_confidence_summary(summary, Path(path), format_name=format_name)
        except Exception as exc:
            logging.getLogger(__name__).warning("Confidence export failed: %s", exc)
            messagebox.showerror(
                tr("confidence.export_title"), tr("confidence.export_failed"), parent=self.root
            )
            return
        messagebox.showinfo(tr("confidence.export_title"), tr("confidence.export_done"), parent=self.root)

    def _collect_raw_params(self) -> Dict[str, Any]:
        raw: Dict[str, Any] = {}
        for key, var in self.vars.items():
            raw[key] = var.get()
        raw["coreless"] = self.coreless_var.get()
        return display_to_canonical_inputs(raw, self._display_unit_preferences)

    def _get_params(self) -> Dict[str, Any]:
        parsed = parse_legacy_gui_params(self._collect_raw_params())
        if not hasattr(self, "_winding_factor_mode_var"):
            return parsed
        # RC2: AUTO replaces the manual `k_w` only when the geometry genuinely
        # supports the derivation. Every other case preserves the manual value,
        # so existing projects and presets are never reinterpreted silently.
        resolution = self._resolve_winding_factor_for(parsed)
        self._winding_factor_resolution = resolution
        if resolution.is_auto and resolution.value is not None:
            parsed = dict(parsed)
            parsed["k_w"] = float(resolution.value)
        return parsed

    def _inject_phase3a_report_summary(self) -> None:
        if not getattr(self, "calc_results", None):
            return
        metadata = self.calc_results.metadata
        summary_lines = [
            "",
            tr("report.phase3a_title"),
            f"{tr('report.control_mode')}: {metadata.get('控制模式', 'N/A')}",
            f"{tr('report.legacy_model')}: {metadata.get('legacy控制模型', 'N/A')}",
            f"{tr('report.mechanical_speed')}: {metadata.get('机械转速_rpm', 'N/A')} rpm",
            f"{tr('report.electrical_frequency')}: {metadata.get('电频率_Hz', 'N/A')} Hz",
            "-" * 70,
            "",
        ]
        self.result_text.insert("1.0", "\n".join(summary_lines))

    def rc2_export_payload(self, result=None) -> Dict[str, Any]:
        """Authoritative, unambiguously named metrics for machine-readable export.

        The legacy kernel keys `性能指标.voltage_margin_percent` and
        `性能指标.fill_factor` keep their historical meaning and are therefore
        not renamed. This payload is what consumers should read instead.
        """

        target = result if result is not None else getattr(self, "calc_results", None)
        payload: Dict[str, Any] = {
            "schema": "rc2.engineering_metrics.v1",
            "note_zh": (
                "本节为权威同基口径指标。计算结果节中的 voltage_margin_percent 与 "
                "fill_factor 为 legacy 兼容值，不得按现代语义解读。"
            ),
        }
        if target is None:
            return payload
        try:
            params = self._get_params()
            assessment = evaluate_design_feasibility(params, target)
        except Exception:  # pragma: no cover - export must never crash the GUI
            logging.getLogger(__name__).warning("RC2 export payload unavailable", exc_info=True)
            return payload

        occupancy = assessment.slot_fill_factor
        # Phase 9B A1/A2: loss values are unchanged; only their model status and
        # limitation text are added so a consumer cannot read them as validated.
        payload.update(loss_model_status_payload())
        payload.update(
            {
                "eddy_loss_w": float(target.performance.eddy_loss_w),
                "core_loss_w": float(target.performance.core_loss_w),
                "slot_occupancy_ratio": occupancy,
                "slot_occupancy_percent": None if occupancy is None else occupancy * 100.0,
                "slot_occupancy_status": assessment.slot_fill_status.value,
                "voltage_margin_same_basis_percent": assessment.voltage_margin_percent,
                "voltage_available_line_rms_v": assessment.available_voltage_line_rms_v,
                "voltage_required_line_rms_v": assessment.required_voltage_line_rms_v,
                "voltage_status": assessment.voltage_status.value,
                # Phase 9B C1 parallel voltage outputs, explicitly named.
                "voltage_required_line_rms_corrected_v": (
                    target.performance.required_voltage_line_rms_corrected_v
                ),
                "voltage_margin_corrected_same_basis_percent": (
                    assessment.corrected_voltage_margin_percent
                ),
                "voltage_legacy_corrected_relative_difference": (
                    target.performance.required_voltage_legacy_corrected_relative_difference
                ),
                "voltage_corrected_status": (
                    target.performance.required_voltage_corrected_status
                ),
                "voltage_corrected_basis": dict(CORRECTED_VOLTAGE_BASIS),
                "current_density_a_per_mm2": assessment.current_density_a_per_mm2,
                "legacy_linear_winding_proxy": assessment.legacy_fill_proxy,
                "legacy_dc_bus_difference_percent": float(
                    target.performance.voltage_margin_percent
                ),
            }
        )
        resolution = self._latest_winding_factor_resolution()
        if resolution is not None:
            payload.update(resolution.to_dict())
        return payload

    def _inject_rc2_engineering_summary(self, params, assessment) -> None:
        """Lead the detailed report with the modern, same-basis conclusions."""

        if not getattr(self, "calc_results", None):
            return
        performance = self.calc_results.performance
        resolution = self._latest_winding_factor_resolution()

        if assessment.slot_fill_factor is None:
            occupancy_line = (
                f"   近似裸铜槽占比        : 信息不足（{assessment.slot_fill_status.value}）"
            )
        else:
            occupancy_line = (
                f"   近似裸铜槽占比        : {assessment.slot_fill_factor:.4f}"
                f" ({assessment.slot_fill_factor * 100.0:.1f} %)"
            )
        if assessment.voltage_margin_percent is None:
            voltage_line = (
                f"   同基电压裕量          : 信息不足（{assessment.voltage_status.value}）"
            )
        else:
            voltage_line = (
                f"   同基电压裕量(legacy)  : {assessment.voltage_margin_percent:.2f} %"
                f" (可用/所需线电压 RMS {assessment.available_voltage_line_rms_v:.2f}"
                f"/{assessment.required_voltage_line_rms_v:.2f} V)"
            )
        # Phase 9B C1: publish both voltage bases side by side. The legacy value
        # stays the production default until the promotion gates pass.
        if assessment.corrected_voltage_margin_percent is None:
            corrected_voltage_line = (
                "   同基电压裕量(修正)    : 不适用（当前控制模式缺少正弦相量基准）"
            )
        else:
            relative = performance.required_voltage_legacy_corrected_relative_difference
            corrected_voltage_line = (
                f"   同基电压裕量(修正)    : {assessment.corrected_voltage_margin_percent:.2f} %"
                f" (所需线电压 RMS {assessment.corrected_required_voltage_line_rms_v:.2f} V"
                f"，较 legacy 高 {relative * 100.0:.2f} %)"
            )

        lines = [
            "",
            "RC2 工程结论摘要（同基口径）",
            "-" * 70,
            f"   额定转矩              : {performance.rated_torque_nm:.4f} Nm",
            f"   输出功率              : {performance.output_power_w:.2f} W",
            f"   当前模型估算效率      : {performance.efficiency_percent:.2f} %",
            f"   电流密度              : {assessment.current_density_a_per_mm2:.4f} A/mm²",
            voltage_line,
            corrected_voltage_line,
            occupancy_line,
        ]
        if resolution is not None:
            lines.extend(format_winding_factor_report_lines_zh(resolution))
        lines.append("")
        lines.extend(loss_limitation_report_lines_zh())
        lines.extend(
            [
                "   说明                  : 槽占比仅为裸铜截面积近似占比，未包含导线绝缘、"
                "槽绝缘、排布和绕制工艺；",
                "                           电压裕量使用统一 line-RMS 基准，不等同于完整"
                "逆变器瞬态动态裕量。",
                "-" * 70,
                "",
            ]
        )
        self.result_text.insert("1.0", "\n".join(lines))

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
            assessment = self._latest_feasibility_assessment
            if assessment is None:
                assessment = evaluate_design_feasibility(params, self.calc_results)
                self._latest_feasibility_assessment = assessment
            self._inject_rc2_engineering_summary(params, assessment)
            dashboard_data = build_dashboard_data(params, self.calc_results, assessment)
            self.results_dashboard.set_result(
                dashboard_data,
                rated_speed_rpm=float(params["n_rated"]),
            )
            self._latest_result_snapshot = build_result_snapshot(
                params,
                self.calc_results.to_dict(),
                APPLICATION_VERSION,
            )
            self.notebook.select(0)
            messagebox.showinfo(tr("analysis.complete_title"), tr("analysis.complete"))
        except (MotorValidationError, MotorCalculationError) as exc:
            logging.getLogger(__name__).warning("Calculation input rejected: %s", exc)
            self.results_dashboard.mark_calculation_failed()
            messagebox.showerror(tr("analysis.error_title"), tr("analysis.invalid"))
        except Exception as exc:
            logging.getLogger(__name__).exception("GUI calculation failed")
            self.results_dashboard.mark_calculation_failed()
            messagebox.showerror(tr("analysis.error_title"), tr("analysis.failed"))

    def _check_design_validity(self, result):
        assessment = evaluate_design_feasibility(self._get_params(), result)
        self._latest_feasibility_assessment = assessment
        return list(format_feasibility_messages_zh(assessment))


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


def _smoke_tk_scaling_argument(arguments: list[str]) -> float | None:
    if "--smoke-tk-scaling" not in arguments:
        return None
    index = arguments.index("--smoke-tk-scaling")
    if index + 1 >= len(arguments):
        raise SystemExit("--smoke-tk-scaling requires a positive numeric value")
    try:
        scaling = float(arguments[index + 1])
    except ValueError:
        raise SystemExit("--smoke-tk-scaling requires a positive numeric value") from None
    if not math.isfinite(scaling) or scaling <= 0.0:
        raise SystemExit("--smoke-tk-scaling requires a positive numeric value")
    return scaling


def main():
    arguments = sys.argv[1:]
    smoke_output = _smoke_output_argument(arguments)
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
    smoke_scaling = _smoke_tk_scaling_argument(arguments) if smoke_output is not None else None
    if smoke_scaling is not None:
        root.tk.call("tk", "scaling", smoke_scaling)
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
    if smoke_output is not None:
        from motor_calculator.runtime.gui_smoke import run_real_gui_smoke

        root.after(300, run_real_gui_smoke, root, app, smoke_output)
    root.mainloop()
