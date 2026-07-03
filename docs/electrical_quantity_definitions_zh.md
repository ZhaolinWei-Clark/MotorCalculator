# 电气量定义说明

更新时间：2026-07-03

本文档统一 Phase 3A 到 Phase 3E 中所有关键电气量、速度量、极数语义、控制模式边界，以及 PMSM / BLDC revised `Ke` / `Kt` 定义。目标不是静默替换 legacy 公式，而是把名称、单位、数学关系和适用边界讲清楚。

## 1. 极对数和总极数

- `pole_pairs`：极对数
- `pole_count`：总极数

统一关系：

```text
pole_count = 2 * pole_pairs
```

## 2. 机械转速与机械角速度

- `mechanical_speed_rpm`：机械转速，单位 `rpm`
- `mechanical_angular_speed_rad_s`：机械角速度，单位 `rad/s`

关系：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60
```

## 3. 电频率与电角速度

- `electrical_frequency_hz`：电频率，单位 `Hz`
- `electrical_angular_speed_rad_s`：电角速度，单位 `rad/s`

关系：

```text
electrical_frequency_hz
= mechanical_speed_rpm * pole_pairs / 60

electrical_angular_speed_rad_s
= mechanical_angular_speed_rad_s * pole_pairs
```

## 4. Y 接公共关系

当前项目默认绕组连接为 Y 接。

- PMSM 正弦模式下：
  - `line_current_rms_a = phase_current_rms_a`
- BLDC 120°导通 revised 模型下：
  - 线导体中的瞬时电流与相电流定义一致
  - 理想 120°导通下 `line_current_rms_a = phase_current_rms_a`
- `dc_bus_current_a` 不得与 `phase_current_rms_a` 混用

## 5. PMSM 正弦模式

PMSM revised 语义只适用于：

- 三相系统
- Y 接
- 正弦相反电势
- 正弦相电流
- 稳态
- 三相平衡
- 电流与反电势同相

PMSM 正弦模式下允许使用标准正弦关系：

```text
phase_voltage_peak_v = sqrt(2) * phase_voltage_rms_v
line_voltage_rms_v = sqrt(3) * phase_voltage_rms_v
line_voltage_peak_v = sqrt(2) * line_voltage_rms_v
phase_current_peak_a = sqrt(2) * phase_current_rms_a
```

## 6. BLDC 120°导通 revised 模型边界

Phase 3E 冻结的 revised BLDC 模型固定为：

- 三相系统
- Y 接
- 梯形相反电势
- 120°六步换相
- 任意时刻理想情况下两相导通、一相悬空
- 导通相电流幅值为恒定 `±I`
- 电流平台与反电势平台理想对齐
- 忽略换相重叠
- 忽略 PWM 电流纹波
- 忽略相电感造成的换相延迟
- 忽略逆变器压降
- 忽略转矩脉动
- 忽略齿槽转矩
- 忽略磁阻转矩
- 机械转速恒定
- 电磁功率等于机械功率，不计损耗

## 7. ideal BLDC 相反电势归一化分段函数

定义归一化相反电势函数：

```text
normalized_bldc_phase_back_emf(θ)
```

其中 `θ` 为电角度，周期为 `2π`，输出范围为 `[-1, 1]`。

Phase A 的分段定义为：

```text
0 <= θ < π/6:
  e_n(θ) = 6θ / π

π/6 <= θ < 5π/6:
  e_n(θ) = 1

5π/6 <= θ < 7π/6:
  e_n(θ) = 1 - 6(θ - 5π/6) / π

7π/6 <= θ < 11π/6:
  e_n(θ) = -1

11π/6 <= θ < 2π:
  e_n(θ) = -1 + 6(θ - 11π/6) / π
```

三相相位偏移固定为：

```text
e_a(θ) = E_flat * e_n(θ)
e_b(θ) = E_flat * e_n(θ - 2π/3)
e_c(θ) = E_flat * e_n(θ + 2π/3)
```

说明：

- `phase_flat_top` 与 `phase_peak` 在当前 ideal BLDC 模型中数值相同
- 这套 revised 分段函数与 legacy `_trapezoidal_back_emf(..., alpha_p)` 不是同一语义
- legacy 示意波形由 `alpha_p` 决定平台宽度，不等于当前固定 120° flat-top revised 模型

## 8. BLDC 相反电势量的区分

当前必须明确区分：

- `back_emf_phase_flat_top_v`
- `back_emf_phase_peak_v`
- `back_emf_phase_rms_v`
- `back_emf_line_to_line_peak_v`
- `back_emf_line_to_line_rms_v`

当前 ideal BLDC revised 模型下：

```text
back_emf_phase_peak_v = back_emf_phase_flat_top_v
```

但以下关系都不是正弦自动换算，必须由分段波形推导或积分得到：

- `phase RMS`
- `line-to-line peak`
- `line-to-line RMS`

## 9. BLDC phase RMS 关系

由分段积分得到：

```text
back_emf_phase_rms_v
= (sqrt(7) / 3) * back_emf_phase_flat_top_v
```

因此：

```text
back_emf_phase_flat_top_v
= (3 / sqrt(7)) * back_emf_phase_rms_v
```

## 10. BLDC line-to-line RMS 与 peak 关系

定义：

```text
e_ab(θ) = e_a(θ) - e_b(θ)
```

当前 ideal BLDC revised 模型下：

```text
back_emf_line_to_line_peak_v
= 2 * back_emf_phase_flat_top_v

