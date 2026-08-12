"""Explicit local uncertainty-assumption editor for the controlled demo."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from motor_calculator.i18n import localize_status, parameter_label, tr
from motor_calculator.validation.uncertainty_form import UncertaintyInputRow, rows_from_parameters
from motor_calculator.validation.uncertainty_models import ParameterUncertainty, UncertaintyKind


class UncertaintyAssumptionDialog:
    def __init__(self, parent, parameters: tuple[ParameterUncertainty, ...]) -> None:
        self.result: tuple[ParameterUncertainty, ...] | None = None
        self.rows = {row.parameter_name: row for row in rows_from_parameters(parameters)}
        self._parameter_by_label = {parameter_label(name): name for name in self.rows}
        self._kind_by_label = {
            tr(f"uncertainty.kind.{kind.value.lower()}"): kind.value for kind in UncertaintyKind
        }
        self.window = tk.Toplevel(parent)
        self.window.title(tr("uncertainty.title"))
        self.window.transient(parent)
        self.window.grab_set()
        frame = ttk.Frame(self.window, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text=tr("uncertainty.intro"),
            style="Warning.TLabel",
            wraplength=700,
        ).pack(fill=tk.X, pady=(0, 10))
        selector = ttk.Frame(frame)
        selector.pack(fill=tk.X)
        ttk.Label(selector, text=tr("uncertainty.parameter")).pack(side=tk.LEFT)
        self.parameter_name = tk.StringVar(value=next(iter(self._parameter_by_label)))
        combo = ttk.Combobox(
            selector, textvariable=self.parameter_name, values=tuple(self._parameter_by_label),
            state="readonly", width=36,
        )
        combo.pack(side=tk.LEFT, padx=8)
        combo.bind("<<ComboboxSelected>>", lambda _event: self._load())
        self.values = {name: tk.StringVar() for name in (
            "nominal_value", "uncertainty_kind", "lower_bound", "upper_bound", "mean", "standard_deviation", "provenance"
        )}
        editor = ttk.LabelFrame(frame, text=tr("uncertainty.declaration"), padding=10)
        editor.pack(fill=tk.X, pady=10)
        for row, (label, key) in enumerate((
            (tr("uncertainty.nominal"), "nominal_value"), (tr("uncertainty.type"), "uncertainty_kind"),
            (tr("uncertainty.lower"), "lower_bound"), (tr("uncertainty.upper"), "upper_bound"),
            (tr("uncertainty.mean"), "mean"), (tr("uncertainty.std"), "standard_deviation"),
            (tr("uncertainty.provenance"), "provenance"),
        )):
            ttk.Label(editor, text=label).grid(row=row, column=0, sticky="w", pady=2)
            if key == "uncertainty_kind":
                widget = ttk.Combobox(
                    editor, textvariable=self.values[key], values=tuple(self._kind_by_label), state="readonly"
                )
            else:
                widget = ttk.Entry(editor, textvariable=self.values[key], width=58)
            widget.grid(row=row, column=1, sticky="ew", pady=2)
        editor.columnconfigure(1, weight=1)
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text=tr("uncertainty.save_parameter"), command=self._save_current).pack(side=tk.LEFT)
        ttk.Button(buttons, text=tr("common.cancel"), command=self.window.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=tr("uncertainty.apply"), command=self._apply).pack(side=tk.RIGHT, padx=4)
        self._load()

    def _load(self) -> None:
        row = self.rows[self._selected_parameter_name()]
        for name in self.values:
            value = getattr(row, name)
            self.values[name].set(
                tr(f"uncertainty.kind.{str(value).lower()}") if name == "uncertainty_kind" else value
            )

    def _save_current(self) -> bool:
        old = self.rows[self._selected_parameter_name()]
        candidate = UncertaintyInputRow(
            parameter_name=old.parameter_name,
            unit=old.unit,
            nominal_value=self.values["nominal_value"].get(),
            uncertainty_kind=self._kind_by_label.get(
                self.values["uncertainty_kind"].get(), self.values["uncertainty_kind"].get()
            ),
            lower_bound=self.values["lower_bound"].get(),
            upper_bound=self.values["upper_bound"].get(),
            mean=self.values["mean"].get(),
            standard_deviation=self.values["standard_deviation"].get(),
            provenance=self.values["provenance"].get(),
            confidence="user_declared",
        )
        try:
            candidate.to_parameter_uncertainty()
        except ValueError as exc:
            messagebox.showerror(tr("uncertainty.error_title"), tr("uncertainty.invalid_current"), parent=self.window)
            return False
        self.rows[candidate.parameter_name] = candidate
        return True

    def _apply(self) -> None:
        if not self._save_current():
            return
        try:
            self.result = tuple(row.to_parameter_uncertainty() for row in self.rows.values())
        except ValueError as exc:
            messagebox.showerror(tr("uncertainty.error_title"), tr("uncertainty.invalid_all"), parent=self.window)
            return
        self.window.destroy()

    def _selected_parameter_name(self) -> str:
        return self._parameter_by_label.get(self.parameter_name.get(), self.parameter_name.get())

    def show(self) -> tuple[ParameterUncertainty, ...] | None:
        self.window.wait_window()
        return self.result
