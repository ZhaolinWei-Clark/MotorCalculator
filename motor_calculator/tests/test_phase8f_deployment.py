from __future__ import annotations

import json
import re
import uuid
import zipfile
from pathlib import Path

from motor_calculator.deployment.release import (
    PROTECTED_FILE_HASHES,
    ReleaseArtifact,
    build_release_manifest,
    create_portable_zip,
    sha256_file,
    validate_release_manifest_artifacts,
    verify_protected_files,
    write_release_manifest,
    write_sha256s,
)
from motor_calculator.project import create_project_document
from motor_calculator.runtime.diagnostics import build_diagnostics
from motor_calculator.runtime.paths import resolve_runtime_paths
from motor_calculator.version import (
    APPLICATION_ID,
    APPLICATION_NAME,
    APPLICATION_VERSION,
    RELEASE_MANIFEST_SCHEMA_VERSION,
    windows_version_tuple,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_SOURCE = REPOSITORY_ROOT / "installer" / "MotorCalculator.iss"


def test_authoritative_version_and_stable_application_identity() -> None:
    assert APPLICATION_VERSION == "1.0.0-rc1"
    assert APPLICATION_NAME == "MotorCalculator"
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-rc\d+)?", APPLICATION_VERSION)
    assert windows_version_tuple() == (1, 0, 0, 1)
    assert str(uuid.UUID(APPLICATION_ID.strip("{}"))).upper() in APPLICATION_ID


def test_project_metadata_uses_authoritative_application_version() -> None:
    from motor_calculator.input_ux import APPLICATION_DEFAULTS

    document = create_project_document("Phase 8F", APPLICATION_DEFAULTS)
    assert document.metadata.application_version == APPLICATION_VERSION


def test_installer_metadata_is_injected_without_duplicate_version() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert "#ifndef AppVersion" in source
    assert "AppVersion={#AppVersion}" in source
    assert "VersionInfoVersion={#AppFileVersion}" in source
    assert APPLICATION_VERSION not in source
    assert "AppId={#AppId}" in source


def test_installer_source_has_no_absolute_repository_path() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert "D:\\Codex" not in source
    assert "C:\\Users" not in source
    assert "..\\dist\\MotorCalculator\\*" in source


def test_installer_packages_only_verified_dist_output() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8").lower()
    assert ".venv" not in source
    assert ".git" not in source
    assert "tmp/" not in source and "tmp\\" not in source
    assert "source: \"..\\dist\\motorcalculator\\*\"" in source


def test_per_user_shortcut_and_desktop_opt_in_policy() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert "DefaultDirName={localappdata}\\Programs\\MotorCalculator" in source
    assert "PrivilegesRequired=lowest" in source
    assert 'Name: "desktopicon"' in source and "Flags: unchecked" in source
    assert 'Name: "{group}\\{#AppDisplayName}"' in source
    assert 'MessagesFile: ".\\third_party\\ChineseSimplified.isl"' in source
    assert (REPOSITORY_ROOT / "installer" / "third_party" / "ChineseSimplified.isl").is_file()


def test_uninstall_policy_preserves_user_data_and_project_documents() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert "[UninstallDelete]" not in source
    assert "%LOCALAPPDATA%\\MotorCalculator is deliberately not removed" in source
    assert ".motorproj files are never owned by the installer" in source


def test_upgrade_identity_is_stable_and_previous_location_is_reused() -> None:
    source = INSTALLER_SOURCE.read_text(encoding="utf-8")
    assert APPLICATION_ID == "{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}"
    assert "UsePreviousAppDir=yes" in source
    assert "UsePreviousGroup=yes" in source


def test_protected_file_hash_gate_matches_frozen_files() -> None:
    assert verify_protected_files(REPOSITORY_ROOT) == PROTECTED_FILE_HASHES


def test_portable_zip_has_single_runnable_root_and_no_development_files(tmp_path: Path) -> None:
    dist = tmp_path / "dist" / "MotorCalculator"
    (dist / "_internal").mkdir(parents=True)
    (dist / "MotorCalculator.exe").write_bytes(b"exe")
    (dist / "_internal" / "runtime.dll").write_bytes(b"dll")
    artifact = create_portable_zip(dist, tmp_path / "portable.zip")
    with zipfile.ZipFile(tmp_path / "portable.zip") as archive:
        names = archive.namelist()
    assert artifact.kind == "portable_zip"
    assert names == ["MotorCalculator/_internal/runtime.dll", "MotorCalculator/MotorCalculator.exe"]
    assert not any(part in name for name in names for part in (".venv", ".git", "tmp/"))


