# Release Strategy — v1.0.0-rc4

> **Superseded by v1.0.0-rc6.** This document is the RC4 record and is kept as-is:
> its statements were accurate for that build and rewriting them would destroy a
> release history. The current release is described in
> [`release_notes_v1.0.0_rc6.md`](release_notes_v1.0.0_rc6.md); the intervening
> release is [`release_notes_v1.0.0_rc5.md`](release_notes_v1.0.0_rc5.md).
> RC4 was published; its artifacts and checksums below remain valid for RC4.

**Status: artifacts built and verified locally. No tag created, nothing uploaded.**

> **v1.0.0-rc3 is not to be published.** Its binaries were built from commit `8fe452e`
> and predate the Phase 10A/10B/10C FEMM validation bridge by 22 commits — verified by
> inspection of the packaged executable, in which `motor_calculator.fea` is absent.
> Publishing them under notes describing the FEA bridge would misrepresent the download.
> They are retained locally under `release/_historical_local_builds/`, classified
> `HISTORICAL_LOCAL_BUILD` / `NOT_FOR_PUBLIC_RELEASE`.

---

## 1. Principle

| Content | Where it goes |
|---|---|
| Source, tests, docs, validation evidence | Git repository |
| Windows installer, portable ZIP (≈ 70 MB) | **GitHub Releases** |
| Build intermediates (`build/`, `dist/`, `release/`) | Neither — local only, gitignored |

Committing release binaries would permanently inflate the history for files GitHub
Releases hosts for free. That boundary is enforced by `.gitignore` and should stay
enforced.

---

## 2. Proposed release: `v1.0.0-rc4`

**Pre-release: yes.** This is a release candidate, not a stable v1.0.

**Build-source commit: recorded in `release/release_manifest.json` as `git_commit`,
and embedded in the package itself as `_internal/build_info.json`.** Source commit,
packaged binaries, manifest and checksums all refer to one build — the property rc3 did
not have, and the reason rc4 exists.

This document deliberately does **not** repeat the artifact hashes. It is itself build
input, so any hash written here would describe the build that existed *before* this file
was last edited, and could never be correct for the build that ships. The authority is
`release/SHA256SUMS.txt` and `release/release_manifest.json`, which are generated from
the final artifacts after the build.

### Assets

Every artifact is verified by recomputing its SHA-256 from the file on disk and
comparing against both the manifest and `SHA256SUMS.txt`:

| Asset | Authority for size and SHA-256 |
|---|---|
| `MotorCalculator-1.0.0-rc4-win64-setup.exe` | `release/SHA256SUMS.txt`, `release/release_manifest.json` |
| `MotorCalculator-1.0.0-rc4-win64-portable.zip` | `release/SHA256SUMS.txt`, `release/release_manifest.json` |
| `SHA256SUMS.txt` | the two lines above are its entire contents |

`SHA256SUMS.txt` lists only the two uploadable assets. The loose
`dist/MotorCalculator/MotorCalculator.exe` is recorded in the manifest as build
provenance but is **not** a release asset: it is an internal PyInstaller one-folder
member and is not standalone. The portable ZIP is the portable asset.

Build environment: Python 3.12.10, PyInstaller 6.16.0, Inno Setup 6.7.3, Tcl/Tk 8.6.15,
stable AppId `{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}`.

### Verified for this build

| Check | Result |
|---|---|
| Source regression | 1036 passed, 3 skipped |
| Real FEMM 4.2 integration | PASS (5 integration tests) |
| FEA layer present in package | 20 runtime `motor_calculator.fea` modules in the packaged PYZ |
| Source GUI smoke | PASS |
| Packaged GUI smoke | PASS |
| Portable ZIP smoke (extracted copy) | PASS |
| Project save/load, crash recovery | PASS |
| Contamination audit | clean — no FEMM, `.venv`, `.git`, `build/`, `tmp/`, logs, secrets or test modules |
| Payload single root | `MotorCalculator/` |
| Provenance | manifest `git_commit` == build HEAD, tree clean |

---

## 3. Known gaps to disclose

Tracked in the release manifest; must not be quietly omitted:

- **Unsigned binaries** (`signed: false`) — SmartScreen will warn
- **Clean-machine acceptance** is `BLOCKED_BY_ENVIRONMENT` — never verified on a machine
  without a developer toolchain
- **Defender scan** is `NOT_PERFORMED`
- **Installer acceptance not run for rc4**: local install, Start Menu, desktop shortcut,
  uninstall, reinstall and upgrade path are all `NOT_RUN`. The installer compiles and is
  recorded `BUILT_UNTESTED_ON_CLEAN_MACHINE`. rc3 had local-install evidence that rc4
  does not; running it requires installing the application on this machine.

---

## 4. Sequence when approved

1. Merge `release/v1.0.0-rc4` into `main`
2. Create an annotated tag `v1.0.0-rc4` on the final build-source commit
3. Create the GitHub Release from that tag, marked **pre-release**
4. Upload the two assets plus `SHA256SUMS.txt`
5. Verify the published checksums match `release_manifest.json`

**Not started.** No tag has been created and no asset uploaded.

---

## 5. Beyond rc4

A stable `v1.0.0` should not be published until at least:

- binaries are signed, or the unsigned status is prominently disclosed
- clean-machine acceptance is actually performed
- installer acceptance is re-run on the shipping build
- the +7.15 % magnetic-circuit residual is either explained or accepted as a documented
  model limitation with a stated accuracy envelope

Numerical FEA agreement alone does not justify dropping the release-candidate label.
