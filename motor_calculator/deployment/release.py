"""Deterministic local release artifacts and machine-readable metadata."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from motor_calculator.version import (
    APPLICATION_ID,
    APPLICATION_NAME,
    APPLICATION_PUBLISHER,
    APPLICATION_VERSION,
    RELEASE_CHANNEL,
    RELEASE_MANIFEST_SCHEMA_VERSION,
)


# Approved-change log for motor_core/calculations.py. The file stays frozen
# except for changes that carry an explicit written approval; each entry records
# the hash the file carried after that approved change.
#
#   416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d
#       frozen baseline through v1.0.0-rc1 and v1.0.0-rc2
#   1609b2ee96ec93fa56a0af68ca4fe3eaea368807d70aa0e2078e7e18c72c1a14
#       Phase 9B Batch B1, approved presentation-only harmonic order mapping
#       (k / pole_pairs instead of k * pole_pairs). Fourier amplitudes, Bg_avg
#       and Bg_rms are unchanged.
#   032fe19062ba844f7ad12cf541d0ed6841050019fea9bb400f48ebd7b3b40970
#       Phase 9B Batch B2, approved adaptive cogging sampling derived from
#       3*LCM(2p, Q), plus an analytic shape peak factor. The cogging waveform
#       grid and the reported cogging peak change; no other output moves.
#   aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942
#       Phase 9B Batch C1, approved corrected required-voltage PARALLEL output.
#       `required_voltage_v` and `voltage_margin_percent` are unchanged and
#       remain the production default; the corrected single-basis phasor value
#       is published alongside them and is gated for promotion.
#
# See docs/reviews/phase9_formula_change_approval_zh.md and
# docs/reviews/phase9b_controlled_formula_corrections_zh.md.
#
# legacy_baseline.json remains frozen at its original hash and is never updated.
PROTECTED_FILE_HASHES = {
    "motor_calculator/motor_core/calculations.py": (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    ),
    "motor_calculator/tests/fixtures/legacy_baseline.json": (
        "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
    ),
}


@dataclass(frozen=True)
class ReleaseArtifact:
    kind: str
    filename: str
    size_bytes: int
    sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_protected_files(repository_root: str | Path) -> dict[str, str]:
    root = Path(repository_root)
    observed: dict[str, str] = {}
    for relative_path, expected in PROTECTED_FILE_HASHES.items():
        actual = sha256_file(root / relative_path)
        if actual != expected:
            raise ValueError(f"Protected-file hash mismatch: {relative_path}: {actual}")
        observed[relative_path] = actual
    return observed


def _portable_entries(dist_dir: Path) -> Iterable[Path]:
    for path in sorted(dist_dir.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_file():
            yield path


def create_portable_zip(dist_dir: str | Path, destination: str | Path) -> ReleaseArtifact:
    source = Path(dist_dir).resolve()
    target = Path(destination).resolve()
    executable = source / "MotorCalculator.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"Portable source executable is missing: {executable}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in _portable_entries(source):
            relative = path.relative_to(source)
            archive_name = (Path("MotorCalculator") / relative).as_posix()
            info = zipfile.ZipInfo(archive_name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            with path.open("rb") as stream:
                archive.writestr(info, stream.read())
    return ReleaseArtifact("portable_zip", target.name, target.stat().st_size, sha256_file(target))


def artifact_record(kind: str, path: str | Path) -> ReleaseArtifact:
    artifact = Path(path)
    return ReleaseArtifact(kind, artifact.name, artifact.stat().st_size, sha256_file(artifact))


def build_release_manifest(
    *,
    git_commit: str,
    python_version: str,
    pyinstaller_version: str,
    tkinter_version: str,
    artifacts: Iterable[ReleaseArtifact],
    protected_hashes: Mapping[str, str],
    test_counts: Mapping[str, int],
    installer_status: str,
    clean_machine_status: str,
    isolated_local_status: str,
    installer_technology: str = "unknown",
    installer_version: str = "unknown",
    defender_status: str = "NOT_PERFORMED",
    smartscreen_observation: str = "NOT_OBSERVED",
    local_install_status: str = "NOT_RUN",
    start_menu_status: str = "NOT_RUN",
    desktop_shortcut_status: str = "NOT_RUN",
    installed_application_status: str = "NOT_RUN",
    project_save_load_status: str = "NOT_RUN",
    recovery_status: str = "NOT_RUN",
    uninstall_status: str = "NOT_RUN",
    user_data_preservation_status: str = "NOT_RUN",
    reinstall_status: str = "NOT_RUN",
    upgrade_status: str = "NOT_RUN",
    portable_status: str = "NOT_RUN",
    source_gui_status: str = "NOT_RUN",
    packaged_gui_status: str = "NOT_RUN",
    strict_no_source_venv_status: str = "NOT_RUN",
    signed: bool = False,
    build_timestamp: str | None = None,
) -> dict[str, object]:
    timestamp = build_timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "app_name": APPLICATION_NAME,
        "version": APPLICATION_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "application_id": APPLICATION_ID,
        "publisher": APPLICATION_PUBLISHER,
        "build_timestamp": timestamp,
        "git_commit": git_commit,
        "python_version": python_version,
        "pyinstaller_version": pyinstaller_version,
        "tkinter_version": tkinter_version,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "artifacts": [asdict(item) for item in artifacts],
        "protected_model_hashes": dict(protected_hashes),
        "test_counts": dict(test_counts),
        "signed": bool(signed),
        "installer_status": installer_status,
        "installer_technology": installer_technology,
        "installer_version": installer_version,
        "clean_machine_status": clean_machine_status,
        "isolated_local_status": isolated_local_status,
        "defender_status": defender_status,
        "smartscreen_observation": smartscreen_observation,
        "local_install_status": local_install_status,
        "start_menu_status": start_menu_status,
        "desktop_shortcut_status": desktop_shortcut_status,
        "installed_application_status": installed_application_status,
        "project_save_load_status": project_save_load_status,
        "recovery_status": recovery_status,
        "uninstall_status": uninstall_status,
        "user_data_preservation_status": user_data_preservation_status,
        "reinstall_status": reinstall_status,
        "upgrade_status": upgrade_status,
        "portable_status": portable_status,
        "source_gui_status": source_gui_status,
        "packaged_gui_status": packaged_gui_status,
        "strict_no_source_venv_status": strict_no_source_venv_status,
    }


def validate_release_manifest_artifacts(
    manifest: Mapping[str, object], release_dir: str | Path
) -> dict[str, str]:
    """Verify that the manifest describes the exact local release artifacts."""

    if manifest.get("version") != APPLICATION_VERSION:
        raise ValueError("Release manifest version does not match the application version")
    if manifest.get("application_id") != APPLICATION_ID:
        raise ValueError("Release manifest application identity is not stable")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Release manifest artifacts must be a list")
    installer_name = f"MotorCalculator-{APPLICATION_VERSION}-win64-setup.exe"
    installer_records = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("kind") == "installer"
    ]
    if len(installer_records) != 1 or installer_records[0].get("filename") != installer_name:
        raise ValueError("Release manifest must contain the versioned installer artifact")

    root = Path(release_dir)
    verified: dict[str, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("Release manifest contains an invalid artifact record")
        filename = item.get("filename")
        expected_size = item.get("size_bytes")
        expected_hash = item.get("sha256")
        if not isinstance(filename, str) or not isinstance(expected_size, int):
            raise ValueError("Release artifact filename or size is invalid")
        if not isinstance(expected_hash, str):
            raise ValueError("Release artifact hash is invalid")
        if item.get("kind") == "packaged_executable":
            path = root.parent / "dist" / "MotorCalculator" / filename
        else:
            path = root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Release artifact is missing: {filename}")
        if path.stat().st_size != expected_size:
            raise ValueError(f"Release artifact size mismatch: {filename}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise ValueError(f"Release artifact hash mismatch: {filename}")
        verified[filename] = actual_hash
    return verified


def write_release_manifest(path: str | Path, manifest: Mapping[str, object]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def write_sha256s(path: str | Path, artifacts: Iterable[ReleaseArtifact]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{artifact.sha256} *{artifact.filename}" for artifact in artifacts]
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return destination


def write_build_metadata(path: str | Path, *, git_commit: str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "application_version": APPLICATION_VERSION,
        "git_commit": git_commit,
        "build_platform": platform.platform(),
        "build_architecture": platform.machine(),
        "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH"),
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
