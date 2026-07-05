"""GUI import and headless smoke coverage."""

from __future__ import annotations

import importlib

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge


def test_app_module_imports():
    module = importlib.import_module("app")
    assert callable(module.main)


def test_gui_main_window_imports_without_loading_legacy_charts():
    module = importlib.import_module("gui.main_window")
    assert callable(module.main)
    assert callable(module.MotorCalculatorApp)


def test_headless_default_calculation_succeeds():
    results = LegacyGuiMotorModelBridge(build_sample_legacy_params()).run_full_analysis()

    assert results.performance.T_rated > 0
    assert results.performance.P_out > 0
    assert results.electrical.Ke > 0
