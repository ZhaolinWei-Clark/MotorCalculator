"""Chinese-first launch surface for existing sandbox analysis engines."""

from __future__ import annotations

import logging
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Mapping

from motor_calculator.analysis_service import (
    AnalysisUnavailableError,
    DynamicAnalysisSettings,
    UncertaintyAnalysisSettings,
    dynamic_analysis_availability,
    run_dynamic_analysis,
    run_sensitivity_analysis,
    run_uncertainty_analysis,
)
from motor_calculator.dynamics import SimulationAccuracy
from motor_calculator.plots import (
    dynamic_result_to_plot_data,
    render_dynamic_figure,
    render_sensitivity_figure,
    render_uncertainty_figure,
    sensitivity_results_to_plot_data,
    uncertainty_result_to_plot_data,
)


_SENSITIVITY_PARAMETERS = {
    "磁体剩磁 Br": "magnet_remanence_t",
    "单侧气隙": "air_gap_m",
    "磁体厚度": "magnet_thickness_m",
    "每相匝数": "turns_per_phase",
    "额定转速": "rated_speed_rpm",
}

_SENSITIVITY_OUTPUTS = {
    "额定转矩": "rated_torque_nm",
    "相反电势峰值": "back_emf_phase_peak_v",
    "线反电势 RMS": "back_emf_line_rms_v",
    "转矩常数": "torque_constant_nm_per_a",
    "所需电压": "required_voltage_v",
    "铜损": "copper_loss_w",
    "铁损": "iron_loss_w",
    "效率": "efficiency_percent",
}


