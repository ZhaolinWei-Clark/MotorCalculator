# Phase 8B Versioned Project File Schema

## 1. Boundary

Phase 8B adds local project persistence only. It does not change electromagnetic formulas, advanced AFPM equations, dynamic/control equations, uncertainty mathematics, validation/calibration logic, default numerical outputs, or the legacy baseline.

Project files are user-selected documents. They are not forced into `%LOCALAPPDATA%`. Logs, preferences, recent-project metadata, feedback records, exports, and caches remain under the application user-data directory.

## 2. File identity

- Extension: `.motorproj`
- Encoding: UTF-8
- Container: JSON
- Current schema: `PROJECT_SCHEMA_VERSION = 1`
- Integrity: canonical-payload SHA-256

The hash detects accidental edits or corruption. It is not a digital signature and does not establish authorship or trust.

## 3. Top-level structure

```json
{
  "schema_version": 1,
  "metadata": {},
  "model": {},
  "inputs": {},
  "uncertainty_assumptions": [],
  "ui_preferences": {},
  "notes": "",
  "validation_references": {"feedback_record_ids": []},
  "derived_cache": null,
  "integrity": {
    "algorithm": "sha256",
    "canonical_payload_sha256": "...",
    "purpose": "accidental corruption detection; not a digital signature"
  }
}
```

### Metadata

`metadata` stores `application_version`, `created_at`, `modified_at`, `project_name`, and a UUID `project_uuid`. Timestamps use ISO-8601 UTC-compatible text.

### Model identity

`model` stores:

- `model_family = legacy_afpm_calculator`
- calculation mode derived from the explicitly saved waveform;
- topology `dual-rotor single-stator dual-air-gap AFPM`.

The mode must agree with the saved waveform. Loading never changes the production model selection.

## 4. Inputs and units

Every required GUI calculation input is stored as a typed value rather than a formatted Tk string:

```json
"n_rated": {
  "value": 2500.0,
  "unit": "rpm",
  "semantics": {"quantity": "mechanical_speed"}
}
```

The v1 schema covers all 41 inputs and groups them under `geometry`, `winding`, `material`, `electrical`, and `operating_point`.

The canonical project units are the validated legacy input API units, including `mm`, `rpm`, `V`, `W`, `degC`, `T`, counts, ratios, and explicit enums. This is intentional: `motor_core/units.py` remains the sole production conversion path from these inputs to internal SI units. The project layer does not duplicate or replace those conversions.

A missing required input, incorrect unit, non-finite number, wrong physical field type, or mode/waveform inconsistency rejects the file. Missing values are never replaced silently with production defaults.

## 5. Determinism and integrity

JSON keys are sorted and formatting is stable. The integrity hash is calculated from a compact canonical JSON representation excluding the `integrity` object itself.

Loading checks, in order:

1. readable UTF-8 JSON;
2. supported schema version or explicit migration path;
3. integrity metadata and content hash;
4. required metadata/model/input structure;
5. field types, finite values, units, and semantics needed for exact restoration.

Invalid projects return user-readable errors and do not replace the current GUI project.

## 6. Atomic save and backup

Saving uses this sequence in the destination directory:

1. serialize and write a uniquely named temporary file;
2. flush and `fsync` the temporary file;
3. if the target exists, copy it to a temporary backup and atomically replace `<project>.motorproj.bak`;
4. atomically replace the target with the new temporary file.

Only one previous backup is retained. If final replacement fails, the existing target remains loadable. Temporary files are removed on failure where Windows permits.

## 7. Versioning and migration

The migration API advances exactly one version per registered function, for example v1 to v2 and then v2 to v3. Phase 8B defines the architecture but no speculative migration.

- current v1 files open directly;
- older files require an explicitly registered migration chain;
- newer unknown versions are rejected;
- no field is guessed merely to make a migration continue.

## 8. Uncertainty assumptions

User-edited Phase 7I parameter assumptions are stored with their nominal value, unit, uncertainty kind, bounds/distribution fields, provenance, confidence, and notes. They are reconstructed exactly on load.

Loading does not run a sweep or Monte Carlo automatically. Production defaults remain unchanged.

## 9. Validation references

Projects store only Phase 7J `record_id` references. They do not duplicate the local feedback JSONL database.

If a referenced record is unavailable, project inputs still load. The GUI warns that the local evidence link is unavailable rather than treating project loading as failed.

## 10. Result cache policy

The schema supports an optional result snapshot with an input hash, model version, and result timestamp. Phase 8B does not write or display a result snapshot by default.

After opening a project, old result widgets are cleared and the user must explicitly run the calculation. A future cache may only be current when both input hash and model version match.

## 11. Project manager and GUI behavior

The GUI File menu provides New Project, Open Project, Save, Save As, Recent Projects, Project Notes, and Exit. Users who do not use project files still launch directly into a usable Untitled calculator.

Input and uncertainty changes mark the project dirty and append `*` to the title. Result display changes alone do not mark it dirty. New, Open, and Exit use Save/Discard/Cancel protection.

Recent-project metadata is local-only, limited to ten entries, and stores path, display name, and access time only. Missing files are ignored by the menu without copying project content into the recent list.

## 12. Verification

- Baseline before Phase 8B: `486 passed`
- Project persistence tests: `22 passed`
- Final full regression: `508 passed`
- Source real-GUI project lifecycle: `PASS`
- Packaged real-GUI project lifecycle: `PASS`
- Packaged run while source `.venv` was absent: `PASS`

The GUI smoke verified new project creation, dirty state, temporary-file save, reset/new, File/Open, exact input restoration, calculation reproduction, File/Save As, recent metadata, and Cancel protection. Smoke project files were written under `%TEMP%`, never into the repository.

## 13. Current limitations

- Schema v1 has no historical migration because no older `.motorproj` version exists.
- Result snapshots are schema-ready but intentionally not activated.
- Notes use a simple plain-text prompt rather than a multiline rich editor.
- File-dialog smoke uses the real GUI command path with an automated temporary-path selection; native shell-dialog appearance is not separately asserted.
- There is no cloud synchronization, project encryption, digital signing, multi-user merge, or autosave journal.

Suggested Phase 8C scope: project recovery/autosave and explicit import/export compatibility tooling, kept separate from motor physics.
