"""Create and destroy a real Tk root to verify the development runtime."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from motor_calculator.runtime.health import probe_tk_runtime


def main() -> int:
    result: dict[str, object] = {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "architecture": platform.architecture()[0],
        "base_prefix": sys.base_prefix,
    }
    try:
        tcl_patchlevel, tk_version, module_path = probe_tk_runtime()
    except Exception as exc:
        result.update(
            {
                "status": "FAILED",
                "error": str(exc),
                "remediation": (
                    "Install a complete Windows CPython distribution with Tcl/Tk, recreate .venv, "
                    "and rerun this script."
                ),
            }
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    result.update(
        {
            "status": "OK",
            "tcl_patchlevel": tcl_patchlevel,
            "tk_version": tk_version,
            "tkinter_module": module_path,
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
