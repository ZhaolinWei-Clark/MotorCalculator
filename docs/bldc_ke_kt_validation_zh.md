# BLDC revised Ke/Kt analytical validation

更新时间：2026-07-03

## 1. BLDC 120°导通假设

当前 Phase 3E 冻结的 revised BLDC 模型固定为：

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

## 2. 为什么需要新的 revised BLDC 模型

现有 legacy BLDC 路径存在两个关键事实：

1. 示意波形 `_trapezoidal_back_emf(..., alpha_p)` 平台宽度由 `alpha_p` 决定，不是固定 `120°` flat-top
2. legacy 电压与 `Kt` 链路保留了 provisional RMS 映射和旧经验推导

因此，Phase 3E 没有把 legacy 波形强行解释成 ideal BLDC，而是建立并行 revised 语义层。

## 3. 梯形相反电势分段定义

定义归一化相反电势：

```text
normalized_bldc_phase_back_emf(θ)
```

其中 `θ` 为电角度，周期为 `2π`。

Phase A 分段：

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

三相偏移：

```text
e_a(θ) = E_flat * e_n(θ)
e_b(θ) = E_flat * e_n(θ - 2π/3)
e_c(θ) = E_flat * e_n(θ + 2π/3)
```

## 4. 相反电势量的区分

本阶段明确区分：

- `back_emf_phase_flat_top_v`
- `back_emf_phase_peak_v`
- `back_emf_phase_rms_v`
- `back_emf_line_to_line_peak_v`
- `back_emf_line_to_line_rms_v`

在当前 ideal 模型中：

```text
back_emf_phase_peak_v = back_emf_phase_flat_top_v
```

## 5. 相反电势 RMS 推导

对 `e_n(θ)^2` 在 `0 ~ 2π` 上积分，可得：

```text
phase_rms
= (sqrt(7) / 3) * phase_flat_top
```

即：

```text
back_emf_phase_rms_v
= (sqrt(7) / 3) * back_emf_phase_flat_top_v
```

## 6. 线间反电势 RMS 推导

定义：

```text
e_ab(θ) = e_a(θ) - e_b(θ)
```

对当前分段波形展开后，可得：

```text
line_to_line_peak
= 2 * phase_flat_top

line_to_line_rms
= (2 * sqrt(5) / 3) * phase_flat_top
```

这一步不能用 `sqrt(3)` 正弦关系代替。

## 7. 120°相电流分段定义

定义归一化相电流：

```text
normalized_bldc_phase_current(θ)
```

Phase A 分段：

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

三相偏移：

```text
i_a(θ) = I_cond * i_n(θ)
i_b(θ) = I_cond * i_n(θ - 2π/3)
i_c(θ) = I_cond * i_n(θ + 2π/3)
```

## 8. phase RMS current 推导

对 `i_n(θ)^2` 在 `0 ~ 2π` 上积分，可得：

```text
phase_current_rms
= sqrt(2/3) * conduction_current
```

即：

```text
phase_current_rms_a
= sqrt(2/3) * phase_current_conduction_a
```

## 9. 三相瞬时功率推导

瞬时电磁功率定义：

```text
p(θ)
= e_a(θ)i_a(θ)
 + e_b(θ)i_b(θ)
 + e_c(θ)i_c(θ)
```

在当前 ideal 对齐假设下，解析推导与高分辨率数值积分共同验证：

```text
P_em_avg
= 2 * E_flat_top * I_conduction
```

## 10. 平均电磁功率与机械功率

机械关系：

```text
P_mechanical
= torque_nm * mechanical_angular_speed_rad_s
```

因此：

```text
torque_nm
= (2 * E_flat_top * I_conduction) / mechanical_angular_speed_rad_s
```

## 11. revised BLDC Ke 定义

所有 revised BLDC `Ke` 都基于机械角速度：

```text
Ke = voltage_quantity / mechanical_angular_speed_rad_s
```

当前新增：

