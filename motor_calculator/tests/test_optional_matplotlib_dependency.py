"""Optional matplotlib behavior for the GUI layer."""

from __future__ import annotations

import builtins
import importlib

import pytest


def test_legacy_gui_module_imports_even_without_matplotlib(monkeypatch):
    main_window = importlib.import_module("gui.main_window")
    monkeypatch.setattr(main_window, "_LEGACY_MODULE", None)

    real_import = builtins.__import__

    def block_matplotlib_import(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError("matplotlib intentionally hidden for optional dependency test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_matplotlib_import)
    legacy_module = main_window._get_legacy_module()

    assert hasattr(legacy_module, "MATPLOTLIB_AVAILABLE")
    assert legacy_module.MATPLOTLIB_AVAILABLE is False
    assert legacy_module.MATPLOTLIB_IMPORT_ERROR is not None


def test_main_reports_tcl_tk_runtime_error_in_chinese(monkeypatch):
    main_window = importlib.import_module("gui.main_window")

    def raise_tcl_error():
        raise main_window.tk.TclError("missing init.tcl")

    monkeypatch.setattr(main_window.tk, "Tk", raise_tcl_error)

    with pytest.raises(SystemExit) as excinfo:
        main_window.main()

    message = str(excinfo.value)
    assert "GUI 启动失败" in message
    assert "Tcl/Tk" in message
    assert "README" in message
