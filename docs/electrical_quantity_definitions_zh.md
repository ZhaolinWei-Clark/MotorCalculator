# 电气量定义说明

更新时间：2026-07-03

本文档统一 Phase 3A 到 Phase 3C 中所有关键电气量、速度量、极数语义、控制模式边界以及 PMSM revised `Ke` / `Kt` 定义。目标不是静默替换 legacy 公式，而是把名称、单位、数学关系和适用边界讲清楚。

## 1. 极对数和总极数

- `pole_pairs`：极对数
- `pole_count`：总极数

统一关系：

```text
pole_count = 2 * pole_pairs
```

说明：

- 公共字段中不再继续传播含糊的 `p` 或 `poles`
- legacy GUI 输入仍可使用 `p`
- 进入核心数据模型后统一转成 `pole_pairs`

## 2. 机械转速与机械角速度

- `mechanical_speed_rpm`：机械转速，单位 `rpm`
- `mechanical_angular_speed_rad_s`：机械角速度，单位 `rad/s`

精确关系：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60
```

这是纯单位换算，不依赖 PMSM、BLDC 或控制策略。

## 3. 电频率与电角速度

- `electrical_frequency_hz`：电频率，单位 `Hz`
- `electrical_angular_speed_rad_s`：电角速度，单位 `rad/s`

精确关系：

```text
electrical_frequency_hz
= mechanical_speed_rpm * pole_pairs / 60

electrical_angular_speed_rad_s
= mechanical_angular_speed_rad_s * pole_pairs
```

## 4. rpm、Hz 和 rad/s 的关系

建议按下面的顺序理解：

1. `rpm -> mechanical_angular_speed_rad_s`
2. `mechanical_speed_rpm + pole_pairs -> electrical_frequency_hz`
3. `mechanical_angular_speed_rad_s + pole_pairs -> electrical_angular_speed_rad_s`

这样可以避免机械量和电气量混用。

## 5. 相电压与线电压

本文档统一使用以下字段：

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

当前项目默认绕组连接为 Y 接。

Phase 3A 到 Phase 3C 明确采用：

```text
line_current_rms_a = phase_current_rms_a
```

说明：

- 这是当前数据模型的明确语义
- 对峰值电流、母线电流、120°导通等情形，不能简单类推

## 7. RMS、峰值和平均值

- `rms`：均方根值，常用于热效应和铜损
- `peak`：峰值，常用于瞬时波形和器件应力
- `average`：平均值，只在特定波形定义下有意义

公共字段中不能把：

- `rms` 与 `peak` 混成同一个字段
- 相量与线量混成同一个字段
- 母线量与相量混成同一个字段

## 8. 正弦波与梯形波

PMSM 正弦模式和 BLDC 120°导通模式必须严格分开：

- PMSM 正弦模式：
  - 正弦反电势
  - 正弦相电流
  - 允许使用标准正弦 RMS/峰值换算
- BLDC 120°导通模式：
  - 梯形反电势
  - 120°导通
  - 许多 RMS/峰值、`Ke/Kt` 关系依赖实际波形和控制策略
  - 本阶段不允许直接套用 PMSM 正弦关系

## 9. PMSM 正弦模式下的精确转换

控制模式枚举：

- `MotorControlMode.PMSM_SINUSOIDAL`

在该模式下，允许使用以下精确转换：

```text
phase_voltage_peak_v = sqrt(2) * phase_voltage_rms_v
line_voltage_rms_v = sqrt(3) * phase_voltage_rms_v
line_voltage_peak_v = sqrt(2) * line_voltage_rms_v
phase_current_peak_a = sqrt(2) * phase_current_rms_a
```

这些换算已经集中到 `electrical_semantics.py`，不得散落在 GUI 或报告代码中。

## 10. BLDC 120°导通模式

控制模式枚举：

- `MotorControlMode.BLDC_120_DEGREE`

在该模式下：

- 不自动使用正弦 RMS/峰值换算函数
- 不把 PMSM 的 `Ke/Kt` 关系直接套过来
- 仅保留 legacy 数值路径
- 新字段或状态字段必须标记为 `legacy` 或 `provisional`

当前 legacy BLDC 标记：

- `legacy_bldc_model`

## 11. Ke 的不同定义

Phase 3C 明确区分：

- `legacy_back_emf_constant_line_rms_v_per_krpm`
- `revised_back_emf_constant_phase_peak_v_per_rad_s`
- `revised_back_emf_constant_phase_rms_v_per_rad_s`
- `revised_back_emf_constant_line_rms_v_per_rad_s`
- `revised_back_emf_constant_line_rms_v_per_krpm`

说明：

- `V/krpm` 和 `V/(rad/s)` 不是同一单位
- `line RMS` 的 `Ke` 与 `phase peak` 的 `Ke` 不是同一语义
- 当前 legacy `Ke` 仍保留，但只对应 legacy 语义

PMSM revised `Ke` 定义为：

```text
Ke_phase_peak
= back_emf_phase_peak_v / mechanical_angular_speed_rad_s

Ke_phase_rms
= back_emf_phase_rms_v / mechanical_angular_speed_rad_s

Ke_line_rms
= back_emf_line_rms_v / mechanical_angular_speed_rad_s

