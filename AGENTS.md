# Repository Context Guide

## Scope

This repository currently contains one active subproject:

- `motor_calculator/`: AFPM PMSM/BLDC motor calculator refactor workspace

The root documents in `docs/` are the canonical high-level project memory for future turns. When conversation context is compressed, recover state from:

1. `docs/project_status_zh.md`
2. `docs/approved_model_assumptions_zh.md`
3. `docs/pending_decisions_zh.md`
4. `docs/external_validation_framework_zh.md`
5. `docs/external_data_source_candidates_zh.md`
6. `docs/external_data_field_mapping_matrix_zh.md`
7. `docs/validation_data_import_plan_zh.md`
8. `docs/textbook_reference_candidates_zh.md`
9. `validation_data/README_data_scouting_zh.md`
10. `motor_calculator/docs/model_assumptions_zh.md`
11. `motor_calculator/docs/formula_inventory_zh.md`
12. `docs/electrical_quantity_definitions_zh.md`
13. `docs/phase3_formula_change_report_zh.md`
14. `docs/bldc_ke_kt_validation_zh.md`

## Current Project Goal

The project is still a controlled refactor, semantics-clarification, and validation-framework effort, not a broad electromagnetic physics upgrade.

Current priorities:

- preserve legacy calculator behavior
- keep the legacy regression baseline stable
- centralize units, constants, assumptions, and validation
- keep all result-changing formula work explicit, reviewable, and parallelized
- keep external validation traceable and isolated from the production default path
- scout reliable external validation sources before importing any real dataset

## Current Approved State

- Target machine type: three-phase axial-flux permanent-magnet motor, AFPM PMSM/BLDC
- Not a brushed PMDC model
- Default topology: dual-rotor, single-stator, dual-air-gap
- Default winding connection: Y connection
- `pole_pairs` means pole pairs
- `pole_count = 2 * pole_pairs` means total poles
- Internal calculations should use SI units
- PMSM and BLDC electrical semantics have been separated in Phase 3A
- Phase 3B is complete and keeps strict-SI rated torque in parallel with legacy rated torque
- Phase 3C is complete and keeps revised PMSM `Ke` / `Kt` in parallel with legacy outputs
- Phase 3D is complete and adds 4 independent PMSM analytical reference cases
- Phase 3E is complete and has passed acceptance
- Phase 4A is complete and adds an external-validation schema, provenance tracking, comparability checks, unit-conversion logging, and validation templates
- Revised PMSM `Ke` / `Kt` have passed unit-semantics, three-phase power-balance, independent analytical reference, and downstream-isolation validation
- Revised BLDC `Ke` / `Kt` have passed piecewise derivation, independent numeric integration, independent analytical reference, production/reference cross-validation, and downstream isolation
- Existing 3 legacy baseline cases are all BLDC-path cases
- Revised PMSM and BLDC outputs are still not production defaults
- No real published benchmark, FEA, or bench-measurement dataset has been imported yet
- Phase 4B scouting has started on branch `research/external-data-source-scouting`
- Phase 4B has produced candidate-source, field-mapping, import-planning, and textbook-reference docs only
- Phase 4B still has not imported any real external dataset into `validation_data/imported/`
- GUI smoke test is complete, but the runtime environment still lacks `matplotlib` and a usable Tk `init.tcl`
- `legacy_baseline.json` remains unchanged with SHA-256 `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- Standard development test command is `.venv\Scripts\python.exe -m pytest -v`

## Phase 3D Freeze Reference

- Phase 3D state-freeze commit before final Phase 3E closeout: `958dc23` `docs: record phase 3D completion and phase 3E scope`
- full pytest result before Phase 3E: `84 passed`

## Phase 3E Completion Snapshot

Phase 3E was completed on branch `feature/bldc-ke-kt-semantics`.

Recorded commits:

- `52373c6` `feat: define ideal BLDC waveform semantics`
- `3168ad2` `feat: derive BLDC Ke Kt from 120 degree power balance`
- `2d28905` `test: add independent BLDC analytical reference cases`
- `9716cb0` `test: validate BLDC Ke Kt semantics and isolation`
- `3bba27d` `docs: document BLDC Ke Kt analytical validation`

Validated state:

- full pytest result after Phase 3E: `117 passed`
- `legacy_baseline.json` unchanged
- `legacy_baseline.json` SHA-256 remains `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- revised BLDC waveform helpers are GUI-independent and live in `motor_core/bldc_ke_kt_models.py`
- ideal BLDC reference model is fixed to three-phase, Y-connected, trapezoidal back EMF, 120-degree six-step conduction
- revised BLDC fields remain parallel-only and do not replace legacy defaults
- rated current, loss, efficiency, `required_voltage_v`, torque waveform, and GUI default paths still use legacy chains
- existing 3 legacy baseline cases remain BLDC-path regression anchors
- new independent BLDC analytical cases exist in `motor_calculator/tests/fixtures/bldc_reference_cases.json`
- revised BLDC line RMS `Ke` differs from legacy by about `2.4695%`
- legacy BLDC `Kt` semantics remain incomplete and should not be forced into a direct error calculation against revised BLDC `Kt`

## Phase 4A Completion Snapshot

Phase 4A is complete on branch `feature/external-validation-framework`.

Recorded commits:

- `87240a5` `feat: add external validation record schema`
- `531e342` `feat: add validation loader and comparability engine`
- `84f88d1` `test: cover validation provenance and error metrics`

Validated state:

- full pytest result after Phase 4A code and tests: `138 passed`
- new framework files live in:
  - `motor_core/validation_records.py`
  - `motor_core/validation_loader.py`
  - `motor_core/validation_comparison.py`
