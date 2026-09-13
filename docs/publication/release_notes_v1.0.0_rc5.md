# MotorCalculator v1.0.0-rc5 — Customer Preview

> **Superseded by v1.0.0-rc6**, a corrective release that fixes how the winding
> factor and slot fill are presented. Everything described here still applies;
> see [`release_notes_v1.0.0_rc6.md`](release_notes_v1.0.0_rc6.md).

**Release channel:** release candidate · engineering preview
**Platform:** Windows x64
**Previous release:** v1.0.0-rc4

This is a preview build. It is offered so that practising machine and drive engineers
can try the new analysis surfaces against their own designs and tell us where the model
stops matching their work. It is not a certified tool, and nothing in it has been
validated against a physical motor.

---

## What's new

### Winding engineering

A dedicated winding view (`Analysis → 绕组工程`) showing the slot-EMF star breakdown —
distribution `kd`, pitch `kp`, skew `ks` — the resulting fundamental winding factor, and
the winding topology it implies.

Three different numbers have historically been called "the winding factor" in this
project, and they are now kept apart on purpose: the value **you entered**, the **ideal
slot-star geometry** value, and the **meshed-geometry** value implied by a 2D FEA slice.
On the reference design the last two differ by about 10 %. The meshed value is
diagnostic only and cannot become the production value.

### Slot fill and manufacturability

Gross and usable slot area, bare-copper fill, insulated-envelope fill, and
usable-envelope fill against a declared packing factor. Findings — comfortable,
feasible, tight, overfilled, geometrically impossible — now appear on the **main
dashboard**, not only inside the winding panel, so a design whose conductors do not
physically fit is visible without opening a second window.

The packing factor and the fill threshold bands are labelled `ENGINEERING_ASSUMPTION`.
They are common practice for random-wound round wire, not a standard, and you can
disagree with them without losing the underlying numbers.

### Geometry-derived winding-factor authority

One decision point with four explicit states:

| State | Meaning |
|---|---|
| `AUTO_FROM_GEOMETRY` | derived from the slot-EMF star; reproducible from stored inputs |
| `MANUAL_OVERRIDE` | you chose a value; the geometry value is shown beside it |
| `LEGACY_MANUAL` | a pre-existing project keeps its stored value **exactly** |
| `UNRESOLVED` | AUTO was asked for but the geometry does not support it — no value is invented |

The shipped startup example is now geometry-authoritative. **Projects and presets saved
before these semantics existed are not re-derived**: they keep the winding factor they
were designed with, because silently changing it would change an existing design's
results without anyone asking.

### Experimental and public-reference data framework

The application can now ingest measurement-shaped data — while being explicit that this
project still has none of its own.

Four source classes that cannot be confused by construction: `USER_EXPERIMENT`,
`PUBLIC_REFERENCE_EXPERIMENT`, `SIMULATED_REFERENCE`, `METHODOLOGY_ONLY`. CSV import
normalises units and **refuses to guess**: a column labelled only `Voltage` is rejected
with its admissible meanings listed, because line-RMS, phase-RMS and phase-peak differ
by up to 73 % and a wrong guess is invisible in the result.

Bench templates, multi-speed Ke regression, Y/delta resistance semantics, torque-current
and efficiency analyses are included — each stating what it does *not* establish.

A machine-compatibility gate decides what imported data may claim:
`SAME_MACHINE`, `COMPATIBLE_REFERENCE`, `DIFFERENT_MACHINE`, `INSUFFICIENT_METADATA`.

### CREATOR public evidence processing

The CREATOR PMSM open dataset (TU Graz, CC BY-NC 4.0, DOI `10.3217/sns1d-77m43`) is
registered as a public reference source. Given your own copy of the data, the
application extracts the back-EMF waveform harmonics, the cogging statistics, the
no-load loss separation, and the equivalent-circuit parameters.

Each published scalar carries its own origin — measured, measurement-derived,
FEA-derived, or unknown. That distinction matters: the source's own documentation states
that `Rs` was measured with an LCR meter while `Ld` and `Lq` came from finite-element
analysis, even though the table presents them side by side.

Reproducing the published back-EMF fundamental from raw samples validates **this
software's processing chain**. It does not validate this project's design — CREATOR is
a different machine (see limitations).

**No raw dataset is redistributed with this software.** The repository stores the
citation, DOI, licence, file hashes and adapters only.

### MTPA, field weakening and torque-speed capability

A new steady-state motor + inverter capability solver (`Analysis → 转矩-转速 / 弱磁能力`):

- **MTPA** solved in closed form. A non-salient machine gives `id = 0` exactly.
- **Inverter voltage limit** derived from the DC bus and modulation strategy —
  SVPWM `Vdc/√3`, SPWM `Vdc/2` — with a configurable, declared utilisation factor.
- **Current limit** as a dq-magnitude circle, with the phase-RMS → peak conversion
  made explicit rather than assumed.