- `revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s`
- `revised_bldc_back_emf_constant_phase_peak_v_per_rad_s`
- `revised_bldc_back_emf_constant_phase_rms_v_per_rad_s`
- `revised_bldc_back_emf_constant_line_rms_v_per_rad_s`
- `revised_bldc_back_emf_constant_line_rms_v_per_krpm`

## 12. revised BLDC Kt 定义

由平均功率平衡推导：

```text
revised_bldc_torque_constant_nm_per_conduction_a
= 2 * revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s
```

进一步结合相电流 RMS 关系：

```text
revised_bldc_torque_constant_nm_per_phase_rms_a
= revised_bldc_torque_constant_nm_per_conduction_a / sqrt(2/3)
```

## 13. 哪些 Ke/Kt 数值关系成立

在当前 fixed ideal BLDC 假设下，可以成立：

- `Kt_conduction = 2 * Ke_phase_flat_top`
- `T = Kt_conduction * I_conduction`
- `T = Kt_phase_rms * I_phase_rms`
- `line_to_line_peak = 2 * phase_flat_top`
- `line_to_line_rms = (2*sqrt(5)/3) * phase_flat_top`

## 14. 哪些关系不成立

当前不成立或不允许笼统写：

- `Kt = Ke`
- `phase_peak = sqrt(2) * phase_rms`
- `line_rms = sqrt(3) * phase_rms`
- 把 PMSM 正弦关系直接套用到 BLDC revised

## 15. legacy 与 revised 的对比原则

可以直接比较：

- `legacy_bldc_back_emf_constant_line_rms_v_per_krpm`
- `revised_bldc_back_emf_constant_line_rms_v_per_krpm`

不应直接用相对误差比较：

- `legacy_bldc_torque_constant_nm_per_phase_rms_a`
- `revised_bldc_torque_constant_nm_per_conduction_a`

即使 `legacy_bldc_torque_constant_nm_per_phase_rms_a` 与 `revised_bldc_torque_constant_nm_per_phase_rms_a` 单位名义上相同，也应保留“legacy BLDC 语义仍为 provisional”的解释，不宜把其误读为已批准的物理真值误差。

## 16. 4 个 analytical reference cases

- `basic_flat_top_case`
- `common_rpm_case`
- `low_speed_high_torque_case`
- `high_speed_low_torque_case`

这些 case 保存在：

```text
motor_calculator/tests/fixtures/bldc_reference_cases.json
```

并由独立 builder：

```text
motor_calculator/tests/bldc_reference_case_builder.py
```

使用标准库重建 expected 值。

## 17. 独立数值积分验证结果

builder 使用高分辨率 midpoint integration 独立验证：

- `phase back EMF RMS`
- `line-to-line back EMF RMS`
- `phase current RMS`
- `average three-phase electromagnetic power`

解析结果与数值积分结果在设定容差内一致。

## 18. revised 未传播到下游的原因

Phase 3E 明确保留下游 legacy 链路：

- 额定电流继续使用 legacy `Kt`
- 铜损继续使用 legacy current
- 效率继续使用 legacy 链路
- `required_voltage_v` 保持不变
- torque waveform 保持不变
- GUI 默认链路保持不变

## 19. 尚未处理的因素

本阶段明确尚未处理：

- 换相重叠
- PWM 电流纹波
- 相电感导致的换相延迟
- 逆变器压降
- `required_voltage_v` 修正
- 损耗模型升级
- 电感模型升级
- 槽满率定义升级

## 20. 为什么 analytical validation 不是实验验证

当前验证属于：

- analytical validation
- numeric cross-validation

当前验证不属于：

- FEA validation
- experimental validation
- published benchmark validation
- full prototype validation

因此，Phase 3E 的结论只能说明 revised BLDC `Ke` / `Kt` 在当前理想波形与功率平衡假设下数学自洽、可独立复核、与 production 并行输出一致；它不等于实验验证。
