# Phase 7I AFPM 不确定性框架

## 1. 为什么单一预测值可能误导

解析模型给出的 `33.329273 V` 是一组确定输入和一组固定模型假设下的结果。实际输入可能只有工程范围、测量标准差、材料分布或未知 uncertainty。如果只显示单值，用户无法区分数值精度、参数敏感性、来源完整性和真实物理准确度。

Phase 7I 因此同时保留 nominal、parameter-bound envelope、Monte Carlo samples、numerical integration difference、external validation status 和 model-form status。

## 2. 四类 uncertainty

- `PARAMETER_UNCERTAINTY`：Br、气隙、磁体厚度、绕组因子、匝数和几何等输入的不确定性；Phase 7I 主要量化此类。
- `NUMERICAL_UNCERTAINTY`：径向切片分辨率、未来 FEA mesh 等数值离散变化，可由收敛结果单独报告。
- `MODEL_FORM_UNCERTAINTY`：漏磁、fringing、饱和、简化磁路、拓扑/绕组抽象等；当前为 `UNQUANTIFIED`。
- `EXTERNAL_VALIDATION_UNCERTAINTY`：外部来源、测量和语义映射的覆盖/不确定性；当前 AFPM coverage 为 `LIMITED`。

这些类别不能相互替代。尤其不能为了让 Monte Carlo 区间变宽而把未知 model-form error 塞入某个输入 PDF。

## 3. UncertaintyKind

- `EXACT`：固定值，不产生采样变化。
- `RANGE`：只有 lower/upper 工程边界，没有 PDF；用于 bound sweep，不自动成为 uniform。
- `NORMAL`：调用者必须明确给出 mean 和 standard deviation；可选 bounds 作为样本拒绝边界，不执行 clamp。
- `UNIFORM`：只有在 lower/upper 和均匀 PDF 都被明确声明时采样。
- `UNKNOWN`：没有可辩护的分布；保持 nominal、禁止采样并产生 warning。

参数 schema 是通用的，可表示 AFPM、电阻/温度，以及未来 inertia、viscous damping、load torque 等量；本阶段只完整演示 back-EMF。

## 4. Deterministic sweep 与 bound envelope

One-at-a-time sweep 在其他参数保持 nominal 时分别计算 lower/upper，报告输出绝对范围和 normalized sensitivity：

`S = (Delta output / nominal output) / (Delta input / nominal input)`

若输入或输出接近零，normalized sensitivity 返回 unavailable，而不是产生不稳定除法。

Bound sweep 支持：

- `ONE_AT_A_TIME`
- `FULL_CORNERS`：小参数集合的 lower/nominal/upper 全组合
- `CAPPED_COMBINATIONS`：带 seed 的确定性上限组合

输出称为 `parameter-bound envelope`，不是 confidence interval。

## 5. Monte Carlo

Monte Carlo 只采样 `NORMAL` 与 `UNIFORM`。`EXACT`、`RANGE` 和 `UNKNOWN` 保持 nominal，其中 RANGE/UNKNOWN 产生显式 warning。调用者必须提供 seed 与 sample count。

本框架报告 valid/rejected count、拒绝原因、mean、median、standard deviation、min/max 和 P05/P10/P50/P90/P95。无效样本不会 clamp，例如负气隙、内半径不小于外半径、`kw > 1`、负厚度或负电阻会被拒绝。

相关性估计采用 normalized Pearson `r^2` association，仅作为 sampled parameters 与输出的线性关联提示，明确不是 Sobol index 或正式全局 variance decomposition。

## 6. Phase 7H 演示

输入机器为冻结的 `CONTROLLED_FEA_REFERENCE` coreless SSDR。所有 uncertainty magnitude 都标记为 `PROJECT-DEMONSTRATION ASSUMPTIONS`。

- nominal phase fundamental RMS back-EMF：`33.329273 V`
- parameter-bound envelope：`28.466740-38.757257 V`
- seed `20260701`，5000 requested samples，4981 valid，19 rejected
- P10/P50/P90：`32.150113 / 33.340058 / 34.534283 V`
- OAT top contributors：Br、winding factor、magnet arc ratio、magnet thickness、outer radius
- 100-to-500 slice numerical difference：约 `2.1e-14%`，可视为浮点噪声
- model-form uncertainty：`UNQUANTIFIED`
- external validation：`LIMITED`
- confidence：`LOW`

LOW 不是由区间宽度单独决定，而是因为 AFPM 外部电磁 evidence limited、存在 UNKNOWN 参数且 model-form error 未量化。当前结果不得自动获得 HIGH。

## 7. Phase 6A 与 Phase 7I

Phase 6A 回答局部工程问题：“某 production input 临时变化 +/-1% 或 +/-5% 时，现有输出怎么变？”

Phase 7I 增加：

- 可审计 uncertainty semantics 和 provenance。
- range-only 与 statistical propagation 分离。
- deterministic seed Monte Carlo 与 percentile。
- invalid physical sample rejection。
- confidence/readiness、external coverage 和 model-form warnings。
- 可供未来 GUI 使用的 `AccuracyEnvelopeResult`。

两者均为只读 sandbox，不校准、不写回 production。

## 8. 当前可以和不可以声称什么

可以声称：在本项目明确声明的演示参数范围/PDF 下，现有 radial-slice 模型输出呈现上述移动范围和样本百分位。

不能声称：这是真实机器误差范围、制造公差、95% accuracy、实验验证或独立 FEA 验证。Monte Carlo 只传播进入它的假设，不会自动使模型变得更真实。

框架在 API 层可供未来 GUI 只读集成；Phase 7I 未修改 GUI。Phase 7J 若实现 optional user validation feedback，应把用户测量 provenance、参数 uncertainty 和 model discrepancy 分开保存，禁止自动 calibration。
