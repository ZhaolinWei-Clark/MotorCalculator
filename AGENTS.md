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

## Current Project Goal

The current goal is not to improve electromagnetic physics yet. The goal is to:

- freeze model definitions
- preserve legacy calculator behavior
- split GUI from the calculation core
- centralize units, constants, assumptions, and validation
- maintain a regression baseline before any formula-level changes

## Approved Model Definition

- Target machine type: three-phase axial-flux permanent-magnet motor, AFPM PMSM/BLDC
- Not a brushed PMDC model
- Default topology: dual-rotor, single-stator, dual-air-gap
- Default winding connection: Y connection
- `pole_pairs` means pole pairs
- `pole_count = 2 * pole_pairs` means total poles
- Internal calculations should use SI units
- Two operating modes are defined:
  - `PMSM`: sinusoidal back-EMF, sinusoidal current
  - `BLDC`: trapezoidal back-EMF, 120-degree conduction

## Hard Rules

- Do not delete or overwrite `motor_calculator/PMDC_Calculator_claude204.py`.
- Do not modify electromagnetic formulas without explicit user approval.
- Do not silently change legacy baseline data to make tests pass.
- Do not claim improved physical accuracy during the current restructuring track.
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

Examples that require prior approval:

- `Kt` / `Ke` semantic adjustments
- replacement of `9.55 * P / n`
- changes to voltage requirement model
- changes to fill-factor definition
- changes to empirical loss models
- changes to dual-rotor / dual-air-gap coefficients

## Legacy Baseline Policy

`motor_calculator/tests/fixtures/legacy_baseline.json` stores legacy behavior only.

- It is a regression anchor for refactoring.
- It is not proof of physical correctness.
- Any mismatch against this file must be explained before updating the fixture.

## Testing

Primary regression coverage currently includes:

- legacy baseline regression
- unit conversion checks
- validation behavior checks

Current execution method:

- `work/run_pytest_style.py`

Reason:

- the current environment does not have a preinstalled `pytest` package
- tests are still written in pytest-style naming so they can later migrate to standard pytest execution

## Key Git State

As of the current documentation freeze:

- working branch: `refactor/core-validation`
- baseline commit: `d2f9f67` `baseline: preserve original single-file motor calculator`
- phase 2 refactor commit: `aaeb2d7` `refactor: split motor core and add validation baseline`

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
work/
  run_pytest_style.py
```

## Next Phase Intent

The next phase should focus on decision preparation before any formula edits:

- enumerate all formula semantics that may change results
- separate approved structural changes from unapproved physics changes
- seek approval before touching calculation semantics

## Open Engineering Issues

- `Kt` / `Ke` semantics still need formal confirmation
- `9.55 * P / n` is still preserved for legacy compatibility
- fill factor is still a legacy proxy, not a true slot fill factor
- voltage requirement model is simplified
- several loss models remain empirical
- standard pytest is not yet available in the local runtime

