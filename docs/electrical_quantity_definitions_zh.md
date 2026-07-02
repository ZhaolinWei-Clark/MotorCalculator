# 电气量定义说明

更新时间：2026-07-02

本文档用于统一 Phase 3A 中所有关键电气量、速度量、极数语义和控制模式边界。目标不是修改 legacy 电磁公式，而是把“名称、单位、数学关系、适用边界”讲清楚，并且让测试、数据模型、报告和 GUI 使用一致语义。

## 1. 极对数和总极数

- `pole_pairs`：极对数。
- `pole_count`：总极数。
- 统一关系：
  - `pole_count = 2 * pole_pairs`

说明：
- 后续不得再把 `p` 或 `poles` 作为公共字段名继续传播。
- legacy GUI 输入仍可能使用 `p`，但进入核心数据模型后统一转为 `pole_pairs`。

## 2. 机械转速与机械角速度

- `mechanical_speed_rpm`：机械转速，单位 `rpm`
- `mechanical_angular_speed_rad_s`：机械角速度，单位 `rad/s`

精确数学关系：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60
```

这是纯单位换算，与波形、控制模式和绕组连接无关。

## 3. 电频率与电角速度

- `electrical_frequency_hz`：电频率，单位 `Hz`
- `electrical_angular_speed_rad_s`：电角速度，单位 `rad/s`

精确数学关系：

```text
electrical_frequency_hz
= mechanical_speed_rpm * pole_pairs / 60

