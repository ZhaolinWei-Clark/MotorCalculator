# Phase 6C 动态仿真验证报告

## 1. Sandbox boundary

本报告只记录 PMSM dynamic sandbox 的数值求解验证。没有执行 calibration、参数优化或 production 写回；没有修改 steady-state calculation chain、默认参数、GUI 行为或 legacy expected outputs。

验证使用 Phase 6B 的纯合成示例参数。所有数值结论只支持“求解器在这个测试问题上的数值行为”，不支持真实电机 accuracy claim。

## 2. Euler vs RK4 comparison

RK4 会在四个 stage 的中间状态重新计算 PMSM dq 导数。Euler 与 RK4 共用 `MotorState`、`StateDerivatives` 和 `step(state, derivatives, dt)` 边界。

在 `0.2 s` 启动/带载瞬态、`dt=1e-2 s` 下：

- Euler 产生数量级达到 `1e80` 至 `1e132` 的状态/输出，判定为 numerical unstable。
- RK4 保持有限：final speed `50.834682 rad/s`、torque `0.842101 N*m`、current magnitude `3.260085 A`。
- 这说明当前示例不能安全地把 `10 ms` 作为 Euler 步长，但不代表所有模型或所有 RK4 步长都稳定。

## 3. Timestep convergence

以 `RK4, dt=1e-4 s` 为相对数值参考：

| Solver | dt (s) | Speed rel. error | Torque rel. error | Current rel. error |
|---|---:|---:|---:|---:|
| Euler | 1e-2 | 8.498249e78 | 5.788737e132 | 2.498484e132 |
| Euler | 1e-3 | 1.246071e-3 | 8.431765e-3 | 8.063108e-3 |
| Euler | 1e-4 | 1.222943e-4 | 8.310752e-4 | 7.928560e-4 |
| RK4 | 1e-2 | 1.849984e-4 | 9.481329e-5 | 9.967275e-5 |
| RK4 | 1e-3 | 8.298443e-9 | 5.678370e-8 | 5.552167e-8 |
| RK4 | 1e-4 | 0 | 0 | 0 |

RK4 的 final speed、final torque 和 final current 均随步长减小而收敛。Euler 在 `1e-3` 到 `1e-4 s` 区间也显示误差下降，但粗步长不稳定。

## 4. Dynamic steady-state comparison

机械稳态参考关系为 `Te = TL + B*omega_m`。5 s RK4 仿真末端：

| Metric | Value |
|---|---:|
| `domega/dt` | 3.508305e-12 rad/s^2 |
| `Te_dynamic` | 1.09789096328 N*m |
| `TL + B*omega_m` | 1.09789096328 N*m |
| Relative error | 3.195495e-14 |

结果验证了 dynamic mechanical equation 的内部稳态一致性。production steady-state model 未参与计算，也未被修改。

## 5. Energy consistency monitoring

新增只读监测量 `Pinput = Vd*id + Vq*iq` 和 `Pmech = Te*omega_m`。趋势如下：

| Time (s) | Pinput (W) | Pmech (W) | Pinput-Pmech (W) |
|---:|---:|---:|---:|
| 0.01 | 675.911356 | 156.336180 | 519.575176 |
| 0.10 | 72.123920 | 79.545069 | -7.421149 |
| 0.50 | 44.042859 | 53.864732 | -9.821874 |
| 1.00 | 43.915848 | 53.737013 | -9.821165 |
| 5.00 | 43.915639 | 53.736802 | -9.821163 |

该差值只是一条 raw trend。由于题目指定的 dq 电功率定义不含变换归一化系数，且本阶段没有铜耗、铁耗、储能变化或热模型，不能把差值命名为 loss、efficiency error 或 calibration residual。

## 6. Known limitations

- 无自适应步长、误差控制、刚性求解器或独立解析瞬态参考。
- 无 FOC、current controller、inverter switching、PWM、磁饱和、铁耗、热模型或 BLDC dynamic model。
- 没有 parameter calibration，也没有 production 参数映射或写回。
- 细步长 RK4 仅作为本次内部收敛参考，不是外部 benchmark。
- Euler 的稳定步长必须针对具体参数和输入重新评估。

## 7. Conclusion

Phase 6C 将 Phase 6B 从单一 Euler 原型扩展为具有真实 RK4 stage 重算、时间步收敛证据、机械稳态一致性检查和功率趋势监测的数值验证基础。本阶段不提出任何 calibrated value。
