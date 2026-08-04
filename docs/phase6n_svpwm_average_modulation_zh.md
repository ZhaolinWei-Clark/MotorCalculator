# Phase 6N：SVPWM / PWM 平均调制基础

## 1. 阶段边界

Phase 6N 只在 `motor_calculator/dynamics/` 沙盒中增加可选的平均电压调制层。它不修改 production calculator、GUI、PMSM plant 方程、控制器方程或既有坐标变换。默认模式仍为 `SIMPLE_DQ_LIMIT`；只有显式选择 `SVPWM_AVERAGE` 并提供启用的 `SVPWMConfig` 时，才经过本阶段的调制路径。

本阶段回答的是“在给定直流母线和占空比边界下，控制器电压命令对应什么平均三相电压”，而不是半导体开关瞬态。

## 2. 为什么需要 PWM / SVPWM

PMSM dq 模型接收连续的 `Vd/Vq`，真实两电平逆变器却只能把各桥臂连接到直流母线的正端或负端。PWM 通过一个开关周期内的导通比例合成目标平均电压；SVPWM 用空间电压矢量组织这一过程，并利用共模偏置改善直流母线电压利用率。

三种模型层级必须区分：

- 理想 dq 电压源：直接把任意 `Vd/Vq` 施加到 plant，没有母线限制。
- 平均逆变器模型：生成占空比并重构一个 PWM 周期内的平均电压，但不产生开关边沿。
- 真实开关逆变器：还需要载波、开关器件、死区、二极管、损耗和寄生参数；Phase 6N 不属于这一层。

## 3. 信号链

```text
Vd/Vq command
  -> existing inverse Park
  -> V_alpha/V_beta
  -> sector and common-mode duty generation
  -> duty_a/duty_b/duty_c
  -> average pole voltages
  -> floating-neutral phase voltages
  -> existing Clarke and Park
  -> actual average Vd/Vq
  -> PMSM plant
```

逆 Park、Clarke 和 Park 均复用 Phase 6H 的幅值不变实现，没有复制或修改变换公式。

## 4. alpha-beta 矢量与六扇区

参考矢量为：

```text
|V_ref| = sqrt(V_alpha^2 + V_beta^2)
angle = atan2(V_beta, V_alpha) wrapped to [0, 2*pi)
```

平面按每 `pi/3` 分成 Sector 1 到 Sector 6。约定为左闭右开：Sector 1 对应 `[0, pi/3)`，Sector 2 对应 `[pi/3, 2*pi/3)`，依此类推；精确边界归入后一个扇区，零矢量固定记录为 Sector 1。扇区只提供确定性元数据，占空比由连续共模注入公式生成，因此跨扇区边界不会切换到不连续的独立公式。

## 5. 调制度与线性区

在默认完整占空比范围 `[0, 1]` 下，沿用 Phase 6F 的圆形电压包络：

```text
V_linear_max = Vdc / sqrt(3)
m = |V_ref| / V_linear_max
```

若配置占空比范围为 `[d_min, d_max]`，则：

```text
V_linear_max = (d_max - d_min) * Vdc / sqrt(3)
```

因此 `m <= 1` 是本阶段保证连续线性重构的范围。默认不允许过调制；当 `m > 1` 时，矢量按比例缩放到圆形边界，方向保持不变，并设置 `voltage_saturated=True` 和告警。

若显式启用 `allow_overmodulation`，圆形边界之外但仍位于可实现六边形内的平均矢量可以保留，并设置 `overmodulation_active=True`。超出六边形时仍会沿原方向缩放。该选项只是静态平均值基础，不描述非线性开关谐波，不能视为完整过调制算法。

## 6. 占空比与平均相电压

逆 Clarke 首先产生平衡相参考 `Va*、Vb*、Vc*`。实现加入连续的零序/共模电压，使三相极值居中于配置的占空比窗口：

```text
duty_x = 0.5 + Vpole_x / Vdc
```

`duty_a/b/c` 表示一个理想 PWM 周期内各上桥臂的导通比例，并被限制在 `[minimum_duty, maximum_duty]`。

重构采用理想两电平桥臂和浮动电机中性点约定：

```text
Vpole_x = (duty_x - 0.5) * Vdc
Vneutral = (Vpole_a + Vpole_b + Vpole_c) / 3
Vphase_x = Vpole_x - Vneutral
```

因此 `Va_avg + Vb_avg + Vc_avg = 0`。重构后的三相平均电压再经过既有 Clarke/Park，形成实际送入 PMSM plant 的 `Vd/Vq`。当传感器角度存在误差时，anti-windup 使用控制器坐标系重构电压，而 plant 使用真实转子坐标系重构电压，保持 measurement 与 plant 的职责分离。

## 7. 模式与元数据

- `SIMPLE_DQ_LIMIT`：原有 `Vdc/sqrt(3)` dq 圆形限幅路径，也是默认行为。
- `SVPWM_AVERAGE`：显式执行逆 Park、占空比生成、平均相电压及 dq 重构。

单步结果记录 sector、调制度、三相 duty、平均相电压、平均 alpha-beta 电压、实际 dq 电压、过调制和饱和状态。闭环结果额外记录过调制次数、SVPWM 饱和次数、观测到的最大/最小调制度及最大/最小占空比。所有字段仅属于 dynamics sandbox metadata。

## 8. 示例实验

示例由 `run_direct_modulation_examples()` 和 `run_speed_mode_comparison()` 可重复生成，采用 `Vdc=48 V`。

| 案例 | 结果摘要 |
|---|---|
| A：低调制 | Sector 2，`m=0.340419472`，duties=`(0.458452170, 0.668510969, 0.331489031)`；`(5, 8) V` dq 命令的往返误差为 `1.26e-15 V`。 |
| B：近电压极限 | `m=0.98`，duties=`(0.982555799, 0.352623941, 0.017444201)`，未饱和。 |
| C：明显过指令 | 请求 `m=1.5`，默认线性策略缩放到 `Vdc/sqrt(3)`，`voltage_saturated=True`，结果保持有限且方向不变。 |

Case D 使用相同电机、控制器、48 V 母线、30 rad/s 目标和 0.2 N·m 负载运行 0.75 s：

| 模式 | 最终速度 rad/s | 速度 RMS 误差 rad/s | iq RMS 跟踪误差 A | 电压饱和次数 | 调制度范围 |
|---|---:|---:|---:|---:|---|
| SIMPLE_DQ_LIMIT | 30.315204 | 9.538329 | 0.190347 | 0 | 不适用 |
| SVPWM_AVERAGE | 30.315204 | 9.538329 | 0.190347 | 0 | 0.108690 到 0.444896 |

线性、未饱和条件下，两种模式产生相同平均 dq 电压，因此闭环结果相同。这用于验证接线一致性，不代表 SVPWM 自动改善效率、纹波或控制性能。

## 9. 当前限制

尚未实现：

- MOSFET / IGBT 开关波形和开关瞬态
- 开关纹波与谐波电流
- 开关损耗和导通损耗
- 死区、二极管导通和器件压降
- gate driver 模型
- 详细 DC-link 纹波
- ADC/PWM 同步采样和电流重构
- EMI / EMC 效应
- 半导体热模型

因此不得把 Phase 6N 的平均值结果解释为器件级、热级或 EMI 级验证，也不得据此修改 production 参数或执行 calibration。
