# Motor Calculator Refactor Workspace

This repository preserves the legacy AFPM PMSM/BLDC calculator behavior while refactoring the code into a testable core.

## Development Setup

Install the development test dependency set:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`matplotlib` is now an optional GUI dependency. The calculator can still import, run headless calculations, and export JSON/CSV/TXT without it. Install it only if you need in-GUI plots and chart image export:

```powershell
.venv\Scripts\python.exe -m pip install matplotlib
```

## Start The GUI

Launch the current GUI entry point with:

```powershell
.venv\Scripts\python.exe motor_calculator\app.py
```

Verify Tcl/Tk independently before GUI work:

```powershell
.venv\Scripts\python.exe work\check_tk_runtime.py
```

Mutable runtime data is stored outside the repository under
`%LOCALAPPDATA%\MotorCalculator\` by default. Set
`MOTOR_CALCULATOR_USER_DATA` only when a controlled portable/test location is required.

If `matplotlib` is not installed, the GUI should still start importing correctly, but chart tabs and chart saving will be disabled with a Chinese error message instead of crashing.

## Run Tests

The formal test command for this project is:

```powershell
.venv\Scripts\python.exe -m pytest -v
```

`work/run_pytest_style.py` is retained only as a temporary compatibility runner for environments that do not yet have `pytest`.

## Common GUI Runtime Issues

### Missing `matplotlib`

Symptoms:

- `motor_calculator\app.py` used to fail during import with `ModuleNotFoundError: No module named 'matplotlib'`

Current behavior:

- GUI import no longer hard-depends on `matplotlib`
- headless calculation and JSON/CSV/TXT export remain available
- chart rendering and chart image export are disabled until `matplotlib` is installed

### Missing Tcl/Tk `init.tcl`

Symptoms:

- `tkinter` can be imported, but `tk.Tk()` or `tkinter.Tcl()` fails
- errors mention `Can't find a usable init.tcl`

Recommended fix:

1. Create the virtual environment from a full Windows CPython installation that includes Tcl/Tk.
2. Prefer the official python.org installer on Windows for GUI work.
3. Recreate `.venv` from that interpreter, then rerun the GUI start command.

If your Python install already includes Tcl/Tk but the runtime cannot find it, you can try setting environment variables before launch:

```powershell
$env:TCL_LIBRARY = "C:\Path\To\Python\tcl\tcl8.6"
$env:TK_LIBRARY = "C:\Path\To\Python\tcl\tk8.6"
.venv\Scripts\python.exe motor_calculator\app.py
```

Do not hard-code these absolute paths into repository code.

## Build The Windows Engineering Preview

Use a complete Windows CPython installation whose Tk probe succeeds, then install the
separate packaging dependency and build the preferred one-folder distribution:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-packaging.txt
powershell -ExecutionPolicy Bypass -File work\build_windows_preview.ps1
```

The build script stops before packaging if Tcl/Tk is unusable. Generated `build/` and
`dist/` directories are intentionally not committed.

## Scope Reminder

The current refactor intentionally does not change production electromagnetic formulas, default calculation chains, or `legacy_baseline.json` unless explicitly approved.