class AnalysisCenterDialog:
    """One explicit, non-automatic entry point for Phase 6/7 analyses."""

    def __init__(
        self,
        parent,
        *,
        inputs_provider: Callable[[], Mapping[str, object]],
        result_provider: Callable[[], object | None],
        repository_root: Path,
        uncertainty_specification_provider: Callable[[], object | None],
        on_uncertainty_complete: Callable[[object], None],
    ) -> None:
        self._parent = parent
        self._inputs_provider = inputs_provider
        self._result_provider = result_provider
        self._repository_root = Path(repository_root)
        self._uncertainty_specification_provider = uncertainty_specification_provider
        self._on_uncertainty_complete = on_uncertainty_complete
        self.last_dynamic_outcome = None
        self.last_uncertainty_result = None
        self.last_sensitivity_summary = None

        self.window = tk.Toplevel(parent)
        self.window.title("工程分析（沙盒）")
        width = min(1000, max(760, self.window.winfo_screenwidth() - 100))
        height = min(720, max(520, self.window.winfo_screenheight() - 140))
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min(780, width), min(540, height))
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)

        intro = ttk.Label(
            self.window,
            text=(
                "以下分析仅在用户点击后运行，不会修改生产计算、项目默认值或校准参数。"
                "动态仿真目前仅支持 PMSM。"
            ),
            wraplength=940,
            justify=tk.LEFT,
        )
        intro.pack(fill=tk.X, padx=12, pady=(10, 6))
        self.tabs = ttk.Notebook(self.window)
        self.tabs.configure(width=max(700, width - 32), height=max(430, height - 105))
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._build_dynamic_tab()
        self._build_uncertainty_tab()
        self._build_sensitivity_tab()

    def select_analysis(self, analysis_name: str) -> None:
        target = {
            "dynamic": self.dynamic_tab,
            "uncertainty": self.uncertainty_tab,
            "sensitivity": self.sensitivity_tab,
        }.get(analysis_name)
        if target is None:
            raise ValueError(f"unsupported analysis tab: {analysis_name}")
        self.tabs.select(target)
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()

    @staticmethod
    def _entry_row(parent, row: int, label: str, variable, unit: str = "") -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=variable, width=14).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w", padx=(6, 0), pady=3)

    def _build_dynamic_tab(self) -> None:
        self.dynamic_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.dynamic_tab, text="动态仿真")
        top = ttk.Frame(self.dynamic_tab)
        top.pack(fill=tk.X)
        form = ttk.LabelFrame(top, text="显式仿真设置", padding=8)
        form.pack(fill=tk.X)
        for column in range(3):
            form.columnconfigure(column, weight=1, uniform="dynamic-setting")
        self.dynamic_time_var = tk.StringVar(value="0.5")
        self.dynamic_speed_var = tk.StringVar(value="1000")
        self.dynamic_load_var = tk.StringVar(value="0.2")
        self.dynamic_initial_speed_var = tk.StringVar(value="0")
        self.dynamic_inertia_var = tk.StringVar(value="0.02")
        self.dynamic_friction_var = tk.StringVar(value="0.001")
        self.dynamic_accuracy_var = tk.StringVar(value="BALANCED")
        rows = (
            ("仿真时长", self.dynamic_time_var, "s"),
            ("目标转速", self.dynamic_speed_var, "rpm"),
            ("负载转矩", self.dynamic_load_var, "Nm"),
            ("初始转速", self.dynamic_initial_speed_var, "rpm"),
            ("转动惯量 J", self.dynamic_inertia_var, "kg*m²"),
            ("阻尼 B", self.dynamic_friction_var, "Nms/rad"),
        )
        for index, (label, variable, unit) in enumerate(rows):
            group = ttk.Frame(form)
            group.grid(row=index // 3, column=index % 3, sticky="ew", padx=5, pady=3)
            ttk.Label(group, text=label).pack(side=tk.LEFT)
            # Reserve the unit label before allowing the entry to consume spare width.
            ttk.Label(group, text=unit).pack(side=tk.RIGHT)
            ttk.Entry(group, textvariable=variable, width=8).pack(side=tk.LEFT, padx=(5, 4))
        accuracy_group = ttk.Frame(form)
        accuracy_group.grid(row=2, column=0, sticky="ew", padx=5, pady=(6, 2))
        ttk.Label(accuracy_group, text="精度预设").pack(side=tk.LEFT)
        ttk.Combobox(
            accuracy_group,
            textvariable=self.dynamic_accuracy_var,
            values=("FAST", "BALANCED", "HIGH_ACCURACY"),
            state="readonly",
            width=15,
        ).pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
        ttk.Button(form, text="运行动态仿真", command=self.run_dynamic).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=(6, 2)
        )
        note_row = ttk.Frame(top)
        note_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(
            note_row,
            text="实际步长由精度预设内部选择；参数映射和控制边界均为沙盒设置。",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(note_row, text="查看映射与精度说明", command=self._show_dynamic_notes).pack(side=tk.RIGHT)
        self.dynamic_status_var = tk.StringVar(value="尚未运行动态仿真。")
        ttk.Label(self.dynamic_tab, textvariable=self.dynamic_status_var, wraplength=930).pack(
            fill=tk.X, pady=(8, 4)
        )
        self.dynamic_plot_host = ttk.Frame(self.dynamic_tab)
        self.dynamic_plot_host.pack(fill=tk.BOTH, expand=True)

    def _show_dynamic_notes(self) -> None:
        messagebox.showinfo(
            "动态仿真边界",
            (
                "FAST 使用较粗 Euler 设置；BALANCED 使用现有 RK4 推荐设置；"
                "HIGH_ACCURACY 使用更细 RK4 设置。实际步长由预设内部选择。\n\n"
                "R、L、Kt 来自当前 PMSM 静态结果；Ld=Lq 是明示的表贴式近似。"
                "J、B 和控制器设置只属于本次沙盒运行，不写回项目默认值或生产模型。"
            ),
            parent=self.window,
        )

    def _build_uncertainty_tab(self) -> None:
        self.uncertainty_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.uncertainty_tab, text="不确定性分析")
        controls = ttk.Frame(self.uncertainty_tab)
        controls.pack(fill=tk.X)
        self.uncertainty_samples_var = tk.StringVar(value="500")
        self.uncertainty_seed_var = tk.StringVar(value="20260701")
        ttk.Label(controls, text="样本数").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=self.uncertainty_samples_var, width=10).pack(side=tk.LEFT, padx=(5, 12))
        ttk.Label(controls, text="随机种子").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=self.uncertainty_seed_var, width=12).pack(side=tk.LEFT, padx=(5, 12))
        ttk.Button(controls, text="运行不确定性分析", command=self.run_uncertainty).pack(side=tk.LEFT)
        ttk.Label(
            self.uncertainty_tab,
            text=(
                "使用 Phase 7I 已有受控 AFPM 参考与当前项目保存的显式假设。"
                "这不是当前生产电机结果的真实误差区间；参数不确定性不等于模型形式误差。"
            ),
            wraplength=930,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 4))
        self.uncertainty_status_var = tk.StringVar(value="尚未执行不确定性分析。")
        ttk.Label(self.uncertainty_tab, textvariable=self.uncertainty_status_var, wraplength=930).pack(fill=tk.X)
        self.uncertainty_plot_host = ttk.Frame(self.uncertainty_tab)
        self.uncertainty_plot_host.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    def _build_sensitivity_tab(self) -> None:
        self.sensitivity_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.sensitivity_tab, text="敏感性分析")
        controls = ttk.Frame(self.sensitivity_tab)
        controls.pack(fill=tk.X)
        self.sensitivity_parameter_var = tk.StringVar(value=next(iter(_SENSITIVITY_PARAMETERS)))
        self.sensitivity_output_var = tk.StringVar(value=next(iter(_SENSITIVITY_OUTPUTS)))
        ttk.Label(controls, text="扰动参数").pack(side=tk.LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.sensitivity_parameter_var,
            values=tuple(_SENSITIVITY_PARAMETERS),
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=(5, 12))
        ttk.Label(controls, text="观察输出").pack(side=tk.LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.sensitivity_output_var,
            values=tuple(_SENSITIVITY_OUTPUTS),
            state="readonly",
            width=20,
        ).pack(side=tk.LEFT, padx=(5, 12))
        ttk.Button(controls, text="运行敏感性分析", command=self.run_sensitivity).pack(side=tk.LEFT)
        ttk.Label(
            self.sensitivity_tab,
            text="只运行 -5%、-1%、+1%、+5% 临时副本扰动；不会优化、校准或写回任何参数。",
            wraplength=930,
        ).pack(fill=tk.X, pady=(8, 4))
        self.sensitivity_status_var = tk.StringVar(value="尚未运行敏感性分析。")
        ttk.Label(self.sensitivity_tab, textvariable=self.sensitivity_status_var, wraplength=930).pack(fill=tk.X)
        self.sensitivity_plot_host = ttk.Frame(self.sensitivity_tab)
        self.sensitivity_plot_host.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    @staticmethod
    def _replace_plot(host, figure) -> None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        for child in host.winfo_children():
            child.destroy()
        toolbar_host = ttk.Frame(host)
        toolbar_host.pack(fill=tk.X)
        canvas = FigureCanvasTkAgg(figure, master=host)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_host, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill=tk.X)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        host._analysis_canvas = canvas
        host._analysis_toolbar = toolbar

    def run_dynamic(self) -> bool:
        try:
            inputs = self._inputs_provider()
            result = self._result_provider()
            available, reason = dynamic_analysis_availability(inputs, result)
            if not available:
                raise AnalysisUnavailableError(reason)
            settings = DynamicAnalysisSettings(
                simulation_time_s=float(self.dynamic_time_var.get()),
                accuracy_level=SimulationAccuracy[self.dynamic_accuracy_var.get()],
                speed_reference_rpm=float(self.dynamic_speed_var.get()),
                load_torque_nm=float(self.dynamic_load_var.get()),
                initial_speed_rpm=float(self.dynamic_initial_speed_var.get()),
                inertia_kg_m2=float(self.dynamic_inertia_var.get()),
                viscous_friction_nm_per_rad_s=float(self.dynamic_friction_var.get()),
            )
            outcome = run_dynamic_analysis(inputs, result, settings)
            data = dynamic_result_to_plot_data(outcome.result)
            self._replace_plot(self.dynamic_plot_host, render_dynamic_figure(data))
        except (AnalysisUnavailableError, KeyError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Dynamic GUI analysis unavailable: %s", exc)
            self.dynamic_status_var.set(f"动态仿真不可用：{exc}")
            return False
        except Exception as exc:
            logging.getLogger(__name__).exception("Dynamic GUI analysis failed")
            self.dynamic_status_var.set("动态仿真失败，技术详情已写入本地日志。")
            return False
        self.last_dynamic_outcome = outcome
        final_rpm = outcome.result.speed[-1] * 60.0 / (2.0 * 3.141592653589793)
        self.dynamic_status_var.set(
            f"完成：{len(outcome.result.time)} 点，运行 {outcome.elapsed_seconds:.3f} s，"
            f"最终转速 {final_rpm:.1f} rpm，电压饱和 {outcome.result.voltage_saturation_count} 次。"
        )
        return True

    def run_uncertainty(self) -> bool:
        try:
            settings = UncertaintyAnalysisSettings(
                sample_count=int(self.uncertainty_samples_var.get()),
                random_seed=int(self.uncertainty_seed_var.get()),
            )
            started = time.perf_counter()
            result = run_uncertainty_analysis(
                self._repository_root,
                settings,
                self._uncertainty_specification_provider(),
            )
            elapsed = time.perf_counter() - started
            data = uncertainty_result_to_plot_data(result.accuracy_envelope)
            self._replace_plot(self.uncertainty_plot_host, render_uncertainty_figure(data))
            self._on_uncertainty_complete(result)
        except (OSError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Uncertainty GUI analysis unavailable: %s", exc)
            self.uncertainty_status_var.set(f"不确定性分析不可用：{exc}")
            return False
        self.last_uncertainty_result = result
        monte_carlo = result.monte_carlo
        self.uncertainty_status_var.set(
            f"完成：valid={monte_carlo.valid_sample_count}，rejected={monte_carlo.failed_sample_count}，"
            f"seed={monte_carlo.random_seed}，运行 {elapsed:.3f} s。模型形式不确定性仍未完整量化。"
        )
        return True

    def run_sensitivity(self) -> bool:
        parameter_name = _SENSITIVITY_PARAMETERS[self.sensitivity_parameter_var.get()]
        output_name = _SENSITIVITY_OUTPUTS[self.sensitivity_output_var.get()]
        try:
            started = time.perf_counter()
            summary = run_sensitivity_analysis(self._inputs_provider(), parameter_name, output_name)
            elapsed = time.perf_counter() - started
            data = sensitivity_results_to_plot_data(summary.run_results, parameter_name, output_name)
            self._replace_plot(self.sensitivity_plot_host, render_sensitivity_figure(data))
        except (KeyError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning("Sensitivity GUI analysis unavailable: %s", exc)
            self.sensitivity_status_var.set(f"敏感性分析不可用：{exc}")
            return False
        self.last_sensitivity_summary = summary
        self.sensitivity_status_var.set(
            f"完成：{len(summary.run_results)} 个只读扰动，运行 {elapsed:.3f} s。"
            "结果不是校准值。"
        )
        return True
