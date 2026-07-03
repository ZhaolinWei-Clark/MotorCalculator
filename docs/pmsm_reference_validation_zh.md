# PMSM Analytical Reference Validation

更新时间：2026-07-03

## 1. 为什么需要独立 PMSM reference cases

Phase 3C 已经把 PMSM 正弦模式下 revised `Ke` / `Kt` 的字段、单位和功率关系澄清出来，但当时只有：

- 单位换算测试
- 三相功率平衡测试
- 下游隔离测试

当时缺少的是：

- 与 legacy baseline 分离的 PMSM 数值参考案例
- 可人工手算复核的 expected 值
- 对 revised `Ke` / `Kt`、转矩和功率关系的独立 analytical verification

因此，Phase 3D 的目标不是改公式，而是建立独立、可追溯、可手算的 PMSM 正弦 reference cases。

## 2. legacy baseline 与 PMSM reference 的区别

`motor_calculator/tests/fixtures/legacy_baseline.json`：

- 用途：回归锁定 legacy 行为
- 当前 3 组案例：全部走 legacy BLDC 路径
- 不能作为 PMSM revised `Ke` / `Kt` 数值参考

`motor_calculator/tests/fixtures/pmsm_reference_cases.json`：

- 用途：验证 PMSM 正弦 revised `Ke` / `Kt`、功率和转矩关系
- 当前 4 组案例：全部标记为 `analytical_reference`
- expected 值全部可由输入独立手算

## 3. 当前 validation 的性质

本阶段属于：

- analytical verification

本阶段不属于：

- experimental validation
- FEA validation
- published benchmark validation

原因是当前案例不来自：

- 台架测量
- 有限元仿真
- 公开论文 benchmark
- 完整材料和几何参数驱动的样机数据

## 4. 独立 reference 计算公式

Phase 3D 固定采用以下 PMSM 正弦关系：

```text
E_phase_rms = E_phase_peak / sqrt(2)
E_line_rms = sqrt(3) * E_phase_rms
I_phase_rms = I_phase_peak / sqrt(2)

Ke_phase_peak = E_phase_peak / omega_m
Ke_phase_rms = E_phase_rms / omega_m
Ke_line_rms = E_line_rms / omega_m
Ke_line_rms_per_krpm = E_line_rms / (rpm / 1000)

Kt_phase_peak = (3/2) * Ke_phase_peak
Kt_phase_rms = sqrt(2) * Kt_phase_peak

P_electromagnetic = (3/2) * E_phase_peak * I_phase_peak
T = P_electromagnetic / omega_m
T = Kt_phase_peak * I_phase_peak
T = Kt_phase_rms * I_phase_rms
```

这些公式在 `motor_calculator/tests/reference_case_builder.py` 中仅使用 `math` 重建，不调用 production calculation functions。

## 5. reference builder 独立性说明

独立 builder：

- 文件：`motor_calculator/tests/reference_case_builder.py`
- 依赖：`json`、`math`、`pathlib`
- 不依赖：
  - `motor_core`
  - `pmsm_ke_kt_models.py`
  - `electrical_semantics.py`
  - `calculations.py`

对应独立性测试：

- `motor_calculator/tests/test_pmsm_reference_independence.py`

## 6. 案例总览

| case_id | source_type | 中文说明 | pole_pairs | rpm | omega_m (rad/s) | E_phase_peak (V) | I_phase_peak (A) |
|---|---|---|---:|---:|---:|---:|---:|
| `analytical_case_1_basic_integer` | `analytical_reference` | 基础整数型案例，便于直接手算 Ke、Kt、功率和转矩。 | 2 | 95.4929658551372 | 10.0 | 20.0 | 4.0 |
| `analytical_case_2_rpm_conversion` | `analytical_reference` | 1000 rpm 换算案例，重点检查 rpm 与 V/krpm 换算。 | 5 | 1000.0 | 104.71975511965977 | 24.0 | 6.0 |
| `analytical_case_3_low_speed_high_torque` | `analytical_reference` | 低速高转矩案例，重点检查低速下单位与转矩关系。 | 7 | 60.0 | 6.283185307179585 | 6.0 | 12.0 |
| `analytical_case_4_high_speed_low_torque` | `analytical_reference` | 高速低转矩案例，重点检查高速下换算与数值稳定性。 | 9 | 6000.0 | 628.3185307179587 | 12.0 | 0.8 |

