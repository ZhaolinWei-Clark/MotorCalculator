# Release Strategy — v1.0.0-rc3

**Status: plan only. No artifacts have been uploaded, and no binaries are committed.**

---

## 1. Principle

| Content | Where it goes |
|---|---|
| Source, tests, docs, validation evidence (112 KB) | Git repository |
| Windows installer, portable ZIP (≈ 70 MB) | **GitHub Releases** |
| Build intermediates (`build/`, `dist/`, `release/`) | Neither — local only, gitignored |

The repository currently tracks **3.35 MB** across 468 files with no binaries, no
archives and no solver artifacts. Committing release binaries would permanently inflate
the history for files that GitHub Releases hosts for free. That boundary is already
enforced by `.gitignore` and should stay enforced.

---

## 2. Proposed release: `v1.0.0-rc3`

**Pre-release: yes.** This is a release candidate, not a stable v1.0. Marking it as a
pre-release on GitHub keeps that honest and stops it being presented as production-ready.

### Assets

Built locally under `release/` and verified against `release/release_manifest.json`:

| Asset | SHA-256 | Size |
|---|---|---:|
| `MotorCalculator-1.0.0-rc3-win64-setup.exe` | `d324d089240a7c7cc49f3d74230dc4d1d69fe559205911cb7d41462ca7e9e431` | 29,873,588 B |
| `MotorCalculator-1.0.0-rc3-win64-portable.zip` | `3af0e67af0a18b159447e146405558849f80d7189f8c98cffc8e2864455fe472` | 41,335,354 B |
| `SHA256SUMS.txt` | — | 308 B |

Build environment: PyInstaller 6.16.0, Inno Setup 6.7.3, Python 3.12.10, Tcl/Tk 8.6.15,
stable AppId `{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}`.

### Draft release notes

> **MotorCalculator v1.0.0-rc3** — release candidate
>
> Electric machine and drive engineering workbench for axial-flux permanent-magnet
> machines: analytical modeling, feasibility and optimization, a drive/control
> simulation sandbox, and an automated FEMM numerical validation bridge.
>
> **Highlights**
> - Corrected PMSM voltage semantics on a single line-RMS basis (authoritative since rc3)
> - Automated FEMM 4.2 validation bridge with deterministic case hashing and full
>   solver provenance
> - First real numerical FEA evidence: no-load back-EMF, geometry-consistent residual
>   **+7.15 %** at `FEA_TIER_3`
> - 1036 tests passing
>
> **Validation status** — the FEA comparison is *numerical*, not experimental. No
> physical motor has been tested. `FEA_TIER_3` is a 2D mean-radius AFPM slice and is not
> a 3D equivalence claim. See the README for the full limitations list.
>
> **Install** — run the setup executable, or unpack the portable ZIP. FEMM is **not**
> bundled; install [FEMM 4.2](https://www.femm.info/) separately if you want the
> validation features. The application runs normally without it.
>
> **Verify** — checksums in `SHA256SUMS.txt`. Binaries are **unsigned**; Windows
> SmartScreen will warn about an unknown publisher.

---

## 3. Known gaps to disclose

These are already tracked in the release manifest and must not be quietly omitted:

- **Unsigned binaries** (`signed: false`) — SmartScreen will warn
- **Clean-machine acceptance** is `BLOCKED_BY_ENVIRONMENT` — never verified on a
  machine without a developer toolchain
- **Defender scan** is `NOT_RERUN_FOR_RC3`
- **Upgrade path tested rc1 → rc3**, not rc2 → rc3 — the rc2 installer was never built

---

## 4. Sequence when approved

1. Choose and add a `LICENSE` (see [`license_options.md`](license_options.md)) —
   ideally before the first public release
2. Merge the portfolio documentation branch into `main`
3. Create an annotated tag `v1.0.0-rc3` on the release commit
4. Create the GitHub Release from that tag, marked **pre-release**
5. Upload the three assets and paste the notes above
6. Verify the published checksums match `release_manifest.json`

**Not started.** No tag has been created and no asset uploaded.

---

## 5. Beyond rc3

A stable `v1.0.0` should not be published until at least:

- a license exists
- binaries are signed, or the unsigned status is prominently disclosed
- clean-machine acceptance is actually performed
- the +7.15 % magnetic-circuit residual is either explained or accepted as a documented
  model limitation with a stated accuracy envelope

Numerical FEA agreement alone does not justify dropping the release-candidate label.