electrical_angular_speed_rad_s
= mechanical_angular_speed_rad_s * pole_pairs
```

说明：
- 电频率取决于机械转速和极对数。
- 这部分关系是严格数学定义，不依赖 PMSM 或 BLDC。

## 4. rpm、Hz 和 rad/s 的关系

三者换算建议统一按下列顺序理解：

1. 先从 `rpm` 转为机械角速度 `rad/s`
2. 再结合 `pole_pairs` 得到电频率 `Hz`
3. 最后把电频率或机械角速度换成电角速度 `rad/s`

这样可以避免机械量和电气量混用。

## 5. 相电压与线电压

本文档中的相/线定义默认基于三相系统：

- `phase_voltage_rms_v`
- `phase_voltage_peak_v`
- `line_voltage_rms_v`
- `line_voltage_peak_v`
- `back_emf_phase_rms_v`
- `back_emf_phase_peak_v`
- `back_emf_line_rms_v`
- `back_emf_line_peak_v`

其中：
- `phase_*` 表示相量
- `line_*` 表示线量
- `rms` 表示有效值
- `peak` 表示峰值

## 6. Y 接电压、电流关系

当前项目默认绕组连接方式仍为 Y 接。

Y 接下当前明确采用：

```text
line_current_rms_a = phase_current_rms_a
```

说明：
- 这是当前数据模型的明确语义。
- 对峰值电流、母线电流、120°导通等情形，仍需结合波形和控制策略分别解释，不能简单类推。

## 7. RMS、峰值和平均值

- `rms`：均方根值，适合热效应、铜损等场景
- `peak`：峰值，适合瞬时波形和绝缘/器件应力场景
- `average`：平均值，只在特定波形或整流定义下有意义

Phase 3A 的基本原则：
- 不能把 `rms` 和 `peak` 混为同一个字段
- 不能把相量和线量混为同一个字段
- 不能把直流母线量和交流相量混为同一个字段

## 8. 正弦波与梯形波

PMSM 正弦模式和 BLDC 120°导通模式在波形语义上必须分开：

- PMSM 正弦模式：
  - 正弦反电势
  - 正弦相电流
  - 允许使用标准正弦 RMS/峰值换算

- BLDC 120°导通模式：
  - 梯形反电势
  - 120°导通
  - 许多 RMS/峰值、Ke/Kt 关系依赖实际波形定义和控制策略
  - 本阶段不允许直接套用 PMSM 正弦关系

## 9. Ke 的不同定义

Phase 3A 明确区分以下字段：

- `back_emf_constant_phase_peak_v_per_rad_s`
- `back_emf_constant_phase_rms_v_per_rad_s`
- `back_emf_constant_line_rms_v_per_rad_s`
- `back_emf_constant_line_rms_v_per_krpm`

说明：
- `V/krpm` 和 `V/(rad/s)` 是不同单位，不能当成同一个数值直接比较。
- `line RMS` 的 Ke 与 `phase peak` 的 Ke 不是同一语义。
- 当前 legacy 输出中的 `Ke` 仍保留，但它只对应 legacy 语义：
  - `legacy_back_emf_constant_line_rms_v_per_krpm`

## 10. Kt 的不同定义

Phase 3A 明确区分以下字段：

- `torque_constant_nm_per_phase_peak_a`
- `torque_constant_nm_per_phase_rms_a`

说明：
- 不能笼统写 `Kt = Ke`
- 不能把 `Nm/A_phase_peak` 与 `V_line_rms/(rad/s)` 直接比较
- 当前 legacy 输出中的 `Kt` 仍保留，但它只对应 legacy 语义：
  - `legacy_torque_constant_nm_per_phase_rms_a`

## 11. PMSM 正弦模式

控制模式枚举：

- `MotorControlMode.PMSM_SINUSOIDAL`

在此模式下，允许使用以下精确数学换算：

```text
phase_voltage_peak_v = sqrt(2) * phase_voltage_rms_v
line_voltage_rms_v = sqrt(3) * phase_voltage_rms_v
line_voltage_peak_v = sqrt(2) * line_voltage_rms_v
phase_current_peak_a = sqrt(2) * phase_current_rms_a
```

这些关系在 Phase 3A 中被视为“正弦模式下的精确换算”。

## 12. BLDC 120°导通模式

控制模式枚举：

- `MotorControlMode.BLDC_120_DEGREE`

在此模式下：
- 不自动使用正弦 RMS/峰值换算函数
- 不把 PMSM 的 Ke/Kt 关系直接套过来
- 暂不实现“修正版 BLDC 模型”
- 仅保留 legacy 数值路径，并在新字段或状态字段上标记为 `provisional`

当前 legacy BLDC 标记：

- `legacy_bldc_model`

## 13. 哪些关系是精确数学转换

以下关系在当前项目中可视为精确换算：

- `pole_count = 2 * pole_pairs`
- `mechanical_speed_rpm -> mechanical_angular_speed_rad_s`
- `mechanical_speed_rpm + pole_pairs -> electrical_frequency_hz`
- `mechanical_angular_speed_rad_s + pole_pairs -> electrical_angular_speed_rad_s`
- Y 接下 `line_current_rms_a = phase_current_rms_a`
- PMSM 正弦模式下的标准 RMS/峰值、相/线换算
- `V/krpm` 与 `V/(rad/s)` 的纯单位换算

## 14. 哪些关系依赖波形和控制策略

以下内容不能只靠简单数学换算确定：

- BLDC 梯形波的 RMS/峰值关系
- BLDC 120°导通时的电流定义
- `Ke` 与 `Kt` 在不同波形和不同电流定义下的对应关系
- 所需电压与逆变器调制度、相位角、控制策略的关系
- 母线电流与相电流/线电流的严格映射

这些内容在 Phase 3A 中只能明确边界，不能擅自“修正”为新公式。

## 15. 当前 legacy 模型仍存在的限制

当前仍保留的 legacy 限制包括：

- `9.55 * P / n` 转矩表达仍保留
- `Ke/Kt` 原始公式未修改
- 所需电压模型未修改
- 铁损、机械损耗、涡流损耗、电感、槽满率、退磁、温升相关经验模型未修改
- 对未知 legacy 波形标签，兼容层仍沿用原有“落到非正弦分支”的行为

因此：
- 通过 regression baseline 只能证明“重构未改旧数值”
- 不能据此宣称“物理精度已提升”

## 16. 下一阶段需要验证的公式

进入 Phase 3B 之前，建议优先验证：

1. `Ke` 的相量/线量、RMS/峰值定义
2. `Kt` 的相电流峰值/有效值定义
3. PMSM 与 BLDC 的 `Ke/Kt` 关系是否应继续共用 legacy 路径
4. BLDC 120°导通下相电流、线电流、母线电流的严格定义
5. `required_voltage_v` 当前到底对应哪一种电压量
6. 旧 `back_emf_line_rms_v` 在 BLDC 情况下是否应保留为 legacy-only 字段

## 17. Phase 3A 结论

Phase 3A 的目标不是换公式，而是：

- 统一命名
- 统一单位
- 集中换算函数
- 划清 PMSM 和 BLDC 边界
- 保持 legacy baseline 数值不变

在这一阶段，任何会改变 legacy baseline 数值的修改都不应被视为“纯语义重构”。
