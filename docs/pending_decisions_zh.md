# 待决策事项

本文档记录在 Phase 4C 完成首条真实 CREATOR PMSM record 导入之后，仍需用户明确批准或补充的信息。

更新时间：2026-07-04

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 revised `Ke` / `Kt`
- Phase 3D 已完成：独立 PMSM analytical reference validation
- Phase 3E 已完成并通过验收：BLDC revised `Ke` / `Kt`
- Phase 4A 已完成：外部验证框架、provenance、comparability、误差/不确定度结构
- Phase 4B 已完成：外部数据源侦察、候选 benchmark 清单、字段匹配矩阵与导入优先级排序
- Phase 4C 已完成首条真实 CREATOR PMSM imported record、loader 校验与 comparison engine 运行

## 2. Phase 4B / Phase 4C 已确认结论

- 当前最适合 Phase 4C 首个真实 validation record 的候选是 `CREATOR PMSM Data`
- 已创建正式 imported record：`validation_data/imported/creator_pmsm_initial_record.json`
- 已审阅 `PM_synchronous_motor.zip` 与 `CREATOR_Machine_Data_2024-11-04.pdf`
- 当前已确认：
  - 来源是 `PMSM`
  - 来源 record 代表径向 PMSM，而不是项目默认 `AFPM`
  - comparison engine 已按预期拦截直接数值比较，主因是 `topology_mismatch`
- 当前候选中有一批来源只适合：
  - 方法参考
  - FEA-only 参考
  - 厂家规格弱参考
  - 控制/热估计参考
- 当前候选中不应被误判为“几何电磁 benchmark”的来源包括：
  - Paderborn/Kaggle electrical-behavior dataset
  - Paderborn/Kaggle temperature dataset
  - 厂家产品规格页

## 3. 当前仍待用户确认的关键问题

### 3.1 是否继续深挖同一 CREATOR PMSM 来源

待确认内容：

- 是否继续从同一 ZIP 中选定一个具体稳态点或 drive-cycle 点，导入损耗/效率类字段
- 是否接受后续仍然严格保持：
  - 不改公式
  - 不切默认值
  - 不把径向 PMSM record 外推为 AFPM 准确度声明

### 3.2 是否优先导入 FEA-only record 作为流程演练

待确认内容：

- 是否允许先用 `FEMM SPM loss tutorial` 打通 `fea_simulation` 记录导入流程
- 是否接受该记录只能证明：
  - FEA 字段映射
  - FEA provenance 记录
  - comparability / exclusion 处理

### 3.3 是否由用户补充 AFPM 方向全文来源

待确认内容：

- 是否由用户提供 `Parviainen 2005` 全文
- 是否提供 `Gieras, Wang, Kamper` 的 AFPM 书籍或相关章节
- 是否提供你已指定但本轮未精确定位的 `FEniCSx PMSM model paper`

### 3.4 是否优先修复 GUI runtime dependency

待确认内容：

- 下一步是优先做 `Phase 4C`
- 还是先做 `Phase 4C-alt: GUI runtime dependency repair`
- 还是先等待用户提供论文/教材全文

### 3.5 是否将 IM 数据保留为 schema 对照来源

待确认内容：

- 是否保留 `CREATOR IM Data` 作为第二批导入候选
- 是否允许其在未来用于：
  - schema robustness 检查
  - comparability gate 压测

## 4. 当前已完成但不代表已解决的事项

- 已有 external validation framework
- 已有 comparability gate
- 已有 uncertainty / tolerance 结构
- 已有数据源候选清单
- 已有字段匹配矩阵
- 已有导入优先级计划
- 已有教材候选清单

这些并不代表：

- 已有真实 external validation 数据
- 已有实验一致性结论
- 已有公开 benchmark 一致性结论
- 已有 FEA 一致性结论
- 已有 GUI runtime 修复

## 5. 当前不应做的事

- 不要把单条径向 PMSM imported record 夸大成项目整体准确度验证
- 不要把该 record 的存在误写成 BLDC 或 AFPM 默认拓扑已获验证
- 不要把工具输出、synthetic example 或 analytical reference 写成真实实验记录
- 不要把厂家规格页写成 controlled measurement
- 不要在未审批时切换任何默认链路
- 不要在未审批时修改任何电磁公式
- 不要根据单个 benchmark 自动校准公式或经验系数
- 不要修改 `legacy_baseline.json`
- 不要把控制数据集夸大成完整电磁 benchmark
