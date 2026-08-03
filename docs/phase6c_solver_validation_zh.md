# Phase 6C：动态求解器数值验证

## 1. 阶段边界

Phase 6C 只验证 `motor_calculator/dynamics/` 中 PMSM 时域仿真器的数值行为。它不执行参数校准，不修改 production calculation chain，不修改默认参数，也不把本报告中的合成示例结果作为实机精度证据。

## 2. RK4 实现

保留 Phase 6B 的显式 Euler 积分器，并新增经典四阶 Runge-Kutta：

\[
k_1=f(x_n,t_n)
\]

\[
k_2=f(x_n+\frac{\Delta t}{2}k_1,t_n+\frac{\Delta t}{2})
\]

\[
k_3=f(x_n+\frac{\Delta t}{2}k_2,t_n+\frac{\Delta t}{2})
\]

\[
k_4=f(x_n+\Delta t k_3,t_n+\Delta t)
\]

\[
x_{n+1}=x_n+\frac{\Delta t}{6}(k_1+2k_2+2k_3+k_4)
\]

`RK4Integrator.step(state, derivatives, dt)` 与 Euler 使用相同状态接口。runner 传入可调用的导数计算器，使 `k2`、`k3`、`k4` 在各自中间状态和子步输入时刻重新计算；固定 `StateDerivatives` 仅用于常导数场景。

## 3. 收敛试验设置

- 模型：Phase 6B 合成表贴式 PMSM 示例，`Rs=0.5 ohm`、`Ld=Lq=0.005 H`、`psi_f=0.1 Wb`、`pole_pairs=4`、`J=0.01 kg*m^2`、`B=0.002 N*m/(rad/s)`。
- 初始状态：`id=iq=omega_m=theta=0`。
- 输入：`Vd=0 V`、`Vq=24 V`、`TL=0.5 N*m`。
- 仿真时间：`0.2 s`。
- 步长：`1e-2 s`、`1e-3 s`、`1e-4 s`。
- 本阶段数值参考：`RK4, dt=1e-4 s`。该参考仅用于步长收敛，不是解析真值或外部验证数据。
- final current：`sqrt(id^2 + iq^2)`。

## 4. Euler 与 RK4 收敛结果

| Solver | dt (s) | Final speed (rad/s) | Final torque (N*m) | Final current (A) | Speed rel. error | Torque rel. error | Current rel. error | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Euler | 1e-2 | -4.319259e80 | 4.874238e132 | 8.144458e132 | 8.498249e78 | 5.788737e132 | 2.498484e132 | unstable |
| Euler | 1e-3 | 50.888611 | 0.834921 | 3.233476 | 1.246071e-3 | 8.431765e-3 | 8.063108e-3 | finite |
| Euler | 1e-4 | 50.831495 | 0.841321 | 3.257175 | 1.222943e-4 | 8.310752e-4 | 7.928560e-4 | finite |
| RK4 | 1e-2 | 50.834682 | 0.842101 | 3.260085 | 1.849984e-4 | 9.481329e-5 | 9.967275e-5 | finite |
| RK4 | 1e-3 | 50.825280 | 0.842021 | 3.259760 | 8.298443e-9 | 5.678370e-8 | 5.552167e-8 | finite |
| RK4 | 1e-4 | 50.825279 | 0.842021 | 3.259760 | 0 | 0 | 0 | reference |

当前示例的电气时间常数 `L/R` 为 `0.01 s`。Euler 在同量级的 `dt=0.01 s` 下发生数值发散；这是真实记录的数值稳定性失败，不代表物理电机发散。步长缩小后 Euler 呈一阶收敛趋势。RK4 在三个步长下均保持有限，并在 `dt=1e-3 s` 时已非常接近细步长参考。

## 5. 动态与稳态机械关系

使用 RK4、`dt=1e-3 s`、`TL=1 N*m` 运行 5 s。稳态机械方程直接给出：

\[
T_{e,steady}=T_L+B\omega_m
\]

结果：

- `omega_m = 48.9454816423 rad/s`
- `Te_dynamic = 1.09789096328 N*m`
- `TL + B*omega_m = 1.09789096328 N*m`
- torque relative error = `3.195495e-14`
- `domega/dt = 3.508305e-12 rad/s^2`

该比较验证动态机械方程的内部一致性，不调用、不替换 production steady-state torque formula。

## 6. 功率监测

Phase 6C 仅增加以下时间序列：

\[
P_{input}=V_d i_d+V_q i_q
\]

\[
P_{mech}=T_e\omega_m
\]

| Time (s) | Pinput (W) | Pmech (W) | Raw difference (W) |
|---:|---:|---:|---:|
| 0.01 | 675.911356 | 156.336180 | 519.575176 |
| 0.10 | 72.123920 | 79.545069 | -7.421149 |
| 0.50 | 44.042859 | 53.864732 | -9.821874 |
| 1.00 | 43.915848 | 53.737013 | -9.821165 |
| 5.00 | 43.915639 | 53.736802 | -9.821163 |

这里只报告趋势。题目指定的原始 dq 输入功率没有加入 Park 变换归一化系数，模型也未记录铜耗、磁场储能变化、铁耗或完整机械损耗，因此 `Pinput-Pmech` 不应被解释为效率、总损耗或能量守恒误差，更不能用于校准。

## 7. 已知限制

- `RK4, dt=1e-4 s` 是本阶段相对参考，不是独立解析解。
- 尚无自适应步长、局部截断误差估计或刚性系统求解器。
- 尚未实现 FOC/current controller、逆变器开关、PWM、磁饱和、铁耗、热模型、BLDC dynamic model 或 parameter calibration。
- 动态参数仍为合成示例值，未与 production 默认参数自动映射。
- 当前功率序列是监测量，不构成损耗或效率模型。
