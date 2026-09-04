"""Phase 8C autosave, crash-recovery, and compatibility tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from motor_calculator.project import (
    PROJECT_MIGRATIONS,
    CompatibilityStatus,
    IntegrityStatus,
    ProjectMetadata,
    RecoveryManager,
    RecoveryPriority,
    RecoveryStatus,
    create_project_document,
    flatten_project_inputs,
    inspect_project,
    inspect_project_sources,
    load_project,
    load_recovery,
    migrate_project,
    project_to_payload,
    recovery_to_payload,
    save_project,
    serialize_recovery,
)
from motor_calculator.project import recovery as recovery_module
from motor_calculator.project import serializer as serializer_module


ROOT = Path(__file__).resolve().parents[2]
LEGACY_BASELINE = ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
CALCULATIONS = ROOT / "motor_calculator" / "motor_core" / "calculations.py"
EXPECTED_CALCULATIONS_HASH = "1609b2ee96ec93fa56a0af68ca4fe3eaea368807d70aa0e2078e7e18c72c1a14"
EXPECTED_LEGACY_HASH = "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"


@pytest.fixture
def default_inputs() -> dict:
    payload = json.loads(LEGACY_BASELINE.read_text(encoding="utf-8"))
    return dict(payload["cases"][0]["legacy_inputs"])


@pytest.fixture
def project(default_inputs):
    return create_project_document(
        "Recovery Motor",
        default_inputs,
        project_uuid="88888888-8888-4888-8888-888888888888",
        created_at="2026-08-12T10:00:00Z",
        modified_at="2026-08-12T10:00:00Z",
        notes="saved note",
        validation_record_ids=("feedback-1",),
    )


def started_manager(tmp_path: Path, session_id: str = "99999999-9999-4999-8999-999999999999") -> RecoveryManager:
    manager = RecoveryManager(tmp_path / "recovery")
    manager.begin_session(session_id)
    return manager


def changed_project(project, default_inputs, **updates):
    values = dict(default_inputs)
    values.update(updates)
    return create_project_document(
        project.metadata.project_name,
        values,
        project_uuid=project.metadata.project_uuid,
        created_at=project.metadata.created_at,
        modified_at="2026-08-12T10:15:00Z",
        notes=project.notes,
        validation_record_ids=project.validation_record_ids,
    )


def test_autosave_only_writes_dirty_project(project, tmp_path):
    manager = started_manager(tmp_path)
    assert manager.write_recovery(project, original_project_path=None, dirty=False) is None
    assert not tuple(manager.root.glob("*.recovery.json"))


def test_dirty_autosave_round_trip_preserves_all_project_state(project, tmp_path):
    manager = started_manager(tmp_path)
    path = manager.write_recovery(project, original_project_path=None, dirty=True)
    restored = load_recovery(path)
    assert restored.project == project
    assert restored.project.notes == "saved note"
    assert restored.project.validation_record_ids == ("feedback-1",)
    assert restored.input_hash
    assert restored.state_hash


def test_recovery_serialization_is_deterministic(project, tmp_path):
    manager = started_manager(tmp_path)
    record = manager.create_record(
        project,
        original_project_path=None,
        dirty=True,
        recovery_timestamp="2026-08-12T10:20:00Z",
    )
    assert serialize_recovery(record) == serialize_recovery(record)


def test_recovery_integrity_rejects_tampering(project, tmp_path):
    manager = started_manager(tmp_path)
    path = manager.write_recovery(project, original_project_path=None, dirty=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["dirty"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exception, match="hash mismatch"):
        load_recovery(path)


def test_atomic_failure_preserves_latest_and_previous(project, default_inputs, tmp_path, monkeypatch):
    manager = started_manager(tmp_path)
    latest = manager.write_recovery(project, original_project_path=None, dirty=True)
    original = latest.read_bytes()
    changed = changed_project(project, default_inputs, Br=1.25)
    real_replace = recovery_module.os.replace

    def fail_latest(source, destination):
        if Path(destination) == latest:
            raise OSError("forced autosave replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(recovery_module.os, "replace", fail_latest)
    with pytest.raises(OSError, match="forced"):
        manager.write_recovery(changed, original_project_path=None, dirty=True)
    previous = manager._previous_path(latest)
    assert latest.read_bytes() == original
    assert previous.read_bytes() == original


def test_rotation_keeps_only_latest_and_one_previous(project, default_inputs, tmp_path):
    manager = started_manager(tmp_path)
    manager.write_recovery(project, original_project_path=None, dirty=True)
    second = changed_project(project, default_inputs, Br=1.24)
    manager.write_recovery(second, original_project_path=None, dirty=True)
    third = changed_project(project, default_inputs, Br=1.26)
    latest = manager.write_recovery(third, original_project_path=None, dirty=True)
    previous = manager._previous_path(latest)
    assert load_recovery(latest).project == third
    assert load_recovery(previous).project == second
    assert len(tuple(manager.root.glob("*.json"))) == 2


def test_unsaved_new_project_crash_is_detected_and_restored(project, default_inputs, tmp_path):
    manager = started_manager(tmp_path)
    changed = changed_project(project, default_inputs, n_rated=2468.0, Br=1.29)
    manager.write_recovery(changed, original_project_path=None, dirty=True)
    scan = RecoveryManager(manager.root).scan()
    assert len(scan.candidates) == 1
    assert scan.candidates[0].status is RecoveryStatus.RECOVERABLE
    recovered = RecoveryManager(manager.root).restore(scan.candidates[0])
    assert recovered.metadata.project_name == "Recovered Project"
    assert flatten_project_inputs(recovered.inputs)["n_rated"] == 2468.0


def test_saved_project_recovery_is_newer_and_official_stays_unchanged(project, default_inputs, tmp_path):
    official = tmp_path / "motor.motorproj"
    save_project(project, official)
    original_bytes = official.read_bytes()
    changed = changed_project(project, default_inputs, Br=1.31)
    manager = started_manager(tmp_path)
    manager.write_recovery(
        changed,
        original_project_path=official,
        dirty=True,
        last_normal_save_timestamp=project.metadata.modified_at,
        recovery_timestamp="2026-08-12T10:16:00Z",
    )
    candidate = manager.scan().candidates[0]
    assert candidate.newer_than_official is True
    assert RecoveryPriority.AUTOSAVE_NEWER in candidate.priorities
    assert flatten_project_inputs(manager.restore(candidate).inputs)["Br"] == 1.31
    assert official.read_bytes() == original_bytes
    assert load_project(official) == project


def test_identical_recovery_is_not_offered(project, tmp_path):
    official = tmp_path / "motor.motorproj"
    save_project(project, official)
    manager = started_manager(tmp_path)
    manager.write_recovery(project, original_project_path=official, dirty=True)
    assert manager.scan().candidates == ()
    candidate = manager.scan(include_non_actionable=True).candidates[0]
    assert candidate.status is RecoveryStatus.IDENTICAL_TO_OFFICIAL


def test_older_different_recovery_is_stale(project, default_inputs, tmp_path):
    official = tmp_path / "motor.motorproj"
    save_project(project, official)
    changed = changed_project(project, default_inputs, Br=1.18)
    manager = started_manager(tmp_path)
    manager.write_recovery(
        changed, original_project_path=official, dirty=True,
        recovery_timestamp="2026-08-12T09:59:00Z",
    )
    assert manager.scan().candidates == ()
    assert manager.scan(include_non_actionable=True).candidates[0].status is RecoveryStatus.STALE


def test_clean_session_recovery_is_not_promoted(project, tmp_path):
    manager = started_manager(tmp_path)
    manager.write_recovery(project, original_project_path=None, dirty=True)
    manager.mark_session_clean()
    assert manager.scan().candidates == ()
    candidate = manager.scan(include_non_actionable=True).candidates[0]
    assert candidate.status is RecoveryStatus.CLEAN_SESSION
    assert candidate.session_was_clean


def test_cleanup_removes_only_matching_project_recovery(project, default_inputs, tmp_path):
    manager = started_manager(tmp_path)
    first = manager.write_recovery(project, original_project_path=None, dirty=True)
    other = create_project_document("Other", dict(default_inputs, Br=1.22))
    other_path = manager.write_recovery(other, original_project_path=None, dirty=True)
    assert manager.cleanup_project(project.metadata.project_uuid, saved_input_hash=project_inputs_hash(project.inputs)) == 1
    assert not first.exists()
    assert other_path.exists()


def project_inputs_hash(inputs):
    from motor_calculator.project import project_inputs_hash as calculate

    return calculate(inputs)


def test_discard_deletes_selected_recovery_only(project, default_inputs, tmp_path):
    manager = started_manager(tmp_path)
    first = manager.write_recovery(project, original_project_path=None, dirty=True)
    other = create_project_document("Other", dict(default_inputs, Br=1.22))
    other_path = manager.write_recovery(other, original_project_path=None, dirty=True)
    manager.discard(first)
    assert not first.exists()
    assert other_path.exists()


def test_corrupt_recovery_is_quarantined_without_crashing(project, tmp_path):
    manager = started_manager(tmp_path)
    path = manager.write_recovery(project, original_project_path=None, dirty=True)
    path.write_text("{broken", encoding="utf-8")
    result = manager.scan()
    assert result.candidates == ()
    assert len(result.warnings) == 1
    assert not path.exists()
    assert len(tuple(manager.corrupt_dir.iterdir())) == 1


def test_corrupt_latest_falls_back_to_previous_valid_snapshot(project, default_inputs, tmp_path):
    manager = started_manager(tmp_path)
    manager.write_recovery(project, original_project_path=None, dirty=True)
    changed = changed_project(project, default_inputs, Br=1.3)
    latest = manager.write_recovery(changed, original_project_path=None, dirty=True)
    latest.write_text("{broken", encoding="utf-8")
    result = manager.scan()
    assert len(result.candidates) == 1
    assert result.candidates[0].path.name.endswith(".recovery.previous.json")
    assert result.candidates[0].record.project == project
    assert any("previous valid recovery" in warning for warning in result.warnings)


def test_autosave_write_failure_degrades_to_warning(project, tmp_path, monkeypatch):
    manager = started_manager(tmp_path)

    def fail(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(manager, "_write_text_atomic", fail)
    result = manager.try_write_recovery(project, original_project_path=None, dirty=True)
    assert not result.written
    assert "disk full" in result.warning


def test_compatibility_inspector_reports_compatible(project, tmp_path):
    path = tmp_path / "valid.motorproj"
    save_project(project, path)
    report = inspect_project(path)
    assert report.status is CompatibilityStatus.COMPATIBLE
    assert report.integrity_status is IntegrityStatus.VERIFIED
    assert report.required_fields_present
    assert report.model_compatible


def test_compatibility_inspector_rejects_newer_schema(project, tmp_path):
    path = tmp_path / "future.motorproj"
    payload = project_to_payload(project)
    payload["schema_version"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = inspect_project(path)
    assert report.status is CompatibilityStatus.NEWER_SCHEMA_UNSUPPORTED
    assert report.schema_version == 99


def test_compatibility_inspector_reports_corrupt_integrity(project, tmp_path):
    path = tmp_path / "corrupt.motorproj"
    save_project(project, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["notes"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = inspect_project(path)
    assert report.status is CompatibilityStatus.CORRUPT
    assert report.integrity_status is IntegrityStatus.FAILED


def test_invalid_project_is_reported_without_execution(tmp_path):
    path = tmp_path / "invalid.motorproj"
    path.write_text("[]", encoding="utf-8")
    assert inspect_project(path).status is CompatibilityStatus.INVALID


def test_backup_is_reported_when_official_is_corrupt(project, tmp_path):
    official = tmp_path / "motor.motorproj"
    backup = official.with_name(official.name + ".bak")
    save_project(project, backup)
    official.write_text("{broken", encoding="utf-8")
    sources = inspect_project_sources(official)
    assert sources.official.status is CompatibilityStatus.INVALID
    assert sources.backup.status is CompatibilityStatus.COMPATIBLE
    assert RecoveryPriority.CORRUPT_OFFICIAL_WITH_VALID_BACKUP in sources.priorities
    assert RecoveryPriority.BACKUP in sources.priorities


def test_backup_and_newer_autosave_are_both_reported(project, default_inputs, tmp_path):
    official = tmp_path / "motor.motorproj"
    save_project(project, official.with_name(official.name + ".bak"))
    official.write_text("{broken", encoding="utf-8")
    changed = changed_project(project, default_inputs, Br=1.3)
    manager = started_manager(tmp_path)
    manager.write_recovery(changed, original_project_path=official, dirty=True)
    candidate = manager.scan().candidates[0]
    assert RecoveryPriority.AUTOSAVE_NEWER in candidate.priorities
    assert RecoveryPriority.CORRUPT_OFFICIAL_WITH_VALID_BACKUP in candidate.priorities
    assert RecoveryPriority.BACKUP in candidate.priorities


def test_migration_registry_is_explicit_and_synthetic_adapter_works(monkeypatch):
    assert PROJECT_MIGRATIONS == {}
    payload = {"schema_version": 0, "legacy": True}

    def migrate_zero(item):
        return {**item, "schema_version": 1}

    assert migrate_project(payload, migrations={0: migrate_zero})["schema_version"] == 1
    monkeypatch.setitem(serializer_module.PROJECT_MIGRATIONS, 0, migrate_zero)
    assert serializer_module.migrate_project(payload)["schema_version"] == 1


def test_inspector_can_report_test_only_migration_path(tmp_path, monkeypatch):
    path = tmp_path / "old.motorproj"
    path.write_text(json.dumps({"schema_version": 0, "metadata": {}, "model": {}, "inputs": {}}), encoding="utf-8")
    monkeypatch.setitem(serializer_module.PROJECT_MIGRATIONS, 0, lambda item: {**item, "schema_version": 1})
    assert inspect_project(path).status is CompatibilityStatus.MIGRATION_AVAILABLE


def test_recovery_payload_is_json_only_and_contains_no_executable_hook(project, tmp_path):
    manager = started_manager(tmp_path)
    record = manager.create_record(project, original_project_path=None, dirty=True)
    payload = recovery_to_payload(record)
    assert "pickle" not in json.dumps(payload).lower()
    assert "__reduce__" not in json.dumps(payload)


def test_protected_files_remain_unchanged():
    assert hashlib.sha256(CALCULATIONS.read_bytes()).hexdigest() == EXPECTED_CALCULATIONS_HASH
    assert hashlib.sha256(LEGACY_BASELINE.read_bytes()).hexdigest() == EXPECTED_LEGACY_HASH
