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
from motor_calculator.project import (
    PROJECT_FILE_EXTENSION,
    ProjectDocument,
    ProjectManager,
    ProjectSerializationError,
    ProjectValidationError,
    RecentProjectStore,
    UnsavedChangesDecision,
    create_project_document,
    flatten_project_inputs,
    missing_feedback_record_ids,
    uncertainty_parameters_from_payload,
    utc_now_iso,
)

from .confidence_panel import ConfidencePanel
from .feedback_dialog import (
    FeedbackMetricOption,
    ValidationFeedbackDialog,
    format_feedback_submission_result,
)
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
        self._initialize_project_support()

    def _initialize_project_support(self) -> None:
        self._project_suppress_dirty = True
        self._project_notes = ""
        self._project_validation_record_ids: list[str] = []
        self._project_default_inputs = dict(self._get_params())
        recent_store = RecentProjectStore(self._runtime_paths.user_data_dir / "recent_projects.json")
        self._project_manager = ProjectManager(recent_store)
        document = create_project_document("Untitled", self._project_default_inputs)
        self._project_manager.new_project(document)
        self._create_project_menu()
        self._project_traces = [
            variable.trace_add("write", self._on_project_input_changed)
            for variable in (*self.vars.values(), self.coreless_var)
        ]
        self.root.protocol("WM_DELETE_WINDOW", self._request_exit)
        self._project_suppress_dirty = False
        self._update_project_title()

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
            for name, value in restored.items():
                if name == "coreless":
                    self.coreless_var.set(bool(value))
                else:
                    self.vars[name].set(str(value))
            self._user_uncertainty_parameters = self._restore_uncertainty_assumptions(document)
            self._project_notes = document.notes
            self._project_validation_record_ids = list(document.validation_record_ids)
            self._clear_project_results()
        finally:
            self._project_suppress_dirty = False
        self._project_manager.mark_clean(document)
        self._update_project_title()

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
        if not self._confirm_abandon_changes():
            return False
        document = create_project_document("Untitled", self._project_default_inputs)
        self._project_manager.new_project(document)
        self._apply_project_document(document)
        return True

    def _open_project(self) -> bool:
        if not self._confirm_abandon_changes():
            return False
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Open MotorCalculator project",
            filetypes=(("MotorCalculator project", f"*{PROJECT_FILE_EXTENSION}"), ("All files", "*.*")),
        )
        return False if not selected else self._open_project_path(Path(selected), prompt_for_unsaved=False)

    def _open_project_path(self, path: Path, *, prompt_for_unsaved: bool = True) -> bool:
        if prompt_for_unsaved and not self._confirm_abandon_changes():
            return False
        try:
            document = self._project_manager.open_project(path)
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

    def _request_exit(self) -> bool:
        if not self._confirm_abandon_changes():
            return False
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
        return raw

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
