# Phase 7B.1 外部 AFPM 逐指标比较报告

## 冻结边界

本报告只读取公开来源并调用既有 strict-SI 额定转矩关系。它不修改生产公式、默认参数、动态模型、GUI 或 legacy baseline，也不执行校准。
有来源数值但拓扑、波形、绕组或 operating-point 语义不兼容时，该行保持 `BLOCKED`，不计算误差。`APPROXIMATE` 证据即使有数值也不得形成 accuracy PASS 声明。

## 汇总

- comparability DIRECT: 1
- comparability SAFE_TRANSFORM: 0
- comparability APPROXIMATE: 0
- comparability BLOCKED: 14
- comparability UNAVAILABLE: 6
- outcome PASS: 1
- outcome WARNING: 0
- outcome FAIL: 0
- outcome APPROXIMATE: 0
- outcome BLOCKED: 14
- outcome UNAVAILABLE: 6

当前唯一外部直接可比较行是 Parviainen 原型机 5 kW / 300 rpm / 159 Nm 的额定轴端功率-转速-转矩关系。它验证 strict-SI `T=P/omega` 一致性，不验证 AFPM 电磁转矩模型。

## 来源：Design and manufacturing of axial flux permanent magnet machines for electric vehicle applications

- topology: double-stator/single-rotor slotted AFPM, 18 slots, 12 poles
- source: https://doi.org/10.2516/stet/2026004

| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |
|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
| abdelli_2026_dssr_afpm | double-stator/single-rotor slotted AFPM, 18 slots, 12 poles | back_emf_phase_waveform | 1000 rpm, no load | unavailable | unavailable | V | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported in the accessible article text.; confidence: high for tables; low for untabulated plot values and absent fields | article p. 6, Figures 10 and 11 | DSSR topology mismatch and graph-only value prevent a project-model numeric comparison. |
| abdelli_2026_dssr_afpm | double-stator/single-rotor slotted AFPM, 18 slots, 12 poles | torque_nm | 1000 rpm, 20-400 A | unavailable | unavailable | Nm | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported in the accessible article text.; confidence: high for tables; low for untabulated plot values and absent fields | article p. 6, Figure 12 | Graph digitization is not approved evidence and DSSR topology differs from the default model. |
| abdelli_2026_dssr_afpm | double-stator/single-rotor slotted AFPM, 18 slots, 12 poles | phase_resistance_ohm | unavailable | unavailable | unavailable | ohm | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | No instrument uncertainty reported in the accessible article text.; confidence: high for tables; low for untabulated plot values and absent fields | entire accessible article, not reported | Missing source value is not represented by zero. |
| abdelli_2026_dssr_afpm | double-stator/single-rotor slotted AFPM, 18 slots, 12 poles | phase_inductance_h | unavailable | unavailable | unavailable | H | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | No instrument uncertainty reported in the accessible article text.; confidence: high for tables; low for untabulated plot values and absent fields | entire accessible article, not reported | Missing source value is not inferred from geometry. |

## 来源：Design and Testing of a Permanent Magnet Axial Flux Wind Power Generator

- topology: dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection
- source: https://ijme.us/issues/spring2009/ijme_sp_09.pdf

| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |
|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
| price_2009_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection | back_emf_phase_peak_v | 600 rpm, no load | unavailable | 37 | V phase peak | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; displayed values are rounded.; confidence: high for explicitly stated measured values; low for absent fields | article p. 65 (issue PDF p. 67), Figure 12 and adjacent text | Magnet remanence, leakage factor, winding factor, and project winding semantics are incomplete. |
| price_2009_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection | torque_nm | 500 rpm, rated load current | unavailable | 12.6 | Nm | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; displayed values are rounded.; confidence: high for explicitly stated measured values; low for absent fields | article p. 65 (issue PDF p. 67), torque paragraph and Figure 14 | Rated-current semantics and missing project magnetic inputs prevent a model-to-measurement comparison. |
| price_2009_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection | phase_resistance_ohm | unavailable | unavailable | unavailable | ohm | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | No instrument uncertainty reported; displayed values are rounded.; confidence: high for explicitly stated measured values; low for absent fields | article pp. 59-66, not reported | No resistance value is inferred from wire dimensions. |
| price_2009_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 9 coils, Y connection | phase_inductance_h | unavailable | unavailable | unavailable | H | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | No instrument uncertainty reported; displayed values are rounded.; confidence: high for explicitly stated measured values; low for absent fields | article pp. 59-66, not reported | No inductance value is inferred from geometry. |

## 来源：Design of Axial-Flux Permanent-Magnet Low-Speed Machines and Performance Comparison Between Radial-Flux and Axial-Flux Machines

- topology: one-rotor/two-stators AFPM; stators electrically parallel; 12 poles
- source: https://lutpub.lut.fi/handle/10024/31185

| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |
|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | rated_torque_nm | 5 kW rated shaft output, 300 rpm | 159.154943092 | 159 | Nm | published_prototype_specification | 0.154943091895 | 0.0974484854688 | DIRECT | PASS | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation p. 73, Table 3.1 | Strict-SI P/omega consistency is topology-independent; this is not electromagnetic torque-current validation. |
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | back_emf_phase_rms_v | rated point, PM temperature approximately 95-100 C | unavailable | 211 | V phase RMS | measured | unavailable | unavailable | BLOCKED | BLOCKED | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation pp. 73 and 78, Table 3.1 and Figure 3.6 | DSSR/parallel-stator topology cannot be routed through the SSDR production magnetic model. |
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | phase_resistance_ohm | prototype DC test | unavailable | 3.7 | ohm | measured | unavailable | unavailable | BLOCKED | BLOCKED | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation p. 77, Table 3.3 | Source quantity is per stator while the machine stators operate electrically in parallel. |
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | Ld_h | inverter estimate | unavailable | 0.055 | H | measured | unavailable | unavailable | BLOCKED | BLOCKED | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation p. 77, Table 3.3 | Production exposes scalar phase inductance; collapsing Ld to that field is not approved. |
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | Lq_h | inverter estimate | unavailable | 0.06 | H | measured | unavailable | unavailable | BLOCKED | BLOCKED | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation p. 77, Table 3.3 | Production exposes scalar phase inductance; collapsing Lq to that field is not approved. |
| parviainen_2005_afpm_prototype | one-rotor/two-stators AFPM; stators electrically parallel; 12 poles | efficiency_percent | rated steady state, natural cooling | unavailable | 89.2 | % | measured | unavailable | unavailable | BLOCKED | BLOCKED | Formal measurement uncertainty is not reported; table values are rounded.; confidence: high for tabulated values and topology metadata | dissertation p. 79, prototype test discussion | Loss/cooling operating-point mapping is incomplete and production loss formulas remain frozen. |

## 来源：Electromagnetic Design of Axial-Flux Permanent Magnet Machines

- topology: slotless axial-flux permanent-magnet generators; details require full article
- source: https://durham-repository.worktribe.com/output/1595511/electromagnetic-design-of-axial-flux-permanent-magnet-machines

| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |
|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
| bumby_2004_afpm_validation | slotless axial-flux permanent-magnet generators; details require full article | back_emf | unavailable from repository abstract | unavailable | unavailable | V | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | Full numeric tables and measurement uncertainty were not accessible.; confidence: low because only metadata and abstract were accessible | repository abstract, abstract only | Full-text numeric evidence is access-blocked; the abstract percentage is not a substitute for source values. |
| bumby_2004_afpm_validation | slotless axial-flux permanent-magnet generators; details require full article | inductance | unavailable from repository abstract | unavailable | unavailable | H | measured | unavailable | unavailable | UNAVAILABLE | UNAVAILABLE | Full numeric tables and measurement uncertainty were not accessible.; confidence: low because only metadata and abstract were accessible | repository abstract, abstract only | Full-text numeric evidence is access-blocked; no inductance is inferred. |

## 来源：Design, Prototyping and Analysis of a Low-Cost Disk Permanent Magnet Generator with Rectangular Flat-Shaped Magnets

- topology: dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils
- source: https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf

| source | topology | metric | operating point | predicted | reference | unit | evidence type | abs error | APE % | comparability | outcome | uncertainty / confidence | provenance | notes |
|---|---|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
| hosseini_2008_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils | back_emf_no_load_peak_to_peak_v | 3000 rpm, no load | unavailable | 160 | V phase peak-to-peak | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; tabulated values are retained at source precision.; confidence: high for tabulated source values; low for missing winding semantics | article p. 201, Table 3 | Unknown connection/waveform semantics and incomplete production winding/leakage inputs block conversion and prediction. |
| hosseini_2008_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils | output_voltage_fundamental_peak_to_peak_v | 3000 rpm, 10 ohm load | unavailable | 102 | V phase peak-to-peak | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; tabulated values are retained at source precision.; confidence: high for tabulated source values; low for missing winding semantics | article p. 201, Table 3 | Peak-to-peak loaded generator output is not the production back-EMF semantic; no unapproved conversion is made. |
| hosseini_2008_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils | efficiency_percent | 3000 rpm nominal load | unavailable | 78.1 | % | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; tabulated values are retained at source precision.; confidence: high for tabulated source values; low for missing winding semantics | article pp. 201-202, Figure 14 and Table 4 | Matched loss and load semantics are unavailable while production loss formulas remain frozen. |
| hosseini_2008_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils | Xsd_ohm | 3000 rpm, 300 Hz nominal operation | unavailable | 2.1 | ohm | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; tabulated values are retained at source precision.; confidence: high for tabulated source values; low for missing winding semantics | article p. 202, Table 4 | Reactance is not converted to the production scalar inductance without an approved dq/scalar model bridge. |
| hosseini_2008_coreless_afpm_generator | dual-rotor/single-coreless-stator AFPM, 24 poles, 18 coils | Xsq_ohm | 3000 rpm, 300 Hz nominal operation | unavailable | 2.1 | ohm | measured | unavailable | unavailable | BLOCKED | BLOCKED | No instrument uncertainty reported; tabulated values are retained at source precision.; confidence: high for tabulated source values; low for missing winding semantics | article p. 202, Table 4 | Reactance is not converted to the production scalar inductance without an approved dq/scalar model bridge. |

## 结论

- 已从完全外部的 AFPM 原型来源建立 1 行直接可比较结果；相对误差约 0.0974%，在 Phase 7A torque tolerance 下为 PASS。
- 该 PASS 只覆盖额定轴功率、转速和转矩的 SI 一致性，不能扩展为 back-EMF、Ke、Kt、磁路、损耗或整体 AFPM accuracy 声明。
- 其余指标继续因拓扑、绕组、波形、参数完整性或全文访问问题阻塞；没有通过调参、图像数字化或推断缺失值来减少 blocker 数量。
- 当前证据适合继续进行逐指标 Phase 7C 前置工作，但不足以开始生产参数校准。
