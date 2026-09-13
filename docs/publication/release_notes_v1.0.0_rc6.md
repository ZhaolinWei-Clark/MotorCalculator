# MotorCalculator v1.0.0-rc6 — Customer Preview

**Release channel:** release candidate · engineering preview
**Platform:** Windows x64
**Previous release:** v1.0.0-rc5

A small corrective release. It adds no physics, no new analysis and no new model.
It fixes two things a preview user could see on the first screen: a winding-factor
field that displayed a number the calculation was not using, and a slot-fill result
that was largely hidden and, when unavailable, unexplained.

Everything in
[the rc5 notes](release_notes_v1.0.0_rc5.md) still applies, including every
limitation. Nothing there has been retracted.

---

## What changed

### The winding-factor field now says which authority it is in

rc5 introduced a production winding-factor authority — `AUTO_FROM_GEOMETRY`,
`MANUAL_OVERRIDE`, `LEGACY_MANUAL`, `UNRESOLVED` — and then never showed the value
it produced. The input panel kept an ordinary editable `k_w` box holding whatever
had last been typed or dragged into it. On the shipped startup example that meant
**0.93 in the box and 0.866025 in every result**, with nothing on screen to say
which was real. A user who dragged the quick-adjust slider could leave any value
there — 0.755, say — and see it change nothing.

In rc6:

| State | The `k_w` control |
|---|---|
| `AUTO_FROM_GEOMETRY` | **read-only**, showing the derived value, labelled 绕组系数 k_w（自动） with its source |
| `MANUAL_OVERRIDE` | editable, labelled 绕组系数 k_w（手动覆盖） |
| `LEGACY_MANUAL` | editable, labelled 绕组系数 k_w（旧项目保留）with a retained-value note |
| `UNRESOLVED` | editable, labelled 绕组系数 k_w（未解析）, with the reason the geometry was insufficient |

The rule is one sentence: **the field is editable exactly when what is typed in it
is what production uses**, and read-only otherwise — showing the number that *is*
used. The quick-adjust slider follows the same rule, so the panel cannot present two
sources of truth for the same quantity.

The authority selector now offers all three choosable states directly in the input
panel. `UNRESOLVED` is deliberately not offered: it is an outcome, not a choice.

The value you typed is **preserved** while an automatic one is in force, so
switching to 手动覆盖 restores your design rather than the derived number that was
temporarily displayed. The winding engineering view still keeps its three winding
factors distinct — the value you entered, the ideal slot-star geometry value, and
the meshed-geometry value — because that distinction is the whole point of the view.

The winding engineering view also used to open on `LEGACY_MANUAL` regardless of what
the session was set to, so it could describe a geometry-derived number as a preserved
historical value. It now opens on the session's authority, and a change made there
is adopted by the session instead of living as a second opinion.

### Slot fill is on the dashboard, in full

rc5 put one of five slot-fill numbers on the dashboard. rc6 adds a **槽满率 / Slot
Fill** card to the normal results view showing:

- copper fill and insulated-envelope fill against the **usable** slot area
- the manufacturability finding in plain Chinese — 宽裕 / 可行 / 偏紧 / 超填 — rather
  than an enum name
- gross and usable slot area, bare-copper area and insulated-envelope area
- all four fill ratios, so the headline figure can be checked
- the packing factor, and a statement that it and the threshold bands are engineering
  assumptions rather than a standard

**An unavailable fill now says why.** Previously the dashboard could read only
"不可用". It now names the specific parameters that are missing — slot depth, slot
widths, bare wire diameter, parallel paths, turns per phase — and distinguishes a
slotless machine, which has no slot fill by construction, from a slotted machine
whose fill could not be computed.

---

## Verified behaviour

On the shipped startup example (`design.manufacturability_start.v3`), recomputed
rather than asserted from stored constants:

| | |
|---|---|
| Production `k_w` | **0.8660254** — identical in the input panel, the dashboard, the winding view, the report and the export |
| Gross slot area | 105.00 mm² |
| Usable slot area | 77.49 mm² |
| Bare copper | 35.63 mm² |
| Insulated envelope | 41.55 mm² |
| Copper fill, gross / usable | 33.93 % / 45.97 % |
| Envelope fill, gross / usable | 39.58 % / 53.62 % |
| Finding | `FEASIBLE` — 可行 |

These reproduce the Phase 10G baseline exactly.

---

## Compatibility

- **`PROJECT_SCHEMA_VERSION` is unchanged.** No new stored field was introduced; the
  four-state authority is derived from what rc2 already stored.
- **Legacy projects are unchanged.** A project with no winding metadata keeps its
  stored `k_w` exactly, is labelled as a retained legacy value, and is never
  re-derived from geometry.
- **Stored FEA `case_id` values are unchanged** by the version bump, as in rc5.
- A project saved under `AUTO_FROM_GEOMETRY` now stores the winding factor it is
  actually calculated with. Previously it stored the superseded manual value, which
  meant the file on disk disagreed with the application's own results.

---

## Not changed

No winding-factor equation, no slot-fill equation, no protected physics file
(`motor_core/calculations.py` and the legacy baseline are byte-identical to rc5),
no calibration, and no new modelling claim. The AFPM reference design remains
**not experimentally validated**.

---

## Verifying your download

```powershell
Get-FileHash .\MotorCalculator-1.0.0-rc6-win64-setup.exe -Algorithm SHA256
```

Windows binaries are **unsigned**; SmartScreen and Defender may warn on first run.

## Licence

Apache-2.0. The CREATOR dataset referenced by this software is CC BY-NC 4.0 and is
**not** redistributed here.
