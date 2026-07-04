# Repository Context Guide

## Scope

This repository currently contains one active subproject:

- `motor_calculator/`: AFPM PMSM/BLDC motor calculator refactor workspace

The root documents in `docs/` are the canonical high-level project memory for future turns. When conversation context is compressed, recover state from:

1. `docs/project_status_zh.md`
2. `docs/approved_model_assumptions_zh.md`
3. `docs/pending_decisions_zh.md`
4. `motor_calculator/docs/model_assumptions_zh.md`
5. `motor_calculator/docs/formula_inventory_zh.md`
6. `docs/electrical_quantity_definitions_zh.md`
7. `docs/phase3_formula_change_report_zh.md`
8. `docs/bldc_ke_kt_validation_zh.md`

## Current Project Goal

The project is still a controlled refactor and semantics-clarification effort, not a broad electromagnetic physics upgrade.

Current priorities:

- preserve legacy calculator behavior
- keep the legacy regression baseline stable
- centralize units, constants, assumptions, and validation
- make all result-changing formula work explicit, reviewable, and parallelized

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
- Revised PMSM `Ke` / `Kt` have passed unit-semantics, three-phase power-balance, independent analytical reference, and downstream-isolation validation
- Revised BLDC `Ke` / `Kt` have passed piecewise derivation, independent numeric integration, independent analytical reference, production/reference cross-validation, and downstream isolation
- Existing 3 legacy baseline cases are all BLDC-path cases
- Revised PMSM and BLDC outputs are still not production defaults
- `legacy_baseline.json` remains unchanged with SHA-256 `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- Standard development test command is `.venv\Scripts\python.exe -m pytest -v`

## Phase 3D Freeze Reference

- Phase 3D state-freeze commit before final Phase 3E closeout: `958dc23` `docs: record phase 3D completion and phase 3E scope`
- full pytest result before Phase 3E: `84 passed`

## Phase 3E Completion Snapshot

Phase 3E is complete on branch `feature/bldc-ke-kt-semantics`.

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

## Phase 4A Approved Scope

Phase 4A is approved as the next stage, but has not started yet.

Allowed in Phase 4A:

- establish an external validation data framework
- establish validation-source provenance tracking
- classify validation sources such as analytical, FEA, published benchmark, and measurement data
- add data-structure and documentation support for future external validation inputs

Not allowed in Phase 4A:

- switch any revised value to a default path
- modify calculation formulas
- modify `required_voltage_v`
- modify rated-current default chains
- modify loss, efficiency, inductance, fill-factor, demagnetization, or thermal-rise formulas
- modify GUI default chains
- modify `legacy_baseline.json`

## Hard Rules

- Do not delete or overwrite `motor_calculator/PMDC_Calculator_claude204.py`.
- Do not delete the legacy calculation implementation.
- Do not silently change legacy baseline data to make tests pass.
- Do not claim improved physical accuracy without explicit evidence and approval.
- GUI must not contain electromagnetic formulas.
- `motor_core/calculations.py` must remain GUI-independent.
- Unit conversions must stay centralized in `motor_core/units.py`.
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

Current expected result after Phase 3E freeze:

- `117 passed`

## Key Git State

Current development branch:

- `feature/bldc-ke-kt-semantics`

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
  electrical_quantity_definitions_zh.md
  phase3_formula_change_report_zh.md
  bldc_ke_kt_validation_zh.md
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
- current validation is still not FEA, bench-test, published-benchmark, or full prototype validation

## Next Phase Intent

The next approved phase is Phase 4A.

Phase 4A should only build:

- external validation data framework
- validation-source provenance tracking

Phase 4A must not:

- switch any default path
- modify any calculation formula
