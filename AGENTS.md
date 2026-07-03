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

## Current Project Goal

The current track is still a controlled refactor and semantics-clarification effort, not a broad electromagnetic physics upgrade.

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
- `revised_rated_torque_nm` is not the production default
- Revised rated torque must not propagate into downstream current, loss, efficiency, or voltage calculations without approval
- Standard development test command is `python -m pytest -v`

## Phase 3A Completion Snapshot

Phase 3A is complete on branch `feature/electrical-semantics`.

Recorded commits:

- `724c305` `test: enable standard pytest`
- `98ba044` `refactor: clarify speed and electrical quantity semantics`
- `47e086a` `refactor: separate PMSM and BLDC control mode semantics`
- `db9749d` `test: add electrical semantics coverage`
- `c0da91b` `docs: document electrical quantity definitions`

Validated state:

- full pytest result: `25 passed`
- `legacy_baseline.json` unchanged
- 3 legacy baseline cases and 18 legacy output fields show no numeric drift
- PMSM and BLDC electrical semantics are isolated
- strict BLDC RMS, peak, `Ke`, and `Kt` relationships are still not established

## Phase 3B Completion Snapshot

Phase 3B is complete on branch `feature/strict-si-rated-torque`.

Recorded commits:

- `d9e675f` `docs: record phase 3A completion and phase 3B scope`
- `1c74397` `feat: add strict SI rated torque comparison`
- `28cc132` `test: cover legacy and strict SI torque models`
- `0adbca7` `docs: document rated torque formula comparison`

Validated state:

- full pytest result: `35 passed`
- `legacy_baseline.json` unchanged
- revised rated torque remains comparison-only
- revised rated torque has not propagated into rated current, loss, efficiency, GUI default paths, or `required_voltage_v`

## Phase 3C Scope

Phase 3C is limited to PMSM sinusoidal `Ke` / `Kt` semantics only.

Allowed:

- define revised PMSM back-EMF constants with explicit units and mechanical-speed basis
- derive revised PMSM torque constants from power balance
- expose legacy and revised values side by side
- document which legacy/revised quantities are directly comparable
- add tests proving revised results do not propagate downstream

Not allowed in Phase 3C:

- modify BLDC `Ke` / `Kt` behavior beyond legacy or provisional labeling
- modify `required_voltage_v`
- use revised `Ke` / `Kt` to recalculate rated current, loss, efficiency, or GUI defaults
- delete or overwrite legacy `Ke` / `Kt` fields
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

- `python -m pytest -v`

Temporary compatibility runner:

- `work/run_pytest_style.py`

Current expected result after Phase 3B freeze:

- `35 passed`

## Key Git State

Current development baseline:

- working branch: `feature/strict-si-rated-torque`
- baseline commit: `d2f9f67` `baseline: preserve original single-file motor calculator`
- phase 2 refactor commit: `aaeb2d7` `refactor: split motor core and add validation baseline`
- context documentation commit: `c2d0039` `docs: freeze project context and approved assumptions`

## Main File Layout

```text
motor_calculator/
  app.py
  PMDC_Calculator_claude204.py
  motor_core/
  gui/
  tests/
  docs/
docs/
  project_status_zh.md
  approved_model_assumptions_zh.md
  pending_decisions_zh.md
  electrical_quantity_definitions_zh.md
  phase3_formula_change_report_zh.md
work/
  run_pytest_style.py
```

## Next Phase Intent

Phase 3C should:

- keep all legacy `Ke` / `Kt` outputs intact
- add revised PMSM sinusoidal `Ke` fields with explicit phase/line and RMS/peak semantics
- derive revised PMSM sinusoidal `Kt` from three-phase power balance
- keep all downstream production calculations on legacy `Kt`

BLDC `Ke` / `Kt` corrections remain out of scope until a later approved phase.

## Open Engineering Issues

- `Kt` / `Ke` semantics still need formal confirmation
- BLDC 120-degree conduction RMS/peak semantics are still provisional
- `9.55 * P / n` remains the active downstream legacy implementation
- revised PMSM `Ke` / `Kt` defaults must not be enabled without explicit approval
- voltage requirement model is still simplified
- fill factor is still a legacy proxy, not a true slot fill factor
- several loss models remain empirical
