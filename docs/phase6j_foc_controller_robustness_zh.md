# Phase 6J：FOC Controller Robustness Foundation

## 1. 阶段边界

Phase 6J 只增强 `motor_calculator/dynamics/` sandbox 中的 FOC 电流控制鲁棒性。它增加可选 PI back-calculation anti-windup、显式 inverter saturation feedback，以及可选 PMSM dq decoupling feedforward。

所有新能力默认关闭。`anti_windup_gain=0` 且 `use_decoupling_feedforward=False` 时，Phase 6G/6I 的 PI-only 行为保持不变。本阶段不修改 PMSM plant equations、production calculator、GUI 或 legacy baseline。

## 2. 为什么饱和会导致积分 windup

PI controller 先计算未受限电压命令：

```text
u = Kp * error + Ki * integral
```

当 dq 命令幅值超过 DC bus 可实现的包络时，inverter limiter 只能施加 `u_sat`。如果积分器仍只根据持续存在的 current error 累积，它会继续把内部命令推向更大的不可实现电压。离开饱和后，过大的 integral state 需要较长时间释放，可能造成 overshoot 和恢复延迟。

## 3. Back-calculation anti-windup

Phase 6J 使用可选 back-calculation：

```text
integrator_dot = error + Kaw * (u_sat - u)
```

其中：

- `u` 是 raw controller voltage command。
- `u_sat` 是 inverter 实际施加的 saturated voltage command。
- `Kaw` 是非负 anti-windup gain。

离散实现中，`compute()` 先执行原有 error integration：

```text
integral += error * dt
```

随后 inverter feedback hook 执行：

```text
integral += Kaw * (u_sat - u) * dt
```

两次更新合起来就是指定的 forward-Euler back-calculation 方程。`Kaw=0` 时第二项严格为零，因此默认行为与 Phase 6G 一致。`reset()` 仍将 integral state 清零。

## 4. Saturation feedback path

更新后的信号链为：

```text
dq PI + optional feedforward
            |
            v
raw voltage command
            |
            v
inverter voltage limiter
            |
            v
saturated / actual voltage command
            |
            +----> PMSM dq plant
            |
            +----> PI anti-windup feedback
```

`DQSaturationFeedback` 和 `FOCStepOutput` 提供以下只读信息：

- `raw_voltage_command`
- `saturated_voltage_command`
- `saturation_error = saturated - raw`
- `saturation_active`

controller、inverter 和 plant 仍是独立组件。FOC runner 只把 inverter 的实际输出反馈给 controller hook，不把限幅公式合并进 PI。

## 5. PMSM dq coupling

现有 PMSM plant 电压方程包含速度相关耦合项：

```text
Vd = Rs*id + Ld*did/dt - omega_e*Lq*iq
Vq = Rs*iq + Lq*diq/dt + omega_e*(Ld*id + psi_f)
```

随着 `omega_e` 增大，纯 PI 必须同时补偿 current error 和 dq coupling/back-EMF。Phase 6J 提供并行、可选的解析 feedforward 基础，但不改变上述 plant equations。

## 6. Decoupling feedforward

可选 feedforward 为：

```text
Vd_ff = -omega_e * Lq * iq
Vq_ff =  omega_e * (Ld*id + psi_f)
```

最终 raw command 为：

```text
Vd_command = Vd_PI + Vd_ff
Vq_command = Vq_PI + Vq_ff
```

`use_decoupling_feedforward=False` 时 helper 返回 `(0, 0)`，FOC runner 保持 PI-only 路径。启用后，最终 raw command 仍先经过相同 inverter limiter；若发生 saturation，raw 与 actual 的总电压差反馈给 PI anti-windup。

本阶段不声称 feedforward 已覆盖参数误差、磁饱和、采样延迟或离散控制延迟。

## 7. 为什么仍不是完整 FOC

- 没有 speed loop。
- 没有 current/voltage sensor models。
- 没有 encoder model 或 rotor-angle observer。
- 没有 PWM switching。
- 没有 SVPWM sector/modulation implementation。
- 没有 field weakening 或 MTPA。
- 没有 dead time、器件压降或 switching loss。
- 没有 automatic PI tuning。
- 没有 thermal model。

Phase 6J 只建立可选鲁棒性机制及其验证基线。Anti-windup gain 和 PI gains 不会自动拟合、校准或写回 production model。
