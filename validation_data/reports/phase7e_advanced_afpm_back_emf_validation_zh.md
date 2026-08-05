# Phase 7E Advanced AFPM Back-EMF Validation

## Boundary

本报告来自 opt-in `motor_calculator/advanced_afpm/` sandbox。没有 calibration、correction-factor fitting、production default substitution 或 legacy output replacement。只有 `DIRECT` 或经批准的 `SAFE_TRANSFORM` 行才能计算 error；`BLOCKED` 行保留 reference 与 provenance，但 predicted/error 必须为空。

## Completeness Matrix

| source | topology | back-EMF | torque | resistance | inductance | efficiency |
|---|---|---|---|---|---|---|
| Abdelli 2026 | DSSR | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| Hosseini 2008 | SSDR | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED |
| Parviainen 2005 | DSSR | BLOCKED | BLOCKED | PARTIAL | PARTIAL | PARTIAL |
| Price 2009 | SSDR | BLOCKED | PARTIAL | BLOCKED | BLOCKED | BLOCKED |

`PARTIAL` 表示 external quantity 已被表示，但 Phase 7E 没有对应 prediction physics 或仍缺少 boundary inputs；它不表示可计算 model error。

## Back-EMF Comparison Attempt

| source | topology | status | represented radial inputs | N | predicted | reference | abs. error | rel. error | semantic compatibility |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| Parviainen 2005 | DSSR | BLOCKED | radii, physical gap, hm, p, Br, turns, speed, parallel stators | 100 | BLOCKED | 211 V phase RMS | N/A | N/A | BLOCKED: flattened waveform vs sinusoidal fundamental prototype |
| Hosseini 2008 | SSDR | BLOCKED | radii, derived effective gap, hm, p, Br, mur, speed | 100 | BLOCKED | 160 V phase peak-to-peak | N/A | N/A | BLOCKED: arbitrary harmonic waveform/Vpp vs sinusoidal fundamental RMS |
| Price 2009 | SSDR | BLOCKED | radii, effective gap, hm, turns, Y, speed | 100 | BLOCKED | 37 V phase peak | N/A | N/A | Potential SAFE_TRANSFORM only if inputs become complete: sinusoidal phase RMS to peak |
| Abdelli 2026 | DSSR | BLOCKED | radii, physical gap, hm, p, speed | 100 | BLOCKED | UNAVAILABLE, graph only | N/A | N/A | BLOCKED: graph-only arbitrary waveform and no authoritative scalar |

## Exact Remaining Blockers

### Parviainen 2005

- missing `geometry.effective_nonmagnetic_gap_m`;
- missing numeric scalar/profile magnet coverage for the sinusoidal magnet planform;
- missing `magnet_relative_permeability`;
- missing source-compatible `winding_factor`;
- source phase RMS waveform is flattened, while the prototype predicts sinusoidal fundamental RMS only.

Provenance: dissertation pp. 73 and 77, Tables 3.1 and 3.3; `https://lutpub.lut.fi/handle/10024/31185`.

### Hosseini 2008

- missing numeric radius-dependent magnet coverage profile in the reconstructed record;
- `conductors_per_coil` cannot be silently converted into `turns_per_phase`;
- missing source-compatible `winding_factor`;
- 160 V is harmonic phase peak-to-peak, not sinusoidal fundamental RMS/peak.

Provenance: article p. 201, Table 3; `https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf`.

### Price 2009

- missing authoritative `pole_pairs`;
- missing numeric radius-dependent magnet coverage;
- missing `remanence_t` and `magnet_relative_permeability`;
- missing source-compatible `winding_factor`.

The 37 V reference is measured sinusoidal phase peak, so its RMS-to-peak semantics are safe only after all physics inputs become available. Provenance: article p. 65, Figure 12 and adjacent text; `https://ijme.us/issues/spring2009/ijme_sp_09.pdf`.

### Abdelli 2026

- missing `geometry.effective_nonmagnetic_gap_m` and numeric magnet coverage semantics;
- missing `remanence_t` and `magnet_relative_permeability`;
- prototype `turns_per_phase`, connection and `winding_factor` remain unavailable/ambiguous;
- no authoritative scalar back-EMF reference was tabulated; graph digitization was not performed.

Provenance: article p. 6, Figures 10-11; `https://doi.org/10.2516/stet/2026004`.

## Decision

- Advanced AFPM representation works for SSDR/DSSR topology, radius-aware geometry, winding semantics, source-native back-EMF, separate Ld/Lq and torque boundary preservation.
- Radial integration converges numerically on the synthetic analytical case.
- External AFPM back-EMF rows unlocked: `DIRECT=0`, `SAFE_TRANSFORM=0`, `APPROXIMATE=0`.
- No first external AFPM back-EMF error can be reported legitimately.
- Remaining blockers combine source-data gaps and model-capability gaps. Parviainen/Hosseini additionally require harmonic/waveform capability; Price is primarily blocked by source material/pole/profile data; Abdelli is blocked by both source completeness and DSSR winding/path representation.
- Recommended Phase 7F: prioritize benchmark acquisition for Price pole/material/profile data and a winding-network physics layer. Harmonic/waveform back-EMF should follow when a source-complete non-sinusoidal case is available. Ld/Lq and torque-current physics remain later independent prototypes.
