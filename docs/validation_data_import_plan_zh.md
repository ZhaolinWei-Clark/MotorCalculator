# validation_data 导入优先级计划

更新时间：2026-07-04

## 1. 说明

本计划只排序候选来源，不触发真实导入。

排序原则：

- 与当前 AFPM PMSM/BLDC 项目目标的相关性
- 几何 / 材料 / 绕组 / 工况字段完整度
- 是否具备可追溯来源与清晰授权
- 是否能直接落到 Phase 4A schema
- 是否容易被误判为“看起来像 benchmark，但其实不是”

## 2. Priority 1

### CREATOR Case: Permanent Magnet Synchronous Motor Data

- 为什么是这个优先级：
  - 这是目前最完整、最可追溯、最像“真实外部 validation record”的公开候选
  - 同时具备设计数据和实验结果
  - 已确认有 DOI、数据包和 license 页面
- 可以验证哪些指标：
  - torque
  - 输入/输出功率
  - efficiency
  - 若数据包中含 no-load / EMF 结果，还可能覆盖 back EMF 相关字段
- 不能验证哪些指标：
  - 是否适用于 AFPM 本体，需要先确认其拓扑
  - 本轮尚未确认 temperature / Ke / Kt 是否直接给出
- 需要用户提供什么：
  - 当前不强制需要用户补源，但 Phase 4C 需要允许人工抽取 ZIP/PDF
- 下一步行动建议：
  - Phase 4C 首选
  - 先做一条 `published_benchmark + bench_measurement` 风格的 PMSM record

## 3. Priority 2

### CREATOR Case: Induction Motor Data

- 为什么是这个优先级：
  - 数据质量很强，但机型不是本项目主目标
  - 更适合做 schema / comparability gate 的外部压测
- 可以验证哪些指标：
  - torque
  - efficiency
  - equivalent-circuit related outputs
- 不能验证哪些指标：
  - PMSM / BLDC / AFPM 特有 Ke/Kt 语义
- 需要用户提供什么：
  - Phase 4C 若真导入，需要允许我们手工抽取 IM 数据页
- 下一步行动建议：
  - 保留为第二批或 schema 扩展测试

### Parviainen 2005 AFPM dissertation / worked examples

- 为什么是这个优先级：
  - 与 AFPM 目标机型高度相关
  - 很可能包含可直接对照的设计示例
  - 但本轮未确认到稳定全文来源
- 可以验证哪些指标：
  - 预计可覆盖 geometry / winding / torque / efficiency 一类设计级指标
- 不能验证哪些指标：
  - 在未看全文前，无法确认是否有 back EMF / loss breakdown / temperature
  - 不一定具备 controlled measurement
- 需要用户提供什么：
  - 最好提供 PDF、DOI、图书馆链接或论文全文
- 下一步行动建议：
  - 若用户能补源，可与 CREATOR PMSM 并列成为 AFPM 方向首批文献抽取目标

### FEMM SPM loss tutorial

- 为什么是这个优先级：
  - 适合作为首条 FEA-only record 打通流程
  - 字段比一般教程更完整，材料与几何也较明确
- 可以验证哪些指标：
  - iron loss
  - 部分 copper / magnet loss
  - back EMF waveform qualitative features
- 不能验证哪些指标：
  - experimental accuracy
  - AFPM topology
  - strict Ke/Kt benchmark
- 需要用户提供什么：
  - 不需要补源，但需要用户接受“这是一条 FEA-only record，不是实验 record”
- 下一步行动建议：
  - 若 Priority 1 先不做实验数据，可把它作为 FEA 导入演练

## 4. Priority 3

### PYLEECAN open-source examples + FEMM coupling

- 为什么是这个优先级：
  - 很适合参考字段组织、代码结构和 FEA 工作流
  - 但它是工具集，不是单一 benchmark 包
- 可以验证哪些指标：
  - 取决于具体 example，可覆盖 torque、loss、back EMF
- 不能验证哪些指标：
  - real-world experimental accuracy
  - 单一固定 benchmark comparability
