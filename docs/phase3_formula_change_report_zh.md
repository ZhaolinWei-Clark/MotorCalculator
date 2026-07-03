# Phase 3 公式变更报告

更新时间：2026-07-03

## 1. 报告范围

本报告覆盖：

- Phase 3B：额定转矩 legacy 与 strict SI 并行比较
- Phase 3C：PMSM 正弦模式下 revised `Ke` / `Kt` 定义、功率一致性验证与下游隔离

本报告不覆盖：

- BLDC `Ke` / `Kt` 修正
- `required_voltage_v` 修正
- revised `Ke` / `Kt` 向额定电流、铜损、效率或 GUI 默认链路传播

## 2. Phase 3B 额定转矩回顾

legacy 额定转矩公式：

```text
legacy_rated_torque_nm
= 9.55 * rated_power_w / mechanical_speed_rpm
```

strict SI 额定转矩公式：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60

revised_rated_torque_nm
= rated_power_w / mechanical_angular_speed_rad_s
```

常数差异说明：

- `9.55` 是 `60 / (2π)` 的近似值
- `60 / (2π) = 9.549296585513721...`
- 绝对差：`0.000703414486280`
- 相对差：`0.000073661392751`
- 相对差百分比：`0.007366139275%`

## 3. Phase 3B 的 3 组 baseline 对比

| 案例 | legacy_rated_torque_nm | revised_rated_torque_nm | absolute_difference_nm | relative_difference | relative_difference_percent |
|---|---:|---:|---:|---:|---:|
| `default_case` | 3.056000000000 | 3.055774907364 | 0.000225092636 | 0.000073661393 | 0.007366139275% |
| `low_power_low_speed_case` | 1.790625000000 | 1.790493109784 | 0.000131890216 | 0.000073661393 | 0.007366139275% |
| `high_power_high_speed_case` | 5.305555555556 | 5.305164769730 | 0.000390785826 | 0.000073661393 | 0.007366139275% |

说明：

- 差异只来自常数近似，不来自新的电磁物理模型
- `legacy_baseline.json` 未修改
- revised 转矩仍未传播到任何下游计算

## 4. Phase 3C 当前 PMSM 假设

Phase 3C 仅适用于下列 PMSM 正弦模式假设：

- 三相系统
- Y 接
- 正弦相反电势
- 正弦相电流
- 稳态
- 三相平衡
- 电流与反电势同相
- 暂不考虑 `d` 轴电流、弱磁、凸极效应和磁阻转矩
- 暂不考虑逆变器谐波
- 转矩只考虑永磁同步转矩分量
- `pole_pairs` 表示极对数
- `mechanical_angular_speed_rad_s` 表示机械角速度

## 5. 相反电势与相/线、RMS/峰值关系

PMSM 正弦模式下采用集中定义：

```text
back_emf_phase_peak_v
= sqrt(2) * back_emf_phase_rms_v

back_emf_line_rms_v
= sqrt(3) * back_emf_phase_rms_v
```

这些关系依赖：

- 正弦反电势
- 三相平衡
- Y 接相/线定义

它们不是 BLDC 120°导通的通用关系。

## 6. 机械角速度与电角速度的区别

本阶段 revised `Ke` 明确基于机械角速度：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60
```

而不是电角速度：

```text
electrical_angular_speed_rad_s
= mechanical_angular_speed_rad_s * pole_pairs
```

因此：

- 若字段名中没有明确写出 `electrical_angular_speed_rad_s`，就不能把它当作电角速度基准
- Phase 3C 的 revised `Ke` 不允许把机械角速度和电角速度混用

## 7. revised Ke 的四种输出定义

Phase 3C 新增的 revised `Ke` 字段为：

```text
revised_back_emf_constant_phase_peak_v_per_rad_s
= back_emf_phase_peak_v / mechanical_angular_speed_rad_s

revised_back_emf_constant_phase_rms_v_per_rad_s
= back_emf_phase_rms_v / mechanical_angular_speed_rad_s

revised_back_emf_constant_line_rms_v_per_rad_s
= back_emf_line_rms_v / mechanical_angular_speed_rad_s

revised_back_emf_constant_line_rms_v_per_krpm
= back_emf_line_rms_v / (mechanical_speed_rpm / 1000)
```

这四个量必须明确区分：

