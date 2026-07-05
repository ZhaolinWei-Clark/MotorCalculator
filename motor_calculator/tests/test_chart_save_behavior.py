"""Chart save and export smoke coverage for the legacy GUI shell."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge


class DummyResultText:
    def __init__(self, text: str = "headless report") -> None:
        self.text = text

    def get(self, *_args):
        return self.text


class MessageRecorder:
    def __init__(self) -> None:
        self.infos: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []
        self.errors: list[tuple[str, str]] = []


class FigureWriter:
    def __init__(self, should_write: bool = True) -> None:
        self.should_write = should_write

    def savefig(self, output_path, **_kwargs) -> None:
        if self.should_write:
            Path(output_path).write_bytes(b"fake-png")


@pytest.fixture
def legacy_module():
    main_window = importlib.import_module("gui.main_window")
    return main_window._get_legacy_module()


@pytest.fixture
def sample_results():
    return LegacyGuiMotorModelBridge(build_sample_legacy_params()).run_full_analysis()


def _install_messagebox_recorder(monkeypatch, legacy_module):
    recorder = MessageRecorder()
    monkeypatch.setattr(legacy_module.messagebox, "showinfo", lambda title, message: recorder.infos.append((title, message)))
    monkeypatch.setattr(
        legacy_module.messagebox,
        "showwarning",
        lambda title, message: recorder.warnings.append((title, message)),
    )
    monkeypatch.setattr(legacy_module.messagebox, "showerror", lambda title, message: recorder.errors.append((title, message)))
    return recorder


def _build_export_dummy(sample_results, report_text: str = "headless report"):
    return SimpleNamespace(
        calc_results=sample_results,
        generated_figures={},
        result_text=DummyResultText(report_text),
        _get_params=lambda: build_sample_legacy_params(),
    )


def test_save_plots_without_matplotlib_shows_error(monkeypatch, legacy_module, sample_results, tmp_path):
    recorder = _install_messagebox_recorder(monkeypatch, legacy_module)
    monkeypatch.setattr(legacy_module.filedialog, "askdirectory", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(legacy_module, "MATPLOTLIB_AVAILABLE", False)

    dummy = _build_export_dummy(sample_results)
    dummy.generated_figures = {"performance_curves": FigureWriter()}

    legacy_module.MotorCalculatorApp.save_plots(dummy)

    assert recorder.infos == []
    assert recorder.errors
    assert "matplotlib" in recorder.errors[0][1]


def test_save_plots_only_reports_success_after_real_files_exist(monkeypatch, legacy_module, sample_results, tmp_path):
    recorder = _install_messagebox_recorder(monkeypatch, legacy_module)
    monkeypatch.setattr(legacy_module.filedialog, "askdirectory", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(legacy_module, "MATPLOTLIB_AVAILABLE", True)

    dummy = _build_export_dummy(sample_results)
    dummy.generated_figures = {
        "performance_curves": FigureWriter(),
        "back_emf": FigureWriter(),
        "torque": FigureWriter(),
        "flux_distribution": FigureWriter(),
        "geometry": FigureWriter(),
    }

    legacy_module.MotorCalculatorApp.save_plots(dummy)

    assert recorder.errors == []
    assert recorder.warnings == []
    assert len(recorder.infos) == 1
    for filename in [
        "performance_curves.png",
        "back_emf.png",
        "torque.png",
        "flux_distribution.png",
        "geometry.png",
    ]:
        assert (tmp_path / filename).exists()


def test_save_plots_does_not_claim_success_when_files_are_missing(monkeypatch, legacy_module, sample_results, tmp_path):
    recorder = _install_messagebox_recorder(monkeypatch, legacy_module)
    monkeypatch.setattr(legacy_module.filedialog, "askdirectory", lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(legacy_module, "MATPLOTLIB_AVAILABLE", True)

    dummy = _build_export_dummy(sample_results)
    dummy.generated_figures = {
        "performance_curves": FigureWriter(False),
        "back_emf": FigureWriter(False),
        "torque": FigureWriter(False),
        "flux_distribution": FigureWriter(False),
        "geometry": FigureWriter(False),
    }

    legacy_module.MotorCalculatorApp.save_plots(dummy)

    assert recorder.infos == []
    assert recorder.errors
    assert "未生成任何图表文件" in recorder.errors[0][1]


def test_export_json_csv_and_txt_succeed_headlessly(monkeypatch, legacy_module, sample_results, tmp_path):
    recorder = _install_messagebox_recorder(monkeypatch, legacy_module)
    dummy = _build_export_dummy(sample_results, report_text="report body")

    json_path = tmp_path / "results.json"
    csv_path = tmp_path / "results.csv"
    txt_path = tmp_path / "report.txt"
    requested_paths = iter([str(json_path), str(csv_path), str(txt_path)])
    monkeypatch.setattr(legacy_module.filedialog, "asksaveasfilename", lambda **_kwargs: next(requested_paths))

    legacy_module.MotorCalculatorApp.export_json(dummy)
    legacy_module.MotorCalculatorApp.export_csv(dummy)
    legacy_module.MotorCalculatorApp._export_txt(dummy)

    assert json_path.exists()
    exported_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert "输入参数" in exported_json
    assert "计算结果" in exported_json

    assert csv_path.exists()
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    assert "永磁直流电机计算结果" in csv_text

    assert txt_path.exists()
    assert txt_path.read_text(encoding="utf-8") == "report body"

    assert len(recorder.infos) == 3
