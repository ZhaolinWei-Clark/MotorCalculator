# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder release-candidate build."""

import importlib.util
from pathlib import Path


repository_root = Path(SPECPATH).resolve().parent
hidden_imports = [
    "motor_calculator.gui.main_window",
    "motor_calculator.gui.results_dashboard",
    "motor_calculator.gui.analysis_dialogs",
    "motor_calculator.analysis_service",
    "motor_calculator.plots",
    "motor_calculator.plots.performance",
    "motor_calculator.plots.export",
    "motor_calculator.plots.analysis",
    "motor_calculator.validation.feedback_service",
    "motor_calculator.validation.phase7i_uncertainty_report",
    # Phase 10A. The FEA bridge is imported lazily from the analysis menu, so
    # PyInstaller cannot see it by static analysis. It has no FEMM dependency:
    # the packaged application must start and run normally on a machine with no
    # FEA software installed.
    "motor_calculator.fea",
    "motor_calculator.fea.service",
    "motor_calculator.fea.view_model",
    "motor_calculator.gui.fea_validation_dialog",
    # Phase 10E. comparison.py imports this lazily inside a function, so static
    # analysis cannot see it and the packaged build would lose the meshed
    # winding factor -- falling back silently to the entered value.
    "motor_calculator.fea.meshed_winding",
    "motor_calculator.fea.diagnostics",
    # Phase 10G. The winding engineering dialog is imported lazily from the
    # analysis menu, so static analysis cannot see it and the packaged build
    # would open the menu entry onto an ImportError.
    "motor_calculator.gui.winding_dialog",
    "motor_calculator.winding",
    "motor_calculator.winding.electrical_axis",
    "motor_calculator.winding.report",
    "motor_calculator.winding.slot_fill",
    "motor_calculator.winding.panel_text",
    # Phase 10H
    "motor_calculator.winding.authority",
    "motor_calculator.winding.persistence",
    "motor_calculator.winding.export",
    "motor_calculator.winding.feasibility",
    # Phase 11A. The winding evaluation and dashboard summary are imported
    # lazily from inside GUI methods; without these the packaged dashboard would
    # silently lose its manufacturability line.
    "motor_calculator.winding.evaluation",
    "motor_calculator.winding.dashboard_summary",
    # Phase 11A. The validation data manager is imported lazily from the
    # analysis menu, and its analysis modules are reached only through the
    # service, so static analysis sees none of them.
    "motor_calculator.gui.validation_data_dialog",
    "motor_calculator.experiment",
    "motor_calculator.experiment.analysis",
    "motor_calculator.experiment.columns",
    "motor_calculator.experiment.comparison",
    "motor_calculator.experiment.compatibility",
    "motor_calculator.experiment.csv_import",
    "motor_calculator.experiment.persistence",
    "motor_calculator.experiment.public_reference",
    "motor_calculator.experiment.regression",
    "motor_calculator.experiment.report",
    "motor_calculator.experiment.schema",
    "motor_calculator.experiment.service",
    "motor_calculator.experiment.sources",
    "motor_calculator.experiment.templates",
    "motor_calculator.experiment.units",
    # Phase 11B. The CREATOR public-reference modules are reached only through
    # the validation dialog's own lazy imports, so static analysis sees none of
    # them; without these the public-reference tab would open onto an
    # ImportError in the packaged build.
    "motor_calculator.experiment.creator_adapter",
    "motor_calculator.experiment.creator_evidence",
    "motor_calculator.experiment.creator_source",
    "motor_calculator.experiment.harmonics",
    "motor_calculator.experiment.origins",
    "motor_calculator.experiment.topology",
    # Phase 12. The capability solver and its figures are imported lazily from
    # the analysis menu, so static analysis sees none of them; without these the
    # capability view would open onto an ImportError in the packaged build.
    "motor_calculator.gui.capability_dialog",
    "motor_calculator.plots.capability",
    "motor_calculator.capability",
    "motor_calculator.capability.conventions",
    "motor_calculator.capability.envelope",
    "motor_calculator.capability.export",
    "motor_calculator.capability.feasibility",
    "motor_calculator.capability.limits",
    "motor_calculator.capability.parameters",
    "motor_calculator.capability.persistence",
    "motor_calculator.capability.solver",
    "motor_calculator.capability.steady_state",
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
    (
        str(
            repository_root
            / "validation_data"
            / "fea_cases"
            / "phase10a_coreless_ssdr_reference_v1.json"
        ),
        "validation_data/fea_cases",
    ),
]
build_info = repository_root / "packaging" / "build_info.json"
if build_info.is_file():
    data_files.append((str(build_info), "."))

version_file = repository_root / "packaging" / "windows_version_info.txt"

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
    version=str(version_file) if version_file.is_file() else None,
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