- validation templates live in `validation_data/templates/`
- `validation_data/imported/` intentionally contains no fabricated benchmark data
- `validation_data/templates/example_synthetic_record.json` is explicitly synthetic, analytical-only, and not for accuracy claims
- external validation data cannot enter the production calculation default path
- the framework does not auto-calibrate formulas or empirical coefficients
- `legacy_baseline.json`, `pmsm_reference_cases.json`, and `bldc_reference_cases.json` remain unchanged

## Current Validation Framework Rules

- Every validation record must track `source_type` and `evidence_level`
- Every validation record must remain traceable to a file, paper, experiment, or user input
- `analytical_reference` cannot be treated as experimental validation
- `manufacturer_data` cannot be treated as controlled bench measurement
- Unknown values must use explicit field status:
  - `provided`
  - `inferred`
  - `unavailable`
  - `not_applicable`
- Unknown data must never be represented by `0`
- Only `directly_comparable` metrics may compute model error
- Unit conversion may be explicit, but it must be recorded
- External validation results must stay separate from uncertainty metadata

## Not Allowed In Current Scope

- switch any revised value to a default path
- modify calculation formulas
- modify `required_voltage_v`
- modify rated-current default chains
- modify loss, efficiency, inductance, fill-factor, demagnetization, or thermal-rise formulas
- modify GUI default chains
- modify `legacy_baseline.json`
- fabricate external validation data or citations
- claim real-world accuracy without explicit evidence and approval

## Hard Rules

- Do not delete or overwrite `motor_calculator/PMDC_Calculator_claude204.py`.
- Do not delete the legacy calculation implementation.
- Do not silently change legacy baseline data to make tests pass.
- Do not claim improved physical accuracy without explicit evidence and approval.
- Do not fabricate published benchmark, FEA, bench, or manufacturer validation sources.
- GUI must not contain electromagnetic formulas.
- `motor_core/calculations.py` must remain GUI-independent.
- Unit conversions must stay centralized in `motor_core/units.py` unless the conversion is validation-record-specific and explicitly logged by the validation framework.
- Constants and legacy factors must stay centralized in `motor_core/constants.py`.

## Formula Change Approval Rule

Before changing any formula that could alter calculated outputs, obtain explicit approval from the user and document:

- formula name
- current implementation
- proposed implementation
- expected numerical impact
- affected outputs
- reason for change

Examples requiring prior approval:

- `Kt` / `Ke` semantic adjustments
- replacing legacy outputs with strict SI defaults
- changes to voltage requirement model
- changes to fill-factor definition
- changes to empirical loss models
- changes to dual-rotor / dual-air-gap coefficients

## Legacy Baseline Policy

`motor_calculator/tests/fixtures/legacy_baseline.json` stores legacy behavior only.

- It is a regression anchor for refactoring.
- It is not proof of physical correctness.
- Any mismatch against this file must be explained before updating the fixture.
- Formula comparison work must keep legacy outputs intact unless the user explicitly approves a default switch.

## Testing

Formal test entry point:

- `.venv\Scripts\python.exe -m pytest -v`

Temporary compatibility runner:

- `work/run_pytest_style.py`

Current expected result after Phase 4A:

- `138 passed`

Current expected result after Phase 4B docs-only work:

- `138 passed`

## Key Git State

Current development branch:

- `research/external-data-source-scouting`

Historical anchor commits:

- `d2f9f67` `baseline: preserve original single-file motor calculator`
- `aaeb2d7` `refactor: split motor core and add validation baseline`
- `c2d0039` `docs: freeze project context and approved assumptions`
- `941551d` `docs: record phase 3C completion and phase 3D scope`
- `958dc23` `docs: record phase 3D completion and phase 3E scope`

## Main File Layout

```text
motor_calculator/
  app.py
  PMDC_Calculator_claude204.py
  motor_core/
  gui/
  tests/
docs/
  project_status_zh.md
  approved_model_assumptions_zh.md
  pending_decisions_zh.md
  external_validation_framework_zh.md
  external_data_source_candidates_zh.md
  external_data_field_mapping_matrix_zh.md
  validation_data_import_plan_zh.md
  textbook_reference_candidates_zh.md
  electrical_quantity_definitions_zh.md
  phase3_formula_change_report_zh.md
  bldc_ke_kt_validation_zh.md
validation_data/
  README_zh.md
  README_data_scouting_zh.md
  templates/
  imported/
  reports/
work/
  run_pytest_style.py
```

## Current Open Engineering Issues

- revised PMSM `Ke` / `Kt` are still not production defaults
- revised BLDC `Ke` / `Kt` are still not production defaults
- `9.55 * P / n` remains the active downstream legacy implementation
- `required_voltage_v` is still a simplified legacy model
- several loss models remain empirical
- inductance and fill-factor models remain legacy approximations
- the external validation framework exists, but real external datasets are still absent
- Phase 4B source scouting is complete, but no real record has been imported yet
- the best current Phase 4C candidate is `CREATOR PMSM Data`
- several AFPM-aligned literature candidates still need user-supplied PDFs or exact citations before extraction
- GUI runtime dependencies remain unresolved despite the smoke test
- current validation is still not FEA, bench-test, published-benchmark, or full prototype validation

## Next Phase Intent

No result-changing formula phase is currently approved beyond Phase 4A.

If work continues, the likely next safe step is one of:

- import a first real external validation record through the Phase 4A framework, preferably `CREATOR PMSM Data`
- import a first FEA-only reference record if explicitly approved
- repair GUI runtime dependencies in a separate non-formula phase
- extract worked examples from user-supplied AFPM papers or textbooks

Any future phase must still not:

- switch any default path without approval
- modify any calculation formula without approval
