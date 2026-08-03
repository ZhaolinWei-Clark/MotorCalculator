# Phase 6K：PMSM Speed Control Loop Foundation

## 1. 阶段边界

Phase 6K 只在 `motor_calculator/dynamics/` sandbox 中增加 PMSM 外层 speed PI 和 multi-rate cascaded runner。它不修改 production calculator、GUI、PMSM plant equations、Clarke/Park transforms 或 legacy baseline。

本阶段仍使用 ideal mechanical speed feedback。Speed controller 只生成 `id_ref/iq_ref`，不会直接生成或限制 voltage command。

## 2. 外层 speed loop 与内层 current loop

```text
omega_ref
    |
    v
SpeedController
    |
    +---- id_ref = 0 A
    |
    +---- bounded iq_ref
              |
              v
DQCurrentController
              |
              v
Vd/Vq command
              |
              v
InverterVoltageLimiter
              |
              v
PMSM dq plant
              |
              +---- omega_m ideal feedback
```

外环根据 speed error 调整 torque-producing q-current reference。内环仍使用 Phase 6G/6J dq PI，根据 `id_ref/iq_ref` 产生 `Vd/Vq`。因此 speed controller 与 voltage、inverter 和 plant 公式保持分离。

## 3. 为什么 current loop 应更快

Speed loop 假设 inner current loop 能较快实现所请求的 current/torque。如果两者速度相近，外环可能在 inner loop 尚未响应时继续增加 demand，导致更强耦合和较差阻尼。

Phase 6K 的保守 sandbox 默认时标为：

```text
plant integration: 100 us  = 10 kHz
current control:   500 us  =  2 kHz
speed control:       5 ms  = 200 Hz
```

`SpeedControlRunnerConfig` 要求 current period 小于 speed period，并要求两个 control period 都是 plant step 的整数倍。它属于工程 sandbox 配置，未接入正常 user-oriented simulation API。

## 4. Speed PI 与 iq reference

Speed error：

```text
error_omega = omega_ref - omega_measured
```

未限制 q-current demand：

```text
integral_error += error_omega * dt
iq_ref_raw = Kp_speed * error_omega + Ki_speed * integral_error
```

显式 current limit：

```text
iq_ref_actual = clamp(iq_ref_raw, iq_min, iq_max)
```

Baseline SPMSM strategy 固定：

```text
id_ref = default_id_ref_a = 0 A
```

这不是 MTPA，也不包含 field weakening。负 `iq_ref` 仅在配置的 `iq_min_a` 允许时用于反向 torque demand。

## 5. Current limiting 与 warning metadata

当 raw demand 超出 `iq_min_a/iq_max_a` 时：

- `iq_ref_actual_a` 被 clamp。
- `current_limit_active=True`。
- `saturation_error_a = iq_ref_actual_a - iq_ref_unsaturated_a`。
- Simulation result 增加 `current_limit_count`。
- Warning 明确记录 q-current reference 到达配置上限。

该限制只作用于 speed-loop 输出。Phase 6K 尚未实现总 current circle、`sqrt(id^2+iq^2)` 优化、MTPA 或 voltage-based field weakening。

## 6. Speed-loop anti-windup

可选 back-calculation 与 Phase 6J current PI 采用相同思想：

```text
integrator_dot = error_omega + Kaw_speed * (iq_ref_actual - iq_ref_raw)
```

离散更新为：

```text
integral_error += error_omega * dt
integral_error += Kaw_speed * saturation_error_a * dt
```

`anti_windup_gain=0` 明确关闭 feedback。Controller state 只能由 `update()` 和 `reset()` 修改，`state` 返回 frozen snapshot，不向 runner 暴露可写 integral。

## 7. Sandbox simulation cases

### Case A：Speed startup

Speed reference 在 20 ms 后从 `0` 变为 `40 rad/s`。示例使用 48 V DC bus 和 `+/-5 A` q-current limit，观察 speed、`iq_ref`、actual `iq`、torque 与 voltage saturation。

### Case B：Load torque step

Speed reference 保持 `30 rad/s`，在 1 s 时将 load torque 从 `0` 增加到 `1 N*m`。预期 speed 暂时下降，`iq_ref` 和 torque demand 增加，然后 speed 向 reference 恢复。

### Case C：Unreachable speed

使用 24 V DC bus、`+/-3 A` q-current limit、`0.5 N*m` load，并请求 `300 rad/s`。该工况用于确认 current demand 被限制、voltage saturation 可见、warning 被记录且数值保持有限，不用于证明目标可达。

## 8. 当前限制

- 没有 MTPA。
- 没有 field weakening。
- 没有 PWM switching。
- 没有 SVPWM。
- 使用 ideal speed feedback。
- 没有 encoder model、observer、噪声或采样延迟。
- 没有 automatic PI tuning。
- 没有 torque optimization 或 combined current-circle limit。
- 没有 thermal model、器件保护或 fault handling。

Phase 6K 只建立外层 speed control 的结构、限制和数值验证基础。它不执行 calibration，也不写回 production model。
