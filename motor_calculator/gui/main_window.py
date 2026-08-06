"""Legacy GUI wrapper that delegates all electromagnetic calculations to motor_core."""

from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict
from tkinter import filedialog, messagebox, ttk

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from motor_core import LegacyGuiMotorModelBridge, MotorCalculationError, MotorValidationError, parse_legacy_gui_params

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
from motor_calculator.validation.feedback_service import submit_feedback
from motor_calculator.validation.phase7i_uncertainty_report import run_phase7i_demonstration
from motor_calculator.validation.uncertainty_models import UncertaintySpecification, load_uncertainty_specification


def _load_legacy_module():
    legacy_path = Path(__file__).resolve().parents[1] / "PMDC_Calculator_claude204.py"
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
        self._repository_root = _REPOSITORY_ROOT
        self._feedback_store = self._repository_root / "validation_data" / "user_feedback" / "feedback_records.jsonl"
        self._latest_accuracy_envelope = None
        self._engineering_confidence_summary = None
        self._user_uncertainty_parameters = None
        self._create_confidence_tab()

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
        self._set_unavailable_current_summary()

    def _export_confidence_summary(self) -> None:
        summary = self._engineering_confidence_summary
        if summary is None:
            messagebox.showinfo("Confidence export", "No confidence summary is available.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export confidence summary locally",
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


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(
            "GUI 启动失败：当前 Python 环境的 Tcl/Tk 运行时不可用，"
            "请参考 README 中的 GUI 启动说明修复 Python/Tcl/Tk 安装。"
        ) from exc
    try:
        root.iconbitmap("motor_icon.ico")
    except Exception:
        pass

    MotorCalculatorApp(root)
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x_pos = (root.winfo_screenwidth() // 2) - (width // 2)
    y_pos = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"+{x_pos}+{y_pos}")
    root.mainloop()
