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

from ..winding.authority import (
    AUTHORITY_LABELS_ZH,
    WindingAuthority,
    resolve_production_winding_factor,
)
from ..winding.evaluation import evaluate_winding
from ..winding.panel_text import build_winding_panel_rows, render_winding_panel_zh
from ..winding.persistence import WindingProjectState
from ..winding.slot_fill import DEFAULT_PACKING_FACTOR

#: Declared allowances. Engineering assumptions, shown as editable inputs so a
#: user is never silently held to a number they did not choose.
DEFAULT_LINER_THICKNESS_MM = 0.25
DEFAULT_CLEARANCE_MM = 0.10
DEFAULT_INSULATION_RATIO = 1.08

NO_SLOT_GEOMETRY_MESSAGE_ZH = (
    "当前设计为无槽（无铁芯）结构，没有槽几何，因此不计算槽利用率。\n"
    "绕组系数部分仍然有效。"
)


def _authority_rows(production):
    """Rows describing which winding factor production used, and why."""

    from ..winding.panel_text import PanelRow

    provenance = {
        WindingAuthority.AUTO_FROM_GEOMETRY: "GEOMETRY_DERIVED",
        WindingAuthority.MANUAL_OVERRIDE: "MANUAL_OVERRIDE",
        WindingAuthority.LEGACY_MANUAL: "MANUAL_OVERRIDE",
        WindingAuthority.UNRESOLVED: "USER_INPUT",
    }[production.authority]
    rows = [
        PanelRow("权威模式", AUTHORITY_LABELS_ZH[production.authority], provenance),
        PanelRow(
            "生产绕组系数",
            "未解析" if production.value is None else f"{production.value:.6f}",
            provenance,
            production.reason_zh,
        ),
        PanelRow(
            "几何推导值",
            "不可用" if production.geometry_value is None else f"{production.geometry_value:.6f}",
            "GEOMETRY_DERIVED",
        ),
    ]
    if production.manual_value is not None:
        rows.append(PanelRow("手动值", f"{production.manual_value:.6f}", "MANUAL_OVERRIDE"))
    if production.overrides_geometry and production.geometry_delta_percent is not None:
        rows.append(
            PanelRow(
                "手动相对几何", f"{production.geometry_delta_percent:+.3f} %",
                "MANUAL_OVERRIDE", "手动值正在覆盖几何推导结果",
            )
        )
    return tuple(rows)


