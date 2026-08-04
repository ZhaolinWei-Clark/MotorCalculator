# Phase 7A：精度容差政策

## 1. 使用前提

容差只能在 topology、waveform、phase/line、RMS/peak、current basis、speed basis、温度与 operating point 均可比后应用。任何 comparability gate 失败都应标为 `BLOCKED`，不得通过单位或经验换算强行计算误差。

以下阈值是 **project provisional acceptance criterion**，不是 industry standard。若来源提供测量不确定度、标准规定或作者误差带，应优先采用 source-driven criterion 并记录依据。

## 2. 分类别暂定阈值

| Metric class | target | warning | fail | justification | basis |
|---|---:|---:|---:|---|---|
| algebraic identity / internal numerical consistency | 相对误差 <= `1e-9`；近零量用绝对误差 | `1e-9` 至 `1e-6` | > `1e-6` | 解析恒等式与确定性转换应接近浮点精度；这不是物理精度 | project provisional |
| electrical scalar benchmark（R、L、稳态 I/V） | APE <= 5% | >5% 且 <=10% | >10% | 给首轮外部比较留出参数温度、测量与建模差异 | project provisional，等待来源不确定度 |
| electromagnetic torque / back-EMF / Ke / Kt | APE <= 5% | >5% 且 <=10% | >10% | 需要先锁定转矩位置、相/线和峰值/RMS 语义 | project provisional，等待来源不确定度 |
| dynamic steady-state benchmark | APE <= 5% | >5% 且 <=10% | >10% | 只在输入、负载、惯量与参数一致时适用 | project provisional |
| dynamic transient benchmark | 关键幅值、上升/稳定时间各 <=10% | >10% 且 <=20% | 任一 >20% | 时序指标受采样、延迟和输入对齐影响，必须逐指标报告 | project provisional |
| loss benchmark | APE <=10% | >10% 且 <=20% | >20% | 损耗分离与温度敏感，需同一工况和边界 | project provisional |
| thermal benchmark | 温升和时间常数误差各 <=10% | >10% 且 <=20% | 任一 >20% | 单节点模型只能对匹配冷却边界和测点进行首阶验证 | project provisional |

## 3. 错误指标

```text
absolute_error = prediction - reference
absolute_error_magnitude = abs(prediction - reference)
relative_error = (prediction - reference) / reference
absolute_percentage_error = abs(prediction - reference) / abs(reference) * 100
symmetric_percentage_error = 200 * abs(prediction-reference) / (abs(prediction)+abs(reference))
```

当 `abs(reference) <= 1e-12` 时，状态为 `near_zero_reference`，不输出 conventional relative error 或 APE；只使用有量纲绝对误差，并在分母稳定时补充 sAPE。prediction 或 reference 缺失时状态为 `unavailable`。

## 4. 判定与归因

- `PASS/WARNING/FAIL` 只用于 directly comparable 行。
- `BLOCKED` 不是 fail，也不是 pass；它表示无法形成有效误差。
- internal analytical pass 只能标为 `INTERNAL_ONLY`，不得并入外部通过率。
- 超阈值后先检查 semantic、topology、input mapping 和 source uncertainty，再讨论 model error。
- Phase 7A 不允许依据任何阈值调参、拟合或增加 correction factor。
