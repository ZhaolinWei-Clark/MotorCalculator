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
        signed=arguments.signed,
    )
    write_release_manifest(release_dir / "release_manifest.json", manifest)
    write_sha256s(release_dir / "SHA256SUMS.txt", artifacts)


if __name__ == "__main__":
    main()
