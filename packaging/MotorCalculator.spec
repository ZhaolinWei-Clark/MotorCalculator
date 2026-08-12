# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder engineering-preview build."""

import importlib.util
from pathlib import Path


repository_root = Path(SPECPATH).resolve().parent
hidden_imports = [
    "motor_calculator.gui.main_window",
    "motor_calculator.validation.feedback_service",
    "motor_calculator.validation.phase7i_uncertainty_report",
    "tkinter.scrolledtext",
]
if importlib.util.find_spec("matplotlib") is not None:
    hidden_imports.extend(
        (
            "matplotlib",
            "matplotlib.backends.backend_tkagg",
            "matplotlib.figure",
        )
    )

data_files = [
    (
        str(repository_root / "motor_calculator" / "PMDC_Calculator_claude204.py"),
        "motor_calculator",
    ),
    (
        str(repository_root / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"),
        "validation_data/uncertainty",
    ),
    (
        str(repository_root / "validation_data" / "fea_reference" / "phase7h_controlled_ssdr_machine.json"),
        "validation_data/fea_reference",
    ),
    (
        str(repository_root / "motor_calculator" / "presets" / "data" / "presets.json"),
        "motor_calculator/presets/data",
    ),
]

analysis = Analysis(
    [str(repository_root / "motor_calculator" / "app.py")],
    pathex=[str(repository_root), str(repository_root / "motor_calculator")],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "motor_calculator.tests"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MotorCalculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MotorCalculator",
)
