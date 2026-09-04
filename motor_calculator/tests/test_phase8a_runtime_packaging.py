"""Phase 8A runtime and packaging reliability tests."""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from pathlib import Path

import pytest

from motor_calculator.runtime.display import (
    bounded_window_size,
    dpi_scaled_window_size,
    windows_work_area,
)
from motor_calculator.runtime.health import (
    HealthStatus,
    check_runtime_health,
    format_startup_failure,
)
from motor_calculator.gui.main_window import _smoke_output_argument
from motor_calculator.runtime.logging_config import LOGGER_NAME, initialize_local_logging
from motor_calculator.runtime.paths import (
    check_packaged_resources,
    create_runtime_directories,
    resolve_runtime_paths,
)
from motor_calculator.validation.feedback_service import load_feedback_records
from motor_calculator.version import APPLICATION_VERSION, RUNTIME_SCHEMA_VERSION, get_git_commit


ROOT = Path(__file__).resolve().parents[2]
CALCULATIONS = ROOT / "motor_calculator" / "motor_core" / "calculations.py"
LEGACY_BASELINE = ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"


def _temporary_paths(tmp_path: Path):
    return resolve_runtime_paths(
        environment={"MOTOR_CALCULATOR_USER_DATA": str(tmp_path / "user-data")},
        source_root=ROOT,
        platform_name="win32",
        home_dir=tmp_path,
    )


def test_source_paths_do_not_depend_on_current_working_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = _temporary_paths(tmp_path)
    assert paths.mode == "source"
    assert paths.application_root == ROOT
    assert paths.resource_root == ROOT


def test_packaged_paths_separate_bundle_and_mutable_user_data(tmp_path: Path):
    install = tmp_path / "Program Files" / "MotorCalculator"
    bundle = tmp_path / "bundle"
    local = tmp_path / "LocalAppData"
    paths = resolve_runtime_paths(
        environment={"LOCALAPPDATA": str(local)},
        packaged=True,
        executable_path=install / "MotorCalculator.exe",
        bundle_root=bundle,
        platform_name="win32",
        home_dir=tmp_path,
    )
    assert paths.application_root == install.resolve()
    assert paths.resource_root == bundle.resolve()
    assert paths.user_data_dir == (local / "MotorCalculator").resolve()
    assert install not in paths.feedback_store.parents


def test_first_run_creates_directories_but_feedback_file_is_lazy(tmp_path: Path):
    paths = create_runtime_directories(_temporary_paths(tmp_path))
    assert paths.log_dir.is_dir()
    assert paths.export_dir.is_dir()
    assert paths.cache_dir.is_dir()
    assert not paths.feedback_store.exists()


def test_default_feedback_loading_uses_user_data_override(tmp_path: Path, monkeypatch):
    target = tmp_path / "portable-user-data"
    monkeypatch.setenv("MOTOR_CALCULATOR_USER_DATA", str(target))
    assert load_feedback_records() == ()
    assert not (ROOT / "validation_data" / "user_feedback" / "feedback_records.jsonl").exists()


def test_resource_integrity_marks_missing_required_resource(tmp_path: Path):
    paths = resolve_runtime_paths(
        environment={"MOTOR_CALCULATOR_USER_DATA": str(tmp_path / "data")},
        packaged=True,
        executable_path=tmp_path / "app" / "MotorCalculator.exe",
        bundle_root=tmp_path / "empty-bundle",
        platform_name="win32",
        home_dir=tmp_path,
    )
    required = [item for item in check_packaged_resources(paths) if item.required]
    assert required
    assert all(not item.available for item in required)


def test_runtime_health_success_is_structured(tmp_path: Path):
    paths = _temporary_paths(tmp_path)
    report = check_runtime_health(paths, tk_probe=lambda: ("8.6.12", "8.6.12", "fake/tkinter.py"))
    assert report.overall_status is HealthStatus.OK
    assert report.critical_failures == ()
    assert report.to_dict()["schema_version"] == RUNTIME_SCHEMA_VERSION


def test_runtime_health_reports_tk_failure_without_hiding_reason(tmp_path: Path):
    def broken_tk():
        raise RuntimeError("init.tcl cannot be sourced")

    paths = _temporary_paths(tmp_path)
    report = check_runtime_health(paths, tk_probe=broken_tk)
    assert report.overall_status is HealthStatus.FAILED
    failure = next(check for check in report.checks if check.name == "tcl_tk_runtime")
    assert "init.tcl" in failure.message
    message = format_startup_failure(RuntimeError("init.tcl unavailable"), paths, report=report)
    assert "无法初始化 Tkinter 运行环境" in message
    assert str(paths.log_file) in message


def test_local_logging_is_rotating_and_stays_in_user_data(tmp_path: Path):
    paths = _temporary_paths(tmp_path)
    logger = initialize_local_logging(paths)
    logger.error("startup probe failure")
    for handler in logger.handlers:
        handler.flush()
    assert paths.log_file.is_file()
    assert "startup probe failure" in paths.log_file.read_text(encoding="utf-8")
    assert all(not hasattr(handler, "host") for handler in logger.handlers)
    for handler in tuple(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logging.getLogger(LOGGER_NAME).handlers.clear()


def test_version_metadata_and_repository_commit_are_truthful():
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-rc\d+)?", APPLICATION_VERSION)
    commit = get_git_commit(ROOT)
    assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)


def test_window_size_is_bounded_for_scaled_desktops():
    assert bounded_window_size(1800, 1000, 1600, 900) == (1520, 855)
    assert bounded_window_size(1200, 700, 1920, 1080) == (1200, 700)


def test_windows_work_area_is_valid_for_current_platform():
    left, top, right, bottom = windows_work_area(1920, 1080)
    assert right > left
    assert bottom > top


@pytest.mark.parametrize(
    ("tk_scaling", "expected"),
    (
        (96.0 / 72.0, (1800, 1000)),
        (120.0 / 72.0, (2250, 1250)),
        (144.0 / 72.0, (2700, 1500)),
        (192.0 / 72.0, (3600, 2000)),
    ),
)
def test_window_request_scales_for_common_windows_dpi(tk_scaling: float, expected: tuple[int, int]):
    assert dpi_scaled_window_size(1800, 1000, tk_scaling) == expected


def test_gui_smoke_argument_is_explicit_and_validated(tmp_path: Path):
    destination = tmp_path / "smoke.json"
    assert _smoke_output_argument(["--smoke-output", str(destination)]) == destination
    assert _smoke_output_argument([]) is None
    with pytest.raises(SystemExit):
        _smoke_output_argument(["--smoke-output"])


def test_runtime_modules_have_no_network_imports():
    forbidden = {"requests", "urllib", "http", "socket", "ftplib"}
    runtime_dir = ROOT / "motor_calculator" / "runtime"
    imported: set[str] = set()
    for path in runtime_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)


def test_one_folder_spec_excludes_development_and_user_data():
    content = (ROOT / "packaging" / "MotorCalculator.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in content
    assert "Path(SPECPATH).resolve().parent" in content
    assert "Path(SPECPATH).resolve().parent.parent" not in content
    assert "feedback_records.jsonl" not in content
    assert "tmp" not in content
    assert "motor_calculator.tests" in content
    assert '"tkinter.scrolledtext"' in content


@pytest.mark.parametrize(
    ("path", "expected_hash"),
    (
        (CALCULATIONS, "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"),
        (LEGACY_BASELINE, "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"),
    ),
)
def test_phase8a_protected_files_remain_byte_identical(path: Path, expected_hash: str):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
