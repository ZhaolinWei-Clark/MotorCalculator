# 已批准的模型假设

本文档用于记录当前已经明确批准、后续不得在未获批准前擅自更改的模型假设。

更新时间：2026-07-03

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

## 11. Phase 3A 到 Phase 3D 固化结论

- revised 额定转矩只允许并行比较，不得传播到额定电流、损耗、效率或 `required_voltage_v`
- revised PMSM `Ke` / `Kt` 只允许并行输出，不得传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路
- revised PMSM `Ke` / `Kt` 已通过独立 analytical validation
- 现有 3 组 `legacy_baseline` 全部为 BLDC 路径，不是 PMSM revised `Ke` / `Kt` 的数值参考

## 12. Phase 3E 已批准且已完成的边界

Phase 3E 只允许建立 BLDC revised 语义、公式和独立 analytical reference cases，并已完成以下内容：

- 建立 ideal BLDC 三相、Y 接、梯形反电势、120°导通的 revised 波形语义
- 建立 `phase_flat_top`、`phase_peak`、`phase_rms`、`line_to_line_peak`、`line_to_line_rms` 的显式定义
- 建立 BLDC revised `Ke` 字段：
  - `revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s`
  - `revised_bldc_back_emf_constant_phase_peak_v_per_rad_s`
  - `revised_bldc_back_emf_constant_phase_rms_v_per_rad_s`
  - `revised_bldc_back_emf_constant_line_rms_v_per_rad_s`
  - `revised_bldc_back_emf_constant_line_rms_v_per_krpm`
- 建立 BLDC revised `Kt` 字段：
  - `revised_bldc_torque_constant_nm_per_conduction_a`
  - `revised_bldc_torque_constant_nm_per_phase_rms_a`
- 建立 4 个独立 BLDC analytical reference cases
- 建立 piecewise formula 与高分辨率 numeric integration 的交叉验证

## 13. Phase 3E 明确不允许且实际未修改的内容

- 不修改 PMSM revised 公式
- 不修改 PMSM reference cases
- 不修改 `required_voltage_v`
- 不修改额定电流默认链路
- 不修改损耗
- 不修改效率
- 不修改电感
- 不修改槽满率
- 不修改退磁或温升
- 不切换 revised 为默认
- 不修改 `legacy_baseline.json`
- 不重新设计 GUI
- 不打包 EXE

## 14. 当前 revised 默认值策略

- revised PMSM `Ke` / `Kt` 不是默认值
- revised BLDC `Ke` / `Kt` 不是默认值
- revised 额定转矩不是默认值
- 所有 revised 结果当前只用于：
  - 比较
  - 报告
  - 测试
  - 实验性输出

## 15. 计算层与 GUI 分层规则

- GUI 不得直接实现电磁公式
- `motor_core/calculations.py` 只负责纯计算
- `motor_core/validation.py` 负责输入合法性与物理合理性检查
- `motor_core/units.py` 负责单位转换
- `motor_core/constants.py` 负责常量和 legacy magic numbers 的集中存放

## 16. 当前已验证与未验证边界

当前已验证：

- PMSM revised `Ke` / `Kt` 的 analytical validation
- BLDC revised `Ke` / `Kt` 的 piecewise waveform + numeric integration + independent analytical reference validation
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