Ke_line_rms_per_krpm
= back_emf_line_rms_v / (mechanical_speed_rpm / 1000)
```

这些字段全部基于机械角速度，不是电角速度。

## 12. Kt 的不同定义

Phase 3C 明确区分：

- `legacy_torque_constant_nm_per_phase_rms_a`
- `revised_torque_constant_nm_per_phase_peak_a`
- `revised_torque_constant_nm_per_phase_rms_a`

说明：

- 不能笼统写 `Kt = Ke`
- 不能把 `Nm/A_phase_peak` 和 `V_line_rms/(rad/s)` 直接比较
- 当前 legacy `Kt` 仍保留，但只对应 legacy 语义

## 13. PMSM revised Kt 的功率推导

Phase 3C 采用下列 PMSM 假设：

- 三相系统
- Y 接
- 正弦相反电势
- 正弦相电流
- 稳态
- 三相平衡
- 电流与反电势同相
- 暂不考虑 `d` 轴电流、弱磁、凸极效应和磁阻转矩
- 暂不考虑逆变器谐波

三相功率关系：

```text
P_electromagnetic
= (3/2) * E_phase_peak * I_phase_peak
```

机械功率关系：

```text
P_mechanical
= torque_nm * mechanical_angular_speed_rad_s
```

因此：

```text
torque_nm
= (3/2)
 * revised_back_emf_constant_phase_peak_v_per_rad_s
 * phase_current_peak_a
```

由此得到：

```text
revised_torque_constant_nm_per_phase_peak_a
= (3/2)
 * revised_back_emf_constant_phase_peak_v_per_rad_s

revised_torque_constant_nm_per_phase_rms_a
= sqrt(2)
 * revised_torque_constant_nm_per_phase_peak_a

revised_torque_constant_nm_per_phase_rms_a
= 3
 * revised_back_emf_constant_phase_rms_v_per_rad_s
```

## 14. 什么情况下可以说 Ke 和 Kt 存在数值关系

只有在以下条件同时成立时，才能讨论 revised `Ke` 与 revised `Kt` 的数值关系：

- 正弦反电势
- 正弦相电流
- 三相平衡
- 电流与反电势同相
- `Ke` 使用机械角速度定义
- `Kt` 明确对应相电流峰值或相电流 RMS

## 15. 为什么不能直接写 Kt = Ke

不能直接写 `Kt = Ke` 的原因：

1. `Ke` 有相量/线量、RMS/峰值和不同速度基准
2. `Kt` 有相电流峰值和相电流 RMS 等不同定义
3. 不同定义之间会带来 `sqrt(2)`、`sqrt(3)`、`3/2` 等系数
4. BLDC 120°导通不满足当前 PMSM 正弦模式的推导前提

## 16. 哪些关系是精确数学转换

以下关系当前可视为精确转换：

- `pole_count = 2 * pole_pairs`
- `mechanical_speed_rpm -> mechanical_angular_speed_rad_s`
- `mechanical_speed_rpm + pole_pairs -> electrical_frequency_hz`
- `mechanical_angular_speed_rad_s + pole_pairs -> electrical_angular_speed_rad_s`
- Y 接下 `line_current_rms_a = phase_current_rms_a`
- PMSM 正弦模式下的标准 RMS/峰值、相/线换算
- `V/krpm` 与 `V/(rad/s)` 的纯单位换算
- PMSM revised `Kt_peak = (3/2) * Ke_phase_peak`
- PMSM revised `Kt_rms = 3 * Ke_phase_rms`

## 17. 哪些关系依赖波形和控制策略

以下内容不能只靠简单换算确定：

- BLDC 梯形波的 RMS/峰值关系
- BLDC 120°导通时的电流定义
- `Ke` 与 `Kt` 在不同波形和不同电流定义下的对应关系
- `required_voltage_v` 与调制方式、相位角、控制策略的关系
- 母线电流与相电流/线电流的严格映射

## 18. 当前 legacy 模型仍存在的限制

当前仍保留的限制包括：

- `9.55 * P / n` 的 legacy 默认链路仍保留
- BLDC `Ke/Kt` 原始公式未修正
- `required_voltage_v` 未修正
- 铁损、机械损耗、涡流损耗、电感、槽满率、退磁、温升等经验模型未修正
- 未知 legacy 波形标签仍会落到 legacy BLDC 分支

因此：

- regression baseline 只能证明“重构未改旧数值”
- 不能据此宣称“物理精度已提升”

## 19. 当前 baseline 的语义边界

- `legacy_baseline.json` 的 3 组历史样例仍保留未知波形标签
- 当前兼容层会把这些样例落到 legacy BLDC 分支
- 因此它们可以继续作为 regression baseline
- 但不能被强行解释为 PMSM revised `Ke/Kt` 误差样例

## 20. 下一阶段需要验证的公式

Phase 3C 完成后，建议优先验证：

1. BLDC 120°导通下相电流、线电流、母线电流的严格定义
2. BLDC 梯形反电势下 `Ke` 的相量/线量、RMS/峰值定义
3. BLDC 120°导通下 `Kt` 与 `Ke` 的功率关系
4. `required_voltage_v` 当前到底对应哪一种电压量
5. revised PMSM `Ke/Kt` 是否允许成为默认值
6. 旧 `back_emf_line_rms_v` 在 BLDC 情况下是否应保留为 legacy-only 字段

## 21. 当前阶段结论

Phase 3A 到 Phase 3C 的目标不是静默换默认值，而是：

- 统一命名
- 统一单位
- 集中换算函数
- 划清 PMSM 和 BLDC 边界
- 建立 PMSM revised `Ke/Kt` 的可验证定义
- 保持 legacy baseline 数值不变

在这一阶段，任何会改变 legacy baseline 数值的修改都不应被视为“纯语义重构”。