- `phase peak`
- `phase RMS`
- `line RMS`
- `V/(rad/s)` 与 `V/krpm`

## 8. 三相功率推导

在当前冻结假设下：

```text
e_a = E_peak * sin(theta)
e_b = E_peak * sin(theta - 2π/3)
e_c = E_peak * sin(theta + 2π/3)

i_a = I_peak * sin(theta)
i_b = I_peak * sin(theta - 2π/3)
i_c = I_peak * sin(theta + 2π/3)
```

当电流与反电势同相时：

```text
P_electromagnetic
= e_a*i_a + e_b*i_b + e_c*i_c
= (3/2) * E_phase_peak * I_phase_peak
```

同时机械功率满足：

```text
P_mechanical
= torque_nm * mechanical_angular_speed_rad_s
```

Phase 3C 的功率一致性测试验证：

- `P_electromagnetic = (3/2) * E_phase_peak * I_phase_peak`
- `P_mechanical = torque_nm * mechanical_angular_speed_rad_s`
- 在当前 PMSM 假设下，两者数值一致

## 9. revised Kt 的推导

由：

```text
E_phase_peak
= revised_back_emf_constant_phase_peak_v_per_rad_s
 * mechanical_angular_speed_rad_s
```

代入三相功率关系：

```text
torque_nm
= (3/2)
 * revised_back_emf_constant_phase_peak_v_per_rad_s
 * phase_current_peak_a
```

因此：

```text
revised_torque_constant_nm_per_phase_peak_a
= (3/2)
 * revised_back_emf_constant_phase_peak_v_per_rad_s
```

又因为：

```text
phase_current_peak_a
= sqrt(2) * phase_current_rms_a
```

所以：

```text
revised_torque_constant_nm_per_phase_rms_a
= sqrt(2)
 * revised_torque_constant_nm_per_phase_peak_a

= 3
 * revised_back_emf_constant_phase_rms_v_per_rad_s
```

## 10. 什么情况下可以说 Ke 和 Kt 存在数值关系

只有在以下条件同时满足时，才能讨论 revised `Ke` 与 revised `Kt` 的数值关系：

- 正弦反电势
- 正弦相电流
- 三相平衡
- 电流与反电势同相
- `Ke` 以机械角速度为基准
- `Kt` 明确对应相电流峰值或相电流 RMS

离开这些前提，`Ke` / `Kt` 的“相等”或“近似相等”都可能失去物理意义。

## 11. 为什么不能直接写 Kt = Ke

不能直接写 `Kt = Ke` 的原因是：

1. `Ke` 有相量/线量、RMS/峰值、`V/(rad/s)` / `V/krpm` 等多种定义
2. `Kt` 也有相电流峰值、相电流 RMS 等多种定义
3. 不同定义之间可能相差 `sqrt(2)`、`sqrt(3)`、`3/2` 等系数
4. BLDC 120°导通根本不满足当前 PMSM 正弦模式的功率推导前提

因此必须写成明确字段名，而不能写成笼统的 `Kt = Ke`。

## 12. 为什么 line RMS 的 Ke 不能直接和 phase peak 的 Kt 比较

`revised_back_emf_constant_line_rms_v_per_rad_s` 与
`revised_torque_constant_nm_per_phase_peak_a`
不能直接比较，因为它们分别对应：

- 线电压 RMS
- 相电流峰值

这两者的物理定义、单位和相/线语义都不同。

Phase 3C 只允许以下“同语义”比较：

- `legacy_back_emf_constant_line_rms_v_per_krpm`
  与
  `revised_back_emf_constant_line_rms_v_per_krpm`
- `legacy_torque_constant_nm_per_phase_rms_a`
  与
  `revised_torque_constant_nm_per_phase_rms_a`
  但前提是只在当前 PMSM 正弦 legacy 标签下解释，不外推到 BLDC

## 13. 3 组 legacy baseline 的 Ke/Kt 可比性表

当前 `legacy_baseline.json` 的 3 组样例保留了原始未知波形标签，因此仍落在 legacy BLDC 分支。根据 Phase 3C 边界：

- 这些样例可以继续做 legacy regression
- 但不能被强行解释为 PMSM revised `Ke` / `Kt` 案例
- 所以 revised PMSM 字段在这些样例中必须保持 `N/A`

