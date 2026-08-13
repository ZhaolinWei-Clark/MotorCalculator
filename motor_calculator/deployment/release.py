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


PROTECTED_FILE_HASHES = {
    "motor_calculator/motor_core/calculations.py": (
        "416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d"
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
        "clean_machine_status": clean_machine_status,
        "isolated_local_status": isolated_local_status,
    }


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
