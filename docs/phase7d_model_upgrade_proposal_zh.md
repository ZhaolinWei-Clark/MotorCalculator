# Phase 7D AFPM Model Upgrade Proposal

## Executive Decision

Phase 7D 不建议修改 production formulas。最小安全升级是先建立 opt-in、sandbox-only 的 advanced AFPM representation 与 completeness/comparability planner；它让模型“知道自己缺什么”，但不会伪装成新的 physics solver。

Phase 7E 推荐只实现 P0 schema foundation。P1 physics 必须拆成后续、逐公式审批的独立阶段。

## 1. 哪些 capability gaps 正在阻塞 external validation？

- topology：SSDR、DSSR、single-sided 及多 stator electrical interconnection 无显式表示。
- geometry：单一 scalar pole arc 不能表示 radius-dependent rectangular 或 sinusoidal magnet profile。
- winding：turns/coil、series coils、parallel branches、connection、pitch/distribution factor 缺少统一来源语义。
- back-EMF：只有 sinusoidal scalar 或 provisional BLDC scalar，不能承载 native waveform/fundamental/harmonics。
- inductance：只有 scalar phase/line/mutual output，没有 optional Ld/Lq。
- torque：electromagnetic、shaft、load 和 mechanical-loss torque boundary 未结构化。
- generator/loss：loaded terminal voltage 和 source-specific power-flow/cooling boundary 不可表达。

## 2. 哪些仍是 source-data problems？

- Price：Br、可靠 pole count、physical per-side gap、source-equivalent leakage/kw 缺失。
- Hosseini：conductors/coil 不能安全变为 turns/phase，series/parallel 和 Y/Delta 未报告，current RMS/peak 未知。
- Abdelli：measured back-EMF/torque 主要是 plots，prototype turns/terminal mapping 和 numeric Br 不完整。
- Parviainen：phase DC resistance measurement temperature 与 production-equivalent coil/leakage fields 缺失。
- Bumby：numeric full text 仍 access-blocked。

任何 model upgrade 都不能把这些 C-class gaps 变成 source-provided values。

## 3. Smallest Safe Upgrade

### P0 - Phase 7E Recommended

1. `AFPMTopologySpec`：SSDR/DSSR/single-sided、disc/gap counts、stator connection。
2. `AFPMAnnulusGeometry`：inner/outer radius、per-gap lengths、magnet shape representation，无 solver。
3. `AFPMWindingSpec`：turns/coil、coils/phase、series/parallel、connection、kw provenance。
4. `BackEMFRepresentation`：scalar/fundamental/spectrum/samples 与 native quantity basis。
5. `InductanceRepresentation`：scalar/Ld/Lq/matrix slots，不做 axis-to-scalar mapping。
6. `TorqueBoundary`：electromagnetic/shaft/load/loss 类型和 power-flow direction。
7. source adapters + completeness gate + comparability planner。

P0 影响全部 14 个 blocker rows 的分类质量，但立即新增 comparison rows 仍为 0。它是安全实现 P1 的前置条件。

### P1 - Physics Prototypes After Separate Approval

1. topology-aware radial-slice magnetic/back-EMF sandbox solver，最多影响 5 个 voltage rows，理论最大可解锁 4。
2. source-equivalent winding-factor derivation与 multi-stator winding network，影响 6 rows，理论最大可解锁 5。
3. optional Ld/Lq sandbox physics，影响并可能解锁 4 inductance rows。
4. torque boundary/loss-torque adapter，影响 2 rows，理论最大可解锁 1。

P1 每一项必须独立 reference cases、numerical impact report 和 no-production-routing test。

### P2 - Later

1. resistance temperature/multi-stator terminal network：1 row。
2. generator loaded-terminal and efficiency/loss boundary：3 rows，理论最大可解锁 2。
3. mutual-inductance matrix、single-sided return path 与更高阶 harmonic physics：当前没有直接 row justification。

所有 unlock counts 都重叠且依赖 source completeness，不可相加。

## 4. 哪些 external rows 可能被解锁？

- 最清晰的短期目标是 4 个 inductance rows，因为 Parviainen Ld/Lq 与 Hosseini axis reactances/frequency 已明确；缺的是 source-compatible Ld/Lq model。
- back-EMF 的高价值目标有 5 rows，但没有一个只靠 schema 即可解锁。Parviainen/Abdelli 受 topology/geometry physics 限制，Price/Hosseini 仍同时有 source gaps。
- Price torque 可在 explicit electromagnetic/shaft loss boundary 后重新评估，但 mechanical-loss torque 未知，不能承诺解锁。
- efficiency/resistance 属于 P2，不应先于 back-EMF/inductance投入大量实现工作。

## 5. 哪些 production formulas 最终可能需要修改？

如果未来选择 integration，而不是永远 sandbox-only，至少涉及：

- magnetic pole area、reluctance、MMF/flux routing 和 leakage treatment。
- back-EMF `f*N*Phi*kw` aggregation、native waveform metrics 和 line/phase conversion routing。
- turn/end-winding length、multi-stator series/parallel resistance。
- scalar air-gap inductance与 optional dq inductance physics。
- electromagnetic-to-shaft torque 和 mechanical-loss torque relationship。
- loaded generator voltage、power flow 与 efficiency boundary。

这些都属于 formula-change approval scope。Phase 7D 没有批准其中任何一项。

## 6. 哪些可以先保持 sandbox-only？

全部 P0，以及 P1 的 radial-slice magnetic solver、winding network、Ld/Lq model 和 torque-boundary adapter。建议目录：

```text
motor_calculator/validation/advanced_afpm/
  topology.py
  geometry.py
  winding.py
  electrical_quantities.py
  inductance.py
  torque_boundaries.py
  source_adapters.py
  comparability_planner.py
```

它不能被 `motor_core/calculations.py`、GUI 或 legacy adapter import。未来 physics prototype 可放在 `motor_calculator/simulation_sandbox/afpm_static/`，仍返回独立 result types。

## 7. Calibration 是否仍然过早？

是。当前没有一个 production AFPM electromagnetic prediction 与 external reference 的合法 pair。唯一 external PASS 是 topology-independent `P/omega` identity。没有多 metric、多 operating point 的 evidence 时，calibration 会把 schema/model mismatch 错当成 coefficient error。

## 8. Recommended Phase 7E Scope

Phase 7E 建议命名为：**Advanced AFPM Representation Sandbox**。

只实现：

- 上述 P0 frozen dataclasses/enums。
- four reconstructed case adapters。
- completeness report：列出 source-provided、derived、ambiguous、missing。
- comparability planner：返回可运行 solver requirements 和 blocker categories。
- backward-compatibility tests：production module 不 import sandbox；legacy hashes 不变。
- no physics、no formula、no GUI、no calibration。

Phase 7E acceptance：能够无损表示四个 reconstructed cases，并对每个 case 得到与 Phase 7C 一致的 blocker set；`DIRECT/SAFE_TRANSFORM` 不要求增加。完成后再决定 Phase 7F 是否实现首个 topology-aware back-EMF physics prototype，或优先实现 Ld/Lq sandbox。
