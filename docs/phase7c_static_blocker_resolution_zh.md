# Phase 7C 静态 Blocker Resolution 决策

## 1. 哪些 blocker 被解决？

- Price 2009 current basis：恢复为 `10 A phase RMS`。
- Price 2009 torque boundary：恢复为 `12.6 Nm measured average shaft torque at 500 rpm`。
- Price winding：恢复为 36 turns/coil、3 series coils/phase、`108 turns/phase`、Y connection。
- Hosseini Xsd/Xsq：利用明确的 300 Hz 安全派生出独立 `Ld=Lq=0.00111408460164 H`。
- Parviainen：恢复 star per stator、840 turns per stator phase、two stators parallel、211 V phase RMS，以及 Figure 3.6 的 flattened waveform 语义。

这些解决的是 source semantics，不等于解决 production comparison。

## 2. 是否新增 DIRECT comparison？

没有。`DIRECT` 仍为 1，且仍只是在 Phase 7B.1 得到的 strict-SI `P/omega` rated shaft torque identity。

## 3. 是否新增 SAFE_TRANSFORM comparison？

没有新的 prediction/reference comparison。Hosseini `X -> Ld/Lq` 是安全派生的 source fields，但 production 不输出 Ld/Lq，因此不能升级为 comparison row。铜电阻温度归一化 helper 已实现和测试，但没有来源 measurement temperature 可供实际运行。

## 4. 哪些 metric 已提供 actual AFPM electromagnetic model evidence？

目前没有。Price/Hosseini 提供有价值的 external AFPM evidence，但 production AFPM magnetic model 仍不能在不补默认值的情况下生成 source-compatible prediction。

## 5. Observed errors

没有新增静态 electromagnetic error。唯一可计算外部误差仍是 Parviainen rated `P/omega`：`159.154943 Nm` 对 `159 Nm`，APE `0.097448%`，它不是 magnetic model error。

## 6. 哪些 blocker 已明确属于 model capability？

- DSSR/SSDR topology 与 stator parallel representation。
- radius-dependent rectangular 或 sinusoidal magnet shape 对单一 pole-arc coefficient 的不兼容。
- source field/FEA leakage 对单一 production leakage factor 的不兼容。
- non-sinusoidal back-EMF waveform。
- Ld/Lq 与 scalar phase inductance 的结构差异。
- loaded generator terminal voltage 与 no-load production back-EMF 的 quantity-boundary 差异。

## 7. 下一阶段决策

项目尚不具备 calibration 条件。建议二选一：

1. 优先进行另一次 evidence acquisition，寻找同 topology SSDR 且同时给出 Br、physical per-side gap、series turns/phase、connection、winding/leakage semantics 和 tabulated native back-EMF 的来源。
2. 进入 Phase 7D static model improvement proposal，但只能提出并评估 parallel schema/physics capability，不得直接修改 production formula。

若 Phase 7D 的目标是“提出可表达 external benchmark 的模型接口”，可以开始；若目标是 calibration 或切换 production default，则证据不足。