back_emf_line_to_line_rms_v
= (2 * sqrt(5) / 3) * back_emf_phase_flat_top_v
```

说明：

- 这里不能使用 `line RMS = sqrt(3) * phase RMS`
- 当前结果来自显式 phase waveform 差分与积分

## 11. ideal BLDC 相电流归一化分段函数

定义归一化相电流函数：

```text
normalized_bldc_phase_current(θ)
```

Phase A 的分段定义为：

```text
0 <= θ < π/6:
  i_n(θ) = 0

π/6 <= θ < 5π/6:
  i_n(θ) = 1

5π/6 <= θ < 7π/6:
  i_n(θ) = 0

7π/6 <= θ < 11π/6:
  i_n(θ) = -1

11π/6 <= θ < 2π:
  i_n(θ) = 0
```

三相相位偏移固定为：

```text
i_a(θ) = I_cond * i_n(θ)
i_b(θ) = I_cond * i_n(θ - 2π/3)
i_c(θ) = I_cond * i_n(θ + 2π/3)
```

## 12. BLDC 电流量的区分

当前必须明确区分：

- `phase_current_conduction_a`
- `phase_current_peak_a`
- `phase_current_rms_a`
- `line_current_rms_a`
- `dc_bus_current_a`

当前 ideal BLDC revised 模型下：

- `phase_current_peak_a = phase_current_conduction_a`
- `phase_current_rms_a` 由 120°导通占空比推导
- `line_current_rms_a = phase_current_rms_a`
- `dc_bus_current_a` 不在 Phase 3E 中被重新定义为新的默认语义量

## 13. BLDC phase RMS current 关系

由 120°导通占空比积分得到：

```text
phase_current_rms_a
= sqrt(2/3) * phase_current_conduction_a
```

因此：

```text
phase_current_conduction_a
= phase_current_rms_a / sqrt(2/3)
```

说明：

- 这里不能使用 `peak = sqrt(2) * rms`
- 当前结果依赖 six-step 120°导通定义

## 14. BLDC 平均电磁功率关系

瞬时功率定义为：

```text
p(θ)
= e_a(θ) i_a(θ)
 + e_b(θ) i_b(θ)
 + e_c(θ) i_c(θ)
```

当前 ideal BLDC revised 模型下，通过分段解析与高分辨率数值积分共同验证：

```text
P_em_avg
= 2 * back_emf_phase_flat_top_v * phase_current_conduction_a
```

机械功率关系仍为：

```text
P_mechanical
= torque_nm * mechanical_angular_speed_rad_s
```

## 15. revised BLDC Ke 定义

所有 revised BLDC `Ke` 当前都基于机械角速度：

```text
Ke = voltage_quantity / mechanical_angular_speed_rad_s
```

新增字段：

- `revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s`
- `revised_bldc_back_emf_constant_phase_peak_v_per_rad_s`
- `revised_bldc_back_emf_constant_phase_rms_v_per_rad_s`
- `revised_bldc_back_emf_constant_line_rms_v_per_rad_s`
- `revised_bldc_back_emf_constant_line_rms_v_per_krpm`

说明：

- `V/krpm` 与 `V/(rad/s)` 不是同一单位
- 只有相同定义和相同单位的量才允许直接比较

## 16. revised BLDC Kt 定义

由平均功率关系与机械功率关系推导：

```text
revised_bldc_torque_constant_nm_per_conduction_a
= 2 * revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s
```

进一步结合：

```text
phase_current_rms_a = sqrt(2/3) * phase_current_conduction_a
```

得到：

```text
revised_bldc_torque_constant_nm_per_phase_rms_a
= revised_bldc_torque_constant_nm_per_conduction_a / sqrt(2/3)
```

当前新增字段：

- `revised_bldc_torque_constant_nm_per_conduction_a`
- `revised_bldc_torque_constant_nm_per_phase_rms_a`

## 17. 哪些 Ke/Kt 数值关系当前成立

当前在 ideal BLDC revised 模型下，可以成立的数值关系包括：

- `phase_peak = phase_flat_top`
- `phase_rms = (sqrt(7)/3) * phase_flat_top`
- `line_to_line_peak = 2 * phase_flat_top`
- `line_to_line_rms = (2*sqrt(5)/3) * phase_flat_top`
- `phase_current_rms = sqrt(2/3) * conduction_current`
- `P_em_avg = 2 * E_flat_top * I_conduction`
- `Kt_conduction = 2 * Ke_phase_flat_top`
- `T = Kt_conduction * I_conduction`
- `T = Kt_phase_rms * I_phase_rms`

## 18. 哪些关系当前不成立或不允许笼统写

当前不允许笼统写：

- `Kt = Ke`
- `line RMS = sqrt(3) * phase RMS`
- `phase peak = sqrt(2) * phase RMS`

当前也不应把以下内容混为一谈：

- PMSM 正弦关系
- BLDC revised 120°关系
- legacy BLDC provisional 关系

## 19. 当前 legacy 模型仍存在的限制

- legacy BLDC 电压链路仍保留 provisional `sqrt(3)` 线相 RMS 映射
- legacy BLDC `Kt` 仍保留旧推导
- `required_voltage_v` 仍未修正
- 损耗、电感、槽满率、退磁、温升等模型仍未修正

因此：

- regression baseline 只能证明“重构未改旧数值”
- 不能据此宣称“物理精度已提升”

## 20. 当前阶段结论

Phase 3A 到 Phase 3E 的核心目标仍然不是静默换默认值，而是：

- 统一命名
- 统一单位
- 集中换算函数
- 划清 PMSM 与 BLDC 边界
- 建立 PMSM revised `Ke` / `Kt` 与 BLDC revised `Ke` / `Kt` 的可验证定义
- 保持 legacy baseline 数值不变
