"""Interaction-first controls layered over exact legacy input variables."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Mapping

from motor_calculator.input_ux import (
    INPUT_DEFINITIONS,
    SLIDER_SPECS,
    DisplayUnitPreferences,
    slider_from_numeric_text,
    slider_range_for_units,
    slider_to_numeric_text,
)
from motor_calculator.presets import PresetDefinition, PresetRegistry


class ToolTip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self._show, add=True)
        widget.bind("<Leave>", self._hide, add=True)

    def _show(self, _event=None) -> None:
        if self.window is not None or not self.text:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{self.widget.winfo_rootx() + 18}+{self.widget.winfo_rooty() + 22}")
        ttk.Label(
            self.window, text=self.text, justify=tk.LEFT, wraplength=360,
            relief=tk.SOLID, borderwidth=1, padding=7,
        ).pack()

    def _hide(self, _event=None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class GuidedInputPanel:
    def __init__(
        self,
        parent,
        field_vars: Mapping[str, tk.Variable],
        registry: PresetRegistry,
        *,
        preferences: DisplayUnitPreferences,
        on_mode_change: Callable[[str], None],
        on_unit_change: Callable[[str, str], None],
        on_apply_preset: Callable[[str], bool],
        on_preset_details: Callable[[str], None],
        on_reset_field: Callable[[str], None],
        on_reset_guided: Callable[[], None],
        on_help: Callable[[], None],
    ) -> None:
        self.parent = parent
        self.field_vars = field_vars
        self.registry = registry
        self.preferences = preferences
        self.on_mode_change = on_mode_change
        self.on_unit_change = on_unit_change
        self.on_apply_preset = on_apply_preset
        self.on_preset_details = on_preset_details
        self.on_reset_field = on_reset_field
        self.on_reset_guided = on_reset_guided
        self.on_help = on_help
        self._syncing = False
        self.mode_var = tk.StringVar(value="ADVANCED")
        self.length_unit_var = tk.StringVar(value=preferences.length)
        self.speed_unit_var = tk.StringVar(value=preferences.speed)
        self.temperature_unit_var = tk.StringVar(value=preferences.temperature)
        self.preset_var = tk.StringVar()
        self.magnet_var = tk.StringVar(value=str(field_vars["magnet_grade"].get()))
        self.guidance_var = tk.StringVar(value="Guidance: inputs not yet evaluated")
        self.slider_status_vars: dict[str, tk.StringVar] = {}
        self.slider_unit_vars: dict[str, tk.StringVar] = {}
        self.sliders: dict[str, ttk.Scale] = {}
        self._preset_by_label = {preset.display_name: preset for preset in registry.presets}
        self._build()
        self._field_traces = [
            field_vars[name].trace_add("write", lambda *_args, field=name: self.sync_field(field))
            for name in SLIDER_SPECS
        ]
        self._magnet_trace = field_vars["magnet_grade"].trace_add("write", self._sync_magnet_selector)
        self.refresh_all()

    def _build(self) -> None:
        self.frame = ttk.LabelFrame(self.parent, text="Guided Input (starting aids, not optimization)", padding=7)
        mode_row = ttk.Frame(self.frame)
        mode_row.pack(fill=tk.X)
        ttk.Label(mode_row, text="Input mode:").pack(side=tk.LEFT)
        for value in ("BASIC", "ADVANCED"):
            ttk.Radiobutton(
                mode_row, text=value.title(), value=value, variable=self.mode_var,
                command=lambda selected=value: self.on_mode_change(selected),
            ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(mode_row, text="Help", width=7, command=self.on_help).pack(side=tk.RIGHT)

        preset_row = ttk.Frame(self.frame)
        preset_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(preset_row, text="Starting template:").pack(side=tk.LEFT)
        template_labels = [
            preset.display_name for preset in self.registry.presets
            if preset.category.value != "magnet_material"
        ]
        self.preset_combo = ttk.Combobox(
            preset_row, textvariable=self.preset_var, values=template_labels,
            state="readonly", width=27,
        )
        self.preset_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        if template_labels:
            self.preset_var.set(template_labels[0])
        ttk.Button(preset_row, text="Preview / Apply", command=self._apply_selected).pack(side=tk.LEFT)
        ttk.Button(preset_row, text="Info", width=5, command=self._details_selected).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        magnet_row = ttk.Frame(self.frame)
        magnet_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(magnet_row, text="Magnet grade:").pack(side=tk.LEFT)
        magnet_values = ["Custom", "N35", "N42", "N48", "N52"]
        self.magnet_combo = ttk.Combobox(
            magnet_row, textvariable=self.magnet_var, values=magnet_values,
            state="readonly", width=12,
        )
        self.magnet_combo.pack(side=tk.LEFT, padx=5)
        self.magnet_combo.bind("<<ComboboxSelected>>", self._apply_magnet_selected)
        ttk.Label(magnet_row, text="Partial preset; Br remains editable").pack(side=tk.LEFT)

        units = ttk.Frame(self.frame)
        units.pack(fill=tk.X, pady=(6, 2))
        self._unit_selector(units, "Length", self.length_unit_var, ("mm", "m"), "length")
        self._unit_selector(units, "Speed", self.speed_unit_var, ("rpm", "rad/s"), "speed")
        self._unit_selector(units, "Temp", self.temperature_unit_var, ("degC", "K"), "temperature")

        quick = ttk.LabelFrame(self.frame, text="Quick adjust + exact entry", padding=5)
        quick.pack(fill=tk.X, pady=(5, 0))
        labels = {"g_side": "Air gap", "n_rated": "Speed", "k_w": "Winding factor"}
        for row, field in enumerate(("g_side", "n_rated", "k_w")):
            ttk.Label(quick, text=labels[field], width=14).grid(row=row * 2, column=0, sticky="w")
            minimum, maximum, _step = slider_range_for_units(SLIDER_SPECS[field], self.preferences)
            scale = ttk.Scale(
                quick, from_=minimum, to=maximum, orient=tk.HORIZONTAL,
                command=lambda value, name=field: self._slider_moved(name, value),
            )
            scale.grid(row=row * 2, column=1, sticky="ew", padx=4)
            exact = ttk.Entry(quick, textvariable=self.field_vars[field], width=12)
            exact.grid(row=row * 2, column=2, padx=(3, 2))
            unit_var = tk.StringVar()
            ttk.Label(quick, textvariable=unit_var, width=6).grid(row=row * 2, column=3, sticky="w")
            ttk.Button(
                quick, text="Reset", width=6,
                command=lambda name=field: self.on_reset_field(name),
            ).grid(row=row * 2, column=4, padx=(3, 0))
            status = tk.StringVar()
            ttk.Label(quick, textvariable=status, foreground="#7A4D00").grid(
                row=row * 2 + 1, column=1, columnspan=4, sticky="w", padx=4,
            )
            quick.columnconfigure(1, weight=1)
            self.sliders[field] = scale
            self.slider_status_vars[field] = status
            self.slider_unit_vars[field] = unit_var
            ToolTip(exact, INPUT_DEFINITIONS[field].tooltip)

        discrete = ttk.Frame(self.frame)
        discrete.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(discrete, text="Pole pairs:").pack(side=tk.LEFT)
        self.pole_spinbox = ttk.Spinbox(
            discrete, from_=1, to=1_000_000_000, increment=1,
            textvariable=self.field_vars["p"], width=8,
        )
        self.pole_spinbox.pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(discrete, text="Waveform:").pack(side=tk.LEFT)
        self.waveform_combo = ttk.Combobox(
            discrete, textvariable=self.field_vars["waveform"],
            values=("正弦波", "梯形波"), state="readonly", width=10,
        )
        self.waveform_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(discrete, text="Reset quick fields", command=self.on_reset_guided).pack(side=tk.RIGHT)
        ToolTip(self.pole_spinbox, INPUT_DEFINITIONS["p"].tooltip)
        ToolTip(self.waveform_combo, INPUT_DEFINITIONS["waveform"].tooltip)

        ttk.Label(
            self.frame, textvariable=self.guidance_var, wraplength=430,
            foreground="#7A4D00", justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(6, 0))

    def _unit_selector(self, parent, label: str, variable: tk.StringVar, values, quantity: str) -> None:
        ttk.Label(parent, text=f"{label}:").pack(side=tk.LEFT)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=6)
        combo.pack(side=tk.LEFT, padx=(3, 8))
        combo.bind("<<ComboboxSelected>>", lambda _event: self.on_unit_change(quantity, variable.get()))

    def _selected_preset(self) -> PresetDefinition | None:
        return self._preset_by_label.get(self.preset_var.get())

    def _apply_selected(self) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self.on_apply_preset(preset.preset_id)

    def _details_selected(self) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self.on_preset_details(preset.preset_id)

    def _apply_magnet_selected(self, _event=None) -> None:
        grade = self.magnet_var.get()
        if grade == "Custom":
            return
        applied = self.on_apply_preset(f"magnet.{grade.lower()}.v1")
        if not applied:
            self._sync_magnet_selector()

    def _sync_magnet_selector(self, *_args) -> None:
        grade = str(self.field_vars["magnet_grade"].get())
        self.magnet_var.set(grade if grade in {"N35", "N42", "N48", "N52"} else "Custom")

    def _slider_moved(self, field: str, value: str) -> None:
        if self._syncing:
            return
        result = slider_to_numeric_text(float(value), SLIDER_SPECS[field], self.preferences)
        self.slider_status_vars[field].set(result.guidance)
        self.field_vars[field].set(result.numeric_text)

    def sync_field(self, field: str) -> None:
        if self._syncing:
            return
        result = slider_from_numeric_text(str(self.field_vars[field].get()), SLIDER_SPECS[field], self.preferences)
        self.slider_status_vars[field].set(result.guidance)
        if result.slider_value is not None:
            self._syncing = True
            try:
                self.sliders[field].set(result.slider_value)
            finally:
                self._syncing = False

    def set_preferences(self, preferences: DisplayUnitPreferences) -> None:
        self.preferences = preferences
        self.length_unit_var.set(preferences.length)
        self.speed_unit_var.set(preferences.speed)
        self.temperature_unit_var.set(preferences.temperature)
        self.refresh_all()

    def set_mode(self, mode: str) -> None:
        self.mode_var.set(mode)

    def refresh_all(self) -> None:
        for field, spec in SLIDER_SPECS.items():
            minimum, maximum, _step = slider_range_for_units(spec, self.preferences)
            self.sliders[field].configure(from_=minimum, to=maximum)
            if spec.quantity == "length":
                unit = self.preferences.length
            elif spec.quantity == "speed":
                unit = self.preferences.speed
            else:
                unit = "-"
            self.slider_unit_vars[field].set(unit)
            self.sync_field(field)

    def set_guidance(self, text: str) -> None:
        self.guidance_var.set(text)
