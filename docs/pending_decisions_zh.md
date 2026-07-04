# 待决策事项

本文档记录 Phase 4A 完成后，仍需用户明确批准或提供外部信息的事项。

更新时间：2026-07-04

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 revised `Ke` / `Kt` 定义
- Phase 3D 已完成：独立 PMSM analytical reference validation
- Phase 3E 已完成并通过验收：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference validation
- Phase 4A 已完成：外部验证数据框架、provenance 跟踪、comparability 与误差/不确定度结构

## 2. Phase 4A 已确认结论

- 外部验证记录现在必须显式记录：
  - `source_type`
  - `evidence_level`
  - 来源标题、作者/机构、标识符、文件、页码/章节
  - 缺失状态
  - 不确定度
  - tolerances
  - excluded comparisons
- analytical reference 不能被标记为实验验证
- 厂家宣传参数不能被标记为台架实测
- synthetic example 只能用于测试导入器和比较引擎
- 只有 `directly_comparable` 的字段才能计算模型误差
- unit conversion 可以显式执行，但必须记录转换过程
- Phase 4A 不会把任何外部数据接入默认计算链

## 3. 当前仍待用户确认的关键问题

### 3.1 是否开始导入真实公开 benchmark

待确认内容：

- 是否先导入公开论文 benchmark
- 选择哪类电机、哪类工况作为第一批 published benchmark
- 是否需要把 DOI、图表页码和授权说明作为强制字段

### 3.2 是否开始导入真实 FEA 数据

待确认内容：

- 是否先导入已有 FEA 报告或导出结果
- FEA 记录是否强制包含：
  - 网格说明
  - 边界条件
  - 材料参数
  - 求解器设置
  - 几何与绕组假设

### 3.3 是否开始导入真实台架测量数据

待确认内容：

- 是否已有可用 bench measurement 数据
- 是否要求强制记录：
  - 传感器型号
  - 校准信息
  - 采样方式
  - 环境条件
  - 不确定度估计

### 3.4 PMSM revised `Ke` / `Kt` 的默认值策略

待确认内容：

- 是否长期接受 revised PMSM `Ke` / `Kt` 只作为并行输出、测试和报告值
- 是否未来允许 revised PMSM `Ke` / `Kt` 替代 legacy 默认值
- 若未来切换默认值，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路

### 3.5 BLDC revised `Ke` / `Kt` 的默认值策略

待确认内容：

- 是否长期接受 revised BLDC `Ke` / `Kt` 只作为并行输出、测试和报告值
- 是否未来允许 revised BLDC `Ke` / `Kt` 替代 legacy 默认值
- 若未来切换默认值，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路
  - 转矩波形

### 3.6 是否单独进入 `required_voltage_v` 修正阶段

待确认内容：

- 是否启动独立阶段处理 `required_voltage_v` 的：
  - 量纲语义
  - 相/线值定义
  - 调制方式
  - 控制策略边界

## 4. 当前已完成但不代表已解决的事项

- 已有 external validation framework
- 已有 comparability gate
- 已有 uncertainty / tolerance 结构
- 已有模板与 synthetic import example

这些并不代表：

- 已有真实 external validation 数据
- 已有实验一致性结论
- 已有公开 benchmark 一致性结论
- 已有 FEA 一致性结论

## 5. 当前不应做的事

- 不要在未审批时导入虚构来源
- 不要把 synthetic example 当成真实外部证据
- 不要在未审批时切换任何默认链路
- 不要在未审批时修改任何电磁公式
- 不要把 revised 结果自动传播到下游
- 不要根据单个 benchmark 自动校准公式
- 不要根据比较结果自动回写经验系数
- 不要修改 `legacy_baseline.json`
- 不要把 analytical validation 或 schema 支持夸大为真实准确度证明