- **Base speed** where the full-current MTPA point first reaches the voltage limit.
  This is a property of the machine *and* the inverter; it is not the rated speed.
- **Field weakening** maximising torque under both constraints at once.
- **Torque-speed and power-speed envelopes**, with regions classified by which
  constraints are actually active rather than by speed thresholds.
- **dq capability view** — current circle, voltage ellipses, MTPA and field-weakening
  trajectories — and a per-speed **operating-point inspector**.

Whether a constant-power region exists is *measured*, not assumed. A machine that does
not have one is reported as not having one.

---

## Important engineering notes

**The AFPM reference design is not experimentally validated.** No motor has been built
or bench-tested against these predictions. Finite-element agreement is independent
*numerical* evidence and is not a measurement. This has not changed in rc5 and will not
change until real bench data exists.

**The capability solver assumes `Ld = Lq`** for the AFPM reference, under a declared
`ISOTROPIC_ASSUMPTION`. The production model exposes a single synchronous inductance, so
no saliency is invented. If your machine is genuinely salient, its reluctance torque and
field-weakening range are **understated** unless you supply `Ld` and `Lq` explicitly.

**An unbounded electrical speed result is not an unbounded rotor speed.** When the
current limit exceeds the machine's characteristic current `ψ/Ld`, no electrical
steady-state speed bound is found within the configured search range, and the figure
shown is the *search ceiling*, flagged as unbounded. Mechanical stress, bearing limits,
rotor retention, thermal limits, switching-frequency limits and control-bandwidth limits
are **not modeled** by this electrical capability solver.

**Public reference data is from different machines.** The CREATOR PMSM is a radial-flux
inset machine with 4 poles and 6 slots; the reference design here is a 16-pole, 24-slot
axial-flux machine. The software refuses to let one validate the other, and it refuses
to construct an AFPM project from a radial-flux machine at all.

**Coreless cogging results are numerical noise.** The peak-to-peak figure roughly halves
with each mesh refinement, which is what remeshing noise looks like in a machine with no
slots to cog against.

**Loaded torque is not independent validation.** A numerical torque result exists, but
its residual tracks the back-EMF residual to within 0.13 percentage points, so it
re-measures the same disagreement rather than testing a new one.

**Windows binaries are unsigned.** SmartScreen and Microsoft Defender may warn on first
run. Verify the published SHA-256 checksums before installing.

**No automatic calibration.** No empirical coefficient is fitted, and no analytical
output is adjusted to match a finite-element or measured value.

---

## Feedback requested

This preview exists to get these six questions answered. Short, specific answers are
more useful than long ones.

1. **Missing machine inputs.** Which parameters does your design process need that this
   tool has no field for? Please name them.

2. **Winding-factor semantics.** Does the `AUTO_FROM_GEOMETRY` / `MANUAL_OVERRIDE` /
   `LEGACY_MANUAL` split match how you actually work? Is the geometry-derived value
   what you would have used?

3. **Slot fill and manufacturability realism.** Is the 0.80 packing factor right for
   your process? Do the tight / overfilled thresholds match what your winding shop
   would actually accept?

4. **Inverter limits.** What DC bus voltage and current limit do you really run, and
   what **voltage utilisation** does your drive use? The tool defaults to 1.0 — the
   whole linear region — and real drives typically reserve 5–10 % for the current
   regulator. Knowing your number would improve the default.

5. **Capability views.** Do the torque-speed envelope, the dq capability plot and the
   operating-point inspector fit your engineering workflow, or are they showing the
   wrong thing? Is the base-speed definition the one you use?

6. **Bench data.** Can you share *any* measured data — a back-EMF curve, a phase
   resistance, a torque-current sweep? Even a single no-load back-EMF measurement on a
   machine whose geometry you can describe would be the most valuable contribution this
   project could receive. It is the only route by which any quantity here becomes
   experimentally validated.

Whether your machine is **salient** is the single most useful thing to tell us
(question 2), because the isotropic assumption is the largest open modelling gap.

---

## Compatibility

- **Project files:** `PROJECT_SCHEMA_VERSION` is unchanged. Projects saved with rc4
  open in rc5 with their winding semantics preserved.
- **FEA case identity:** stored `case_id` values are unchanged by the version bump.
  The application version is deliberately excluded from case identity, so an rc4 → rc5
  upgrade does not invalidate a solved field result.
- **New projects** created in rc5 default to `AUTO_FROM_GEOMETRY` where the geometry
  supports it; existing projects do not change behaviour.

---

## Verifying your download

Check the SHA-256 of each file against `SHA256SUMS.txt` before installing:

```powershell
Get-FileHash .\MotorCalculator-1.0.0-rc5-win64-setup.exe -Algorithm SHA256
```

---

## Licence

Apache-2.0. The CREATOR dataset referenced by this software is CC BY-NC 4.0 and is
**not** redistributed here.
