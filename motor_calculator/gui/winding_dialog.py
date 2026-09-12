"""Phase 10G: the winding engineering dialog.

Its own entry in the analysis menu rather than a tab inside the FEA validation
dialog, because winding factors and slot fill are ordinary design questions. A
user deciding whether 50 turns of 0.9 mm wire will fit should not have to open a
finite-element validation window to find out.

The dialog holds no engineering logic. It reads the design, calls the winding
and slot-fill engines, and renders what they return with their provenance
attached.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Mapping

from ..winding.panel_text import build_winding_panel_rows, render_winding_panel_zh
from ..winding.report import build_winding_report
from ..winding.slot_fill import (
    DEFAULT_PACKING_FACTOR,
    ConductorSpec,
    SlotGeometry,
    compute_slot_fill,
)

#: Declared allowances. Engineering assumptions, shown as editable inputs so a
#: user is never silently held to a number they did not choose.
DEFAULT_LINER_THICKNESS_MM = 0.25
DEFAULT_CLEARANCE_MM = 0.10
DEFAULT_INSULATION_RATIO = 1.08

NO_SLOT_GEOMETRY_MESSAGE_ZH = (
    "当前设计为无槽（无铁芯）结构，没有槽几何，因此不计算槽利用率。\n"
    "绕组系数部分仍然有效。"
)


class WindingEngineeringDialog:
    """A read-only engineering view of the winding and the slot."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        parameters_provider: Callable[[], Mapping[str, object]],
        meshed_factor_provider: Callable[[], tuple[float | None, float | None]] | None = None,
    ) -> None:
        self._parameters_provider = parameters_provider
        self._meshed_factor_provider = meshed_factor_provider

        self.window = tk.Toplevel(master)
        self.window.title("绕组工程")
        self.window.geometry("880x720")

        ttk.Label(
            self.window,
            text="绕组系数、导体与槽利用率。所有数值标注来源；工程假设可在下方调整。",
            wraplength=840,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=10, pady=(10, 4))

        self._build_assumptions()
        self._build_output()
        ttk.Button(self.window, text="关闭", command=self.window.destroy).pack(
            side=tk.RIGHT, padx=10, pady=(0, 10)
        )
        self.refresh()

    # ------------------------------------------------------------------
    def _build_assumptions(self) -> None:
        frame = ttk.LabelFrame(self.window, text="工程假设（可调整）")
        frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.liner_var = tk.StringVar(value=f"{DEFAULT_LINER_THICKNESS_MM:.2f}")
        self.clearance_var = tk.StringVar(value=f"{DEFAULT_CLEARANCE_MM:.2f}")
        self.insulation_var = tk.StringVar(value=f"{DEFAULT_INSULATION_RATIO:.3f}")
        self.packing_var = tk.StringVar(value=f"{DEFAULT_PACKING_FACTOR:.2f}")
        self.layers_var = tk.StringVar(value="2")

        for column, (label, variable) in enumerate(
            (
                ("槽绝缘厚度 (mm)", self.liner_var),
                ("间隙 (mm)", self.clearance_var),
                ("绝缘线径比", self.insulation_var),
                ("装填系数", self.packing_var),
                ("层数", self.layers_var),
            )
        ):
            ttk.Label(frame, text=f"{label}：").grid(
                row=0, column=column * 2, sticky=tk.W, padx=(8, 2), pady=6
            )
            ttk.Entry(frame, textvariable=variable, width=8).grid(
                row=0, column=column * 2 + 1, sticky=tk.W, padx=(0, 8), pady=6
            )
        ttk.Button(frame, text="重新计算", command=self.refresh).grid(
            row=0, column=10, padx=8, pady=6
        )

    def _build_output(self) -> None:
        frame = ttk.Frame(self.window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self.text = tk.Text(frame, wrap=tk.WORD, height=26)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    def _float(self, variable: tk.StringVar, fallback: float) -> float:
        try:
            return float(variable.get())
        except (TypeError, ValueError):
            return fallback

    def build_sections(self):
        """Compute the panel content. Separated so it can be tested headlessly."""

        parameters = dict(self._parameters_provider())
        warnings: list[str] = []

        slots = int(parameters.get("slots") or 0)
        pole_pairs = int(parameters.get("p") or 0)
        if slots <= 0 or pole_pairs <= 0:
            return (), ("缺少槽数或极对数，无法计算绕组。",), ()

        meshed = width_factor = None
        if self._meshed_factor_provider is not None:
            try:
                meshed, width_factor = self._meshed_factor_provider()
            except Exception:  # noqa: BLE001 - a failed probe must not break the view
                meshed = width_factor = None

        layers = max(1, int(self._float(self.layers_var, 2.0)))
        report = build_winding_report(
            slots=slots,
            pole_pairs=pole_pairs,
            coil_span_slots=float(parameters.get("coil_span_slots") or 1),
            layers=layers,
            parallel_paths=int(parameters.get("n_parallel") or 1),
            entered_winding_factor=(
                float(parameters["k_w"]) if parameters.get("k_w") is not None else None
            ),
            entered_provenance="USER_INPUT",
            meshed_winding_factor=meshed,
            finite_width_factor=width_factor,
        )

        fill = None
        coreless = bool(parameters.get("coreless")) or str(parameters.get("slot_type")) == "无槽"
        if coreless:
            warnings.append(NO_SLOT_GEOMETRY_MESSAGE_ZH)
        else:
            try:
                geometry = SlotGeometry(
                    slot_count=slots,
                    top_width_mm=float(parameters["w_slot_top"]),
                    bottom_width_mm=float(parameters["w_slot_bottom"]),
                    depth_mm=float(parameters["h_slot"]),
                    wedge_height_mm=float(parameters.get("h_wedge") or 0.0),
                    liner_thickness_mm=self._float(self.liner_var, DEFAULT_LINER_THICKNESS_MM),
                    clearance_mm=self._float(self.clearance_var, DEFAULT_CLEARANCE_MM),
                )
                bare = float(parameters["d_wire"])
                conductor = ConductorSpec(
                    bare_diameter_mm=bare,
                    insulated_diameter_mm=bare
                    * self._float(self.insulation_var, DEFAULT_INSULATION_RATIO),
                    parallel_strands=int(parameters.get("n_parallel") or 1),
                )
                turns_per_phase = float(parameters["N_ph_turns"])
                turns_per_coil_side = turns_per_phase * report.phases / slots
                fill = compute_slot_fill(
                    geometry=geometry,
                    conductor=conductor,
                    turns_per_coil=turns_per_coil_side,
                    coil_sides_per_slot=layers,
                    packing_factor=self._float(self.packing_var, DEFAULT_PACKING_FACTOR),
                )
                warnings.extend(fill.warnings)
            except (KeyError, TypeError, ValueError) as error:
                warnings.append(f"槽利用率无法计算：{error}")

        sections = build_winding_panel_rows(report=report, fill=fill)
        return sections, tuple(warnings), report.notes_zh

    def refresh(self) -> None:
        sections, warnings, notes = self.build_sections()
        content = render_winding_panel_zh(sections, warnings=warnings, notes=notes)
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.configure(state=tk.DISABLED)