- 需要用户提供什么：
  - 若后续锁定具体 case，可能需要指定一个 example
- 下一步行动建议：
  - 先只保留为方法参考，不立即导入

### FEMM outrunner BLDC optimization example

- 为什么是这个优先级：
  - 适合参考 BLDC FEA 优化流程
  - 不适合当真实 external validation data
- 可以验证哪些指标：
  - torque-oriented FEA reasoning
- 不能验证哪些指标：
  - Ke / Kt benchmark
  - efficiency / loss / temperature chain
- 需要用户提供什么：
  - 无强制
- 下一步行动建议：
  - 仅作 BLDC FEA 参考

### TUMFTM Electric_Machine_Design

- 为什么是这个优先级：
  - 有设计逻辑、有效率图输出、有公开仓库
  - 但它更像工具输出，不像原始 benchmark 数据
- 可以验证哪些指标：
  - nominal design trends
  - efficiency map style outputs
- 不能验证哪些指标：
  - 原始实验 expected
  - AFPM-specific benchmark
- 需要用户提供什么：
  - 若后续要深入使用，需先确认仓库 license 和输出字段
- 下一步行动建议：
  - 保留为设计方法和字段参考

## 5. Priority 4

### Paderborn / Kaggle electrical-behavior dataset

- 为什么是这个优先级：
  - 数据量大、控制研究价值高
  - 但不是几何电磁 benchmark
- 可以验证哪些指标：
  - control-oriented dynamic behavior
  - system identification / inverter-machine electrical interaction
- 不能验证哪些指标：
  - 几何电磁模型
  - back EMF / Ke / Kt benchmark
  - material / winding assumptions
- 需要用户提供什么：
  - 若未来要用，需确认实际 dataset 页面和字段清单
- 下一步行动建议：
  - 当前不导入

### Paderborn / Kaggle temperature benchmark dataset

- 为什么是这个优先级：
  - 对未来 thermal model 可能有用
  - 但目前 thermal 链仍是 legacy/provisional，且几何字段缺失
- 可以验证哪些指标：
  - 温度估计
  - 热状态趋势
- 不能验证哪些指标：
  - electromagnetics
  - full thermal FE consistency
- 需要用户提供什么：
  - 实际 dataset 页面或论文全文
- 下一步行动建议：
  - 等 thermal validation phase 明确后再跟进

### EMRAX public product pages

- 为什么是这个优先级：
  - AFPM 相关性高
  - 但只是厂家规格页
- 可以验证哪些指标：
  - 只能做 very weak reference，例如数量级 sanity check
- 不能验证哪些指标：
  - controlled measurement
  - back EMF / Ke / Kt
  - loss breakdown
- 需要用户提供什么：
  - 即便补源，也不建议升格为强 validation
- 下一步行动建议：
  - 不导入，只做背景参考

### FEniCSx PMSM model paper (exact source unresolved)

- 为什么是这个优先级：
  - 方向有潜力
  - 但本轮没有确认到精确来源，不能猜字段
- 可以验证哪些指标：
  - 暂无法判断
- 不能验证哪些指标：
  - 暂无法判断
- 需要用户提供什么：
  - 论文 DOI、标题、PDF 或仓库链接
- 下一步行动建议：
  - 只有在用户补源后才重新排序

## 6. 当前推荐路线

推荐路线 A：直接进入 Phase 4C

1. 先导入 `CREATOR PMSM Data`
2. 若用户希望同时建立 FEA-only 样例，再导入 `FEMM SPM loss tutorial`

推荐路线 B：先补 AFPM 更贴近的文献源

1. 用户提供 `Parviainen 2005` 全文
2. 再和 `CREATOR PMSM Data` 做双轨导入比较

推荐路线 C：先不导入，只继续补源

1. 用户补充 AFPM 论文或教材
2. 明确是否先修 GUI runtime dependency

## 7. 当前不建议做的事

- 不要先导入厂家规格页
- 不要先导入控制数据集并把它宣称为电磁 benchmark
- 不要把工具输出直接当 external expected
- 不要在 Phase 4B 把任何来源写入 `validation_data/imported/`