| 案例 | control_mode | legacy Ke line RMS V/krpm | revised Ke phase peak V/(rad/s) | revised Ke phase RMS V/(rad/s) | revised Ke line RMS V/(rad/s) | revised Ke line RMS V/krpm | legacy Kt phase RMS Nm/A | revised Kt phase peak Nm/A | revised Kt phase RMS Nm/A | 说明 |
|---|---|---:|---|---|---|---|---:|---|---|---|
| `default_case` | `bldc_120_degree` | 14.733169889368 | `N/A` | `N/A` | `N/A` | `N/A` | 0.243684668435 | `N/A` | `N/A` | 该案例是 legacy BLDC 路径，PMSM revised `Ke/Kt` 不适用 |
| `low_power_low_speed_case` | `bldc_120_degree` | 12.388626927987 | `N/A` | `N/A` | `N/A` | `N/A` | 0.204906240000 | `N/A` | `N/A` | 该案例是 legacy BLDC 路径，PMSM revised `Ke/Kt` 不适用 |
| `high_power_high_speed_case` | `bldc_120_degree` | 17.829821587827 | `N/A` | `N/A` | `N/A` | `N/A` | 0.294902875248 | `N/A` | `N/A` | 该案例是 legacy BLDC 路径，PMSM revised `Ke/Kt` 不适用 |

## 14. PMSM 正弦样例中的可直接比较量

在当前 PMSM 正弦样例中，以下量可以直接比较：

| 案例 | legacy Ke line RMS V/krpm | revised Ke line RMS V/krpm | Ke relative difference | legacy Kt phase RMS Nm/A | revised Kt phase peak Nm/A | revised Kt phase RMS Nm/A | Kt relative difference | 功率一致性状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `sample_pmsm_case` | 16.353818577199 | 16.353818577199 | 0.000000000000 | 0.270489981963 | 0.191265300489 | 0.270489981963 | 0.000000000000 | `validated_from_three_phase_power_balance` |

解释：

- `legacy Ke line RMS V/krpm` 与 `revised Ke line RMS V/krpm` 单位和语义兼容，可直接比较
- `legacy Kt phase RMS Nm/A` 与 `revised Kt phase RMS Nm/A` 只在当前 PMSM 正弦 legacy 标签下解释为兼容量
- `revised Kt phase peak Nm/A` 不能和 `legacy Kt phase RMS Nm/A` 直接做相对误差比较

## 15. 为什么 revised 结果未传播到下游

Phase 3C 明确保持下游隔离，原因是：

1. 当前额定电流仍明确使用 `legacy_torque_constant_nm_per_phase_rms_a`
2. 铜损仍由 legacy 额定电流链路驱动
3. 效率仍由 legacy 损耗链决定
4. `required_voltage_v` 仍保持 legacy 线 RMS 模型
5. GUI 默认链路仍不切换到 revised `Ke` / `Kt`

因此 revised `Ke` / `Kt` 目前只进入：

- 输出模型
- 差异字段
- 自动测试
- 报告层

## 16. BLDC 尚未解决的问题

Phase 3C 没有解决以下问题：

- BLDC 120°导通下相电流、线电流、母线电流的严格 RMS/峰值定义
- BLDC 梯形反电势下 `Ke` 的相量/线量映射
- BLDC 120°导通下 `Kt` 与 `Ke` 的严格功率关系
- legacy BLDC `back_emf_line_rms_v` 是否应长期保留为 provisional 字段

这些问题必须进入后续独立阶段，不能在当前 PMSM 正弦阶段顺手“套公式”处理。

## 17. 本阶段尚未纳入的物理因素

Phase 3C 明确未纳入：

- 磁阻转矩项
- 弱磁
- `d/q` 轴控制
- 凸极效应
- 逆变器谐波
- `required_voltage_v` 修正

## 18. 结论声明

Phase 3C 提升的是：

- PMSM 正弦模式下 `Ke` / `Kt` 字段定义的明确性
- 相量/线量、RMS/峰值与单位基准的可验证性
- 三相功率与机械功率之间的一致性验证
- revised 结果切换为默认值前的风险可见性

Phase 3C 不代表：

- BLDC `Ke` / `Kt` 已修正
- 整个电机模型已得到实验验证
- `required_voltage_v`、损耗、效率或热模型已经同步升级
- revised `Ke` / `Kt` 已获批准成为生产默认值
