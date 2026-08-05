# Phase 7B：静态误差诊断

## 1. 诊断状态

`AFPM_STATIC_BENCHMARK_STATUS = BLOCKED`

本阶段没有生成外部 comparison row，所以没有 absolute error、relative error、PASS、WARNING 或 FAIL 可诊断。把“无法形成比较”写成 model failure，或把缺失值补成默认参数再计算，都会制造虚假的精度结论。

## 2. Blocker diagnosis

| Metric family | Status | Primary cause class | Evidence |
|---|---|---|---|
| back EMF | `BLOCKED` | semantic mismatch + insufficient source data | 最近候选输出为图形化 loaded phase voltage，且 waveform 明确非正弦；peak/RMS、phase/line 与 no-load/load 语义不能推断 |
| Ke | `BLOCKED` | semantic mismatch | 缺少可数值化且 basis 明确的 back EMF；不能对非正弦 waveform 自动套用 `sqrt(2)` 或 `sqrt(3)` |
| torque | `BLOCKED` | operating-point mismatch + insufficient source data | 候选 torque 数据未与完整 current、voltage、temperature 和 production input set 成套提供 |
| Kt | `BLOCKED` | winding interpretation + insufficient source data | current basis 或 phase current 不可得；不能从 current density 推断 |
| resistance | `BLOCKED` | insufficient source data | 最近候选没有 phase resistance 和 measurement temperature |
| inductance | `BLOCKED` | inductance abstraction + insufficient source data | 最近候选没有 scalar phase inductance 或 `Ld/Lq`；coreless 不等于 zero inductance |

## 3. Candidate-specific mismatch causes

- Parviainen 2005：`geometry interpretation / topology mismatch`，主要原型是一转子两定子，不能映射为默认单定子双转子。
- Price 2008：`insufficient source data / magnetic circuit approximation`，同拓扑但缺数值 `Br` 与完整 production inputs。
- Kowal 2010：`geometry interpretation / winding interpretation`，T-shaped magnets 和关键图形数据不能安全压缩为当前 input semantics。
- Si 2022：`winding interpretation / insufficient source data`，ED-TW 是特殊绕组，且 N48SH 牌号不能替代来源未给出的数值 `Br`。
- Shahnazari 2026：`winding interpretation / semantic mismatch / insufficient source data`，connection 与 phase series turns 未给，健康电压仅图示且非正弦。

## 4. No-fix boundary

本诊断没有修改 magnetic circuit、leakage/fringing、winding factor、inductance、loss 或 empirical coefficient。所有原因都是待验证假设；在第一批直接比较行出现前，不能把任何一项宣称为已确认的 model error。
