# Phase 6I：FOC Runner Skeleton

## 1. 本阶段新增内容

Phase 6I 在 `motor_calculator/dynamics/foc_runner.py` 中增加 sandbox-only FOC 信号链编排。它连接 Phase 6B-6H 已验证的坐标变换、dq PI 电流控制器、DC bus 电压包络和 PMSM dq plant，但不修改这些组件的公式或行为。

新增的核心接口为：

- `FOCReference`：直接给定 `id_ref_a` 和 `iq_ref_a`。
- `FOCStepInput`：理想 abc 电流反馈、机械角、机械速度和负载转矩。
- `FOCRunnerConfig`：极对数、控制周期和是否启用逆变器限幅。
- `FOCRunner.step()`：执行一次变换、控制、限幅和 plant 积分。
- `FOCStepOutput`：记录测量 dq 电流、命令/实际 dq 电压、限幅状态、转矩、速度和警告。
- `run_foc_current_control_simulation()`：生成最小 dq 电流跟踪历史。

## 2. FOC 信号链

```text
ideal abc current feedback
          |
          v
amplitude-invariant Clarke transform
          |
          v
alpha-beta current
          |
          v
Park transform using theta_e = pole_pairs * theta_m
          |
          v
measured id / iq
          |
          v
dq PI current controller
          |
          v
Vd / Vq command
          |
          v
optional inverter voltage limiter
          |
          v
Vd / Vq actual
          |
          v
existing PMSM dq dynamic plant
```

Controller、inverter 和 plant 仍是独立对象。FOC runner 只负责确定调用顺序和数据流，不复制它们的内部方程。

## 3. One-step 语义

`FOCRunner.step()` 使用输入 abc 电流完成 Clarke/Park 变换，得到当前控制采样的 `id_measured_a` 和 `iq_measured_a`。PI 积分在该控制采样更新一次。

实际 dq 电压在一个控制周期内按零阶保持方式施加给现有 PMSM plant。`FOCStepOutput` 中：

- measured dq currents 是积分前的理想反馈值。
- commanded dq voltages 是 PI 输出。
- actual dq voltages 是可选 DC bus 限幅后的 plant 输入。
- torque 和 mechanical speed 是一个 plant 积分步后的结果。

`FOCRunnerConfig.pole_pairs` 必须与 `PMSMDynamicParameters.pole_pairs` 一致。启用 `use_inverter_limit` 时必须显式提供 `DCBusConfig`，避免静默退化为无限理想电压源。

## 4. 最小闭环仿真

`run_foc_current_control_simulation()` 直接使用内部 PMSM dq state。为了经过完整的测量变换链，它在每个控制步先用 inverse Park 和 inverse Clarke 将当前 dq 电流重建为 balanced abc 理想反馈，然后再通过正 Clarke/Park 变换送入 PI。

输出包含：

- time、id、iq 历史
- Vd/Vq command 历史
- Vd/Vq actual 历史
- torque、speed 历史
- voltage saturation count
- 去重后的 voltage-limit warnings

初始采样点的 command/actual voltage 记为零，因为该时刻尚未执行第一次控制更新。最后不足一个完整控制周期的时间段会使用实际余数步长，不会越过请求的 simulation time。

## 5. 仍然简化的内容

- 使用理想 current feedback，不含传感器动态。
- 没有 current sensor model、噪声、偏置或采样延迟。
- 机械角直接来自 state/input，没有 encoder sensor model 或 observer。
- 没有 PWM switching。
- 没有 SVPWM 或 modulation sector。
- 没有 speed loop。
- 没有 dead time、器件压降或 switching loss。
- 没有 current reconstruction。
- 没有 field weakening 或 MTPA。
- 没有 decoupling feedforward 或 back-EMF compensation。
- 没有 automatic PI tuning。
- 没有 anti-windup algorithm；Phase 6G hook 仍为 no-op。

## 6. 为什么仍是 sandbox-only

当前 runner 只验证信号链连接和基础 dq current tracking。它没有真实测量、调制、保护、实时调度、故障处理或硬件约束，因此不能替代工业电机控制器，也不能写入 production calculator 或用于参数校准。

## 7. Phase 6J 建议

建议 Phase 6J 继续以分层验证为优先，而不是立即加入全部工业功能：

1. 增加 FOC current-loop validation report，覆盖不同电角速度、负载和 DC bus 饱和工况。
2. 建立显式 rotor-angle provider 接口，为后续 ideal angle、encoder 和 observer 模型保留边界。
3. 在实现 speed loop 前，独立设计并验证 anti-windup 策略。
4. 将 decoupling/back-EMF feedforward 作为可选并行路径，保留当前纯 PI 基线。
5. 将 modulation/PWM 作为独立模块，不把开关逻辑写入 PMSM plant 或 PI controller。

每项扩展都应继续保持 sandbox-only，并为数值稳定性、坐标约定和饱和行为增加独立测试。
