# Phase 6L：PMSM MTPA 与弱磁控制基础

## 1. 阶段边界

Phase 6L 在动态仿真 sandbox 中新增独立的电流参考优化层，不修改静态计算器、PMSM plant 方程、PI 电流控制器、逆变器模型、GUI 或默认输出。本阶段不执行参数辨识或自动校准，也不声称控制器达到工业应用等级。

默认配置保持：

- `enable_mtpa=False`
- `enable_field_weakening=False`

因此现有 FOC 输入仍直接作为 `id_ref/iq_ref` 进入电流 PI，Phase 6A-6K 行为不变。

## 2. MTPA 解决的问题

MTPA（Maximum Torque Per Ampere）尝试在给定电磁转矩要求下减小 dq 电流幅值：

```text
I = sqrt(id^2 + iq^2)
```

使用现有 PMSM 转矩关系：

```text
Te = (3/2) * p * [psi_f * iq + (Ld - Lq) * id * iq]
```

### SPMSM

当 `Ld` 与 `Lq` 近似相等时，磁阻转矩项接近零。本阶段明确采用：

```text
id_ref = 0
iq_ref = Te_ref / [(3/2) * p * psi_f]
```

### IPMSM

当 `Ld != Lq` 时，控制器在配置的 dq 电流圆内对 `id` 做确定性离散搜索，并由转矩方程反求 `iq`，选择电流幅值最小的可行点。典型 `Lq > Ld` 的 IPMSM 会得到负 `id`，从而利用磁阻转矩。

这不是基于损耗图、磁饱和图或标定数据的最优效率算法。若目标转矩不可达，返回电流圆边界上的最大可用转矩点并显式标记限流。若 `Ld/Lq` 无效，则安全回退到 `id=0` 策略。

## 3. 弱磁解决的问题

转速升高时，反电动势随电角速度增加。平均 dq 电压受逆变器包络约束：

```text
V_available = Vdc / sqrt(3)
sqrt(Vd^2 + Vq^2) <= V_available
```

本阶段使用稳态 dq 电压估算：

```text
Vd_est = Rs * id - omega_e * Lq * iq
Vq_est = Rs * iq + omega_e * (Ld * id + psi_f)
```

电压裕量定义为：

```text
voltage_margin = V_available - sqrt(Vd_est^2 + Vq_est^2)
```

当裕量为负且电角速度非零时，弱磁控制器生成受电流限制的负 `id`，降低 `Ld*id + psi_f` 有效磁链。本算法只提供稳定、可观测的基础命令，不求解完整电压椭圆与电流圆联合优化。

## 4. 转矩限制与电压限制

- 电流/转矩限制决定可产生多大的电磁转矩，主要受 `sqrt(id^2+iq^2)` 限制。
- 电压限制决定在给定转速下能否建立目标电流，主要受 DC bus 与反电动势限制。
- MTPA 优先处理电流利用率；弱磁在高转速电压不足时引入更多负 `id`。
- 两者同时启用时，最终 dq 参考仍会投影到配置的电流圆内。

## 5. FOC 接入顺序

```text
torque/current reference
        -> MTPA（可选）
        -> field weakening（可选）
        -> dq current PI
        -> inverter voltage limiter
        -> PMSM dq plant
```

FOC runner 只修改传给现有 PI 的有效电流参考；PI、anti-windup、逆变器限制与 plant 的职责保持分离。

## 6. 当前限制

- 无磁饱和、交叉饱和或随电流变化的 `Ld/Lq`。
- 无铁耗、铜耗最优化或效率地图，因此不能声称达到最优效率。
- IPMSM MTPA 使用离散搜索，不是经过标定的实时查表或解析控制律。
- 弱磁使用稳态电压估算，不含电流导数、电压动态裕量调节和联合约束优化。
- 无 PWM/SVPWM、死区、开关损耗、DC bus 动态或半导体热模型。
- 无传感器、编码器、参数在线辨识和自动 PI/MTPA 调参。
- 无 MTPV、高速稳定性证明和工业级保护状态机。
- 所有参数仍是 sandbox 输入，不会写回 production model。
