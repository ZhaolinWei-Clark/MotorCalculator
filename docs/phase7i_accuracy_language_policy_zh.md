# Phase 7I Accuracy Language Policy

## 1. 目的

Phase 7I 输出的是在显式参数范围或概率分布下，解析模型预测可能移动多少。它不证明真实机器必定位于该区间，也不量化尚无外部证据支持的 model-form error。

## 2. 允许使用的表述

- “Estimated parameter-driven range” / “估计的参数驱动范围”。
- “Parameter-bound prediction envelope” / “参数边界预测包络”。
- “Monte Carlo percentile range under declared assumptions” / “在已声明假设下的 Monte Carlo 样本百分位范围”。
- “P10/P50/P90 of accepted samples under the declared parameter distributions”。
- “External validation coverage: limited”。
- “Model-form error is not included / remains unquantified”。
- “Numerical integration difference between the declared resolutions”。
- “PROJECT-DEMONSTRATION ASSUMPTIONS”。

## 3. 禁止或需改写的表述

| 禁止表述 | 原因 | 合规改写 |
|---|---|---|
| “实际值一定在 +/-5%” | 没有实验统计覆盖与 model-form bound | “在已声明参数边界内，模型输出移动范围为...” |
| “95% accurate” | 百分位不是 accuracy percentage | “accepted Monte Carlo samples 的 P05-P95 范围为...” |
| “90% confidence interval” | 当前参数 PDF 是演示假设，且不是参数估计置信区间 | “declared distributions 下的 P05-P95 sample percentile interval” |
| “guaranteed error” | 未量化模型形式误差 | “parameter-driven envelope，不包含 model-form error” |
| “industry-standard accuracy” | 当前 1% mesh/slice 门槛是项目规则 | “project-declared numerical tolerance” |
| “validated AFPM accuracy” | 外部直接 AFPM 电磁验证仍有限 | “internal analytical result with limited external validation coverage” |

## 4. Percentile 语义

P10 表示 accepted Monte Carlo 输出样本中约 10% 不高于该值，P50 是样本中位数，P90 表示约 90% 不高于该值。这些解释只在调用者声明的参数分布、随机种子、样本数、物理拒绝规则和模型公式下成立。

P10-P90 不能被自动称为 80% 真实值覆盖区间；P05-P95 也不能被自动称为 90% confidence interval。

## 5. Model-form 分离规则

以下项保持 `MODEL_FORM_UNCERTAINTY = UNQUANTIFIED`，不得伪装成 Br、气隙或绕组因子的随机分布：

- 漏磁和 fringing omission。
- 简化磁路。
- mean-radius 或 radial-slice representation error。
- 未建模 saturation。
- 简化 winding representation。
- 3D magnet/coil geometry omission。
- topology abstraction。

只有独立实验或 FEA evidence 直接支持数值边界时，才可提出单独的 model-form estimate；仍不得把它写回 production calibration。

## 6. GUI 使用约束

未来 GUI 可以只读展示 `AccuracyEnvelopeResult`，但必须同时显示 assumption label、UNKNOWN 参数、external validation status、model-form status 和 warnings。不得只显示一个看似精确的 +/- 数字。
