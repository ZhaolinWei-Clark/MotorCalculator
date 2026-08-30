# Phase 8H 输出盘点

## 1. 盘点原则

本盘点只登记项目已经产生、可追溯或明确不可用的结果。仪表板不得根据相邻点插值出“商业化”能力曲线，不得把未运行的动态、不确定性或敏感性分析显示为零，也不得从已有总损耗反推不存在的损耗分量。机器可读清单位于 `motor_calculator/plots/inventory.py`。

## 2. 静态结果与工程状态

| 指标 | 单位 | 来源 | 展示 | 证据边界 |
|---|---|---|---|---|
| 额定转矩 | Nm | `AnalysisResult.performance.rated_torque_nm` | KPI、扫描 | 当前 production/legacy 路径输出 |
| 输出/输入功率 | W | `AnalysisResult.performance` | KPI、扫描、表格 | 当前输入工作点与现有损耗模型 |
| 当前模型估算效率 | % | `AnalysisResult.performance.efficiency_percent` | KPI、扫描 | 受 legacy 损耗模型限制，不是完整效率地图 |
| 机械转速 | rpm | 输入支持的工作点 | KPI、扫描 | 输入支持 |
| 相电流 RMS | A | `AnalysisResult.performance.phase_current_rms_a` | KPI | 波形/电流基准按现有语义 |
| 所需线电压 RMS | V | `AnalysisResult.performance.required_voltage_v` | KPI、扫描 | legacy 静态电压模型 |
| 同基电压裕量 | % | Phase 8G feasibility | KPI、范围条、扫描 | 仅正弦 PMSM；SVPWM-compatible 近似 |
| 电流密度 | A/mm² | Phase 8G feasibility | KPI、范围条 | 相 RMS、电流均流、裸铜直径假设 |
| 近似裸铜槽占比 | 比值 | Phase 8G feasibility | KPI、范围条 | 需要槽几何；不是制造认证槽满率 |
| Ke / Kt | V/krpm、Nm/A | `AnalysisResult.electrical` | KPI | 使用现有显式电压/电流语义，不替换生产默认 |
| 线反电动势 RMS | V | `AnalysisResult.electrical` | 表格/后续图 | 当前控制模式语义 |

## 3. 损耗与热

| 指标 | 来源 | 当前行为 |
|---|---|---|
| 铜耗 | `performance.copper_loss_w` | 原值展示 |
| legacy 涡流损耗 | `performance.eddy_loss_w` | 原值展示并标记模型受限 |
| legacy 机械损耗 | `performance.mechanical_loss_w` | 原值展示并标记模型受限 |
| legacy 铁芯损耗 | `performance.core_loss_w` | 原值展示并标记模型受限 |
| 静态温升 | 未实现 | `UNAVAILABLE`：当前静态模式无可信温升预测 |
| 动态绕组温度 | `ThermalSimulationResult` | 只有显式运行动态热仿真后才可用 |

## 4. 可选分析结果

| 分析 | 数据类型 | 未运行时状态 |
|---|---|---|
| 动态速度、转矩、id/iq | `SimulationResult` | `NOT_RUN`，尚未运行动态仿真 |
| 不确定性包络与 P10/P50/P90 | `AccuracyEnvelopeResult` | `NOT_RUN`，尚未执行不确定性分析 |
| 单参数敏感性 | Phase 6A `SensitivityRunResult` | `NOT_RUN`，尚未运行敏感性分析 |
| 工程置信度 | Phase 7K confidence summary | 分类证据，不解释为概率或综合得分 |

动态、不确定性和敏感性适配器只读取已经存在的结构化结果。绘图降采样只改变显示点，不改变或覆盖原始序列。

## 5. 模式限制

- PMSM 电压扫描比较所需 line-RMS 与 Phase 8G 同基可用 line-RMS。
- BLDC 缺少安全的正弦同基电压语义，电压裕量曲线明确显示不可用；转矩和功率仍可按当前静态模型逐点计算。
- 无槽/无铁芯输入缺少槽几何时，近似裸铜槽占比显示信息不足，不使用 generic `N/A`。
- 每个无效扫描点保留 `INVALID`、原因和空数据，绘图使用断点，不跨越无效点连线。

## 6. 精度策略

显示层按工程量采用固定且可读的小数位：转矩 3 位、功率 1 位、效率/裕量 2 位、转速 0 位、Ke/Kt 4 位。CSV 保留 Python 计算结果的可复现文本值，不使用卡片显示精度截断底层数据。