def test_release_manifest_schema_and_status_are_deterministic(tmp_path: Path) -> None:
    artifact = ReleaseArtifact("portable_zip", "portable.zip", 7, "a" * 64)
    manifest = build_release_manifest(
        git_commit="b" * 40,
        python_version="3.12.10",
        pyinstaller_version="6.16.0",
        tkinter_version="8.6.15",
        artifacts=[artifact],
        protected_hashes=PROTECTED_FILE_HASHES,
        test_counts={"full_regression": 576, "deployment_specific": 13},
        installer_status="BLOCKED_BY_INSTALLER_COMPILER",
        clean_machine_status="BLOCKED_BY_ENVIRONMENT",
        isolated_local_status="ISOLATED_LOCAL_PASS",
        installer_technology="Inno Setup",
        installer_version="6.7.3",
        defender_status="PASS_NO_THREATS",
        local_install_status="PASS",
        uninstall_status="PASS",
        reinstall_status="PASS",
        build_timestamp="2026-08-13T00:00:00Z",
    )
    path = write_release_manifest(tmp_path / "manifest.json", manifest)
    assert json.loads(path.read_text(encoding="utf-8")) == manifest
    assert manifest["schema_version"] == RELEASE_MANIFEST_SCHEMA_VERSION
    assert manifest["signed"] is False
    assert manifest["installer_version"] == "6.7.3"
    assert manifest["defender_status"] == "PASS_NO_THREATS"
    assert manifest["local_install_status"] == "PASS"


def test_release_manifest_requires_versioned_installer_and_valid_checksums(tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    dist_dir = tmp_path / "dist" / "MotorCalculator"
    release_dir.mkdir()
    dist_dir.mkdir(parents=True)
    installer = release_dir / f"MotorCalculator-{APPLICATION_VERSION}-win64-setup.exe"
    portable = release_dir / f"MotorCalculator-{APPLICATION_VERSION}-win64-portable.zip"
    executable = dist_dir / "MotorCalculator.exe"
    installer.write_bytes(b"installer")
    portable.write_bytes(b"portable")
    executable.write_bytes(b"packaged executable")
    artifacts = [
        ReleaseArtifact("installer", installer.name, installer.stat().st_size, sha256_file(installer)),
        ReleaseArtifact("portable_zip", portable.name, portable.stat().st_size, sha256_file(portable)),
        ReleaseArtifact(
            "packaged_executable",
            executable.name,
            executable.stat().st_size,
            sha256_file(executable),
        ),
    ]
    manifest = build_release_manifest(
        git_commit="b" * 40,
        python_version="3.12.10",
        pyinstaller_version="6.16.0",
        tkinter_version="8.6.15",
        artifacts=artifacts,
        protected_hashes=PROTECTED_FILE_HASHES,
        test_counts={"full_regression": 589, "deployment_specific": 14},
        installer_status="PASS",
        clean_machine_status="BLOCKED_BY_ENVIRONMENT",
        isolated_local_status="ISOLATED_LOCAL_PASS",
    )
    assert validate_release_manifest_artifacts(manifest, release_dir) == {
        installer.name: sha256_file(installer),
        portable.name: sha256_file(portable),
        executable.name: sha256_file(executable),
    }


def test_artifact_sha256_and_checksum_file(tmp_path: Path) -> None:
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"phase8f")
    digest = sha256_file(payload)
    artifact = ReleaseArtifact("test", payload.name, payload.stat().st_size, digest)
    sums = write_sha256s(tmp_path / "SHA256SUMS.txt", [artifact])
    assert digest == "b7387bc82a39906ae720fab3c31734d5e66205806f2d592544b5969eceff8f79"
    assert sums.read_text(encoding="ascii") == f"{digest} *artifact.bin\n"


def test_diagnostics_are_local_versioned_and_exclude_project_payload(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(
        packaged=True,
        executable_path=tmp_path / "MotorCalculator.exe",
        bundle_root=tmp_path,
        environment={"LOCALAPPDATA": str(tmp_path / "local")},
        platform_name="win32",
        home_dir=tmp_path,
    )
    diagnostics = build_diagnostics(paths, recent_errors=("safe summary",))
    assert diagnostics["application_version"] == APPLICATION_VERSION
    assert diagnostics["runtime_mode"] == "packaged"
    assert diagnostics["recent_non_sensitive_errors"] == ["safe summary"]
    assert "inputs" not in diagnostics and "project_data" not in diagnostics
