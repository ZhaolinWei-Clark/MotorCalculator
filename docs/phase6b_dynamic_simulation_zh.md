# Phase 6B：PMSM 动态仿真基础

## 1. 阶段边界

Phase 6B 在 `motor_calculator/dynamics/` 中建立独立的时域仿真沙盒。它回答“给定动态参数、初始状态和时变输入后，状态如何随时间演化”，不回答“参数应校准为什么值”。

本阶段不替换 steady-state analytical calculator，不修改 production calculation chain，不读取或写回默认参数，也不把示例结果作为 calibration 或实机精度证据。

## 2. 状态、输入与参数

状态向量为：

\[
x = [i_d,\ i_q,\ \omega_m,\ \theta]^T
\]

- `id`、`iq`：dq 轴电流，单位 A。
- `omega_m`：机械角速度，单位 rad/s。
- `theta`：未折返的机械转子角度，单位 rad。

输入向量为：

\[
u = [V_d,\ V_q,\ T_L]^T
\]

- `Vd`、`Vq`：dq 轴电压，单位 V。
- `load_torque`：负载转矩，单位 N·m。

独立沙盒参数 `PMSMDynamicParameters` 包含 `Rs`、`Ld`、`Lq`、`psi_f`、`pole_pairs`、`J` 和 `B`。它们全部显式使用 SI 单位，并检查有限性、正值或非负值约束。这些参数没有与 production 默认值建立自动映射。

## 3. 模型方程

电角速度：

\[
\omega_e = p\omega_m
\]

d 轴电流导数：

\[
\frac{di_d}{dt} = \frac{V_d-R_s i_d+\omega_e L_q i_q}{L_d}
\]

q 轴电流导数：

\[
\frac{di_q}{dt} = \frac{V_q-R_s i_q-\omega_e(L_d i_d+\psi_f)}{L_q}
\]

电磁转矩：

\[
T_e = \frac{3}{2}p[\psi_f i_q+(L_d-L_q)i_d i_q]
\]

表贴式 PMSM 在 `Ld = Lq` 时，磁阻转矩项为零：

\[
T_e = \frac{3}{2}p\psi_f i_q
\]

机械速度和位置导数：

\[
\frac{d\omega_m}{dt}=\frac{T_e-T_L-B\omega_m}{J}
\]

\[
\frac{d\theta}{dt}=\omega_m
\]

机械功率一致性检查采用：

\[
P_{mech}=T_e\omega_m
\]

`PMSMDynamicModel` 只计算瞬时导数、转矩和机械功率代数，不执行积分。

## 4. 积分与运行架构

首个积分器为显式 Euler：

\[
x_{k+1}=x_k+\dot{x}_k\Delta t
\]

`EulerIntegrator.step()` 与模型解耦；`SimulationRunner` 接收初始状态、动态参数、常量输入或时间输入函数、总仿真时间和步长，并返回等长的 `time`、`id`、`iq`、`speed`、`position`、`torque` 元组。该边界允许未来增加 RK4 或 `solve_ivp`，无需改写 dq 方程。

Euler 是一阶显式方法，稳定性和精度强烈依赖步长。本阶段不提供自适应步长、误差估计或刚性系统求解能力。

## 5. 首批示例

三个示例位于 `motor_calculator/dynamics/examples.py`，使用公开、纯合成的演示参数，不代表 AFPM 默认模型或任何 calibrated motor。

1. Motor startup：从零电流、零转速开始施加恒定 `Vq = 24 V`，1 s 后速度约为 `58.418132 rad/s`。
2. Load step：1 s 前 `TL = 0`，1 s 后 `TL = 1 N·m`；速度由约 `58.418132 rad/s` 降至 2 s 时约 `48.945515 rad/s`，`iq` 响应到约 `1.829811 A`。
3. Steady-state verification：恒定 `Vq = 24 V`、`TL = 1 N·m` 仿真 5 s；最终 `Te` 约为 `1.097891 N·m`，与 `TL + B*omega_m` 平衡，`domega/dt` 接近零。

这些结果只验证代码路径与方程行为，不是 accuracy claim，也不得作为校准值。

## 6. 仿真假设

- 三相 PMSM 使用同步旋转 dq 坐标系的集中参数模型。
- `Rs`、`Ld`、`Lq`、`psi_f`、`J`、`B` 在单次仿真中保持常数。
- 转子位置是机械角度且不执行 `2*pi` 折返。
- 负载转矩由输入函数直接给定。
- 电源直接以理想 `Vd/Vq` 输入表示，不建模逆变器与直流母线约束。
- 示例的 `Ld = Lq`，对应表贴式 PMSM 的零磁阻转矩特例；核心方程仍支持 `Ld != Lq`。

## 7. 当前限制

以下能力尚未实现：

- FOC controller
- current controller
- inverter switching
- PWM
- magnetic saturation
- iron loss
- thermal model
- parameter calibration
- BLDC dynamic model
- FEA

此外，当前仅有显式 Euler 积分器，没有电压/电流限幅、齿槽转矩、空间谐波、机械弹性、传感器模型或数值误差控制。

## 8. 后续扩展

合理的后续顺序是先增加 RK4 与步长收敛测试，再定义动态参数与 steady-state 输出之间的只读、可追踪映射。控制器、逆变器、PWM、损耗和热模型应继续作为分层模块加入，不应把控制逻辑或动态状态写入 production analytical calculation chain。
