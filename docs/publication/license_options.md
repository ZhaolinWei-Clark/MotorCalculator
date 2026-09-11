# License Options — Decision Support

> ## ✅ Decision: **Apache-2.0**
>
> Approved and applied. The repository root carries the unmodified Apache License 2.0
> as [`LICENSE`](../../LICENSE), with third-party attribution in
> [`NOTICE`](../../NOTICE).
>
> The comparison below is retained as the record of *why*, not as an open question.

---

**The analysis below was written before the decision, and is preserved unchanged.**

Until a `LICENSE` file exists at the repository root, default copyright applies:
the work is "all rights reserved". Publishing source publicly does **not** grant reuse
rights. Anyone who clones the repository has no legal permission to use, modify or
redistribute it, and a cautious engineer or employer will treat it as unusable.

That is the practical cost of leaving this open.

---

## 1. What the choice actually decides

| Question | What it affects |
|---|---|
| Can someone use this in a commercial product? | permissive vs copyleft |
| Must derivative works be published? | copyleft strength |
| Is there explicit patent protection? | Apache-2.0 yes; MIT silent |
| Does it help or hinder a portfolio/hiring reader? | any clear license helps; none hurts |

---

## 2. Options

### MIT

- **Reuse:** anyone may use, copy, modify, merge, publish, distribute, sublicense, sell
- **Commercial use:** permitted without restriction
- **Derivative obligations:** retain the copyright and licence notice; that is all
- **Patents:** no express grant. A contributor could in principle hold a patent
  covering their contribution — a theoretical concern for a project of this kind
- **Portfolio suitability:** very good. Short, universally recognised, zero friction
  for a reviewer

### Apache-2.0

- **Reuse:** same practical freedom as MIT
- **Commercial use:** permitted without restriction
- **Derivative obligations:** retain notices, state significant changes, include the
  licence text; a `NOTICE` file is propagated if present
- **Patents:** **express patent grant** from contributors, plus automatic termination
  of that grant for anyone who initiates patent litigation over the work
- **Portfolio suitability:** very good, and slightly stronger signal of professional
  intent. Preferred by many companies precisely because of the patent clause
- **Cost:** longer text; a per-file header is conventional though not required

### GPL-3.0

- **Reuse:** permitted, but any distributed derivative must also be GPL-3.0
- **Commercial use:** permitted — but the copyleft obligation usually deters commercial
  adopters
- **Derivative obligations:** **strong copyleft.** Distributing a modified version
  requires publishing its complete corresponding source
- **Patents:** express grant, plus anti-tivoisation terms
- **Portfolio suitability:** mixed. It signals a stance on software freedom, but many
  employers screen against GPL in anything they might build on. For a portfolio piece
  intended to be *read and admired* rather than *incorporated*, the practical
  difference is small; for one intended to be reused, it is large

### No explicit license *(current state)*

- **Reuse:** none granted. All rights reserved by default
- **Commercial use:** not permitted
- **Derivative obligations:** N/A — derivatives are not permitted at all
- **Patents:** N/A
- **Portfolio suitability:** **poor.** A reviewer cannot legally run modified copies,
  and the omission reads as an oversight rather than a decision

---

## 3. A consideration specific to this project

MotorCalculator does not bundle or redistribute FEMM; it detects an external install
and drives it through generated Lua over a subprocess. No FEMM code or binary is
included in this repository, so **FEMM's own licensing does not propagate into this
choice**.

One third-party file *is* vendored: `installer/third_party/ChineseSimplified.isl`, an
Inno Setup translation, which carries its own licence and source attribution alongside
it. Whichever licence is chosen for MotorCalculator, that file keeps its own terms —
worth a line in the eventual `LICENSE` or a `NOTICE` file.

Nothing else in the tree carries an inherited obligation. Runtime dependencies
(`numpy`, `matplotlib`, `pytest`, `PyInstaller`) are permissively licensed and are not
vendored.

---

## 4. Recommendation

**Apache-2.0**, with **MIT** as the equally reasonable simpler alternative.

Apache-2.0 is suggested first because this is an engineering tool that models physical
machines and could plausibly touch patented control or machine-topology territory. The
express patent grant and the litigation-termination clause make it the safer choice for
anyone who might build on it, and the choice reads as deliberate rather than default.

Choose **MIT** instead if brevity and maximum familiarity matter more than the patent
clause — it is the lowest-friction option and is entirely defensible here.

**GPL-3.0 is not recommended** for this repository unless reciprocity is an explicit
goal, because it would discourage exactly the reuse that makes a public engineering
portfolio valuable.

---

## 5. How the decision was applied

| Step | Status |
|---|---|
| `LICENSE` at repository root, unmodified Apache-2.0 text | ✅ added |
| Copyright line — `Copyright 2026 Zhaolin Wei` | ✅ set |
| `NOTICE` covering the vendored Inno Setup translation (MIT, kirakira) | ✅ added |
| README `License` section and badge | ✅ updated |
| GitHub sidebar licence detection | automatic once `LICENSE` is on the default branch |

The `NOTICE` file also records that **FEMM is detected, not bundled or redistributed**,
and lists the runtime dependencies with their own licences. No patent claim is made
beyond the standard Apache-2.0 grant, and no third-party licence file was modified.