## 7. 每个案例的输入与对比

### Case 1：`analytical_case_1_basic_integer`

输入：

| 量 | 数值 |
|---|---:|
| `mechanical_speed_rpm` | 95.4929658551372 |
| `mechanical_angular_speed_rad_s` | 10.0 |
| `back_emf_phase_peak_v` | 20.0 |
| `back_emf_phase_rms_v` | 14.14213562373095 |
| `back_emf_line_rms_v` | 24.494897427831777 |
| `phase_current_peak_a` | 4.0 |
| `phase_current_rms_a` | 2.82842712474619 |

手算关系：

- `Ke_phase_peak = 20 / 10 = 2.0`
- `Kt_phase_peak = (3/2) * 2.0 = 3.0`
- `P = (3/2) * 20 * 4 = 120`
- `T = 120 / 10 = 12.0`

对比：

| 量 | expected | actual | 绝对误差 | 相对误差 |
|---|---:|---:|---:|---:|
| `Ke_phase_peak` | 2.0 | 2.0 | 0.0 | 0.0 |
| `Ke_phase_rms` | 1.414213562373095 | 1.414213562373095 | 0.0 | 0.0 |
| `Ke_line_rms` | 2.449489742783178 | 2.449489742783178 | 0.0 | 0.0 |
| `Ke_line_rms_per_krpm` | 256.5099660323728 | 256.5099660323728 | 0.0 | 0.0 |
| `Kt_phase_peak` | 3.0 | 3.0 | 0.0 | 0.0 |
| `Kt_phase_rms` | 4.242640687119286 | 4.242640687119286 | 0.0 | 0.0 |
| `P_electromagnetic` | 120.0 | 120.0 | 0.0 | 0.0 |
| `T` | 12.0 | 12.0 | 0.0 | 0.0 |

测试结论：通过

### Case 2：`analytical_case_2_rpm_conversion`

输入：

| 量 | 数值 |
|---|---:|
| `mechanical_speed_rpm` | 1000.0 |
| `mechanical_angular_speed_rad_s` | 104.71975511965977 |
| `back_emf_phase_peak_v` | 24.0 |
| `back_emf_phase_rms_v` | 16.97056274847714 |
| `back_emf_line_rms_v` | 29.393876913398135 |
| `phase_current_peak_a` | 6.0 |
| `phase_current_rms_a` | 4.242640687119285 |

手算关系：

- `omega_m = 1000 * 2π / 60 = 104.71975511965977`
- `Ke_line_rms_per_krpm = 29.393876913398135 / 1 = 29.393876913398135`
- `P = (3/2) * 24 * 6 = 216`
- `T = 216 / 104.71975511965977 = 2.0626480624709638`

对比：

| 量 | expected | actual | 绝对误差 | 相对误差 |
|---|---:|---:|---:|---:|
| `Ke_phase_peak` | 0.2291831180523293 | 0.2291831180523293 | 0.0 | 0.0 |
| `Ke_phase_rms` | 0.1620569369082791 | 0.1620569369082791 | 0.0 | 0.0 |
| `Ke_line_rms` | 0.2806908484441234 | 0.2806908484441234 | 0.0 | 0.0 |
| `Ke_line_rms_per_krpm` | 29.393876913398135 | 29.393876913398135 | 0.0 | 0.0 |
| `Kt_phase_peak` | 0.34377467707849396 | 0.34377467707849396 | 0.0 | 0.0 |
| `Kt_phase_rms` | 0.48617081072483737 | 0.48617081072483737 | 0.0 | 0.0 |
| `P_electromagnetic` | 216.0 | 216.0 | 0.0 | 0.0 |
| `T` | 2.0626480624709638 | 2.0626480624709638 | 0.0 | 0.0 |

测试结论：通过

### Case 3：`analytical_case_3_low_speed_high_torque`

输入：

| 量 | 数值 |
|---|---:|
| `mechanical_speed_rpm` | 60.0 |
| `mechanical_angular_speed_rad_s` | 6.283185307179585 |
| `back_emf_phase_peak_v` | 6.0 |
| `back_emf_phase_rms_v` | 4.242640687119285 |
| `back_emf_line_rms_v` | 7.348469228349534 |
| `phase_current_peak_a` | 12.0 |
| `phase_current_rms_a` | 8.48528137423857 |

手算关系：