class WindingEngineeringDialog:
    """A read-only engineering view of the winding and the slot."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        parameters_provider: Callable[[], Mapping[str, object]],
        meshed_factor_provider: Callable[[], tuple[float | None, float | None]] | None = None,
        initial_authority: WindingAuthority | None = None,
        manual_winding_factor_provider: Callable[[], float | None] | None = None,
        on_authority_change: Callable[[WindingAuthority], None] | None = None,
    ) -> None:
        self._parameters_provider = parameters_provider
        self._meshed_factor_provider = meshed_factor_provider
        # RC5.1: the session decides the authority; this view shows and edits
        # it. Defaulting to LEGACY_MANUAL here meant the panel could describe a
        # geometry-derived value as a preserved historical one.
        self._initial_authority = initial_authority or WindingAuthority.LEGACY_MANUAL
        self._manual_winding_factor_provider = manual_winding_factor_provider
        self._on_authority_change = on_authority_change

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
        self._apply_authority_state()
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

        # Phase 10H. The production winding-factor authority. Changing it
        # changes Ke, Kt, voltage and feasibility, so it is an explicit control
        # with a warning rather than a silent default.
        authority_frame = ttk.LabelFrame(self.window, text="生产绕组系数权威")
        authority_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.authority_var = tk.StringVar(
            value=AUTHORITY_LABELS_ZH[self._initial_authority]
        )
        ttk.Label(authority_frame, text="模式：").grid(row=0, column=0, sticky=tk.W, padx=(8, 2), pady=6)
        self.authority_combo = ttk.Combobox(
            authority_frame,
            textvariable=self.authority_var,
            values=[
                AUTHORITY_LABELS_ZH[WindingAuthority.AUTO_FROM_GEOMETRY],
                AUTHORITY_LABELS_ZH[WindingAuthority.MANUAL_OVERRIDE],
                AUTHORITY_LABELS_ZH[WindingAuthority.LEGACY_MANUAL],
            ],
            state="readonly",
            width=26,
        )
        self.authority_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 12), pady=6)
        self.authority_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_authority_changed())
        ttk.Label(authority_frame, text="手动 kw：").grid(row=0, column=2, sticky=tk.W, padx=(8, 2), pady=6)
        self.manual_kw_var = tk.StringVar(value="")
        self.manual_kw_entry = ttk.Entry(authority_frame, textvariable=self.manual_kw_var, width=10)
        self.manual_kw_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 12), pady=6)
        self.authority_status_var = tk.StringVar(value="")
        ttk.Label(
            authority_frame, textvariable=self.authority_status_var,
            wraplength=820, justify=tk.LEFT, foreground="#8a5a00",
        ).grid(row=1, column=0, columnspan=6, sticky=tk.W, padx=8, pady=(0, 6))

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
        """Compute the panel content. Separated so it can be tested headlessly.

        Phase 11A moved the assembly itself into ``winding.evaluation`` so the
        main dashboard shows the same numbers this panel does, computed once.
        This method now supplies the dialog's editable assumptions and renders
        the result.
        """

        parameters = dict(self._parameters_provider())

        meshed = width_factor = None
        if self._meshed_factor_provider is not None:
            try:
                meshed, width_factor = self._meshed_factor_provider()
            except Exception:  # noqa: BLE001 - a failed probe must not break the view
                meshed = width_factor = None

        evaluation = evaluate_winding(
            parameters,
            authority=self.selected_authority(),
            manual_winding_factor=self._manual_kw(parameters),
            assumptions=self.assumptions(),
            meshed_winding_factor=meshed,
            finite_width_factor=width_factor,
        )
        self._evaluation = evaluation
        self._production = evaluation.production
        if evaluation.report is None:
            return (), evaluation.warnings, ()

        warnings = list(evaluation.warnings)
        for issue in evaluation.issues:
            warnings.append(f"[{issue.code}/{issue.severity}] {issue.message_zh}")

        sections = build_winding_panel_rows(report=evaluation.report, fill=evaluation.fill)
        sections = sections + ((
            "生产绕组系数权威",
            _authority_rows(evaluation.production),
        ),)
        return sections, tuple(warnings), evaluation.report.notes_zh

    def assumptions(self) -> WindingProjectState:
        """The editable engineering allowances, as a winding state."""

        return WindingProjectState(
            layers=max(1, int(self._float(self.layers_var, 2.0))),
            insulation_ratio=self._float(self.insulation_var, DEFAULT_INSULATION_RATIO),
            liner_thickness_mm=self._float(self.liner_var, DEFAULT_LINER_THICKNESS_MM),
            clearance_mm=self._float(self.clearance_var, DEFAULT_CLEARANCE_MM),
            packing_factor=self._float(self.packing_var, DEFAULT_PACKING_FACTOR),
        )

    def selected_authority(self) -> WindingAuthority:
        label = str(self.authority_var.get()).strip()
        for authority, text in AUTHORITY_LABELS_ZH.items():
            if text == label:
                return authority
        return WindingAuthority.LEGACY_MANUAL

    def _manual_kw(self, parameters):
        raw = str(self.manual_kw_var.get()).strip()
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
        # RC5.1: while AUTO is in force the parameter mapping already carries
        # the derived value, so reading `k_w` from it would report the automatic
        # number as the user's manual one. The session supplies the value the
        # user actually entered.
        if self._manual_winding_factor_provider is not None:
            entered = self._manual_winding_factor_provider()
            if entered is not None:
                return float(entered)
        value = parameters.get("k_w")
        return float(value) if value is not None else None

    def adopt_authority(self, authority: WindingAuthority) -> None:
        """Show the authority the session is in, without re-notifying it."""

        if authority not in AUTHORITY_LABELS_ZH:
            return
        if self.selected_authority() is authority:
            self.refresh()
            return
        self.authority_var.set(AUTHORITY_LABELS_ZH[authority])
        self._apply_authority_state()
        self.refresh()

    def _apply_authority_state(self) -> None:
        """Widget state and explanation for the selected authority."""

        authority = self.selected_authority()
        editable = authority is not WindingAuthority.AUTO_FROM_GEOMETRY
        self.manual_kw_entry.configure(state=tk.NORMAL if editable else tk.DISABLED)
        if authority is WindingAuthority.AUTO_FROM_GEOMETRY:
            self.authority_status_var.set(
                "切换为自动模式后，生产绕组系数将改用几何推导值，"
                "Ke、Kt、电压需求、电压裕度与可行性判定都会随之重新计算。"
            )
        elif authority is WindingAuthority.MANUAL_OVERRIDE:
            self.authority_status_var.set(
                "手动覆盖：输入值将取代几何推导值，面板会同时显示二者之差。"
            )
        else:
            self.authority_status_var.set(
                "历史项目手动值：按原样保留存储的绕组系数，不会自动改用几何值。"
                "可在上方显式切换模式进行迁移。"
            )

    def _on_authority_changed(self) -> None:
        """Never switch silently: say that results will be recalculated.

        RC5.1: the choice is also handed back to the session, so the main input
        panel, the dashboard and this view cannot end up describing different
        authorities for the same design.
        """

        self._apply_authority_state()
        if self._on_authority_change is not None:
            self._on_authority_change(self.selected_authority())
        self.refresh()

    def refresh(self) -> None:
        sections, warnings, notes = self.build_sections()
        content = render_winding_panel_zh(sections, warnings=warnings, notes=notes)
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.configure(state=tk.DISABLED)
