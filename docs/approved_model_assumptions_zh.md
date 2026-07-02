# 已批准的模型假设

本文档用于记录当前已经明确批准、后续不得在未获批准前擅自更改的模型假设。

更新时间：2026-07-02

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

## 6. Phase 3A 已批准的电气语义

- `pole_pairs` 表示极对数
- `pole_count = 2 * pole_pairs` 表示总极数
- 公共速度字段使用：
  - `mechanical_speed_rpm`
  - `mechanical_angular_speed_rad_s`
  - `electrical_frequency_hz`
  - `electrical_angular_speed_rad_s`
- 公共字段中不再继续传播含糊的 `p`、`poles`、`omega`、`f`
- PMSM 与 BLDC 的电气语义已隔离
- BLDC 120°导通下的严格 RMS、peak、`Ke`、`Kt` 关系尚未建立，只能保留 provisional 或 legacy 标记

## 7. 单位语义

- 内部计算统一使用 SI 单位
- `mm -> m`、`rpm -> rad/s` 等转换必须集中处理
- GUI、报告和计算层不得重复做不一致的单位换算

## 8. legacy 公式策略

- 当前所有电磁经验公式暂时保留
- 不得擅自替换经验公式
- 只允许明确标记其来源状态、适用限制和风险

## 9. 结果稳定性约束

- 原则上不得改变现有正常输入下的计算结果
- 任何会改变结果的修改，必须先单独列出并等待批准
- 所有会改变结果的公式修改，都必须保留 legacy 与 revised 并行输出

## 10. baseline 规则

- `legacy_baseline.json` 是重构前行为基线
- 它只用于回归比较
- 不能把它当作物理正确值
- 不得为了通过测试而擅自修改基准数据

## 11. 当前不允许擅自修改的公式类别

以下内容在未获批准前不得主动修改：

- `Kt` 与 `Ke` 关系式
- `9.55 * P / n` 的下游默认使用方式
- 所需电压模型
- `K_fill` 定义
- 铁损、机械损耗、涡流损耗经验公式
- 双转子 / 双气隙相关系数

## 12. Phase 3B 已批准范围

Phase 3B 只允许处理额定转矩公式对比：

- legacy：`legacy_rated_torque_nm = 9.55 * rated_power_w / mechanical_speed_rpm`
- revised：`revised_rated_torque_nm = rated_power_w / mechanical_angular_speed_rad_s`

并且明确批准以下边界：

- revised 结果只能用于比较、报告和测试
- 当前下游继续使用 `legacy_rated_torque_nm`
- revised 结果不得传播到：
  - 额定电流
  - 铜损
  - 铁损
  - 机械损耗
  - 效率
  - `required_voltage_v`
  - 转矩波形

## 13. 计算层与 GUI 分层规则

- GUI 不得直接实现电磁公式
- `motor_core/calculations.py` 只负责纯计算
- `motor_core/validation.py` 负责输入合法性与物理合理性检查
- `motor_core/units.py` 负责单位转换
- `motor_core/constants.py` 负责常量和 legacy magic numbers 的集中存放

## 14. 修改公式前必须获得批准

修改公式前至少需要向用户提交：

- 当前公式
- 所在代码位置
- 拟修改公式
- 修改理由
- 预计影响的输出项
- 是否会打破 legacy baseline

## 15. Phase 3C 预留边界

Phase 3C 才允许进入以下内容：

- PMSM `Ke` / `Kt` 语义修正
- 更严格的相量 / 线量、RMS / peak 关系落地
- 评估 revised 默认值向下游传播的影响