- `omega_m = 60 * 2π / 60 = 2π`
- `P = (3/2) * 6 * 12 = 108`
- `T = 108 / (2π) = 17.1887338539247`

对比：

| 量 | expected | actual | 绝对误差 | 相对误差 |
|---|---:|---:|---:|---:|
| `Ke_phase_peak` | 0.9549296585513722 | 0.9549296585513722 | 0.0 | 0.0 |
| `Ke_phase_rms` | 0.6752372371178296 | 0.6752372371178296 | 0.0 | 0.0 |
| `Ke_line_rms` | 1.1695452018505144 | 1.1695452018505144 | 0.0 | 0.0 |
| `Ke_line_rms_per_krpm` | 122.4744871391589 | 122.4744871391589 | 0.0 | 0.0 |
| `Kt_phase_peak` | 1.4323944878270582 | 1.4323944878270582 | 0.0 | 0.0 |
| `Kt_phase_rms` | 2.0257117113534893 | 2.0257117113534893 | 0.0 | 0.0 |
| `P_electromagnetic` | 108.0 | 108.0 | 0.0 | 0.0 |
| `T` | 17.1887338539247 | 17.1887338539247 | 0.0 | 0.0 |

测试结论：通过

### Case 4：`analytical_case_4_high_speed_low_torque`

输入：

| 量 | 数值 |
|---|---:|
| `mechanical_speed_rpm` | 6000.0 |
| `mechanical_angular_speed_rad_s` | 628.3185307179587 |
| `back_emf_phase_peak_v` | 12.0 |
| `back_emf_phase_rms_v` | 8.48528137423857 |
| `back_emf_line_rms_v` | 14.696938456699067 |
| `phase_current_peak_a` | 0.8 |
| `phase_current_rms_a` | 0.565685424949238 |

手算关系：

- `omega_m = 6000 * 2π / 60 = 628.3185307179587`
- `P = (3/2) * 12 * 0.8 = 14.4`
- `T = 14.4 / 628.3185307179587 = 0.02291831180523293`

对比：

| 量 | expected | actual | 绝对误差 | 相对误差 |
|---|---:|---:|---:|---:|
| `Ke_phase_peak` | 0.01909859317102744 | 0.01909859317102744 | 0.0 | 0.0 |
| `Ke_phase_rms` | 0.01350474474235659 | 0.01350474474235659 | 0.0 | 0.0 |
| `Ke_line_rms` | 0.02339090403701028 | 0.02339090403701028 | 0.0 | 0.0 |
| `Ke_line_rms_per_krpm` | 2.449489742783178 | 2.449489742783178 | 0.0 | 0.0 |
| `Kt_phase_peak` | 0.02864788975654116 | 0.02864788975654116 | 0.0 | 0.0 |
| `Kt_phase_rms` | 0.040514234227069776 | 0.040514234227069776 | 0.0 | 0.0 |
| `P_electromagnetic` | 14.4 | 14.4 | 0.0 | 0.0 |
| `T` | 0.02291831180523293 | 0.02291831180523293 | 0.0 | 0.0 |

测试结论：通过

## 8. 误差汇总

| case_id | 最大绝对误差 | 最大相对误差 | 结果 |
|---|---:|---:|---|
| `analytical_case_1_basic_integer` | 0.0 | 0.0 | 通过 |
| `analytical_case_2_rpm_conversion` | 0.0 | 0.0 | 通过 |
| `analytical_case_3_low_speed_high_torque` | 0.0 | 0.0 | 通过 |
| `analytical_case_4_high_speed_low_torque` | 0.0 | 0.0 | 通过 |

## 9. 本阶段证明了什么

- revised PMSM `Ke` / `Kt` 在当前三相、Y 接、正弦稳态假设下可以被独立手算
- production calculation functions 与独立 analytical expected 值数值一致
- `torque = power / omega`
- `torque = Kt_phase_peak * I_phase_peak`
- `torque = Kt_phase_rms * I_phase_rms`
- revised 输出仍未影响 legacy 下游默认链路

## 10. 本阶段没有证明什么

本阶段尚未证明：

- FEA 一致性
- 台架实验一致性
- 公开论文 benchmark 一致性
- 完整材料、几何、磁路和绕组参数闭环下的样机真实性能
- BLDC `Ke` / `Kt` 正确性

因此，Phase 3D 的结论是：

- revised PMSM `Ke` / `Kt` 已通过 analytical validation
- 但这仍不等于 experimental validation
