# Phase 6M：传感器与编码器非理想基础

## 1. 阶段边界

Phase 6M 只在动态控制 sandbox 的反馈路径中加入可选测量非理想性。它不修改 PMSM plant 方程、PI 控制器方程、Clarke/Park 约定、production calculator、GUI 或 legacy baseline，也不执行传感器参数校准。

默认配置仍然使用理想反馈：

```text
enable_sensor_nonidealities = False
```

传感器关闭时，FOC 和级联速度控制路径与 Phase 6L 完全相同。

## 2. 真实状态与测量反馈

仿真中明确保留两条路径：

```text
真实 MotorState --------------------------> PMSM plant / RK4
       |
       -> abc、位置、速度传感器 -> measured feedback -> controller
```

FOC controller 使用测量后的 abc 电流、机械角和速度。PMSM plant 始终使用真实 `id`、`iq`、`omega_m` 和 `theta`。测量偏置、噪声或量化不会直接覆盖物理状态。

## 3. 相电流传感器

每相电流按固定顺序处理：

```text
true current
-> gain error
-> offset
-> optional Gaussian noise
-> optional bipolar quantization / full-scale clipping
-> measured current
```

配置项包括：

- `offset_a`
- `gain_error_fraction`
- `noise_std_a`
- `resolution_bits`
- `full_scale_a`
- `enabled`

当 `noise_std_a=0` 时结果完全确定。启用噪声时必须显式传入 `random.Random`；模型不会调用隐藏的全局随机状态。量化使用 `[-full_scale_a, +full_scale_a]` 双极范围，超范围值会被截断并记录 warning。

## 4. 位置与编码器

机械角测量顺序为：

```text
theta_m_true
-> mechanical offset
-> optional Gaussian noise
-> optional counts-per-revolution quantization
-> wrap to [0, 2*pi)
```

测量机械角随后通过现有函数映射为电角度：

```text
theta_e = pole_pairs * theta_m_measured
```

Clarke/Park 变换公式与 amplitude-invariant 约定没有变化。

## 5. 为什么电角度误差重要

Park 变换依赖转子电角度。若估计角度偏移为 `delta_theta_e`，真实 dq 电流会在 controller 坐标系中发生旋转。以真实 `id=0`、`iq>0` 为例，角度误差会产生非零 measured d-axis 分量，并减小 measured q-axis 投影。

机械误差会被极对数放大：

```text
delta_theta_e = pole_pairs * delta_theta_m
```

因此多极电机对同样的机械角误差具有更大的电角度误差。

## 6. 速度传感器

Phase 6M 支持直接速度测量的：

- offset
- gain error
- Gaussian noise
- `sample_period_s` 配置 metadata

本阶段没有从 encoder 差分估算速度，也没有 sample-and-hold、滤波器或 estimator。`sample_period_s` 仅记录预期采样周期，runner 仍在控制更新时直接测量真实速度。

## 7. SensorSuite 与结果 metadata

`SensorSuiteConfig` 可分别配置三相电流、位置和速度传感器。每个测量结果记录：

- true value
- measured value
- measurement error
- whether quantization was applied
- whether noise was applied
- warning messages

FOC step 另外返回 true dq 与 measured dq，便于验证 controller feedback 与 plant state 的隔离。

## 8. 实验解释边界

Phase 6M 提供：

- `0/1/5/10` electrical-degree rotor-angle offset cases
- phase-A current offset
- all-phase gain error
- ADC quantization
- small seeded Gaussian noise

报告中的 `torque_variation_proxy_nm` 是当前平均电压 dq 模型时间序列的低频变化标准差。由于未实现 PWM 或开关逆变器，它不能称为 switching-frequency torque ripple。

## 9. 当前限制

- 无 observer、Kalman filter 或状态估计。
- 无 sensorless FOC。
- 无 resolver 励磁、解调或模拟前端模型。
- 无 ADC aperture、转换延迟、通道 skew 或采样保持模型。
- 无 encoder missing-count、index pulse、方向迟滞或速度差分模型。
- 无 PWM synchronization、SVPWM 或 switching ripple。
- 无传感器温漂、带宽和频率响应。
- 无参数自动校准，实验数值不能写回 production。
