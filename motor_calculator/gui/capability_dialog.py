"""Phase 12: the torque-speed / field-weakening capability view.

Holds no engineering logic. It collects the inverter inputs, calls the solver,
and renders what comes back. The ``build_*`` methods are separated from the
widgets so the entire surface can be exercised without a display.

The operating-point inspector is the part that earns this window its place: a
torque-speed curve tells you *what* the machine can do, and only the dq
operating point at a chosen speed tells you *why* it stops there.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Mapping

from ..capability.envelope import REGION_LABELS_ZH
from ..capability.export import (
    CALIBRATION_STATUS,
    EVIDENCE_NOTE_ZH,
    EVIDENCE_STATEMENT,
    export_capability,
    render_summary_zh,
)
from ..capability.feasibility import capability_issues
from ..capability.limits import MODULATION_LABELS_ZH, Modulation
from ..capability.parameters import render_provenance_zh
from ..capability.solver import InverterSettings, solve_from_analysis

CAPABILITY_DIALOG_VERSION = "phase12.gui.capability.v1"

INTRO_ZH = (
    "稳态电机 + 逆变器能力求解：MTPA、基速、弱磁轨迹与转矩-转速包络。\n"
    "全部结果为**解析模型输出**，不是测量值，也未经实验验证。"
)


class CapabilityDialog:
    """Capability headline values, curves, and an operating-point inspector."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        analysis_provider: Callable[[], Any],
        parameters_provider: Callable[[], Mapping[str, Any]],
        settings_provider: Callable[[], InverterSettings] | None = None,
        on_settings_changed: Callable[[InverterSettings], None] | None = None,
        export_dir: Path | None = None,
    ) -> None:
        self._analysis_provider = analysis_provider
        self._parameters_provider = parameters_provider
        self._settings_provider = settings_provider
        self._on_settings_changed = on_settings_changed
        self._export_dir = Path(export_dir) if export_dir else Path.cwd()
        self.result = None
        self._error: str | None = None

        self.window = tk.Toplevel(master)
        self.window.title("转矩-转速 / 弱磁能力")
        self.window.geometry("1000x760")

        ttk.Label(self.window, text=INTRO_ZH, wraplength=960, justify=tk.LEFT).pack(
            anchor=tk.W, padx=10, pady=(10, 6)
        )

        self._build_inputs()
        self.tabs = ttk.Notebook(self.window)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self._build_summary_tab()
        self._build_torque_speed_tab()
        self._build_dq_tab()
        self._build_inspector_tab()
        self._build_provenance_tab()

        ttk.Button(self.window, text="关闭", command=self.window.destroy).pack(
            side=tk.RIGHT, padx=10, pady=(0, 10)
        )
        self.refresh()

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------

    def _build_inputs(self) -> None:
        frame = ttk.LabelFrame(self.window, text="逆变器设置", padding=(8, 6))
        frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        settings = self._settings_provider() if self._settings_provider else None
        ttk.Label(frame, text="母线电压 V_dc").grid(row=0, column=0, sticky="w")
        self.bus_var = tk.StringVar(
            value=f"{settings.dc_bus_voltage_v:.3f}" if settings else "48.0"
        )
        ttk.Entry(frame, textvariable=self.bus_var, width=10).grid(row=0, column=1, padx=(4, 14))

        ttk.Label(frame, text="调制方式").grid(row=0, column=2, sticky="w")
        self.modulation_var = tk.StringVar(
            value=MODULATION_LABELS_ZH[settings.modulation if settings else Modulation.SVPWM]
        )
        self.modulation_combo = ttk.Combobox(
            frame, textvariable=self.modulation_var,
            values=list(MODULATION_LABELS_ZH.values()), state="readonly", width=28,
        )
        self.modulation_combo.grid(row=0, column=3, padx=(4, 14))

        ttk.Label(frame, text="电压利用率").grid(row=0, column=4, sticky="w")
        self.utilization_var = tk.StringVar(
            value=f"{settings.voltage_utilization:.3f}" if settings else "1.000"
        )
        ttk.Entry(frame, textvariable=self.utilization_var, width=8).grid(
            row=0, column=5, padx=(4, 14)
        )

        ttk.Label(frame, text="电流上限 (A rms)").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.current_var = tk.StringVar(
            value=(
                f"{settings.current_limit_rms_a:.4f}"
                if settings and settings.current_limit_rms_a
                else ""
            )
        )
        ttk.Entry(frame, textvariable=self.current_var, width=10).grid(
            row=1, column=1, padx=(4, 14), pady=(4, 0)
        )
        ttk.Label(frame, text="（留空 = 使用设计额定电流）").grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(4, 0)
        )

        self.solve_button = ttk.Button(frame, text="求解能力", command=self.refresh)
        self.solve_button.grid(row=1, column=4, padx=(4, 6), pady=(4, 0))
        self.export_button = ttk.Button(frame, text="导出...", command=self.export)
        self.export_button.grid(row=1, column=5, pady=(4, 0))

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            self.window, textvariable=self.status_var, wraplength=960,
            justify=tk.LEFT, foreground="#8a6d1f",
        ).pack(anchor=tk.W, padx=10, pady=(0, 4))

    def _text_tab(self, label: str) -> tk.Text:
        frame = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(frame, text=label)
        widget = tk.Text(frame, wrap=tk.NONE)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=widget.yview)
        widget.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return widget

    def _build_summary_tab(self) -> None:
        self.summary_text = self._text_tab("能力总览")

    def _build_torque_speed_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(frame, text="转矩-转速曲线")
        self.torque_speed_host = ttk.Frame(frame)
        self.torque_speed_host.pack(fill=tk.BOTH, expand=True)
        self.torque_speed_status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.torque_speed_status, wraplength=900).pack(anchor=tk.W)

    def _build_dq_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(frame, text="dq 电流平面")
        self.dq_host = ttk.Frame(frame)
        self.dq_host.pack(fill=tk.BOTH, expand=True)
        self.dq_status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.dq_status, wraplength=900).pack(anchor=tk.W)

    def _build_inspector_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(frame, text="工作点查看")
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row, text="转速 (rpm)").pack(side=tk.LEFT)
        self.inspect_speed_var = tk.StringVar(value="")
        entry = ttk.Entry(row, textvariable=self.inspect_speed_var, width=12)
        entry.pack(side=tk.LEFT, padx=(4, 6))
        entry.bind("<Return>", lambda _event: self.refresh_inspector())
        ttk.Button(row, text="查看", command=self.refresh_inspector).pack(side=tk.LEFT)
        self.inspector_text = tk.Text(frame, wrap=tk.WORD, height=22)
        self.inspector_text.pack(fill=tk.BOTH, expand=True)
        self.inspector_text.configure(state=tk.DISABLED)

    def _build_provenance_tab(self) -> None:
        self.provenance_text = self._text_tab("参数溯源")

    # ------------------------------------------------------------------
    # Headless-testable content
    # ------------------------------------------------------------------

    def selected_modulation(self) -> Modulation:
        label = str(self.modulation_var.get()).strip()
        for modulation, text in MODULATION_LABELS_ZH.items():
            if text == label:
                return modulation
        return Modulation.SVPWM

    def current_settings(self) -> InverterSettings:
        def number(variable, fallback):
            try:
                return float(str(variable.get()).strip())
            except (TypeError, ValueError):
                return fallback

        raw_current = str(self.current_var.get()).strip()
        return InverterSettings(
            dc_bus_voltage_v=number(self.bus_var, 48.0),
            modulation=self.selected_modulation(),
            voltage_utilization=number(self.utilization_var, 1.0),
            current_limit_rms_a=float(raw_current) if raw_current else None,
        )

    def solve(self):
        """Run the capability solver. Returns the result, or None with a reason."""

        self._error = None
        try:
            analysis = self._analysis_provider()
            parameters = dict(self._parameters_provider())
        except Exception as error:  # noqa: BLE001 - the view must survive
            self._error = f"无法获取当前设计：{error}"
            return None
        if analysis is None:
            self._error = "尚未运行计算：请先在主窗口执行一次分析。"
            return None
        try:
            self.result = solve_from_analysis(analysis, parameters, self.current_settings())
        except Exception as error:  # noqa: BLE001
            self._error = f"能力求解失败：{error}"
            self.result = None
            return None
        if self._on_settings_changed is not None:
            self._on_settings_changed(self.current_settings())
        return self.result

    def render_summary_text(self) -> str:
        if self.result is None:
            return self._error or "尚无能力结果。"
        text = render_summary_zh(self.result)
        issues = capability_issues(
            self.result,
            required_speed_rpm=float(self._parameters_provider().get("n_rated") or 0) or None,
            required_torque_nm=None,
        )
        if issues:
            text += "\n\n可行性提示：\n" + "\n".join(
                f"  [{issue.severity}] {issue.code}\n      {issue.message_zh}"
                for issue in issues
            )
        return text

    def render_inspector_text(self, speed_rpm: float | None = None) -> str:
        if self.result is None:
            return self._error or "尚无能力结果。"
        if speed_rpm is None:
            speed_rpm = self.result.base_speed.speed_rpm
        point = self.result.point_at(speed_rpm)
        if point is None:
            return "该转速下没有可行工作点。"
        return "\n".join(
            [
                f"请求转速：{speed_rpm:.1f} rpm　→　最近的已求解包络点：{point.speed_rpm:.1f} rpm",
                "",
                f"id                ：{point.id_a:+.6f} A（相电流峰值）",
                f"iq                ：{point.iq_a:+.6f} A（相电流峰值）",
                f"vd                ：{point.vd_v:+.6f} V（相电压峰值）",
                f"vq                ：{point.vq_v:+.6f} V（相电压峰值）",
                "",
                f"电流幅值 |I|      ：{point.current_magnitude_a:.6f} A"
                f"（上限 {self.result.current_limit.peak_a:.6f} A）",
                f"电压幅值 |V|      ：{point.voltage_magnitude_v:.6f} V"
                f"（上限 {self.result.voltage_limit.phase_peak_v:.6f} V）",
                f"电流利用率        ：{point.current_utilization * 100.0:.3f} %",
                f"电压利用率        ：{point.voltage_utilization * 100.0:.3f} %",
                "",
                f"转矩 T_em         ：{point.torque_nm:.6f} N·m",
                f"机械功率 T·ω_m    ：{point.mechanical_power_w:.4f} W",
                f"ω_m               ：{point.omega_m_rad_s:.4f} rad/s",
                f"ω_e               ：{point.omega_e_rad_s:.4f} rad/s",
                "",
                f"运行区间          ：{point.region.value}",
                f"                    {REGION_LABELS_ZH[point.region]}",
                f"起作用的约束      ：{', '.join(point.active_constraints)}",
                "",
                f"证据类别：{EVIDENCE_STATEMENT}",
                f"  {EVIDENCE_NOTE_ZH}",
                f"标定状态：{CALIBRATION_STATUS}",
            ]
        )

    def render_provenance_text(self) -> str:
        if self.result is None:
            return self._error or "尚无能力结果。"
        return render_provenance_zh(self.result.parameters)

    def headline_values(self) -> dict[str, Any]:
        """The headline numbers, for the smoke harness and tests."""

        if self.result is None:
            return {"available": False, "error": self._error}
        return {
            "available": True,
            "base_speed_rpm": self.result.base_speed.speed_rpm,
            "base_speed_resolved": self.result.base_speed.resolved,
            "maximum_speed_rpm": self.result.maximum_speed.speed_rpm,
            "maximum_speed_bounded": self.result.maximum_speed.bounded,
            "peak_torque_nm": self.result.peak_torque_nm,
            "peak_power_w": self.result.peak_power_w,
            "dc_bus_voltage_v": self.result.voltage_limit.dc_bus_voltage_v,
            "current_limit_peak_a": self.result.current_limit.peak_a,
            "voltage_limit_phase_peak_v": self.result.voltage_limit.phase_peak_v,
            "modulation": self.result.voltage_limit.modulation.value,
            "mtpa_method": self.result.mtpa_at_limit.method,
            "mtpa_id_a": self.result.mtpa_at_limit.id_a,
            "field_weakening_active": self.result.field_weakening_active,
            "constant_power_exists": self.result.constant_power.exists,
            "regions": [region.value for region in self.result.regions_present()],
            "evidence": EVIDENCE_STATEMENT,
            "calibration_status": CALIBRATION_STATUS,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _render_figure(self, host, builder, status_var) -> bool:
        for child in host.winfo_children():
            child.destroy()
        if self.result is None:
            status_var.set(self._error or "尚无能力结果。")
            return False
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            figure = builder(self.result)
            canvas = FigureCanvasTkAgg(figure, master=host)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            status_var.set(EVIDENCE_NOTE_ZH)
            return True
        except Exception as error:  # noqa: BLE001 - a plot must never break the view
            status_var.set(f"绘图不可用：{error}")
            return False

    def refresh_inspector(self) -> str:
        raw = str(self.inspect_speed_var.get()).strip()
        try:
            speed = float(raw) if raw else None
        except ValueError:
            speed = None
        text = self.render_inspector_text(speed)
        self.inspector_text.configure(state=tk.NORMAL)
        self.inspector_text.delete("1.0", "end")
        self.inspector_text.insert("1.0", text)
        self.inspector_text.configure(state=tk.DISABLED)
        return text

    def refresh(self):
        from ..plots.capability import build_id_iq_figure, build_torque_speed_figure

        self.solve()
        if self.result is None:
            self.status_var.set(self._error or "尚无能力结果。")
        else:
            base = self.result.base_speed
            maximum = self.result.maximum_speed
            self.status_var.set(
                f"基速 {base.speed_rpm:.0f} rpm　|　最高转速 {maximum.speed_rpm:.0f} rpm"
                f"{'' if maximum.bounded else '（搜索上限）'}　|　"
                f"峰值转矩 {self.result.peak_torque_nm:.3f} N·m　|　"
                f"峰值功率 {self.result.peak_power_w:.0f} W　|　"
                f"MTPA {self.result.mtpa_at_limit.method}　|　"
                f"弱磁 {'已进入' if self.result.field_weakening_active else '未进入'}"
            )
            if not self.inspect_speed_var.get().strip():
                self.inspect_speed_var.set(f"{base.speed_rpm:.0f}")

        for widget, text in (
            (self.summary_text, self.render_summary_text()),
            (self.provenance_text, self.render_provenance_text()),
        ):
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state=tk.DISABLED)

        self._render_figure(self.torque_speed_host, build_torque_speed_figure, self.torque_speed_status)
        self._render_figure(self.dq_host, build_id_iq_figure, self.dq_status)
        self.refresh_inspector()
        return self.result

    def export(self, destination: str | Path | None = None):
        if self.result is None:
            messagebox.showwarning("无结果", "尚无可导出的能力结果。", parent=self.window)
            return None
        if destination is None:
            destination = filedialog.askdirectory(
                parent=self.window, title="选择能力导出目录",
                initialdir=str(self._export_dir),
            )
            if not destination:
                return None
        return export_capability(
            self.result,
            destination,
            required_speed_rpm=float(self._parameters_provider().get("n_rated") or 0) or None,
        )
