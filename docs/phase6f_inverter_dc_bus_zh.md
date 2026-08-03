# Phase 6F：PMSM 逆变器与直流母线基础

## 1. 阶段边界

Phase 6F 只在 `motor_calculator/dynamics/` 动态仿真沙盒内，为 PMSM dq 电压输入增加物理电压上限。它不修改 production calculation chain、不替换现有 PMSM 动态方程，也不进行参数校准。

未提供 `DCBusConfig` 时，`InputState.Vd` 和 `InputState.Vq` 仍按原有无限理想 dq 电压源处理，保持 Phase 6B-6E 的 runner 行为。提供配置时，这两个值被解释为电压命令，经过限幅后再传入现有 PMSM 导数模型。

## 2. 为什么理想 Vdq 电压源不现实

真实电机驱动器由有限直流母线供电，逆变器无法生成任意大的定子电压。忽略该约束会使高速或大电压命令工况继续使用无法实现的 `Vd/Vq`，从而高估电流和转矩响应能力。

Phase 6F 用平均电压包络限制命令，但不生成开关波形。

## 3. 直流母线与 dq 电压限制

采用简化的正弦调制/SVPWM 兼容假设：

```text
Vmax = Vdc / sqrt(3)
```

dq 电压命令必须满足：

```text
sqrt(Vd_command^2 + Vq_command^2) <= Vmax
```

若命令幅值超过上限，`Vd` 和 `Vq` 使用同一个比例因子缩放：

```text
saturation_ratio = command_magnitude / Vmax
scale = 1 / saturation_ratio
Vd_actual = Vd_command * scale
Vq_actual = Vq_command * scale
```

因此限幅后 dq 向量方向不变。`saturation_ratio > 1` 表示发生饱和，数值越大表示命令超过电压包络越多；零电压命令的比值定义为 `0`。

## 4. 配置与结果元数据

`DCBusConfig` 包含：

- `nominal_voltage_v`：用于计算电压包络的直流母线标称电压。
- `current_limit_a`：为后续阶段预留并校验的元数据，Phase 6F 不执行电流限幅。
- `inverter_efficiency`：为后续损耗模型预留并校验的元数据，Phase 6F 不改变功率或能量计算。

`SimulationResult` 以向后兼容的默认字段记录：

- `inverter_limited_count`：发生限幅的用户可见采样点数量，包括初始采样点；RK4 内部子阶段不重复计数。
- `max_voltage_saturation_ratio`：所有用户可见采样点中的最大命令幅值与电压上限之比。无逆变器配置时为 `0`。
- `voltage_limit_warnings`：去重后的电压限幅警告。

发生限幅时动态结果状态为 `WARNING`，不会静默地把受限结果标记为完全正常。动态结果中的电气输入功率监测使用限幅后的实际 `Vd/Vq`。

## 5. 简化假设

本阶段的逆变器仅为圆形平均 dq 电压包络：

- 假定直流母线电压在仿真期间恒定。
- 不计算调制指数、扇区或开关时刻。
- 不引入器件压降、谐波或开关纹波。
- 不执行 `current_limit_a`，也不应用 `inverter_efficiency`。
- 不改变已有 PMSM 电气与机械微分方程。

## 6. 尚未实现

- PWM
- 开关损耗
- 死区时间
- 半导体热模型
- 电流控制器
- FOC
- 直流母线动态与电池内阻
- 过调制和六步运行

因此 Phase 6F 只能回答有限 DC bus 电压包络如何约束动态输入，不能代表完整逆变器、控制器或硬件波形仿真。
