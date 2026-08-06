"""Optional Tk validation-feedback dialog and pure result formatter."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from motor_calculator.validation.feedback_models import (
    EnvelopeComparison,
    FeedbackComparability,
    FeedbackFormModel,
    MetricSemantics,
    ValidationEvidenceType,
    ValidationFeedbackRecord,
)


EVIDENCE_TYPE_LABELS = {
    "Bench measurement - physical motor test": ValidationEvidenceType.BENCH_MEASUREMENT,
    "Published experiment - traceable publication": ValidationEvidenceType.PUBLISHED_EXPERIMENT,
    "FEA result - independent field solver": ValidationEvidenceType.FEA,
    "Manufacturer data - supplier information": ValidationEvidenceType.MANUFACTURER_DATA,
    "Analytical reference - equation/reference case": ValidationEvidenceType.ANALYTICAL_REFERENCE,
    "Other - unclassified evidence": ValidationEvidenceType.OTHER,
}


@dataclass(frozen=True)
class FeedbackMetricOption:
    metric_name: str
    predicted_value: float
    unit: str
    semantics: MetricSemantics


@dataclass(frozen=True)
class FeedbackDialogValues:
    metric_name: str
    reference_value: float
    reference_unit: str
    evidence_type: ValidationEvidenceType
    speed_rpm: float
    current_a: float | None
    voltage_v: float | None
    temperature_c: float | None
    source_name: str | None
    source_reference: str | None
    notes: str
    reference_semantics: MetricSemantics


def _optional_number(value: str) -> float | None:
    return None if not value.strip() else float(value)


def format_feedback_submission_result(
    record: ValidationFeedbackRecord,
    envelope_comparison: EnvelopeComparison | None = None,
) -> str:
    lines = [
        f"Compatibility: {record.comparability.value}",
        f"Evidence quality: {record.evidence_quality.value}",
        f"Prediction: {record.predicted_value:.4f} {record.unit}",
        f"Reference: {record.reference_value:.4f} {record.reference_unit}",
    ]
    if record.comparability.value == FeedbackComparability.BLOCKED.value:
        lines.extend((
            "Numerical error: not computed",
            "Reason: No approved unit/semantic transformation is available.",
        ))
    else:
        lines.append(f"Signed error: {record.signed_error:+.4f} {record.unit}")
        lines.append(
            "APE: unavailable for a near-zero reference"
            if record.absolute_percentage_error is None
            else f"APE: {record.absolute_percentage_error:.4f}%"
        )
    if envelope_comparison is not None:
        lines.append(f"Reference vs uncertainty envelope: {envelope_comparison.position.value}")
    lines.append("The record was stored as local evidence only; no calibration was performed.")
    return "\n".join(lines)


class ValidationFeedbackDialog:
    def __init__(self, parent, metric_options: dict[str, FeedbackMetricOption], *, default_speed: float) -> None:
        self.result: FeedbackDialogValues | None = None
        self.metric_options = metric_options
        self.window = tk.Toplevel(parent)
        self.window.title("Add Validation Result")
        self.window.transient(parent)
        self.window.grab_set()
        frame = ttk.Frame(self.window, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)
        self.vars = {
            "metric": tk.StringVar(value=next(iter(metric_options), "")),
            "reference": tk.StringVar(),
            "unit": tk.StringVar(),
            "evidence": tk.StringVar(value=next(iter(EVIDENCE_TYPE_LABELS))),
            "speed": tk.StringVar(value=f"{default_speed:g}"),
            "current": tk.StringVar(),
            "voltage": tk.StringVar(),
            "temperature": tk.StringVar(),
            "source_name": tk.StringVar(),
            "source_reference": tk.StringVar(),
            "scope": tk.StringVar(),
            "kind": tk.StringVar(),
            "waveform": tk.StringVar(),
            "torque_boundary": tk.StringVar(),
            "current_basis": tk.StringVar(),
        }
        self.prediction_text = tk.StringVar()
        rows = (
            ("Metric", "metric"), ("Reference / measured value", "reference"),
            ("Reference unit", "unit"), ("Evidence type", "evidence"),
            ("Speed (rpm)", "speed"), ("Current (A, optional)", "current"),
            ("Voltage (V, optional)", "voltage"), ("Temperature (C, optional)", "temperature"),
            ("Source name", "source_name"), ("Source reference", "source_reference"),
        )
        for row, (label, key) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            if key == "metric":
                widget = ttk.Combobox(frame, textvariable=self.vars[key], values=tuple(metric_options), state="readonly", width=46)
                widget.bind("<<ComboboxSelected>>", lambda _event: self._load_metric_defaults())
            elif key == "evidence":
                widget = ttk.Combobox(frame, textvariable=self.vars[key], values=tuple(EVIDENCE_TYPE_LABELS), state="readonly", width=46)
            else:
                widget = ttk.Entry(frame, textvariable=self.vars[key], width=49)
            widget.grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(frame, text="Prediction").grid(row=len(rows), column=0, sticky="w")
        ttk.Label(frame, textvariable=self.prediction_text, style="SubHeader.TLabel").grid(row=len(rows), column=1, sticky="w")

        advanced = ttk.LabelFrame(frame, text="Reference semantics", padding=8)
        advanced.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="ew", pady=10)
        for row, (label, key) in enumerate((
            ("Quantity scope", "scope"), ("RMS / peak", "kind"), ("Waveform", "waveform"),
            ("Torque boundary", "torque_boundary"), ("Current basis", "current_basis"),
        )):
            ttk.Label(advanced, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(advanced, textvariable=self.vars[key], width=38).grid(row=row, column=1, sticky="ew", pady=1)
        ttk.Label(frame, text="Notes").grid(row=len(rows) + 2, column=0, sticky="nw")
        self.notes = tk.Text(frame, width=48, height=4)
        self.notes.grid(row=len(rows) + 2, column=1, sticky="ew")
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(rows) + 3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.window.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text="Save local evidence", command=self._submit).pack(side=tk.RIGHT, padx=4)
        frame.columnconfigure(1, weight=1)
        self._load_metric_defaults()

    def _load_metric_defaults(self) -> None:
        option = self.metric_options.get(self.vars["metric"].get())
        if option is None:
            return
        self.prediction_text.set(f"{option.predicted_value:.4f} {option.unit}")
        self.vars["unit"].set(option.unit)
        semantics = option.semantics
        for key, value in (
            ("scope", semantics.quantity_scope), ("kind", semantics.rms_peak_semantics),
            ("waveform", semantics.waveform_semantics), ("torque_boundary", semantics.torque_boundary),
            ("current_basis", semantics.current_basis),
        ):
            self.vars[key].set(value or "")

    def _submit(self) -> None:
        form = FeedbackFormModel(
            metric=self.vars["metric"].get(),
            predicted_value=str(self.metric_options[self.vars["metric"].get()].predicted_value),
            reference_value=self.vars["reference"].get(),
            evidence_source=self.vars["source_reference"].get(),
            speed_rpm=self.vars["speed"].get(),
            current_a=self.vars["current"].get(),
            voltage_v=self.vars["voltage"].get(),
            temperature_c=self.vars["temperature"].get(),
            notes=self.notes.get("1.0", tk.END).strip(),
        )
        messages = form.validate_for_display()
        if messages:
            messagebox.showerror("Validation feedback", "\n".join(messages), parent=self.window)
            return
        try:
            self.result = FeedbackDialogValues(
                metric_name=self.vars["metric"].get(),
                reference_value=float(self.vars["reference"].get()),
                reference_unit=self.vars["unit"].get().strip(),
                evidence_type=EVIDENCE_TYPE_LABELS[self.vars["evidence"].get()],
                speed_rpm=float(self.vars["speed"].get()),
                current_a=_optional_number(self.vars["current"].get()),
                voltage_v=_optional_number(self.vars["voltage"].get()),
                temperature_c=_optional_number(self.vars["temperature"].get()),
                source_name=self.vars["source_name"].get().strip() or None,
                source_reference=self.vars["source_reference"].get().strip() or None,
                notes=form.notes,
                reference_semantics=MetricSemantics(
                    quantity_scope=self.vars["scope"].get().strip() or None,
                    rms_peak_semantics=self.vars["kind"].get().strip() or None,
                    waveform_semantics=self.vars["waveform"].get().strip() or None,
                    torque_boundary=self.vars["torque_boundary"].get().strip() or None,
                    current_basis=self.vars["current_basis"].get().strip() or None,
                ),
            )
        except ValueError as exc:
            messagebox.showerror("Validation feedback", str(exc), parent=self.window)
            return
        self.window.destroy()

    def show(self) -> FeedbackDialogValues | None:
        self.window.wait_window()
        return self.result
