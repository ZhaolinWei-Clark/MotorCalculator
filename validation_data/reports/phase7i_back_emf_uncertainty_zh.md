# Phase 7I AFPM 反电势不确定性包络

## 1. 边界声明

假设标签：`PROJECT-DEMONSTRATION ASSUMPTIONS`。本报告仅回答显式参数变化会让模型预测移动多少。它不是实际误差保证，不包含 model-form error，也不是实验或 FEA 验证。

## 2. 核心结果

- 指标：`back_emf_phase_fundamental_rms_v`
- nominal prediction：33.329273 V
- parameter-bound envelope：28.466740 - 38.757257 V
- Monte Carlo P10 / P50 / P90：32.150113 / 33.340058 / 34.534283 V
- Monte Carlo standard deviation：0.915269 V
- confidence：`LOW`
- model-form uncertainty：`UNQUANTIFIED`
- external validation coverage：`LIMITED`

## 3. 参数定义

| 参数 | Kind | Nominal | Bounds / PDF | Provenance |
|---|---|---:|---|---|
| magnet_remanence_t | NORMAL | 1.2 T | mean=1.2, sigma=0.024, bounds=[1.128, 1.272] | PROJECT-DEMONSTRATION ASSUMPTION: mean equals frozen Phase 7H Br; sigma=2% and bounds=mean +/- 3 sigma chosen only for software demonstration. |
| air_gap_m | UNIFORM | 0.001 m per side | [0.00095, 0.00105] | PROJECT-DEMONSTRATION ASSUMPTION: +/-0.05 mm around the frozen Phase 7H per-side physical gap. |
| magnet_thickness_m | RANGE | 0.005 m | [0.0048, 0.0052] | PROJECT-DEMONSTRATION ASSUMPTION: bounded engineering exploration only. |
| winding_factor | NORMAL | 0.933013 1 | mean=0.933013, sigma=0.00933013, bounds=[0.905022, 0.961003] | PROJECT-DEMONSTRATION ASSUMPTION: mean equals frozen 12-slot/10-pole analytical projection kw; sigma=1% and bounds=mean +/- 3 sigma. |
| turns_per_phase | EXACT | 100 turn | no variation / no declared distribution | Frozen Phase 7H winding definition: 25 turns per coil and four series coils per phase. |
| inner_radius_m | RANGE | 0.05 m | [0.04975, 0.05025] | PROJECT-DEMONSTRATION ASSUMPTION: +/-0.25 mm bounded geometry exploration. |
| outer_radius_m | RANGE | 0.1 m | [0.09975, 0.10025] | PROJECT-DEMONSTRATION ASSUMPTION: +/-0.25 mm bounded geometry exploration. |
| magnet_arc_ratio | UNIFORM | 0.7 1 | [0.68, 0.72] | PROJECT-DEMONSTRATION ASSUMPTION: explicit bounded uniform PDF around the frozen scalar magnet coverage. |
| magnet_relative_permeability | UNKNOWN | 1.05 1 | no variation / no declared distribution | Frozen Phase 7H controlled nominal; no defensible uncertainty distribution declared. |

`RANGE` 不参与 Monte Carlo；`UNKNOWN` 保持 nominal 并产生警告。所有非 exact 数值均为项目演示假设，不是通用制造公差。

## 4. One-at-a-time sensitivity

| Rank | 参数 | Output low | Output nominal | Output high | Absolute range | Normalized sensitivity |
|---:|---|---:|---:|---:|---:|---:|
| 1 | magnet_remanence_t | 31.329517 | 33.329273 | 35.329029 | 3.999513 | 1.000000 |
| 2 | winding_factor | 32.329395 | 33.329273 | 34.329151 | 1.999756 | 1.000000 |
| 3 | magnet_arc_ratio | 32.377008 | 33.329273 | 34.281538 | 1.904530 | 1.000000 |
| 4 | magnet_thickness_m | 32.632840 | 33.329273 | 33.999048 | 1.366207 | 0.522388 |
| 5 | outer_radius_m | 33.107356 | 33.329273 | 33.551746 | 0.444390 | 2.670000 |
| 6 | air_gap_m | 33.500863 | 33.329273 | 33.159432 | 0.341431 | -0.102966 |
| 7 | inner_radius_m | 33.440093 | 33.329273 | 33.217898 | 0.222195 | -0.668333 |

## 5. Parameter-bound envelope

模式：`FULL_CORNERS`；评估 2187 个 lower/nominal/upper 组合，有效 2187，拒绝 0。

观察到的 minimum / maximum：28.466740 / 38.757257 V。该区间必须称为 parameter-bound prediction envelope，不能称为 confidence interval。

## 6. Monte Carlo

seed=20260701，requested=5000，valid=4981，rejected=19。

P05/P10/P50/P90/P95 = 31.843268 / 32.150113 / 33.340058 / 34.534283 / 34.865999 V。

这些是 declared demonstration distributions 下的 sample percentiles，不是 90% 或 95% 真实置信区间。

Correlation-based variance association（不是 Sobol index）：

| 参数 | Normalized r-squared association |
|---|---:|
| magnet_remanence_t | 51.575% |
| magnet_arc_ratio | 34.304% |
| winding_factor | 13.105% |
| air_gap_m | 1.017% |

## 7. Numerical 与 model-form uncertainty

100-to-500 radial-slice numerical difference：0.000000000000%。当前常数 magnet coverage 下 midpoint radial integral 对线性半径项给出相同结果；这不代表物理模型无误差。

Model-form uncertainty 保持 `UNQUANTIFIED`，未进入 sweep 或 Monte Carlo。未量化项包括 leakage、fringing、简化磁路、未建模 saturation、线圈/磁体三维几何和 topology abstraction。

## 8. Confidence 与 readiness

结果为 `LOW`：拓扑和数值积分路径可执行，但外部 AFPM 电磁验证 coverage limited，存在 UNKNOWN 参数，且 model-form error 未量化。因此不允许 HIGH。

框架的数据结构已可供未来 GUI 只读展示，但 Phase 7I 不接入 GUI。建议 Phase 7J 仅实现 optional user validation feedback，并继续把用户观测、参数 uncertainty 与 model-form discrepancy 分开。

## 9. Phase 6A 对比

Phase 6A 提供 production input 上的局部百分比工程敏感性；Phase 7I 新增显式 uncertainty kinds、非概率边界包络、带 seed 的 Monte Carlo、percentile、拒绝原因以及外部验证/模型形式 readiness 语境。两者都不写回 production，也不执行 calibration。

## 10. Warnings

- This is a parameter-bound envelope, not a confidence interval.
- Model-form uncertainty is not included.
- UNKNOWN parameters held nominal: magnet_relative_permeability.
- Percentiles describe samples under declared parameter distributions; they are not confidence intervals.
- RANGE parameters held nominal because no PDF is declared: magnet_thickness_m, inner_radius_m, outer_radius_m.
- UNKNOWN parameters held nominal and unsampled: magnet_relative_permeability.
- External AFPM electromagnetic validation coverage remains limited.
- The envelope quantifies parameter movement only; it is not the true model error range.
