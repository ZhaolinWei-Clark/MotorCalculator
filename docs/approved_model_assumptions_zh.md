# 已批准的模型假设

本文档用于记录当前已经明确批准、后续不得在未获批准前擅自更改的模型假设。

更新时间：2026-07-04

## 1. 项目目标定义

- 当前项目是三相轴向磁通永磁无刷电机计算程序的重构工程。
- 当前目标是冻结模型定义、拆分计算内核、建立回归基线、输入校验与清晰的电气语义。
- 当前目标不是全面提升电磁物理精度。

## 2. 电机对象定义

- 电机类型：AFPM PMSM/BLDC
- 不是有刷 PMDC

## 3. 拓扑假设

- 默认拓扑是双转子、单定子、双气隙结构。
- 当前磁路和电气计算中，凡 legacy 实现隐含双侧结构者，继续保留该假设。

## 4. 绕组连接方式

- 默认连接方式为 Y 接。
- 线电压、线电阻和线电流定义均以 Y 接为准。

## 5. 运行模式定义

- `PMSM`：
  - 正弦反电势
  - 正弦电流
- `BLDC`：
  - 梯形反电势
  - 120°导通

## 6. 公共电气语义

- `pole_pairs` 表示极对数
- `pole_count = 2 * pole_pairs` 表示总极数
- 公共速度字段使用：
  - `mechanical_speed_rpm`
  - `mechanical_angular_speed_rad_s`
  - `electrical_frequency_hz`
  - `electrical_angular_speed_rad_s`
- 公共字段中不再继续传播含糊的 `p`、`poles`、`omega`、`f`
- 内部计算统一使用 SI 单位
- `mm -> m`、`rpm -> rad/s` 等转换必须集中处理

## 7. legacy 公式策略

- 当前所有电磁经验公式暂时保留
- 不得擅自替换经验公式
- 只允许明确标记其来源状态、适用限制和风险

## 8. 结果稳定性约束

- 原则上不得改变现有正常输入下的计算结果
- 任何会改变结果的修改，必须先单独列出并等待批准
- 所有会改变结果的公式修改，都必须保留 legacy 与 revised 并行输出

## 9. baseline 规则

- `legacy_baseline.json` 是重构前行为基线
- 它只用于回归比较
- 不能把它当作物理正确值
- 不得为了通过测试而擅自修改基准数据

## 10. 当前不允许擅自修改的公式类别

以下内容在未获批准前不得主动修改：

- `Kt` 与 `Ke` 关系式
- `9.55 * P / n` 的下游默认使用方式
- 所需电压模型
- `K_fill` 定义
- 铁损、机械损耗、涡流损耗经验公式
- 双转子 / 双气隙相关系数

## 11. Phase 3A 到 Phase 3E 固化结论

- revised 额定转矩只允许并行比较，不得传播到额定电流、损耗、效率或 `required_voltage_v`
- revised PMSM `Ke` / `Kt` 只允许并行输出，不得传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路
- revised BLDC `Ke` / `Kt` 只允许并行输出，不得传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路
- revised PMSM `Ke` / `Kt` 已通过独立 analytical validation
- revised BLDC `Ke` / `Kt` 已通过分段解析、独立数值积分、独立 analytical reference、production/reference 交叉验证与 downstream isolation
- 现有 3 组 `legacy_baseline` 全部为 BLDC 路径
- revised BLDC line RMS `Ke` 与 legacy 相差约 `2.4695%`
- legacy BLDC `Kt` 语义仍不完整，不应强制计算误差

## 12. 当前默认值策略

- revised PMSM `Ke` / `Kt` 不是默认值
- revised BLDC `Ke` / `Kt` 不是默认值
- revised 额定转矩不是默认值
- 所有 revised 结果当前只用于：
  - 比较
  - 报告
  - 测试
  - 实验性输出

## 13. 当前保持不变的下游链路

以下内容当前明确保持 legacy 链路不变：

- `required_voltage_v`
- 额定电流默认链路
- 铜损与其他损耗链路
- 效率链路
- GUI 默认链路

## 14. Phase 4A 已批准边界

Phase 4A 只允许建立外部验证数据框架和数据来源追踪。

明确边界：

- 不切换任何默认链路
- 不修改任何计算公式
- 不修改 `required_voltage_v`
- 不修改额定电流默认链路
- 不修改损耗、效率、电感、槽满率、退磁或温升公式
- 不修改 `legacy_baseline.json`

## 15. 计算层与 GUI 分层规则

- GUI 不得直接实现电磁公式
- `motor_core/calculations.py` 只负责纯计算
- `motor_core/validation.py` 负责输入合法性与物理合理性检查
- `motor_core/units.py` 负责单位转换
- `motor_core/constants.py` 负责常量和 legacy magic numbers 的集中存放

## 16. 当前已验证与未验证边界

当前已验证：

- PMSM revised `Ke` / `Kt` 的 analytical validation
- BLDC revised `Ke` / `Kt` 的分段解析、独立数值积分、独立 analytical reference、production/reference 交叉验证与 downstream isolation
- revised 字段未传播到下游默认链路

当前仍未验证：

- FEA 一致性
- 实验台架一致性
- 公开论文 benchmark 一致性
- 完整样机验证

## 17. 修改公式前必须获得批准

修改公式前至少需要向用户提交：

- 当前公式
- 所在代码位置
- 拟修改公式
- 修改理由
- 预计影响的输出项
- 是否会打破 legacy baseline
