# Phase 7E Radial Integration Convergence

## Sandbox Boundary

本报告验证 `advanced_afpm.radial_slice_back_emf` 的数值行为，不验证 production AFPM accuracy。测试案例是明确标记为 `synthetic_internal_only` 的分析案例，不是 published benchmark，不用于 calibration，也不向 `motor_core/calculations.py` 写回结果。

## Model Assumptions

radial-slice prototype 使用：

- midpoint rule，将 active annulus 从 `r_inner` 到 `r_outer` 等分为 `N` 个 radial slices；
- `B = Br * lm_total / (lm_total + mur * g_effective)`；
- `dA_pole = (pi / pole_pairs) * r * dr * local_magnet_arc_ratio(r)`；
- `dPhi = B * dA_pole`；
- `E_phase_fundamental_rms = 4.44 * f * N_phase * Phi_pole * kw`；
- SSDR 对称磁路使用两个 magnet layers；不使用 leakage、fringing、saturation、slotting 或经验 correction factor。

Synthetic case 固定输入：`ri=0.05 m`、`ro=0.10 m`、`g_effective=0.012 m`、`hm=0.005 m`、`p=5`、`Br=1.2 T`、`mur=1.05`、`100 turns/phase`、`kw=0.95`、`1000 rpm`。magnet arc ratio 只来自三点 profile：`(0.05, 0.45)`、`(0.075, 0.65)`、`(0.10, 0.80)`。

## Convergence Results

| slices N | phase fundamental RMS (V) | relative difference from previous |
|---:|---:|---:|
| 10 | 28.880808961008 | N/A |
| 50 | 28.889017692397 | 0.028414713% |
| 100 | 28.889274215253 | 0.000887952% |
| 500 | 28.889356302567 | 0.000284144% |

`N=100` 与 `N=500` 的绝对差为 `0.000082087314 V`。对当前 piecewise-linear profile，`N=100` 已提供远小于 `0.001%` 的 successive-resolution difference，因此推荐作为 sandbox 默认分辨率；`N=500` 用于 convergence reference，不代表 physics accuracy 更高。

## Mean-Radius Comparison

| method | predicted phase fundamental RMS |
|---|---:|
| mean-radius coverage at `r=0.075 m` | 28.583975370621 V |
| radial-slice midpoint, `N=500` | 28.889356302567 V |

absolute difference 为 `0.305380931945 V`，radial-slice 相对 mean-radius 高 `1.068364103%`。原因是 local magnet coverage 随半径增加，而 pole-area weighting 与 `r` 成正比；单一 mean-radius coverage 没有完整保留外半径区域的较高面积权重。

该差异只说明 radius-dependent geometry representation 能改变积分结果，不证明 synthetic profile 或 prototype 磁路比 production model 更接近真实电机。

## Limitations

- 仅输出 sinusoidal phase fundamental RMS back-EMF。
- 没有 harmonic/waveform synthesis。
- 没有 leakage、fringing、slotting、saturation、3D end effects 或 FEA field solution。
- winding factor 必须显式提供，绝不自动推导。
- effective nonmagnetic gap 必须显式提供或由 source geometry 安全推导。
- 数值收敛不等于 external accuracy validation。
