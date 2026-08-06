# Phase 7J 用户验证反馈与证据数据库

## 1. 为什么需要用户验证数据

解析计算给出的是模型预测；台架、已发表实验、独立 FEA、制造商数据或外部测试报告给出的是参考证据。只有把两者的机器配置、运行点和电气/机械语义一起保存，未来才能判断差异来自模型、输入、测量还是运行点。

单独保存“预测 33 V、测量 31 V”不可复现。Phase 7J 因此绑定完整输入快照、模型身份、公式/schema 版本、Git commit、来源和可选不确定性快照。

## 2. 提交流程

```text
prediction
-> optional validation feedback
-> quality and comparability checks
-> append-only local JSONL evidence store
-> descriptive aggregate statistics
-> future controlled review
```

绝不存在 `prediction -> one user value -> automatic correction` 路径。

## 3. 证据类型与质量

支持 `BENCH_MEASUREMENT`、`PUBLISHED_EXPERIMENT`、`FEA`、`MANUFACTURER_DATA`、`ANALYTICAL_REFERENCE` 和 `OTHER`。

质量分为：

- `HIGH`：可追溯 bench/published experiment、完整运行点与语义、完整输入快照，并且指标可比；
- `MEDIUM`：可信 FEA、制造商、发表实验或解析参考，来源和主要语义完整；
- `LOW`：有部分来源或输入，但语义/运行点/来源不完整；
- `UNVERIFIED`：支持信息不足的手工输入。任何 `SYNTHETIC/DEMO` 记录强制为此级别。

低质量证据不会被丢弃，但不能作为校准权威。

## 4. 指标兼容门

Phase 7J 分别保存预测和参考的：quantity scope、RMS/peak、waveform、torque boundary 和 current basis。结果只有三类：

- `DIRECT`：单位和全部必要语义一致；
- `SAFE_TRANSFORM`：仅执行批准且可追溯的正弦 RMS/peak 或已知 Y 接相线转换；
- `BLOCKED`：单位不兼容、未知波形 RMS/peak、轴/标量电感、轴/相电流或轴端/电磁转矩等语义不一致。

`BLOCKED` 记录仍入库，但 normalized reference 和误差保持空值。

## 5. 误差与聚合

兼容记录计算：

```text
signed_error = prediction - reference
absolute_error = abs(prediction - reference)
relative_error = signed_error / reference
APE = absolute_error / abs(reference) * 100
```

参考接近零时不生成不稳定的相对误差和 APE。可按 metric、topology、model version、evidence type/quality、1000 rpm 速度区间和 20 C 温度区间分组。

项目治理警告为：`N < 3` 时 `INSUFFICIENT_FOR_AGGREGATE_INTERPRETATION`；`3 <= N < 10` 时 `VERY_LIMITED_EVIDENCE`。`N >= 10` 也不自动意味着“已验证”。

当至少三条兼容记录中 75% 以上误差方向一致时，只报告 `POSSIBLE_POSITIVE_BIAS` 或 `POSSIBLE_NEGATIVE_BIAS`。该标记不产生或应用修正系数。

## 6. 与 Phase 7I 包络的关系

外部参考可被标记为：位于 Monte Carlo P10-P90 内、仅位于参数边界包络内、或位于两者之外。落在区间外不自动证明模型失败，原因也可能包括 model-form error、参数不确定性假设、测量误差或运行点不匹配。

验证覆盖度分为 `NONE / VERY_LIMITED / LIMITED / MODERATE / STRONG`，依据兼容记录数量、质量、独立来源和速度覆盖。它是项目治理摘要，不会单独把 Phase 7I 置信度提升到 `HIGH`。

## 7. 演示结果

`work/run_phase7j_feedback_demo.py` 使用明确的 synthetic demo：预测相 fundamental RMS back-EMF 约 33.3293 V，参考 31.8 V，1000 rpm。它得到 `DIRECT`、绝对误差约 1.5293 V、APE 约 4.8090%，参考值位于参数边界包络内但位于 P10-P90 外。

演示证据质量固定为 `UNVERIFIED`，覆盖度为 `VERY_LIMITED`，偏差结论为 `INSUFFICIENT_EVIDENCE`。它不是实际测量，也不得用于 accuracy 或 calibration claim。

## 8. GUI readiness 与后续建议

`FeedbackFormModel` 和只读 `ValidationSummary` 已可供未来 GUI 使用，且返回用户可读验证消息；本阶段没有修改 GUI。Phase 7K 建议优先做 **D. result confidence + accuracy UX**，让用户先正确理解证据质量、语义阻断、包络和覆盖度，再考虑 GUI 写入流程或受控校准治理。
