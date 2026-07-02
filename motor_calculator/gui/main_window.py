"""Legacy GUI wrapper that delegates all electromagnetic calculations to motor_core."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

from motor_core import LegacyGuiMotorModelBridge, MotorCalculationError, MotorValidationError, parse_legacy_gui_params


def _load_legacy_module():
    legacy_path = Path(__file__).resolve().parents[1] / "PMDC_Calculator_claude204.py"
    spec = importlib.util.spec_from_file_location("legacy_motor_calculator_ui", legacy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 legacy GUI 文件: {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PMDCMotorModel = LegacyGuiMotorModelBridge
    return module


_LEGACY_MODULE = _load_legacy_module()
tk = _LEGACY_MODULE.tk
ttk = _LEGACY_MODULE.ttk
messagebox = _LEGACY_MODULE.messagebox


class MotorCalculatorApp(_LEGACY_MODULE.MotorCalculatorApp):
    """GUI subclass with strict input parsing and non-crashing error handling."""

    def _collect_raw_params(self) -> Dict[str, Any]:
        raw: Dict[str, Any] = {}
        for key, var in self.vars.items():
            raw[key] = var.get()
        raw["coreless"] = self.coreless_var.get()
        return raw

    def _get_params(self) -> Dict[str, Any]:
        return parse_legacy_gui_params(self._collect_raw_params())

    def _inject_phase3a_report_summary(self) -> None:
        if not getattr(self, "calc_results", None):
            return
        metadata = self.calc_results.metadata
        summary_lines = [
            "",
            "Phase 3A Electrical Semantics",
            f"控制模式: {metadata.get('控制模式', 'N/A')}",
            f"legacy控制模型: {metadata.get('legacy控制模型', 'N/A')}",
            f"机械转速: {metadata.get('机械转速_rpm', 'N/A')} rpm",
            f"电频率: {metadata.get('电频率_Hz', 'N/A')} Hz",
            "-" * 70,
            "",
        ]
        self.result_text.insert("1.0", "\n".join(summary_lines))

    def run_analysis(self):
        try:
            params = self._get_params()
            model = LegacyGuiMotorModelBridge(params)
            self.calc_results = model.run_full_analysis()
            self.calculation_history.append(
                {
                    "timestamp": _LEGACY_MODULE.datetime.now().isoformat(),
                    "params": params,
                    "results": self.calc_results.to_dict(),
                }
            )
            self._display_report()
            self._inject_phase3a_report_summary()
            self._plot_performance_curves()
            self._plot_back_emf()
            self._plot_torque()
            self._plot_flux_distribution()
            self._draw_geometry()
            self.notebook.select(0)
            messagebox.showinfo("分析完成", "电磁分析计算已完成。\n请查看各选项卡中的结果。")
        except (MotorValidationError, MotorCalculationError) as exc:
            messagebox.showerror("分析错误", str(exc))
        except Exception as exc:
            messagebox.showerror("分析错误", f"计算失败:\n{exc}")


def main():
    root = tk.Tk()
    try:
        root.iconbitmap("motor_icon.ico")
    except Exception:
        pass

    MotorCalculatorApp(root)
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x_pos = (root.winfo_screenwidth() // 2) - (width // 2)
    y_pos = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"+{x_pos}+{y_pos}")
    root.mainloop()
