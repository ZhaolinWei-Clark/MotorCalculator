# Motor Calculator Refactor Workspace

This repository preserves the legacy AFPM PMSM/BLDC calculator behavior while refactoring the code into a testable core.

## Development Testing

Create or reuse the local virtual environment, install development dependencies, and run the standard test suite:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -v
```

The formal test command for this project is:

```powershell
python -m pytest -v
```

`work/run_pytest_style.py` is retained only as a temporary compatibility runner for environments that do not yet have `pytest`.
