# Phase 7C Model Input Support Gap

## 分类规则

- A - schema-only limitation：物理关系可能已有，但输入/输出结构不能表达来源语义。
- B - model-physics limitation：当前公式本身不包含来源所需的 topology、waveform 或磁路物理。
- C - source-data limitation：论文没有给出必要值或定义。

本阶段只分类，不修复 schema 或公式。

## Gap Matrix

| gap | class | affected sources/metrics | consequence |
|---|---|---|---|
| dual-stator vs dual-rotor topology field | A+B | Parviainen/Abdelli E, R, L, efficiency | `MotorAnalysisInput` 无可验证的 DSSR/SSDR routing；磁路公式固定为默认双转子/双气隙解释 |
| stator-series/parallel representation | A+B | Parviainen E/R/L | 双 stator parallel 无法表示为来源等价 phase quantity |
| scalar pole_arc_coefficient | B | Price/Hosseini/Parviainen/Abdelli E | rectangular radius-dependent or sinusoidal magnet shape 无法由单一 alpha_p 表达 |
| scalar leakage_factor | B+C | all back-EMF candidates | 来源多用 FEA/radial-slice leakage；缺少 production-equivalent scalar |
| winding factor and explicit coil pitch | A+B+C | all back-EMF candidates | geometry may exist, but production expects one kw without a source-approved bridge |
| waveform enum limited to PMSM sinusoidal or provisional BLDC | A+B | Parviainen/Hosseini back-EMF | flattened/harmonic phase waveform 不能安全转换或直接预测 |
| loaded terminal voltage vs no-load back-EMF | B | Hosseini 102 V fundamental | production static chain does not reconstruct the source generator/load boundary |
| Ld/Lq vs scalar phase inductance | A+B | Parviainen/Hosseini inductance | source axis values must remain separate; production output cannot be compared |
| resistance terminal/per-stator topology | A+B | Parviainen resistance | per-stator DC phase resistance and two parallel stators cannot be mapped safely |
| resistance temperature absent | C | Parviainen resistance | approved copper transform cannot run without measured temperature |
| Br/pole count/per-side gap missing | C | Price back-EMF | otherwise attractive SSDR benchmark cannot produce a complete model input |
| conductors/coil vs turns/phase and connection | C | Hosseini back-EMF | no safe series turns or terminal mapping |
| graph-only scalar output | C | Abdelli back-EMF/torque | only `APPROXIMATE_FROM_FIGURE` could be extracted, while deeper blockers remain |

## Inductance Semantics

| quantity | current production meaning | source meaning | safe action |
|---|---|---|---|
| `phase_inductance_h` | scalar phase self-inductance from air-gap area plus fixed end-winding ratio | not reported directly by reviewed sources | compare only to an explicitly equivalent scalar phase measurement |
| `line_inductance_h` | production scalar phase value minus fixed mutual term | not reported | no external comparison |
| Parviainen `Ld=0.055 H` | unavailable in production static output | inverter-estimated d-axis synchronous inductance | retain as Ld; do not collapse |
| Parviainen `Lq=0.060 H` | unavailable in production static output | inverter-estimated q-axis synchronous inductance | retain as Lq; do not collapse |
| Hosseini `Xsd=2.1 ohm @ 300 Hz` | no axis reactance output | d-axis synchronous reactance | safe derive `Ld=Xsd/(2*pi*f)` only |
| Hosseini `Xsq=2.1 ohm @ 300 Hz` | no axis reactance output | q-axis synchronous reactance | safe derive `Lq=Xsq/(2*pi*f)` only |

## Phase 7D Implication

A future proposal may add explicit topology, magnet-shape, winding-layout, waveform and dq-inductance schemas. That proposal must remain parallel to production until formula impact is approved. Phase 7C provides no authority to alter the current model.
