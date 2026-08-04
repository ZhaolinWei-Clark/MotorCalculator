# Phase 6M 传感器与编码器非理想实验报告

## 1. Sandbox 边界

本报告由 dynamics sandbox 的确定性实验函数生成。所有传感器均为可选 feedback 模型，PMSM plant 使用真实状态。结果不用于 production、参数校准或真实硬件精度声明。

公共实验条件：

- SPMSM：`Rs=0.5 ohm`、`Ld=Lq=0.005 H`、`psi_f=0.1 Wb`、`p=4`
- DC bus：`48 V`
- 速度目标：`30 rad/s`
- 负载转矩：`0.5 Nm`
- 仿真时间：`1.2 s`
- plant / current / speed update：`10 kHz / 2 kHz / 200 Hz`
- 尾段统计窗口：最后 25% 样本

## 2. 转子电角度误差

机械 offset 按 `delta_theta_m = delta_theta_e / pole_pairs` 设置。

| 电角度误差 | 最终真实速度 rad/s | 速度误差 rad/s | mean true id A | mean true iq A | mean measured id A | mean measured iq A | mean torque Nm | torque variation proxy Nm | peak current demand A |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 deg | 29.746022 | 0.253978 | 0.000000 | 0.893945 | 0.000000 | 0.893949 | 0.536367 | 0.000687 | 5.000000 |
| 1 deg | 29.746069 | 0.253931 | -0.015604 | 0.893945 | -0.000001 | 0.894085 | 0.536367 | 0.000687 | 5.000000 |
| 5 deg | 29.745737 | 0.254263 | -0.078216 | 0.893976 | -0.000003 | 0.897395 | 0.536386 | 0.000695 | 5.000000 |
| 10 deg | 29.744201 | 0.255799 | -0.157658 | 0.894091 | -0.000006 | 0.907888 | 0.536454 | 0.000717 | 5.000000 |

观察：

- current PI 将 measured `id` 拉回接近零，但真实 `id` 随角度误差增大而变得更负；这正是 true state 与 controller frame 错位的表现。
- `10 deg` case 的真实平均 `id` 为约 `-0.158 A`，而 controller 看到的平均 `id` 仍接近零。
- 速度误差和低频转矩变化代理在较大角度误差下上升，但本短时、小角度案例不用于给出稳定性边界。

## 3. 电流传感器误差

| Case | 最终真实速度 rad/s | 速度误差 rad/s | id tracking RMS A | iq tracking RMS A | voltage-command variation V | torque variation proxy Nm |
|---|---:|---:|---:|---:|---:|---:|
| Ideal | 29.746022 | 0.253978 | 0.000000 | 0.000041 | 0.010943 | 0.000687 |
| Phase-A offset `+0.2 A` | 29.698202 | 0.301798 | 0.029688 | 0.027531 | 0.066529 | 0.086693 |
| All-phase gain `+2%` | 29.741932 | 0.258068 | 0.000000 | 0.000044 | 0.011170 | 0.000723 |
| 10-bit, `+/-20 A` | 29.751206 | 0.248794 | 0.013155 | 0.014468 | 0.032680 | 0.002870 |
| Gaussian noise `0.02 A` | 29.747508 | 0.252492 | 0.024265 | 0.023952 | 0.052860 | 0.004793 |

观察：

- 单相 offset 破坏三相测量一致性，在这些案例中造成最大的速度误差、电压命令变化和低频转矩变化代理。
- 三相相同 gain error 主要改变标度，闭环 PI 在该工作点可补偿大部分稳态误差。
- 量化与 seeded noise 增加 dq tracking error 和控制电压变化。
- Gaussian noise 使用固定 seed `20260804`，不依赖全局随机状态，可重复生成同一结果。

## 4. 结论与警告

这些实验只回答“测量反馈偏离真实状态时，当前 sandbox 控制链如何响应”。它们不证明硬件性能，不代表 calibrated sensor values，也不包含 PWM switching-frequency torque ripple、ADC timing、observer、sensorless FOC 或 Kalman filtering。
