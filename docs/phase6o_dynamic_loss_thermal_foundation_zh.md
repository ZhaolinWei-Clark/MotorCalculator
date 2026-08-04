# Phase 6O：动态损耗与集总热模型基础

## 1. 阶段边界

Phase 6O 仅在 `motor_calculator/dynamics/` 沙盒中增加动态损耗监测、单节点热 RC 和可选的临时电阻反馈。它不修改 production calculator、GUI、PMSM dq 方程、控制器方程或默认参数。

`ThermalElectricalSimulationRunner` 是独立包装层。`ThermalElectricalCouplingConfig.enabled=False` 时，它直接委托原 `SimulationRunner`，因此返回对象与 Phase 6N 原路径完全一致。开启后使用 frozen dataclass 的临时副本传入当前步 `Rs(T)`，不会修改调用者提供的 `PMSMDynamicParameters`。

## 2. 铜损与电流语义

平衡三相、每相 RMS 电流下：

```text
Pcu = 3 * I_phase_rms^2 * Rs(T)
```

项目使用幅值不变 Clarke/Park 变换。稳态平衡正弦中，dq 电流是相电流峰值矢量，因此：

```text
I_phase_rms^2 = (id^2 + iq^2) / 2
Pcu = 1.5 * Rs(T) * (id^2 + iq^2)
```

实现分别提供 `compute_from_phase_rms()` 和 `compute_from_dq_peak()`，避免把 phase peak、phase RMS 和 dq 矢量幅值静默混用。

## 3. 温度相关电阻

线性铜电阻模型为：

```text
R(T) = R_ref * [1 + alpha_cu * (T - T_ref)]
```

默认 `alpha_cu=0.00393 /°C` 是接近室温的显式近似铜系数，调用方可以覆盖。该系数不是 calibration 结果，也不会写回 production。例：`R_ref=0.5 Ω`、`T_ref=20°C` 时，`R(100°C)=0.6572 Ω`。

## 4. 铁损基础

默认 `UnavailableIronLossModel` 返回 `iron_loss_w=None` 和告警，不用 `0` 假装已有物理估计，也不复用 legacy 百分比。

调用方可以显式提供 `ProvisionalIronLossModel(kh, ke)`：

```text
Pfe = kh * f_e * B_proxy^2 + ke * f_e^2 * B_proxy^2
```

这里的 `B_proxy`、`kh` 和 `ke` 必须由调用方提供；结果始终标记 provisional。接口为未来 Steinmetz、Bertotti、FEA loss map 或实测 loss map 保留扩展位置。

## 5. 机械损耗

Phase 6O 只监测现有机械方程中已经使用的粘性阻尼：

```text
Pmech_loss = B * omega_m^2
```

该功率不会再次从机械方程中扣除，否则会重复计算阻尼。尚未增加库仑摩擦、风阻或轴承图谱。

## 6. 单节点热 RC

热状态只有绕组温度 `T`，环境温度固定为 `Tamb`：

```text
Cth * dT/dt = Ploss - (T - Tamb) / Rth

dT/dt = [Ploss - (T - Tamb) / Rth] / Cth
```

固定损耗稳态为：

```text
Tss = Tamb + Ploss * Rth
tau = Rth * Cth
```

支持 Euler 和 RK4 热积分，默认 RK4。热更新时间由 `thermal_update_period_s` 独立配置，必须不快于 plant 步长；runner 在热周期内积累损耗能量，再以平均损耗更新热节点，避免把热步长盲目绑定到 PWM 或电流控制周期。

当前单节点把所有已启用且 available 的损耗视为同一个总热源。这是粗略集总假设，并不表示铜、铁、转子、壳体和轴承具有相同温度或热路径。

## 7. 热电反馈

可选反馈链为：

```text
winding temperature
  -> temporary Rs(T)
  -> existing PMSM dq derivative evaluation
  -> dq current
  -> copper loss
  -> lumped thermal update
```

关闭 `enable_resistance_feedback` 时，整个热仿真仍使用传入的原始 `motor_parameters.Rs`。开启后，每个电气步只创建当前温度对应的临时参数副本。

固定电流与固定电压必须区别解释：恒流下，电阻升高会直接提高 `I^2R`；电压驱动 PMSM 中，电阻升高也可能降低电流，使最终铜损低于无反馈案例。Phase 6O 不把任一结果解释为自动效率优化。

## 8. 示例实验

`run_thermal_foundation_experiments()` 提供可重复的 prescribed dq-peak current 案例，采用 `Tamb=25°C`、`Rth=0.5°C/W`、`Cth=100 J/°C`、`Rs=0.5 Ω`。

| 案例 | 结果 |
|---|---|
| A：5 A 恒流加热 | `Pcu=18.75 W`；理论 `Tss=34.375°C`，300 s 后 `34.3518°C`。 |
| B：10 A 更高电流 | `Pcu=75 W`，正好为 5 A 案例的 4 倍；300 s 后 `62.4070°C`。 |
| C：电阻反馈 | 无反馈保持 `0.5 Ω / 18.75 W / 34.3518°C`；反馈后为 `0.51907 Ω / 19.4650 W / 34.7035°C`。 |
| D：冷却 | 150 s 后去除电流，最终温度下降到 `25.0221°C`。 |

另一个 voltage-driven PMSM 耦合示例在 1 s 后得到：

| 模式 | 温度 °C | Rs Ω | iq A | 铜损 W |
|---|---:|---:|---:|---:|
| 热监测但无 Rs 反馈 | 39.2271 | 0.50000 | 19.7607 | 293.0189 |
| 启用临时 Rs(T) 反馈 | 38.9105 | 0.52733 | 18.8389 | 280.8564 |

该案例中固定电压下电流下降超过了电阻上升效应，因此铜损和温度略低；这只是耦合方向验证，不是经过校准的性能预测。

## 9. 告警与元数据

启用模式记录：

- `winding_temperature_c`
- `effective_phase_resistance_ohm`
- `copper_loss_w`
- `iron_loss_w`，不可用时为 `None`
- `mechanical_loss_w`
- `total_loss_w`
- thermal update count 和去重告警

达到 `warning_temperature_c` 时只产生告警，不执行自动停机。无效热阻、热容、时间步或负损耗会被安全拒绝。

## 10. 当前限制

尚未实现：

- 分布式多节点热网络
- 绕组、铁芯、磁钢、转子、壳体和轴承的独立温度
- CFD 或冷却流体模型
- 槽内热点、端部绕组和接触热阻
- 半导体热模型与逆变器损耗热源
- 经验证的 Steinmetz/Bertotti 系数或铁损图谱
- FEA 热耦合
- 辐射、非线性对流和温度相关冷却条件
- 绝缘寿命、退磁温度限制或自动关断

因此 Phase 6O 不能被描述为 Motor-CAD、CFD、FEA 或台架验证级热模型，也不能用于自动 calibration 或 production 参数更新。
