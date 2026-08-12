"""Tkinter-native confidence and validation panel with no chart dependency."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from motor_calculator.i18n import input_label, localize_message, localize_status, tr
from motor_calculator.validation.confidence_summary import EngineeringConfidenceSummary


def _format_value(value: float | None, unit: str) -> str:
    return tr("common.unavailable") if value is None else f"{value:.4f} {unit}"


def _driver_impact(index: int, count: int) -> str:
    if index < max(1, count // 3):
        return tr("confidence.high_impact")
    if index < max(2, (2 * count) // 3):
        return tr("confidence.medium_impact")
    return tr("confidence.lower_impact")


def _driver_name(name: str) -> str:
    try:
        return input_label(name)
    except KeyError:
        return name


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
        self._source = tk.StringVar(value=tr("confidence.no_result"))
        self._nominal = tk.StringVar(value=tr("common.unavailable"))
        self._bounds = tk.StringVar(value=tr("common.unavailable"))
        self._percentiles = tk.StringVar(value=tr("common.unavailable"))
        self._confidence = tk.StringVar(value=localize_status("INSUFFICIENT"))
        self._coverage = tk.StringVar(value=localize_status("NONE"))
        self._breakdown = tk.StringVar(value=tr("confidence.no_estimate"))
        self._drivers = tk.StringVar(value=tr("common.unavailable"))
        self._evidence = tk.StringVar(value=tr("confidence.no_evidence"))
        self._warning = tk.StringVar(value=tr("confidence.run_normal"))

        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        ttk.Label(header, text=tr("confidence.title"), style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self._source).pack(side=tk.RIGHT)

        ttk.Label(
            self,
            textvariable=self._warning,
            style="Warning.TLabel",
            justify=tk.LEFT,
            wraplength=900,
        ).pack(fill=tk.X, pady=(10, 14))

        metrics = ttk.LabelFrame(self, text=tr("confidence.metrics"), padding=10)
        metrics.pack(fill=tk.X)
        for index, (label, variable) in enumerate((
            (tr("confidence.nominal"), self._nominal),
            (tr("confidence.range"), self._bounds),
            (tr("confidence.monte_carlo"), self._percentiles),
            (tr("confidence.overall"), self._confidence),
            (tr("confidence.coverage"), self._coverage),
        )):
            row, block = divmod(index, 2)
            column = block * 2
            ttk.Label(metrics, text=label).grid(
                row=row, column=column, sticky="w", padx=(0, 16), pady=2
            )
            ttk.Label(metrics, textvariable=variable, style="SubHeader.TLabel").grid(
                row=row, column=column + 1, sticky="w", padx=(0, 28), pady=2
            )

        self.range_canvas = tk.Canvas(self, height=92, background="#f5f2ea", highlightthickness=1, highlightbackground="#c9c2b5")
        self.range_canvas.pack(fill=tk.X, pady=12)
        self.range_canvas.bind("<Configure>", lambda _event: self._draw_range())

        self.actions = ttk.Frame(self)
        self.actions.pack(side=tk.BOTTOM, fill=tk.X, pady=(14, 0))
        ttk.Button(self.actions, text=tr("confidence.estimate"), command=on_estimate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(self.actions, text=tr("confidence.edit"), command=on_edit_assumptions).pack(side=tk.LEFT, padx=6)
        ttk.Button(self.actions, text=tr("confidence.add"), command=on_add_feedback).pack(side=tk.LEFT, padx=6)
        ttk.Button(self.actions, text=tr("confidence.export"), command=on_export).pack(side=tk.RIGHT)

        details = ttk.Frame(self)
        details.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(details, text=tr("confidence.breakdown"), padding=10)
        right = ttk.LabelFrame(details, text=tr("confidence.evidence"), padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        ttk.Label(left, textvariable=self._breakdown, justify=tk.LEFT, wraplength=410).pack(anchor="w")
        ttk.Separator(left).pack(fill=tk.X, pady=8)
        ttk.Label(left, text=tr("confidence.drivers"), style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(left, textvariable=self._drivers, justify=tk.LEFT, wraplength=410).pack(anchor="w", pady=(4, 0))
        ttk.Label(right, textvariable=self._evidence, justify=tk.LEFT, wraplength=410).pack(anchor="w")


    def set_summary(self, summary: EngineeringConfidenceSummary) -> None:
        self._summary = summary
        self._source.set(summary.source_label)
        self._nominal.set(_format_value(summary.nominal_value, summary.unit))
        self._bounds.set(
            tr("common.unavailable")
            if summary.parameter_bound_min is None or summary.parameter_bound_max is None
            else f"{summary.parameter_bound_min:.4f} - {summary.parameter_bound_max:.4f} {summary.unit}"
        )
        self._percentiles.set(
            tr("common.unavailable")
            if summary.p10 is None or summary.p90 is None
            else f"{summary.p10:.4f} - {summary.p90:.4f} {summary.unit}"
        )
        self._confidence.set(localize_status(summary.confidence_level))
        self._coverage.set(localize_status(summary.external_validation_coverage))
        reasons = "\n".join(f"- {localize_message(reason)}" for reason in summary.confidence_reasons)
        self._breakdown.set(
            f"{tr('confidence.numerical')}：{localize_status(summary.numerical_uncertainty_status)}\n"
            f"{tr('confidence.parameter')}：{localize_status(summary.parameter_uncertainty_status)}\n"
            f"{tr('confidence.model_form')}：{localize_status(summary.model_form_uncertainty_status)}\n\n{reasons}"
        )
        drivers = summary.dominant_uncertainty_parameters
        self._drivers.set(
            tr("common.unavailable") if not drivers else "\n".join(
                f"{index + 1}. {_driver_name(name)} - {_driver_impact(index, len(drivers))}"
                for index, name in enumerate(drivers)
            )
        )
        self._evidence.set(
            f"{tr('confidence.compatible')}：{summary.compatible_validation_records}\n"
            f"{tr('confidence.high_quality')}：{summary.high_quality_validation_records}\n"
            f"{tr('confidence.coverage')}：{localize_status(summary.external_validation_coverage)}\n\n"
            f"{tr('confidence.evidence_note')}"
        )
        self._warning.set(
            tr("confidence.parameter_warning")
            if summary.parameter_bound_min is not None
            else localize_message(summary.warnings[0])
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
            canvas.create_text(width / 2, 45, text=tr("confidence.no_estimate"), fill="#5c574f")
            return
        low, high = summary.parameter_bound_min, summary.parameter_bound_max
        if high <= low:
            canvas.create_text(width / 2, 45, text=tr("confidence.degenerate"), fill="#5c574f")
            return
        left, right, y = 50.0, width - 50.0, 42.0
        scale = lambda value: left + (float(value) - low) / (high - low) * (right - left)
        canvas.create_line(left, y, right, y, width=6, fill="#b8b09f")
        if summary.p10 is not None and summary.p90 is not None:
            canvas.create_line(scale(summary.p10), y, scale(summary.p90), y, width=10, fill="#4b8b76")
        canvas.create_oval(scale(summary.nominal_value) - 6, y - 6, scale(summary.nominal_value) + 6, y + 6, fill="#c44e2f", outline="")
        markers = (
            (low, tr("confidence.bound_min")),
            (summary.p10, "P10"),
            (summary.nominal_value, tr("confidence.nominal_marker")),
            (summary.p90, "P90"),
            (high, tr("confidence.bound_max")),
        )
        for value, label in markers:
            if value is None:
                continue
            x = scale(value)
            canvas.create_line(x, y - 14, x, y + 14, fill="#4b463f")
            canvas.create_text(x, y + 28, text=f"{label}\n{value:.2f}", anchor="n", fill="#39352f", font=("TkDefaultFont", 8))
