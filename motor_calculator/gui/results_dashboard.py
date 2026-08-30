"""Chinese-first Phase 8H results dashboard for structured existing outputs."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Mapping

from motor_calculator.plots import (
    AvailabilityStatus,
    DashboardData,
    DashboardMetric,
    DashboardStatus,
    SnapshotAssessment,
    build_speed_sweep_series,
    configure_chinese_matplotlib,
    export_figure,
    export_speed_sweep_csv,
    extract_snapshot_primary_values,
    render_speed_sweep_figure,
    run_speed_sweep,
    uncertainty_result_to_plot_data,
)


_STATUS_COLORS = {
    DashboardStatus.NORMAL: "#177245",
    DashboardStatus.INFO: "#275d82",
    DashboardStatus.REVIEW: "#806000",
    DashboardStatus.WARNING: "#9a5b00",
    DashboardStatus.SEVERE: "#a12622",
    DashboardStatus.UNAVAILABLE: "#666666",
    DashboardStatus.INSUFFICIENT: "#666666",
}


class _RangeBar(ttk.Frame):
    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        self._title = ttk.Label(self, text=title)
        self._title.pack(anchor="w")
        self.canvas = tk.Canvas(self, height=30, highlightthickness=0, background="#f4f5f3")
        self.canvas.pack(fill=tk.X, expand=True, pady=(3, 0))
        self._caption = ttk.Label(self, text="尚无结果", foreground="#666666")
        self._caption.pack(anchor="w", pady=(2, 0))

    def set_value(
        self,
        value: float | None,
        minimum: float,
        maximum: float,
        segments: tuple[tuple[float, str], ...],
        caption: str,
    ) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 240)
        height = 22
        previous = minimum
        for boundary, color in segments:
            right = min(max(boundary, minimum), maximum)
            x0 = (previous - minimum) / (maximum - minimum) * width
            x1 = (right - minimum) / (maximum - minimum) * width
            self.canvas.create_rectangle(x0, 3, x1, height, fill=color, outline="")
            previous = right
        if previous < maximum:
            x0 = (previous - minimum) / (maximum - minimum) * width
            self.canvas.create_rectangle(x0, 3, width, height, fill="#d77872", outline="")
        if value is not None:
            clamped = min(max(value, minimum), maximum)
            x = (clamped - minimum) / (maximum - minimum) * width
            self.canvas.create_line(x, 1, x, height + 2, fill="#17202a", width=3)
        self._caption.configure(text=caption)


class ResultsDashboard(ttk.Frame):
    """Display existing results and run explicitly requested static sweeps."""

    def __init__(
        self,
        parent,
        *,
        input_provider: Callable[[], Mapping[str, object]],
        export_directory: Path,
    ) -> None:
        super().__init__(parent)
        self._input_provider = input_provider
        self._export_directory = Path(export_directory)
        self.data: DashboardData | None = None
        self.last_speed_sweep = None
        self.performance_figure = None
        self.performance_canvas = None
        self.performance_toolbar = None
        self.last_initial_render_seconds: float | None = None
        self.last_plot_render_seconds: float | None = None
        self.chinese_font_name = configure_chinese_matplotlib()
        self._metric_widgets: dict[
            str, tuple[tk.Widget, tk.Widget, tk.Widget, tk.Widget]
        ] = {}
        self._has_displayed_snapshot = False
        self._availability_rows: dict[str, str] = {}

        self._source_var = tk.StringVar(value="尚未运行计算")
        ttk.Label(self, textvariable=self._source_var, style="SubHeader.TLabel").pack(
            fill=tk.X, padx=10, pady=(8, 4)
        )
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._build_overview_tab()
        self._build_performance_tab()
        self._build_loss_tab()
        self._build_availability_tab()
        self.clear()

    def _build_overview_tab(self) -> None:
        self.overview_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.overview_tab, text="结果总览")
        self.overview_canvas = tk.Canvas(
            self.overview_tab, highlightthickness=0, background="#f0f0ed"
        )
        overview_scrollbar = ttk.Scrollbar(
            self.overview_tab, orient=tk.VERTICAL, command=self.overview_canvas.yview
        )
        self.overview_canvas.configure(yscrollcommand=overview_scrollbar.set)
        overview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.overview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content = ttk.Frame(self.overview_canvas, padding=10)
        self._overview_window = self.overview_canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )
        content.bind(
            "<Configure>",
            lambda _event: self.overview_canvas.configure(
                scrollregion=self.overview_canvas.bbox("all")
            ),
        )
        self.overview_canvas.bind(
            "<Configure>",
            lambda event: self.overview_canvas.itemconfigure(
                self._overview_window, width=event.width
            ),
        )
        self._design_var = tk.StringVar(value="尚无设计状态")
        ttk.Label(content, textvariable=self._design_var, style="Header.TLabel").pack(
            anchor="w", pady=(0, 8)
        )
        self._cards = ttk.Frame(content)
        self._cards.pack(fill=tk.X)
        for column in range(4):
            self._cards.columnconfigure(column, weight=1, uniform="dashboard-card")
        keys = (
            "rated_torque_nm", "output_power_w", "mechanical_speed_rpm", "efficiency_percent",
            "current_density_a_per_mm2", "voltage_margin_percent", "slot_fill_factor", "design_status",
            "ke_line_rms", "kt_phase_rms", "phase_current_rms_a", "required_voltage_v",
        )
        for index, key in enumerate(keys):
            card = ttk.LabelFrame(self._cards, text="--", padding=(8, 6))
            card.grid(row=index // 4, column=index % 4, sticky="nsew", padx=4, pady=4)
            value = ttk.Label(card, text="不可用", style="Header.TLabel")
            value.pack(anchor="w")
            status = ttk.Label(card, text="尚无结果", foreground="#666666")
            status.pack(anchor="w", pady=(3, 0))
            explanation = ttk.Label(card, text="", wraplength=220, justify=tk.LEFT)
            explanation.pack(anchor="w", pady=(3, 0))
            self._metric_widgets[key] = (card, value, status, explanation)

        gauges = ttk.LabelFrame(content, text="工程范围视图", padding=8)
        gauges.pack(fill=tk.X, pady=(10, 0))
        for column in range(3):
            gauges.columnconfigure(column, weight=1, uniform="dashboard-gauge")
        self.current_density_bar = _RangeBar(gauges, "电流密度 A/mm²")
        self.voltage_margin_bar = _RangeBar(gauges, "同基电压裕量 %")
        self.slot_fill_bar = _RangeBar(gauges, "近似裸铜槽占比")
        for column, bar in enumerate((self.current_density_bar, self.voltage_margin_bar, self.slot_fill_bar)):
            bar.grid(row=0, column=column, sticky="ew", padx=6)

    def _build_performance_tab(self) -> None:
        self.performance_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.performance_tab, text="性能扫描")
        controls = ttk.Frame(self.performance_tab)
        controls.pack(fill=tk.X)
        self._minimum_speed_var = tk.StringVar(value="1100")
        self._maximum_speed_var = tk.StringVar(value="3300")
        self._point_count_var = tk.StringVar(value="21")
        for label, variable, width in (
            ("最低转速 rpm", self._minimum_speed_var, 10),
            ("最高转速 rpm", self._maximum_speed_var, 10),
            ("采样点", self._point_count_var, 6),
        ):
            ttk.Label(controls, text=label).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Entry(controls, textvariable=variable, width=width).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(controls, text="生成曲线", command=self.run_performance_sweep).pack(side=tk.LEFT, padx=3)
        ttk.Button(controls, text="导出 PNG/SVG", command=self.export_current_figure).pack(side=tk.LEFT, padx=3)
        ttk.Button(controls, text="导出 CSV", command=self.export_current_csv).pack(side=tk.LEFT, padx=3)
        self._sweep_status_var = tk.StringVar(value="扫描不会自动运行；每个点使用当前静态模型独立计算。")
        ttk.Label(self.performance_tab, textvariable=self._sweep_status_var, foreground="#555555").pack(
            fill=tk.X, pady=(6, 4)
        )
        self._plot_host = ttk.Frame(self.performance_tab)
        self._plot_host.pack(fill=tk.BOTH, expand=True)
        self._plot_placeholder = ttk.Label(
            self._plot_host,
            text="点击“生成曲线”后显示实际计算结果；不会构造恒转矩或恒功率包络。",
            justify=tk.CENTER,
        )
        self._plot_placeholder.pack(expand=True)

    def _build_loss_tab(self) -> None:
        self.loss_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.loss_tab, text="损耗与热")
        ttk.Label(
            self.loss_tab,
            text="仅展示当前静态 AnalysisResult 已存在的损耗项；不补全或反推缺失损耗。",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.loss_tree = ttk.Treeview(
            self.loss_tab, columns=("value", "source", "note"), show="tree headings", height=7
        )
        self.loss_tree.heading("#0", text="损耗项")
        self.loss_tree.heading("value", text="数值")
        self.loss_tree.heading("source", text="来源")
        self.loss_tree.heading("note", text="边界说明")
        self.loss_tree.column("#0", width=150, stretch=False)
        self.loss_tree.column("value", width=120, stretch=False)
        self.loss_tree.column("source", width=180, stretch=False)
        self.loss_tree.column("note", width=420, stretch=True)
        self.loss_tree.pack(fill=tk.BOTH, expand=True)
        self._thermal_var = tk.StringVar(value="静态温升：当前静态模式无可信温升预测。")
        ttk.Label(self.loss_tab, textvariable=self._thermal_var, foreground="#7a4d00").pack(
            anchor="w", pady=(10, 0)
        )

    def _build_availability_tab(self) -> None:
        self.availability_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.availability_tab, text="分析可用性")
        ttk.Label(
            self.availability_tab,
            text="未运行与不可用是不同状态；本页不会把缺失分析显示成零。",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.availability_tree = ttk.Treeview(
            self.availability_tab, columns=("status", "reason"), show="tree headings", height=8
        )
        self.availability_tree.heading("#0", text="分析")
        self.availability_tree.heading("status", text="状态")
        self.availability_tree.heading("reason", text="原因")
        self.availability_tree.column("#0", width=160, stretch=False)
        self.availability_tree.column("status", width=110, stretch=False)
        self.availability_tree.column("reason", width=620, stretch=True)
        self.availability_tree.pack(fill=tk.BOTH, expand=True)
        self._uncertainty_var = tk.StringVar(value="不确定性：尚未执行不确定性分析。")
        ttk.Label(self.availability_tab, textvariable=self._uncertainty_var, wraplength=800).pack(
            anchor="w", pady=(10, 0)
        )

    def _set_metric(self, key: str, metric: DashboardMetric | None) -> None:
        card, value, status, explanation = self._metric_widgets[key]
        if metric is None:
            card.configure(text=key)
            value.configure(text="不可用")
            status.configure(text="尚无结果", foreground="#666666")
            explanation.configure(text="")
            return
        card.configure(text=metric.label_zh)
        suffix = f" {metric.unit}" if metric.unit else ""
        value.configure(text=f"{metric.display_value}{suffix}")
        status.configure(text=metric.status_label_zh, foreground=_STATUS_COLORS[metric.status])
        explanation.configure(text=metric.interpretation_zh)

    def set_result(self, data: DashboardData, *, rated_speed_rpm: float) -> None:
        started = time.perf_counter()
        self.data = data
        self._has_displayed_snapshot = False
        self._source_var.set(data.result_label_zh)
        self._design_var.set(data.design_status.headline_zh)
        for key in self._metric_widgets:
            self._set_metric(key, data.metric_by_key.get(key))
        current = data.metric_by_key["current_density_a_per_mm2"]
        voltage = data.metric_by_key["voltage_margin_percent"]
        slot = data.metric_by_key["slot_fill_factor"]
        self.current_density_bar.set_value(current.value, 0.0, 15.0, ((5.0, "#7fc59a"), (8.0, "#e5c36a")), f"{current.display_value} A/mm² · {current.status_label_zh}")
        self.voltage_margin_bar.set_value(voltage.value, -50.0, 50.0, ((0.0, "#d77872"), (10.0, "#e5c36a"), (50.0, "#7fc59a")), f"{voltage.display_value} % · {voltage.status_label_zh}")
        self.slot_fill_bar.set_value(slot.value, 0.0, 0.8, ((0.45, "#7fc59a"), (0.60, "#e5c36a")), f"{slot.display_value} · {slot.status_label_zh}")
        self._populate_losses(data)
        self._populate_availability(data)
        self._minimum_speed_var.set(f"{rated_speed_rpm * 0.5:.0f}")
        self._maximum_speed_var.set(f"{rated_speed_rpm * 1.5:.0f}")
        self._clear_sweep("输入或计算结果已更新；请按需重新生成曲线。")
        self.last_initial_render_seconds = time.perf_counter() - started

    def _populate_losses(self, data: DashboardData) -> None:
        self.loss_tree.delete(*self.loss_tree.get_children())
        for metric in data.loss_metrics:
            self.loss_tree.insert(
                "", "end", text=metric.label_zh,
                values=(f"{metric.display_value} {metric.unit}", metric.source, metric.interpretation_zh),
            )

    def _populate_availability(self, data: DashboardData) -> None:
        self.availability_tree.delete(*self.availability_tree.get_children())
        labels = {
            AvailabilityStatus.AVAILABLE: "可用",
            AvailabilityStatus.UNAVAILABLE: "不可用",
            AvailabilityStatus.NOT_RUN: "未运行",
            AvailabilityStatus.INVALID: "无效",
        }
        self._availability_rows = {}
        for item in data.availability_items:
            self._availability_rows[item.key] = item.reason_zh
            self.availability_tree.insert(
                "", "end", text=item.label_zh, values=(labels[item.status], item.reason_zh)
            )

    def set_uncertainty_result(self, result) -> None:
        data = uncertainty_result_to_plot_data(result)
        if data.availability is not AvailabilityStatus.AVAILABLE:
            self._uncertainty_var.set(f"不确定性：{data.reason_zh}")
            return
        self._uncertainty_var.set(
            f"不确定性：{data.metric_name} = {data.nominal_value:g} {data.unit}，"
            f"参数边界 [{data.lower_value:g}, {data.upper_value:g}] {data.unit}；"
            "仅来自显式受控分析，不是自动置信概率。"
        )

    def show_snapshot(self, assessment: SnapshotAssessment) -> None:
        self.clear()
        self._has_displayed_snapshot = True
        self._source_var.set(assessment.message_zh)
        values = extract_snapshot_primary_values(assessment.result or {})
        labels = {
            "rated_torque_nm": ("转矩", "Nm"),
            "output_power_w": ("输出功率", "W"),
            "mechanical_speed_rpm": ("转速", "rpm"),
            "efficiency_percent": ("当前模型估算效率", "%"),
        }
        for key, (label, unit) in labels.items():
            value = values.get(key)
            metric = DashboardMetric(
                key=key, label_zh=label, value=value,
                display_value="不可用" if value is None else f"{value:.3f}", unit=unit,
                status=DashboardStatus.INFO if assessment.is_current else DashboardStatus.REVIEW,
                interpretation_zh="项目保存的结构化结果快照；其他结果需重新计算。",
                availability=AvailabilityStatus.AVAILABLE if value is not None else AvailabilityStatus.UNAVAILABLE,
                source="ProjectDocument.result_snapshot",
            )
            self._set_metric(key, metric)

    def mark_input_stale(self) -> None:
        if self.data is not None or self._has_displayed_snapshot:
            self._source_var.set("输入已更改；当前展示为上一次成功计算，请重新计算。")

    def mark_calculation_failed(self) -> None:
        if self.data is not None or self._has_displayed_snapshot:
            self._source_var.set("本次计算失败；当前展示为上一次成功计算。")

    def clear(self) -> None:
        self.data = None
        self._has_displayed_snapshot = False
        self._source_var.set("尚未运行计算")
        self._design_var.set("尚无设计状态")
        for key in self._metric_widgets:
            self._set_metric(key, None)
        self.loss_tree.delete(*self.loss_tree.get_children())
        self.availability_tree.delete(*self.availability_tree.get_children())
        self._thermal_var.set("静态温升：当前静态模式无可信温升预测。")
        self._uncertainty_var.set("不确定性：尚未执行不确定性分析。")
        self._clear_sweep("扫描不会自动运行；每个点使用当前静态模型独立计算。")

    def _clear_sweep(self, message: str) -> None:
        self.last_speed_sweep = None
        self.performance_figure = None
        self._sweep_status_var.set(message)
        for child in self._plot_host.winfo_children():
            child.destroy()
        self._plot_placeholder = ttk.Label(
            self._plot_host,
            text="点击“生成曲线”后显示实际计算结果；无效点将保留为空白断点。",
            justify=tk.CENTER,
        )
        self._plot_placeholder.pack(expand=True)

    def run_performance_sweep(self) -> bool:
        try:
            minimum = float(self._minimum_speed_var.get())
            maximum = float(self._maximum_speed_var.get())
            count = int(self._point_count_var.get())
            parameters = dict(self._input_provider())
            sweep = run_speed_sweep(parameters, minimum, maximum, count)
        except (TypeError, ValueError) as exc:
            messagebox.showwarning("性能扫描", f"扫描参数无效：{exc}", parent=self.winfo_toplevel())
            return False
        started = time.perf_counter()
        figure = render_speed_sweep_figure(sweep)
        self._show_figure(figure)
        self.last_plot_render_seconds = time.perf_counter() - started
        self.last_speed_sweep = sweep
        self.performance_figure = figure
        invalid = len(sweep.points) - len(sweep.valid_points)
        self._sweep_status_var.set(
            f"已计算 {len(sweep.points)} 点，{invalid} 个无效断点；"
            f"模型计算 {sweep.elapsed_seconds:.3f} s，绘图 {self.last_plot_render_seconds:.3f} s。"
        )
        return True

    def _show_figure(self, figure) -> None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        for child in self._plot_host.winfo_children():
            child.destroy()
        toolbar_host = ttk.Frame(self._plot_host)
        toolbar_host.pack(fill=tk.X)
        canvas = FigureCanvasTkAgg(figure, master=self._plot_host)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_host, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill=tk.X)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.performance_canvas = canvas
        self.performance_toolbar = toolbar

    def export_current_figure(self, destination: Path | None = None) -> Path | None:
        if self.performance_figure is None:
            messagebox.showinfo("导出性能图", "请先生成性能扫描曲线。", parent=self.winfo_toplevel())
            return None
        if destination is None:
            selected = filedialog.asksaveasfilename(
                parent=self.winfo_toplevel(), title="导出性能图", initialdir=str(self._export_directory),
                defaultextension=".png", filetypes=(("PNG", "*.png"), ("SVG", "*.svg")),
            )
            if not selected:
                return None
            destination = Path(selected)
        try:
            return export_figure(self.performance_figure, Path(destination))
        except (OSError, ValueError) as exc:
            logging.getLogger(__name__).warning("Dashboard figure export failed: %s", exc)
            messagebox.showerror("导出性能图", "性能图导出失败。", parent=self.winfo_toplevel())
            return None

    def export_current_csv(self, destination: Path | None = None) -> Path | None:
        if self.last_speed_sweep is None:
            messagebox.showinfo("导出扫描数据", "请先生成性能扫描曲线。", parent=self.winfo_toplevel())
            return None
        if destination is None:
            selected = filedialog.asksaveasfilename(
                parent=self.winfo_toplevel(), title="导出扫描数据", initialdir=str(self._export_directory),
                defaultextension=".csv", filetypes=(("CSV", "*.csv"),),
            )
            if not selected:
                return None
            destination = Path(selected)
        try:
            return export_speed_sweep_csv(self.last_speed_sweep, Path(destination))
        except OSError as exc:
            logging.getLogger(__name__).warning("Dashboard CSV export failed: %s", exc)
            messagebox.showerror("导出扫描数据", "扫描数据导出失败。", parent=self.winfo_toplevel())
            return None

    @property
    def sweep_series(self):
        return () if self.last_speed_sweep is None else build_speed_sweep_series(self.last_speed_sweep)
