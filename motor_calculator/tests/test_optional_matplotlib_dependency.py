"""Optional matplotlib behavior for the GUI layer."""

from __future__ import annotations

import importlib

import pytest


def test_legacy_gui_module_imports_even_without_matplotlib():
    main_window = importlib.import_module("gui.main_window")
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
