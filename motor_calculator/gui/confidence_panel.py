"""Tkinter-native confidence and validation panel with no chart dependency."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from motor_calculator.validation.confidence_summary import EngineeringConfidenceSummary


def _format_value(value: float | None, unit: str) -> str:
    return "Unavailable" if value is None else f"{value:.4f} {unit}"


def _driver_impact(index: int, count: int) -> str:
    if index < max(1, count // 3):
        return "High impact"
    if index < max(2, (2 * count) // 3):
        return "Medium impact"
    return "Lower impact"


class ConfidencePanel(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        on_estimate: Callable[[], None],
        on_edit_assumptions: Callable[[], None],
        on_add_feedback: Callable[[], None],
        on_export: Callable[[], None],
    ) -> None:
        super().__init__(parent, padding=16)
        self._summary: EngineeringConfidenceSummary | None = None
        self._source = tk.StringVar(value="No result selected")
        self._nominal = tk.StringVar(value="Unavailable")
        self._bounds = tk.StringVar(value="Unavailable")
        self._percentiles = tk.StringVar(value="Unavailable")
        self._confidence = tk.StringVar(value="INSUFFICIENT")
        self._coverage = tk.StringVar(value="NONE")
        self._breakdown = tk.StringVar(value="Uncertainty estimate not available for this result.")
        self._drivers = tk.StringVar(value="Unavailable")
        self._evidence = tk.StringVar(value="No local validation evidence loaded.")
        self._warning = tk.StringVar(value="Run the normal calculation without any additional steps.")

        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Engineering Confidence & Validation", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self._source).pack(side=tk.RIGHT)

        ttk.Label(
            self,
            textvariable=self._warning,
            style="Warning.TLabel",
            justify=tk.LEFT,
            wraplength=900,
        ).pack(fill=tk.X, pady=(10, 14))

        metrics = ttk.LabelFrame(self, text="Prediction and estimated movement", padding=10)
        metrics.pack(fill=tk.X)
        for row, (label, variable) in enumerate((
            ("Nominal prediction", self._nominal),
            ("Estimated parameter-driven range", self._bounds),
            ("Monte Carlo P10-P90", self._percentiles),
            ("Overall engineering confidence", self._confidence),
            ("External validation coverage", self._coverage),
        )):
            ttk.Label(metrics, text=label).grid(row=row, column=0, sticky="w", padx=(0, 24), pady=2)
            ttk.Label(metrics, textvariable=variable, style="SubHeader.TLabel").grid(row=row, column=1, sticky="w", pady=2)

        self.range_canvas = tk.Canvas(self, height=92, background="#f5f2ea", highlightthickness=1, highlightbackground="#c9c2b5")
        self.range_canvas.pack(fill=tk.X, pady=12)
        self.range_canvas.bind("<Configure>", lambda _event: self._draw_range())

        details = ttk.Frame(self)
        details.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(details, text="Confidence breakdown", padding=10)
        right = ttk.LabelFrame(details, text="Validation evidence", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        ttk.Label(left, textvariable=self._breakdown, justify=tk.LEFT, wraplength=410).pack(anchor="w")
        ttk.Separator(left).pack(fill=tk.X, pady=8)
        ttk.Label(left, text="Dominant uncertainty drivers", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(left, textvariable=self._drivers, justify=tk.LEFT, wraplength=410).pack(anchor="w", pady=(4, 0))
        ttk.Label(right, textvariable=self._evidence, justify=tk.LEFT, wraplength=410).pack(anchor="w")

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(actions, text="Estimate controlled-reference uncertainty", command=on_estimate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="View / edit assumptions", command=on_edit_assumptions).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Add validation result", command=on_add_feedback).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Export local summary", command=on_export).pack(side=tk.RIGHT)

    def set_summary(self, summary: EngineeringConfidenceSummary) -> None:
        self._summary = summary
        self._source.set(summary.source_label)
        self._nominal.set(_format_value(summary.nominal_value, summary.unit))
        self._bounds.set(
            "Unavailable"
            if summary.parameter_bound_min is None or summary.parameter_bound_max is None
            else f"{summary.parameter_bound_min:.4f} - {summary.parameter_bound_max:.4f} {summary.unit}"
        )
        self._percentiles.set(
            "Unavailable"
            if summary.p10 is None or summary.p90 is None
            else f"{summary.p10:.4f} - {summary.p90:.4f} {summary.unit}"
        )
        self._confidence.set(summary.confidence_level.value)
        self._coverage.set(summary.external_validation_coverage.value)
        reasons = "\n".join(f"- {reason}" for reason in summary.confidence_reasons)
        self._breakdown.set(
            f"Numerical convergence: {summary.numerical_uncertainty_status.value}\n"
            f"Parameter uncertainty: {summary.parameter_uncertainty_status.value}\n"
            f"Model-form uncertainty: {summary.model_form_uncertainty_status.value}\n\n{reasons}"
        )
        drivers = summary.dominant_uncertainty_parameters
        self._drivers.set(
            "Unavailable" if not drivers else "\n".join(
                f"{index + 1}. {name.replace('_', ' ').title()} - {_driver_impact(index, len(drivers))}"
                for index, name in enumerate(drivers)
            )
        )
        self._evidence.set(
            f"Compatible records: {summary.compatible_validation_records}\n"
            f"High-quality records: {summary.high_quality_validation_records}\n"
            f"Coverage: {summary.external_validation_coverage.value}\n\n"
            "Evidence changes coverage only. It never changes the calculated motor result automatically."
        )
        self._warning.set(
            "Parameter uncertainty is quantified for this explicit analysis, but these intervals are not guaranteed real-world error bounds. "
            "Model-form uncertainty and external evidence must be read separately."
            if summary.parameter_bound_min is not None
            else summary.warnings[0]
        )
        self.after_idle(self._draw_range)

    def _draw_range(self) -> None:
        canvas = self.range_canvas
        canvas.delete("all")
        summary = self._summary
        width = max(canvas.winfo_width(), 400)
        if (
            summary is None
            or summary.parameter_bound_min is None
            or summary.parameter_bound_max is None
            or summary.nominal_value is None
        ):
            canvas.create_text(width / 2, 45, text="Uncertainty estimate not available for this result.", fill="#5c574f")
            return
        low, high = summary.parameter_bound_min, summary.parameter_bound_max
        if high <= low:
            canvas.create_text(width / 2, 45, text="Range is degenerate; no scale drawn.", fill="#5c574f")
            return
        left, right, y = 50.0, width - 50.0, 42.0
        scale = lambda value: left + (float(value) - low) / (high - low) * (right - left)
        canvas.create_line(left, y, right, y, width=6, fill="#b8b09f")
        if summary.p10 is not None and summary.p90 is not None:
            canvas.create_line(scale(summary.p10), y, scale(summary.p90), y, width=10, fill="#4b8b76")
        canvas.create_oval(scale(summary.nominal_value) - 6, y - 6, scale(summary.nominal_value) + 6, y + 6, fill="#c44e2f", outline="")
        markers = ((low, "bound min"), (summary.p10, "P10"), (summary.nominal_value, "nominal"), (summary.p90, "P90"), (high, "bound max"))
        for value, label in markers:
            if value is None:
                continue
            x = scale(value)
            canvas.create_line(x, y - 14, x, y + 14, fill="#4b463f")
            canvas.create_text(x, y + 28, text=f"{label}\n{value:.2f}", anchor="n", fill="#39352f", font=("TkDefaultFont", 8))
