"""Phase 8B versioned project persistence tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from motor_calculator.motor_core import LegacyGuiMotorModelBridge
from motor_calculator.project import (
    PROJECT_FILE_EXTENSION,
    PROJECT_SCHEMA_VERSION,
    ProjectInputValue,
    ProjectIntegrityError,
    ProjectManager,
    ProjectSerializationError,
    ProjectValidationError,
    RecentProjectStore,
    UnsupportedProjectVersionError,
    UnsavedChangesDecision,
    create_project_document,
    flatten_project_inputs,
    load_project,
    migrate_project,
    missing_feedback_record_ids,
    project_to_payload,
    save_project,
    serialize_project,
    validate_project,
    validate_project_document,
)
from motor_calculator.project import serializer as project_serializer


ROOT = Path(__file__).resolve().parents[2]
LEGACY_BASELINE = ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
CALCULATIONS = ROOT / "motor_calculator" / "motor_core" / "calculations.py"
EXPECTED_CALCULATIONS_HASH = "032fe19062ba844f7ad12cf541d0ed6841050019fea9bb400f48ebd7b3b40970"
EXPECTED_LEGACY_HASH = "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"


@pytest.fixture
def default_inputs() -> dict:
    payload = json.loads(LEGACY_BASELINE.read_text(encoding="utf-8"))
    return dict(payload["cases"][0]["legacy_inputs"])


@pytest.fixture
def project(default_inputs):
    return create_project_document(
        "Default Motor",
        default_inputs,
        project_uuid="11111111-1111-4111-8111-111111111111",
        created_at="2026-08-11T00:00:00Z",
        modified_at="2026-08-11T00:00:00Z",
        notes="Plain-text engineering note.",
        validation_record_ids=("feedback-present", "feedback-missing"),
    )


def test_new_project_creation_is_versioned_and_complete(project):
    assert PROJECT_FILE_EXTENSION == ".motorproj"
    assert project.schema_version == PROJECT_SCHEMA_VERSION == 1
    assert project.metadata.project_name == "Default Motor"
    assert len(flatten_project_inputs(project.inputs)) == 41


def test_serialization_is_deterministic(project):
    assert serialize_project(project) == serialize_project(project)


def test_save_load_round_trip_preserves_document(project, tmp_path):
    path = tmp_path / "round-trip.motorproj"
    save_project(project, path)
    assert load_project(path) == project


def test_exact_input_restoration(project, default_inputs):
    assert flatten_project_inputs(project.inputs) == default_inputs


def test_calculation_is_reproducible_after_round_trip(project, default_inputs, tmp_path):
    path = tmp_path / "reproducible.motorproj"
    save_project(project, path)
    restored = flatten_project_inputs(load_project(path).inputs)
    before = LegacyGuiMotorModelBridge(dict(default_inputs)).run_full_analysis().to_dict()
    after = LegacyGuiMotorModelBridge(restored).run_full_analysis().to_dict()
    before["元数据"].pop("计算时间", None)
    after["元数据"].pop("计算时间", None)
    assert after == before


def test_atomic_save_failure_preserves_existing_valid_project(project, default_inputs, tmp_path, monkeypatch):
    target = tmp_path / "atomic.motorproj"
    save_project(project, target)
    changed_inputs = dict(default_inputs, V_dc=52.0)
    changed = create_project_document(
        "Changed",
        changed_inputs,
        project_uuid=project.metadata.project_uuid,
        created_at=project.metadata.created_at,
        modified_at="2026-08-11T01:00:00Z",
    )
    real_replace = project_serializer.os.replace

    def fail_target_replace(source, destination):
        if Path(destination) == target:
            raise OSError("forced atomic replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(project_serializer.os, "replace", fail_target_replace)
    with pytest.raises(ProjectSerializationError, match="atomically"):
        save_project(changed, target)
    assert load_project(target) == project


def test_existing_project_creates_one_previous_backup(project, default_inputs, tmp_path):
    target = tmp_path / "backup.motorproj"
    save_project(project, target)
    changed = create_project_document(
        "Changed",
        dict(default_inputs, n_rated=2600.0),
        project_uuid=project.metadata.project_uuid,
        created_at=project.metadata.created_at,
        modified_at="2026-08-11T01:00:00Z",
    )
    save_project(changed, target)
    backup = target.with_name(target.name + ".bak")
    assert load_project(target) == changed
    assert load_project(backup) == project
    assert list(tmp_path.glob("*.bak")) == [backup]


def test_invalid_json_returns_user_readable_error(tmp_path):
    path = tmp_path / "corrupt.motorproj"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ProjectSerializationError, match="valid UTF-8 JSON"):
        load_project(path)


def test_unsupported_newer_schema_is_rejected_before_open(project):
    payload = project_to_payload(project)
    payload["schema_version"] = PROJECT_SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedProjectVersionError, match="newer"):
        validate_project(payload)


def test_migration_interface_supports_explicit_one_version_step(project):
    migrated = migrate_project(
        {"schema_version": 0},
        migrations={0: lambda _payload: project_to_payload(project)},
    )
    assert migrated["schema_version"] == PROJECT_SCHEMA_VERSION


def test_integrity_hash_detects_accidental_corruption(project):
    payload = project_to_payload(project)
    payload["metadata"]["project_name"] = "Tampered"
    with pytest.raises(ProjectIntegrityError, match="hash mismatch"):
        validate_project(payload)


def test_invalid_physical_field_type_is_rejected(project):
    inputs = {category: dict(fields) for category, fields in project.inputs.items()}
    original = inputs["operating_point"]["n_rated"]
    inputs["operating_point"]["n_rated"] = ProjectInputValue(
        value="not-a-speed",
        unit=original.unit,
        semantics=original.semantics,
    )
    with pytest.raises(ProjectValidationError, match="n_rated.*float"):
        validate_project_document(replace(project, inputs=inputs))


def test_missing_required_input_is_not_replaced_by_a_default(project):
    inputs = {category: dict(fields) for category, fields in project.inputs.items()}
    del inputs["electrical"]["V_dc"]
    with pytest.raises(ProjectValidationError, match="missing.*V_dc"):
        validate_project_document(replace(project, inputs=inputs))


def test_dirty_state_tracking_and_save_as(project, tmp_path):
    manager = ProjectManager(RecentProjectStore(tmp_path / "recent.json"))
    manager.new_project(project)
    assert manager.is_dirty is False
    manager.mark_dirty()
    assert manager.is_dirty is True
    target = manager.save_as(project, tmp_path / "managed.motorproj")
    assert target.is_file()
    assert manager.is_dirty is False
    assert manager.current_path == target


@pytest.mark.parametrize(
    ("decision", "save_result", "expected"),
    (
        (UnsavedChangesDecision.CANCEL, True, False),
        (UnsavedChangesDecision.DISCARD, False, True),
        (UnsavedChangesDecision.SAVE, True, True),
        (UnsavedChangesDecision.SAVE, False, False),
    ),
)
def test_unsaved_changes_decision_logic(project, tmp_path, decision, save_result, expected):
    manager = ProjectManager(RecentProjectStore(tmp_path / "recent.json"))
    manager.new_project(project)
    manager.mark_dirty()
    assert manager.can_abandon(decision, save_callback=lambda: save_result) is expected


def test_recent_projects_are_local_bounded_and_missing_safe(project, tmp_path):
    store = RecentProjectStore(tmp_path / "user-data" / "recent.json", maximum_entries=2)
    existing = tmp_path / "existing.motorproj"
    save_project(project, existing)
    missing = tmp_path / "missing.motorproj"
    another = tmp_path / "another.motorproj"
    save_project(project, another)
    store.add(existing, "Existing", accessed_at="2026-08-11T00:00:00Z")
    store.add(missing, "Missing", accessed_at="2026-08-11T01:00:00Z")
    store.add(another, "Another", accessed_at="2026-08-11T02:00:00Z")
    assert [entry.project_name for entry in store.entries()] == ["Another", "Missing"]
    assert [entry.project_name for entry in store.entries(existing_only=True)] == ["Another"]
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert "inputs" not in json.dumps(raw)


def test_missing_linked_feedback_is_reported_without_blocking_load(project, tmp_path):
    path = tmp_path / "feedback-links.motorproj"
    save_project(project, path)
    loaded = load_project(path)
    assert missing_feedback_record_ids(loaded, ["feedback-present"]) == ("feedback-missing",)


def test_project_operations_do_not_mutate_inputs_or_protected_files(project, default_inputs, tmp_path):
    import hashlib

    before_inputs = dict(default_inputs)
    calculations_hash = hashlib.sha256(CALCULATIONS.read_bytes()).hexdigest()
    legacy_hash = hashlib.sha256(LEGACY_BASELINE.read_bytes()).hexdigest()
    path = tmp_path / "isolation.motorproj"
    save_project(project, path)
    load_project(path)
    assert default_inputs == before_inputs
    assert calculations_hash == EXPECTED_CALCULATIONS_HASH
    assert legacy_hash == EXPECTED_LEGACY_HASH


def test_result_snapshot_is_not_required_for_valid_project(project):
    assert project.result_snapshot is None
    assert replace(project, result_snapshot=None) == project
