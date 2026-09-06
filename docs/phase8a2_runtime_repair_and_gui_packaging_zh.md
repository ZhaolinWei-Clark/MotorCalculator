# Phase 8A.2 Windows Runtime Repair and Packaged GUI Validation

## 1. Scope and freeze boundary

Phase 8A.2 only repairs and verifies the Windows development/runtime packaging path. It does not change motor physics, production calculations, dynamic/control equations, advanced AFPM equations, calibration logic, or the legacy baseline.

The existing repository `tmp/` directory was not used, modified, staged, or committed.

## 2. Python and Tcl/Tk repair

The previous managed Python distribution contained Tcl/Tk files but could not initialize a real Tk root. Environment-variable overrides did not repair that distribution.

The project environment was rebuilt from the standard 64-bit CPython installation:

- Base interpreter: `D:\Python312\python.exe`
- Python: `3.12.10`
- Tcl/Tk: `8.6.15`
- Virtual environment: repository `.venv`, recreated from the base interpreter
- PyInstaller: `6.16.0`
- NumPy: `2.3.5`
- Matplotlib: `3.11.0`
- pytest: `9.1.1`

Both the base interpreter and rebuilt virtual environment can create and destroy a real Tk root. The original `BLOCKED_BY_BASE_PYTHON_DISTRIBUTION` condition is resolved.

## 3. Source GUI verification

`SOURCE_GUI_STATUS = PASS`

The real source GUI was launched with Tk rather than a headless widget mock. The smoke procedure verified:

- main window creation and clean shutdown;
- the default static calculation;
- the `Confidence & Validation` tab;
- feedback and uncertainty dialogs;
- local feedback append and reload;
- local confidence export;
- Matplotlib availability;
- absence of `TclError` and Matplotlib startup failures.

The default smoke calculation returned finite outputs, including phase RMS back-EMF `23.604703894560327 V`, line RMS back-EMF `40.88454644299743 V`, and efficiency `91.95522091262109%`.

## 4. One-folder package

`PACKAGING_STATUS = PASS`

The existing one-folder PyInstaller configuration was retained. A first packaged launch exposed a genuine dynamic-import omission for `tkinter.scrolledtext`; adding that module to the spec hidden imports resolved the failure. No one-file conversion was attempted.

- Dist directory: `dist\MotorCalculator`
- Executable: `dist\MotorCalculator\MotorCalculator.exe`
- File count: `1242`
- Package size: `89,962,040 bytes` (`85.79 MiB`)

Required packaged Tcl/Tk resources were confirmed present:

- `_internal\tcl86t.dll`
- `_internal\tk86t.dll`
- `_internal\_tkinter.pyd`
- `_internal\_tcl_data\init.tcl`
- `_internal\_tk_data\tk.tcl`

## 5. Packaged functional and persistence smoke

`PACKAGED_GUI_STATUS = PASS`

The rebuilt executable was launched from `%TEMP%`, not from the repository working directory, with `TCL_LIBRARY` and `TK_LIBRARY` removed. It exited with code `0` after verifying the same static calculation, Confidence UI, dialogs, Matplotlib, logs, local export, feedback append/reload, restart behavior, and clean shutdown.

The final no-source-environment run temporarily renamed the repository `.venv`. During execution `.venv` was absent, and the packaged application still passed all smoke checks. The virtual environment was restored afterward.

`NO_SOURCE_VENV_STATUS = PASS`

This demonstrates that the packaged application does not depend at runtime on the repository working directory, source virtual environment, developer Tcl/Tk variables, or source Python site-packages.

## 6. DPI, work area, and visual verification

`PACKAGED_VISUAL_STATUS = PASS`

The window sizing path uses Tk scaling and the Windows work area rather than the full monitor bounds. Final verification was performed at the current approximately 200% scaling environment:

- Reported screen DPI: approximately `192.19`
- Tk scaling: approximately `2.6693`
- Screen: `3072 x 1920`
- Windows work area: `3072 x 1824`
- Application window: `2918 x 1732`

The corrected Pillow HWND capture contains the MotorCalculator window itself rather than the window behind it. Visual inspection confirmed:

- critical left-panel controls and bottom export/reset actions are visible;
- all result tabs, including `Confidence & Validation`, are usable;
- confidence actions at the bottom of the tab are visible;
- feedback and uncertainty dialogs fit within the work area;
- no critical clipping or taskbar overlap is present.

The current high-DPI behavior is acceptable for this engineering-preview gate. This is not a claim that every monitor arrangement, font setting, or remote-desktop configuration has been certified.

## 7. Tests

- Before environment rebuild: `480 passed`
- After environment rebuild checkpoint: `480 passed`
- Final runtime/packaging targeted suite: `23 passed`
- Final full suite: `486 passed in 16.63s`

The increase from 480 to 486 is caused by six new runtime, work-area, DPI-scaling, and smoke-argument tests. There were no test failures.

One intermediate run encountered `PermissionError` in pytest's default `%TEMP%\pytest-of-<USER>` directory after a restricted sandbox process created incompatible ACL state. The final full suite used a fresh unique pytest `--basetemp`; this was an execution-environment issue, not a product failure.

## 8. Remaining deployment limitations

- The one-folder package has been validated on the current Windows machine, but not yet on a separate clean Windows host or VM.
- The executable is not code-signed and no installer is produced.
- One-file packaging, automatic updates, installer upgrade/uninstall behavior, and enterprise policy compatibility remain outside Phase 8A.2.
- Visual verification covers the current high-DPI environment and earlier source checks; it is not an exhaustive monitor/DPI matrix certification.

`CLEAN_MACHINE_READINESS = READY_FOR_EXTERNAL_CLEAN_MACHINE_PILOT`

## 9. Final decision

The original Tcl/Tk blocker is resolved, the real source GUI and rebuilt one-folder executable both pass functional and visual smoke gates, and the package runs without the source `.venv`. Phase 8A can therefore be formally closed as an engineering-preview Windows runtime and packaging foundation.

Phase 8B may be recommended as the next separately approved phase, but it is not started here.
