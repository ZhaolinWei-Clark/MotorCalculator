"""Minimal pytest-style test runner for environments without pytest installed."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path


def load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1] / "motor_calculator"
    sys.path.insert(0, str(repo_root))
    tests_dir = repo_root / "tests"
    test_files = sorted(path for path in tests_dir.glob("test_*.py"))

    passed = 0
    failed = 0

    for test_file in test_files:
        module = load_module(test_file)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            try:
                function()
                passed += 1
                print(f"PASS {test_file.name}::{name}")
            except Exception:
                failed += 1
                print(f"FAIL {test_file.name}::{name}")
                traceback.print_exc()

    print(f"SUMMARY passed={passed} failed={failed} total={passed + failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
