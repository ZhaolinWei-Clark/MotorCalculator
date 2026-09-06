"""Tk dialog for the Phase 10A FEA validation bridge.

This module is a view only. Every decision — supportability, availability,
whether a solve may run, whether results may be shown — comes from
``motor_calculator.fea.view_model.FEAValidationViewModel``, so none of it lives
in a Tk callback and all of it is testable without a display.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Mapping

from ..fea.models import FEAValidationTarget
from ..fea.view_model import (
    MODELLING_PARAMETER_NOTICE_ZH,
    NO_DATA_PLOT_MESSAGE_ZH,
    TARGET_CHOICES_ZH,
    FEAValidationViewModel,
)
from ..motor_core.calculations import LegacyGuiMotorModelBridge
from ..motor_core.validation import parse_legacy_gui_params

LOGGER = logging.getLogger(__name__)

INTRO_ZH = (
    "FEA 验证只在你点击「运行 FEMM 验证」后才会执行，不会随普通计算自动运行，"
    "也不会修改任何解析参数。当前范围仅限空载反电动势 / Ke、平均电磁转矩与齿槽转矩。"
)

TIER_NOTICE_ZH = (
    "本桥接使用 FEMM 的二维平面求解器，对轴向磁通电机只能建立中径展开切片，"
    "保真度等级为 FEA_TIER_3，不构成完整三维 FEA 等价性声明。"
)


class FEAValidationDialog:
    """The 分析 → FEA 验证 window."""

    def __init__(
        self,
        parent,
        *,
        inputs_provider: Callable[[], Mapping[str, object]],
        result_provider: Callable[[], object | None],
        export_dir: Path,
    ) -> None:
        self._parent = parent
        self._inputs_provider = inputs_provider
        self._result_provider = result_provider
        self._export_dir = Path(export_dir)
        self.view_model: FEAValidationViewModel | None = None

        self.window = tk.Toplevel(parent)
        self.window.title("FEA 验证（FEMM 桥接）")
        width = min(1000, max(760, self.window.winfo_screenwidth() - 100))
        height = min(760, max(540, self.window.winfo_screenheight() - 140))
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min(780, width), min(560, height))
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)

        ttk.Label(
            self.window, text=INTRO_ZH, wraplength=940, justify=tk.LEFT
        ).pack(fill=tk.X, padx=12, pady=(10, 2))
        ttk.Label(
            self.window, text=TIER_NOTICE_ZH, wraplength=940, justify=tk.LEFT
        ).pack(fill=tk.X, padx=12, pady=(0, 8))

        self.solver_status_var = tk.StringVar(value="正在检测求解器…")
        self.solver_status_label = ttk.Label(
            self.window, textvariable=self.solver_status_var, wraplength=940, justify=tk.LEFT
        )
        self.solver_status_label.pack(fill=tk.X, padx=12, pady=(0, 8))

        self._build_controls()
        self._build_output()
        self._build_actions()
        self.refresh()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_controls(self) -> None:
        frame = ttk.LabelFrame(self.window, text="验证目标与建模参数")
        frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        ttk.Label(frame, text="验证目标：").grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        self.target_var = tk.StringVar(value=TARGET_CHOICES_ZH[0][1])
        self.target_combo = ttk.Combobox(
            frame,
            textvariable=self.target_var,
            values=[label for _target, label in TARGET_CHOICES_ZH],
            state="readonly",
            width=24,
        )
        self.target_combo.grid(row=0, column=1, sticky=tk.W, padx=8, pady=6)
        self.target_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_target_changed())
        self.target_status_var = tk.StringVar(value="")
        ttk.Label(
            frame, textvariable=self.target_status_var, wraplength=620, justify=tk.LEFT
        ).grid(row=0, column=2, columnspan=3, sticky=tk.W, padx=8, pady=6)

        ttk.Label(
            frame, text=MODELLING_PARAMETER_NOTICE_ZH, wraplength=900, justify=tk.LEFT
        ).grid(row=1, column=0, columnspan=4, sticky=tk.W, padx=8, pady=(2, 6))

        ttk.Label(frame, text="转子磁轭厚度 (mm)：").grid(row=2, column=0, sticky=tk.W, padx=8, pady=6)
        self.back_iron_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.back_iron_var, width=12).grid(
            row=2, column=1, sticky=tk.W, padx=8, pady=6
        )
        ttk.Label(frame, text="线圈节距 (槽)：").grid(row=2, column=2, sticky=tk.W, padx=8, pady=6)
        self.coil_span_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.coil_span_var, width=12).grid(
            row=2, column=3, sticky=tk.W, padx=8, pady=6
        )
        ttk.Button(frame, text="确认建模参数", command=self._confirm_parameters).grid(
            row=2, column=4, sticky=tk.W, padx=8, pady=6
        )

    def _build_output(self) -> None:
        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        review_frame = ttk.Frame(self.tabs)
        self.review_text = tk.Text(review_frame, wrap=tk.WORD, height=18)
        review_scroll = ttk.Scrollbar(
            review_frame, orient=tk.VERTICAL, command=self.review_text.yview
        )
        self.review_text.configure(yscrollcommand=review_scroll.set, state=tk.DISABLED)
        self.review_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        review_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tabs.add(review_frame, text="案例复核")

        results_frame = ttk.Frame(self.tabs)
        self.results_text = tk.Text(results_frame, wrap=tk.WORD, height=18)
        results_scroll = ttk.Scrollbar(
            results_frame, orient=tk.VERTICAL, command=self.results_text.yview
        )
        self.results_text.configure(yscrollcommand=results_scroll.set, state=tk.DISABLED)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        results_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tabs.add(results_frame, text="对比结果")

    def _build_actions(self) -> None:
        frame = ttk.Frame(self.window)
        frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.run_button = ttk.Button(
            frame, text="运行 FEMM 验证", command=self._run_validation, state=tk.DISABLED
        )
        self.run_button.pack(side=tk.LEFT)
        self.export_case_button = ttk.Button(
            frame, text="导出验证案例", command=self._export_case, state=tk.DISABLED
        )
        self.export_case_button.pack(side=tk.LEFT, padx=(8, 0))
        self.export_scripts_button = ttk.Button(
            frame, text="导出求解脚本", command=self._export_scripts, state=tk.DISABLED
        )
        self.export_scripts_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(frame, text="关闭", command=self.window.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _build_view_model(self) -> FEAValidationViewModel | None:
        try:
            bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(dict(self._inputs_provider())))
            analysis = self._result_provider()
            if analysis is None:
                analysis = bridge.run_full_analysis()
            return FEAValidationViewModel(inputs=bridge.input_data, analysis=analysis)
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.warning("FEA validation dialog could not read the current design: %s", error)
            return None

    def refresh(self) -> None:
        if self.view_model is None:
            self.view_model = self._build_view_model()
        if self.view_model is None:
            self.solver_status_var.set("无法读取当前设计参数，请先完成一次有效计算。")
            self._set_text(self.review_text, "无法读取当前设计参数。")
            self._set_text(self.results_text, "无法读取当前设计参数。")
            return

        model = self.view_model
        self.solver_status_var.set(f"{model.solver_message_zh}\n{model.solver_detail_zh}")
        if not self.back_iron_var.get():
            back_iron_m, coil_span = model.suggested_values()
            self.back_iron_var.set(f"{back_iron_m * 1000.0:.3f}")
            self.coil_span_var.set(str(coil_span))

        self.target_status_var.set(model.target_validation_status_zh)
        self._set_text(self.review_text, model.review_text_zh())
        self._set_text(
            self.results_text,
            model.results_text_zh() if model.last_run else NO_DATA_PLOT_MESSAGE_ZH,
        )

        can_generate = model.can_generate_case
        self.export_case_button.configure(state=tk.NORMAL if can_generate else tk.DISABLED)
        self.export_scripts_button.configure(state=tk.NORMAL if can_generate else tk.DISABLED)
        # The run button is enabled only when a real solver is present. There is
        # no code path that offers a fake or disabled-looking result instead.
        self.run_button.configure(state=tk.NORMAL if model.can_run_solver else tk.DISABLED)

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_target_changed(self) -> None:
        if self.view_model is None:
            return
        label = self.target_var.get()
        for target, choice in TARGET_CHOICES_ZH:
            if choice == label:
                self.view_model.set_target(target)
                break
        self.refresh()

    def _confirm_parameters(self) -> None:
        if self.view_model is None:
            return
        try:
            back_iron_mm = float(self.back_iron_var.get())
            coil_span = int(float(self.coil_span_var.get()))
            self.view_model.confirm_modelling_parameters(
                rotor_back_iron_thickness_m=back_iron_mm / 1000.0,
                coil_span_slots=coil_span,
            )
        except ValueError as error:
            messagebox.showerror("建模参数无效", str(error), parent=self.window)
            return
        self.refresh()

    def _run_validation(self) -> None:
        if self.view_model is None or not self.view_model.can_run_solver:
            return
        try:
            self.view_model.run()
        except (ValueError, OSError) as error:
            LOGGER.exception("FEA validation run failed: %s", error)
            messagebox.showerror("FEA 验证失败", str(error), parent=self.window)
            return
        self.refresh()
        self.tabs.select(1)

    def _export_case(self) -> None:
        if self.view_model is None:
            return
        directory = filedialog.askdirectory(
            parent=self.window, title="选择导出目录", initialdir=str(self._export_dir)
        )
        if not directory:
            return
        try:
            written = self.view_model.export_results(Path(directory))
        except (ValueError, OSError) as error:
            messagebox.showerror("导出失败", str(error), parent=self.window)
            return
        messagebox.showinfo(
            "导出完成", f"已导出 {len(written)} 个文件。", parent=self.window
        )

    def _export_scripts(self) -> None:
        if self.view_model is None:
            return
        directory = filedialog.askdirectory(
            parent=self.window, title="选择求解脚本输出目录", initialdir=str(self._export_dir)
        )
        if not directory:
            return
        try:
            written = self.view_model.export_scripts(Path(directory))
        except (ValueError, OSError) as error:
            messagebox.showerror("导出失败", str(error), parent=self.window)
            return
        messagebox.showinfo(
            "导出完成",
            f"已生成 {len(written)} 个 FEMM Lua 脚本。未安装 FEMM 时也可生成，"
            "可复制到已安装 FEMM 的机器上运行。",
            parent=self.window,
        )


__all__ = ["FEAValidationDialog", "FEAValidationTarget"]
