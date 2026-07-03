# Phase 3 公式变更报告

更新时间：2026-07-03

## 1. 报告范围

本报告覆盖：

- Phase 3B：额定转矩 legacy 与 strict SI 并行比较
- Phase 3C：PMSM 正弦模式下 revised `Ke` / `Kt` 定义、功率一致性验证与下游隔离
- Phase 3E：BLDC 120°导通模式下 revised `Ke` / `Kt` 定义、功率一致性验证与下游隔离

本报告不覆盖：

- `required_voltage_v` 修正
- 损耗模型修正
- 电感模型修正
- 填充率定义修正
- revised 结果切换为默认值

## 2. Phase 3B：额定转矩回顾

legacy 额定转矩公式：

```text
legacy_rated_torque_nm
= 9.55 * rated_power_w / mechanical_speed_rpm
```

strict SI 额定转矩公式：

```text
revised_rated_torque_nm
= rated_power_w / mechanical_angular_speed_rad_s
```

Phase 3B 结论：

- 差异只来自常数近似
- revised 额定转矩仍未传播到任何下游计算

## 3. Phase 3C：PMSM revised `Ke` / `Kt` 回顾

PMSM revised `Ke` 当前建立了：

- `phase peak`
- `phase RMS`
- `line RMS`
- `V/(rad/s)` 与 `V/krpm`

PMSM revised `Kt` 当前建立了：

- `Nm/A_phase_peak`
- `Nm/A_phase_rms`

PMSM revised 结论：

- 已通过三相功率平衡与独立 analytical reference validation
- 仍未切换为默认值
- 仍未传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路

## 4. Phase 3E：现有 legacy BLDC 与 revised BLDC 的边界

当前必须明确区分两件事：

1. 现有 legacy BLDC 路径
2. 本阶段新建的 ideal BLDC revised 路径

现有 legacy BLDC 的关键限制：

- legacy 示意波形 `_trapezoidal_back_emf(..., alpha_p)` 的平台宽度由 `alpha_p` 决定
- 它不是固定 `120°` flat-top revised 模型
- legacy 电压链路仍保留 `line_rms = sqrt(3) * phase_rms` 的 provisional 关系
- legacy `Kt` 仍保留旧推导

因此 Phase 3E 没有把 legacy 波形“解释成” revised，而是建立了一套并行的 ideal BLDC revised 语义层。

## 5. Phase 3E：ideal BLDC revised 相反电势关系

在当前 ideal BLDC revised 模型下：

```text
phase_peak = phase_flat_top

phase_rms = (sqrt(7) / 3) * phase_flat_top

line_to_line_peak = 2 * phase_flat_top

line_to_line_rms = (2 * sqrt(5) / 3) * phase_flat_top
```

这些关系来自显式分段波形与积分，而不是正弦自动换算。

## 6. Phase 3E：ideal BLDC revised 电流关系

在当前 ideal BLDC revised 模型下：

```text
phase_current_rms
= sqrt(2/3) * conduction_current
```

说明：

- 当前不能使用 `peak = sqrt(2) * rms`
- `dc_bus_current` 未在 Phase 3E 中被重新定义为新的默认语义量

## 7. Phase 3E：ideal BLDC revised 平均功率关系

在当前 ideal BLDC revised 模型下，已通过分段推导与高分辨率数值积分交叉验证：

```text
P_em_avg
= 2 * E_flat_top * I_conduction
```

机械功率关系：

```text
P_mechanical
= torque_nm * mechanical_angular_speed_rad_s
```

## 8. Phase 3E：revised BLDC Ke 定义

当前新增：

```text
revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s
revised_bldc_back_emf_constant_phase_peak_v_per_rad_s
revised_bldc_back_emf_constant_phase_rms_v_per_rad_s
revised_bldc_back_emf_constant_line_rms_v_per_rad_s
revised_bldc_back_emf_constant_line_rms_v_per_krpm
```

统一定义：

```text
Ke = voltage_quantity / mechanical_angular_speed_rad_s
```

## 9. Phase 3E：revised BLDC Kt 定义

当前新增：

```text
revised_bldc_torque_constant_nm_per_conduction_a
revised_bldc_torque_constant_nm_per_phase_rms_a
```

推导关系：

```text
revised_bldc_torque_constant_nm_per_conduction_a
= 2 * revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s

revised_bldc_torque_constant_nm_per_phase_rms_a
= revised_bldc_torque_constant_nm_per_conduction_a / sqrt(2/3)
```

说明：

