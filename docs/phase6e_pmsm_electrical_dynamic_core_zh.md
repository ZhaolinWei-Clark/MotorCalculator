# Phase 6E：PMSM dq 电气-机械动态核心

## 1. 阶段审计与边界

Phase 6E 开始时的代码审计确认：Phase 6B 已在 `PMSMDynamicModel.compute_derivatives()` 中实现完整的 PMSM dq 电压方程、电角速度、电磁转矩和机械方程，`SimulationRunner` 也已经联合积分 `id`、`iq`、`omega_m` 与兼容性位置状态 `theta`。因此本阶段没有复制第二套物理公式，也没有替换现有 runner。

本阶段把电气导数和机械速度导数拆成可独立调用、可独立验证的边界，并增加解析参考测试。所有代码仍位于 dynamics sandbox，不修改 production calculation chain、默认参数、GUI behavior 或 legacy baseline。

## 2. 状态和输入

题目要求的耦合核心状态为：

\[
x_{core}=[i_d,\ i_q,\ \omega_m]^T
\]

现有 `MotorState` 继续保留 `theta`：

\[
x=[i_d,\ i_q,\ \omega_m,\ \theta]^T
\]

`theta` 的导数仍为 `omega_m`，它不改变 dq 电气方程或转矩关系。保留该字段避免破坏 Phase 6B-6D 的 state、integrator、runner 和 result 接口。

输入为：

\[
u=[V_d,\ V_q,\ T_L]^T
\]

所有内部量使用 SI 单位。

## 3. dq 电气方程

电角速度：

\[
\omega_e=p\omega_m
\]

d 轴电压：

\[
V_d=R_s i_d+L_d\frac{di_d}{dt}-\omega_eL_qi_q
\]

导数形式：

\[
\frac{di_d}{dt}=\frac{V_d-R_si_d+\omega_eL_qi_q}{L_d}
\]

q 轴电压：

\[
V_q=R_s i_q+L_q\frac{di_q}{dt}+\omega_e(L_di_d+\psi_f)
\]

导数形式：

\[
\frac{di_q}{dt}=\frac{V_q-R_si_q-\omega_e(L_di_d+\psi_f)}{L_q}
\]

`compute_electrical_derivatives()` 返回 immutable `DQElectricalDerivatives(did_dt, diq_dt, omega_e)`。原 `compute_derivatives()` 调用该方法，因此公式只有一个实现来源。

## 4. 电磁转矩和机械耦合

电磁转矩：

\[
T_e=\frac{3}{2}p[\psi_fi_q+(L_d-L_q)i_di_q]
\]

机械速度：

\[
\frac{d\omega_m}{dt}=\frac{T_e-T_L-B\omega_m}{J}
\]

`compute_mechanical_speed_derivative()` 保留以外部 `electromagnetic_torque` 驱动机械方程的兼容边界。完整 PMSM 路径由 dq 电流计算 `Te` 后调用同一机械方法；这保证电气-机械耦合和 torque-driven mechanical relationship 不会分叉成两套公式。

## 5. Runner behavior

`SimulationRunner` 无需修改即可支持完整耦合：每个 Euler/RK4 stage 都使用候选 `id`、`iq`、`omega_m` 重新计算 `omega_e`、dq 导数和 `Te`，然后同时推进电流、速度和位置。

既有 API 保持不变：

- `MotorState`
- `InputState`
- `PMSMDynamicParameters`
- `PMSMDynamicModel.compute_derivatives()`
- `SimulationRunner.run()`
- Euler/RK4 integrator contract
- Phase 6D user-oriented interface

## 6. 验证结果

Phase 6E 新增七类测试：

1. 零电压、零电流、零速度、零负载保持严格稳态。
2. 纯 d 轴恒压响应匹配独立 RL 解析解 `id=(Vd/Rs)*(1-exp(-Rs*t/Ld))`。
3. 恒定 q 轴电压产生正 `iq`、正电磁转矩和正机械加速度。
4. salient PMSM 的磁体转矩项与 reluctance torque 项匹配指定公式。
5. 三相 dq 功率满足：

\[
\frac{3}{2}(V_di_d+V_qi_q)
=\frac{3}{2}R_s(i_d^2+i_q^2)
+\frac{3}{2}(L_di_d\dot{i_d}+L_qi_q\dot{i_q})
+T_e\omega_m
\]

6. RK4 的 d 轴电流响应在 `dt=1e-2`、`1e-3`、`1e-4 s` 下向解析解收敛。
7. 外部转矩驱动的机械速度导数继续满足原机械方程。

这里的铜耗只作为方程能量恒等式中的电阻项，不是 production loss model，也没有写入 efficiency chain。

## 7. 限制

- 未实现 FOC 或 current controller。
- 未实现 PWM、逆变器开关或 DC bus saturation。
- 未实现磁饱和、交叉饱和、空间谐波或参数随温度变化。
- 未实现完整 iron-loss、thermal 或 FEA 模型。
- 未实现 BLDC dynamic model。
- 未执行 parameter calibration，也没有把 dynamic parameters 映射或写回 production defaults。
- 当前模型仍是集中参数、同步旋转 dq 坐标系模型。

## 8. Conclusion

Phase 6E 没有重复或替换已经存在的耦合模型，而是把它整理为可独立验证的 PMSM electrical core，并用解析电流响应、能量恒等式和 solver convergence 补强证据。它仍是 sandbox-only dynamic simulation work，不是 production physics switch。
