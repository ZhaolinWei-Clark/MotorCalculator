"""Create portable output, checksums, and the Phase 8F release manifest."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import PyInstaller

from motor_calculator.deployment.release import (
    artifact_record,
    build_release_manifest,
    create_portable_zip,
    validate_release_manifest_artifacts,
    verify_protected_files,
    write_release_manifest,
    write_sha256s,
)
from motor_calculator.version import APPLICATION_VERSION


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--tkinter-version", required=True)
    parser.add_argument("--installer-status", required=True)
    parser.add_argument("--clean-machine-status", required=True)
    parser.add_argument("--isolated-local-status", required=True)
    parser.add_argument("--installer-technology", default="unknown")
    parser.add_argument("--installer-version", default="unknown")
    parser.add_argument("--defender-status", default="NOT_PERFORMED")
    parser.add_argument("--smartscreen-observation", default="NOT_OBSERVED")
    parser.add_argument("--local-install-status", default="NOT_RUN")
    parser.add_argument("--start-menu-status", default="NOT_RUN")
    parser.add_argument("--desktop-shortcut-status", default="NOT_RUN")
    parser.add_argument("--installed-application-status", default="NOT_RUN")
    parser.add_argument("--project-save-load-status", default="NOT_RUN")
    parser.add_argument("--recovery-status", default="NOT_RUN")
    parser.add_argument("--uninstall-status", default="NOT_RUN")
    parser.add_argument("--user-data-preservation-status", default="NOT_RUN")
    parser.add_argument("--reinstall-status", default="NOT_RUN")
    parser.add_argument("--upgrade-status", default="NOT_RUN")
    parser.add_argument("--portable-status", default="NOT_RUN")
    parser.add_argument("--source-gui-status", default="NOT_RUN")
    parser.add_argument("--packaged-gui-status", default="NOT_RUN")
    parser.add_argument("--strict-no-source-venv-status", default="NOT_RUN")
    parser.add_argument("--full-test-count", type=int, required=True)
    parser.add_argument("--deployment-test-count", type=int, required=True)
    parser.add_argument("--signed", action="store_true")
    arguments = parser.parse_args()

    root = arguments.repository_root.resolve()
    release_dir = root / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [
        create_portable_zip(
            root / "dist" / "MotorCalculator",
            release_dir / f"MotorCalculator-{APPLICATION_VERSION}-win64-portable.zip",
        )
    ]
    installer = release_dir / f"MotorCalculator-{APPLICATION_VERSION}-win64-setup.exe"
    if installer.is_file():
        artifacts.append(artifact_record("installer", installer))
    executable = root / "dist" / "MotorCalculator" / "MotorCalculator.exe"
    artifacts.append(artifact_record("packaged_executable", executable))
    protected = verify_protected_files(root)
    manifest = build_release_manifest(
        git_commit=arguments.git_commit,
        python_version=platform.python_version(),
        pyinstaller_version=PyInstaller.__version__,
        tkinter_version=arguments.tkinter_version,
        artifacts=artifacts,
        protected_hashes=protected,
        test_counts={
            "full_regression": arguments.full_test_count,
            "deployment_specific": arguments.deployment_test_count,
        },
        installer_status=arguments.installer_status,
        clean_machine_status=arguments.clean_machine_status,
        isolated_local_status=arguments.isolated_local_status,
        installer_technology=arguments.installer_technology,
        installer_version=arguments.installer_version,
        defender_status=arguments.defender_status,
        smartscreen_observation=arguments.smartscreen_observation,
        local_install_status=arguments.local_install_status,
        start_menu_status=arguments.start_menu_status,
        desktop_shortcut_status=arguments.desktop_shortcut_status,
        installed_application_status=arguments.installed_application_status,
        project_save_load_status=arguments.project_save_load_status,
        recovery_status=arguments.recovery_status,
        uninstall_status=arguments.uninstall_status,
        user_data_preservation_status=arguments.user_data_preservation_status,
        reinstall_status=arguments.reinstall_status,
        upgrade_status=arguments.upgrade_status,
        portable_status=arguments.portable_status,
        source_gui_status=arguments.source_gui_status,
        packaged_gui_status=arguments.packaged_gui_status,
        strict_no_source_venv_status=arguments.strict_no_source_venv_status,
        signed=arguments.signed,
    )
    write_release_manifest(release_dir / "release_manifest.json", manifest)
    write_sha256s(release_dir / "SHA256SUMS.txt", artifacts)
    validate_release_manifest_artifacts(manifest, release_dir)


if __name__ == "__main__":
    main()
