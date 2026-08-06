# Phase 7K Engineering Confidence & Accuracy UX

## 1. 用户看到什么

现有主计算和报告保持原样。结果 notebook 新增可选 `Confidence & Validation` 页签，包含：

- nominal prediction；
- estimated parameter-driven range；
- Monte Carlo P10-P90；
- overall engineering confidence；
- external validation coverage；
- numerical / parameter / model-form 分项状态；
- dominant uncertainty drivers；
- 本地 validation evidence 计数；
- Tkinter-native 范围条。

该页签不依赖 matplotlib，不替换主结果，也不要求用户输入 uncertainty 或 feedback。

## 2. Nominal prediction

Nominal prediction 是一组确定输入和固定模型假设下的输出。更多小数位表示数值表示更细，不代表真实物理预测具有同样精度。普通 legacy-compatible GUI 计算完成后会显示其 nominal back-EMF，但不会自动附加 Phase 7I 区间，因为两者不是同一模型轨道。

## 3. Parameter-bound range

Parameter-bound envelope 是显式 lower/nominal/upper 参数组合产生的模型输出范围。它回答“声明的输入边界内，预测可能移动多少”，不是 confidence interval，也不是 guaranteed real-world error bound。

Phase 7K 只在用户点击 `Estimate controlled-reference uncertainty` 后运行该分析。该操作使用 Phase 7H/7I controlled reference，并显示 `not the current production calculation`，不得把它套用到当前 legacy 结果。

## 4. P10 / P90

P10/P50/P90 来自带固定 seed 的 Monte Carlo 样本。只有 `NORMAL` 和 `UNIFORM` 参数被采样；`RANGE` 没有 PDF，`UNKNOWN` 不会被静默采样。P10-P90 只描述声明分布下的样本百分位，不是现实误差概率保证。

Normal calculation 不运行 Monte Carlo。用户必须显式触发，避免每次字段变化执行数千次计算。

## 5. Confidence 的含义

Confidence 不是 accuracy score。解释引擎分别检查：外部 evidence coverage、model-form 状态、参数 completeness、dominant drivers 和 numerical convergence。区间窄不能单独产生 `HIGH`。

Phase 7I controlled demo 为 `LOW`，主要原因是：

- external AFPM validation very limited；
- model-form uncertainty `UNQUANTIFIED`；
- Br 和 winding factor 等参数对输出敏感；
- radial integration 数值收敛良好，但数值收敛不等于物理正确。

## 6. Model-form uncertainty

Parameter propagation 不包含 leakage、fringing、磁饱和、简化磁路、拓扑/绕组抽象和三维几何遗漏。当前这些 model-form effects 仍是 `UNQUANTIFIED`。GUI 在高级 AFPM confidence 结果中持续显示该限制。

## 7. Validation feedback

`Add validation result` 对话框在已有计算后可用。用户选择 metric 和 evidence type，并填写 reference、speed、current、voltage、temperature、source、notes 及 reference semantics。

支持类型：bench measurement、published experiment、FEA、manufacturer data、analytical reference、other。界面说明不同 evidence 类型并不等强。

提交后显示：

- `DIRECT / SAFE_TRANSFORM / BLOCKED`；
- `HIGH / MEDIUM / LOW / UNVERIFIED`；
- prediction 与 reference；
- 兼容时的 signed error 和 APE；
- 可用时相对于 uncertainty envelope 的位置。

当 phase/line、RMS/peak、waveform、torque boundary、current basis 或 inductance semantics 不兼容时，界面显示 `Numerical error: not computed`。记录仍可保存在本地 evidence database。

## 8. 假设可见性

`View / edit assumptions` 显示 controlled-reference 参数的 nominal、kind、bounds/PDF 和 provenance。用户可以明确选择 `EXACT / RANGE / NORMAL / UNIFORM / UNKNOWN`。缺失的 normal mean/sigma 或 uniform bounds 会被拒绝，不会自动补分布。

编辑结果只保存在当前 GUI 会话，用于下一次显式 controlled-reference estimate；不修改 JSON、production defaults 或 legacy baseline。

## 9. 本地导出与隐私

Summary 可导出为本地 UTF-8 JSON 或 text，包含 nominal、range、confidence、coverage、warnings 和 evidence counts。Phase 7K 不包含 upload、telemetry、后台网络调用或云同步。反馈继续写入默认被 Git 忽略的本地 JSONL。

## 10. Graceful degradation

- 无 uncertainty：显示 `Uncertainty estimate not available for this result.`，计算继续可用。
- feedback JSONL 不存在：coverage 为 `NONE`。
- feedback JSONL 损坏：evidence counts 降级为空并显示 warning；uncertainty summary 与主计算仍可用，新的 feedback append 被安全拒绝。
- matplotlib 不存在：confidence tab 和 Tkinter range bar 仍可用；旧 chart tab 使用其既有 placeholder 行为。
- Tcl/Tk 不可用：入口保持既有明确启动错误；这属于运行时安装问题，不是电磁计算失败。

## 11. Synthetic demo

`work/run_phase7k_confidence_demo.py` 提供 GUI-neutral 可复现数据：

- nominal：33.329273 V；
- parameter bounds：28.466740-38.757257 V；
- P10/P50/P90：32.150113 / 33.340058 / 34.534283 V；
- confidence：`LOW`；
- synthetic reference：31.8 V；
- APE：4.809035%；
- coverage：`VERY_LIMITED`；
- envelope position：`INSIDE_PARAMETER_BOUNDS_ONLY`。

该 feedback 明确为 `SYNTHETIC / UNVERIFIED`，不是实验结果。
