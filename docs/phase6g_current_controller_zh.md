# Phase 6G：PMSM dq 电流控制器基础

## 1. 阶段边界

Phase 6G 只在 `motor_calculator/dynamics/` 动态仿真沙盒中增加基础 dq 电流控制层。它不修改 production calculation chain、不改变 PMSM 微分方程、不写回任何参数，也不代表已完成 FOC。

本阶段的数据流为：

```text
id_ref / iq_ref
      |
      v
DQCurrentController（两个独立 PI）
      |
      v
Vd / Vq command
      |
      v
InverterVoltageLimiter
      |
      v
Vd / Vq actual
      |
      v
PMSMDynamicModel
```

## 2. 为什么控制器与电机模型分离

PMSM plant 描述给定实际 dq 电压和负载转矩后的电气、机械状态导数；电流控制器描述如何根据参考电流和测量电流产生电压命令；逆变器负责把命令限制在 DC bus 可实现的电压包络内。这三者具有不同职责和状态，不能合并成一个公式模块。

分离后可以：

- 在不改变 PMSM 方程的情况下替换或验证控制算法。
- 在不改变控制器的情况下替换积分器或逆变器模型。
- 明确区分 commanded voltage 与 physically applied voltage。
- 保持既有电压驱动 `SimulationRunner` 的 API 和结果不变。

## 3. PI 电流控制原理

d、q 轴电流误差分别为：

```text
error_d = id_ref - id
error_q = iq_ref - iq
```

每个轴使用相同形式的基础 PI：

```text
integral_next = integral_current + error * dt
output = Kp * error + Ki * integral_next
```

因此：

```text
Vd_command = Kp * error_d + Ki * integral(error_d)
Vq_command = Kp * error_q + Ki * integral(error_q)
```

`PIController` 保存可观察的 `integral_state`，并提供 `reset()`。`DQCurrentController.reset()` 同时清除 d、q 两个积分状态。

## 4. 闭环仿真编排

`CurrentControlSimulationRunner` 独立编排 controller、inverter 和 plant：

1. 在每个外部时间步读取 `DQCurrentReference`。
2. 根据当前 `id/iq` 更新一次 PI 并生成 dq 电压命令。
3. 可选地通过 `DCBusConfig` 和 `InverterVoltageLimiter` 获得实际 dq 电压。
4. 在该时间步内用零阶保持的实际电压推进现有 PMSM plant。

PI 积分只在外部控制采样更新一次，不在 RK4 的四个内部子阶段重复更新。当前控制周期与积分时间步相同，尚未建立独立的多速率控制调度器。

若未提供 `DCBusConfig`，闭环 runner 将 PI 输出作为理想 dq 电压命令直接施加；提供配置时会保留 Phase 6F 的限幅警告、计数和最大饱和比元数据。

## 5. Anti-windup 状态

Phase 6G 只提供 `apply_anti_windup()` 与 `track_applied_voltage()` 扩展钩子。钩子接收 commanded/applied voltage，但当前明确为 no-op，`anti_windup_enabled` 为 `False`。

这意味着持续电压饱和时积分仍可能累积。本阶段不声称已解决 integral windup，后续引入 back-calculation、conditional integration 或积分限幅时必须单独验证。

## 6. 当前限制

- 没有 abc/alpha-beta/dq 坐标变换，因此不是完整 FOC。
- 没有转子角度估算或传感器模型。
- 没有速度外环，也不会自动生成 `iq_ref`。
- 没有交叉耦合补偿、反电势前馈或电阻压降前馈。
- 没有 PI 自动整定、带宽设计或参数校准。
- 没有实际 anti-windup 算法。
- 没有 PWM、调制时序、开关纹波、死区或开关损耗。
- 没有电流采样延迟、量化、噪声和控制计算延迟。
- 没有电流限幅、过流保护或 MTPA/弱磁控制。

Phase 6G 的目标是建立可组合、可测试的 dq 电流 PI 基础，不是提高 production calculator 精度，也不是完成电机驱动控制系统。