- 没有照搬 PMSM 的 `Kt_peak = 3/2 Ke_phase_peak`
- 没有照搬 PMSM 的 `Kt_rms = 3 Ke_phase_rms`
- 不能笼统写 `BLDC Kt = Ke`

## 10. Phase 3E：4 个独立 BLDC analytical reference cases

| case_id | rpm | omega_m (rad/s) | phase_flat_top (V) | conduction_current (A) | phase_rms (V) | line_rms (V) | phase_current_rms (A) | P_em_avg (W) | torque (Nm) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `basic_flat_top_case` | 95.4929658551372 | 10.0 | 20.0 | 4.0 | 17.638342073764 | 29.814239699997 | 3.265986323711 | 160.0 | 16.0 |
| `common_rpm_case` | 1000.0 | 104.719755119660 | 24.0 | 6.0 | 21.166010488517 | 35.777087639997 | 4.898979485566 | 288.0 | 2.750197416628 |
| `low_speed_high_torque_case` | 60.0 | 6.283185307180 | 6.0 | 12.0 | 5.291502622129 | 8.944271909999 | 9.797958971133 | 144.0 | 22.918311805233 |
| `high_speed_low_torque_case` | 6000.0 | 628.318530717959 | 12.0 | 0.8 | 10.583005244258 | 17.888543819998 | 0.653197264742 | 19.2 | 0.030557749074 |

## 11. Phase 3E：解析与数值积分交叉验证

已独立验证以下量：

- `phase back EMF RMS`
- `line-to-line back EMF RMS`
- `phase current RMS`
- `average electromagnetic power`

当前数值积分与解析结果在高分辨率 midpoint integration 下保持一致，`test_bldc_reference_cases.py` 与 `test_bldc_reference_independence.py` 均已通过。

## 12. 3 组 legacy baseline 的 BLDC parallel comparison

说明：

- 现有 3 组 legacy baseline 全部走 BLDC fallback 路径
- `legacy_baseline.json` 未修改
- 这里只比较 revised 并行输出，不改变 baseline 锚点

| case | legacy BLDC Ke line RMS V/krpm | revised BLDC Ke line RMS V/krpm | absolute difference | relative difference | legacy BLDC Kt phase RMS Nm/A | revised BLDC Kt conduction Nm/A | revised BLDC Kt phase RMS Nm/A | comparability status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `default_case` | 14.733169889368 | 14.378101569798 | 0.355068319571 | 0.024695076596 | 0.243684668435 | 0.184208294571 | 0.225608164044 | `Ke direct comparable; Kt not directly comparable` |
| `low_power_low_speed_case` | 12.388626927987 | 12.090061922755 | 0.298565005232 | 0.024695076596 | 0.204906240000 | 0.154894558036 | 0.189706315561 | `Ke direct comparable; Kt not directly comparable` |
| `high_power_high_speed_case` | 17.829821587827 | 17.400124188219 | 0.429697399607 | 0.024695076596 | 0.294902875248 | 0.222925619664 | 0.273027009385 | `Ke direct comparable; Kt not directly comparable` |

差异来源解释：

- `Ke` 差异来自 revised BLDC fixed 120° waveform 定义与 legacy provisional RMS 映射不同
- `Kt` 不直接可比，原因包括：
  - 波形定义不同
  - 电流基准不同
  - legacy BLDC `Kt` 仍保留 provisional 语义
  - revised BLDC `Kt` 明确区分了 `conduction current` 与 `phase RMS current`

## 13. revised 未传播到下游的原因

Phase 3E 明确保留下游隔离，原因是：

1. 额定电流继续使用 legacy `Kt`
2. 铜损继续使用 legacy current 链路
3. 效率继续使用 legacy loss 链路
4. `required_voltage_v` 继续使用 legacy line RMS requirement model
5. torque waveform 继续使用 legacy 示意模型
6. GUI 默认链路没有切换到 revised

## 14. 本阶段没有改什么

Phase 3E 没有修改：

- PMSM revised 公式
- PMSM reference cases
- `required_voltage_v`
- 额定电流默认链路
- 损耗
- 效率
- 电感
- 槽满率
- 退磁或温升
- `legacy_baseline.json`

## 15. 结论声明

Phase 3E 提升的是：

- BLDC revised `Ke` / `Kt` 的定义清晰度
- flat-top / peak / RMS / line-to-line 量的可验证性
- 120°导通 average power balance 的可验证性
- revised 结果切换为默认值前的风险可见性

Phase 3E 不代表：

- legacy BLDC 已经被静默修正
- BLDC revised 已成为默认值
- `required_voltage_v`、损耗或效率模型已经同步升级
- 整个电机模型已经获得实验验证
