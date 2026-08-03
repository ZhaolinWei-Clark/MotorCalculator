# Phase 6H：FOC 坐标变换基础

## 1. 阶段边界

Phase 6H 只在 `motor_calculator/dynamics/transforms.py` 中建立经过数学验证的坐标变换。它不接入或修改 PMSM plant、dq 电流控制器、逆变器、production calculator 或 GUI，也不构成完整 FOC runner。

本阶段明确选择 **幅值不变（amplitude-invariant）** Clarke/Park 约定。所有变换均为无状态纯函数，输入和输出使用 frozen dataclass。

## 2. FOC 为什么需要坐标变换

三相定子电流和电压天然表示在随时间变化的 `abc` 三相坐标中。FOC 通常先通过 Clarke 变换把 balanced 三相量映射到静止的二维 `alpha-beta` 平面，再通过 Park 变换把该平面旋转到与转子电气角同步的 `dq` 坐标。

在理想同步旋转条件下，原本随电角度变化的正弦量可以在 dq 坐标中表现为近似直流量，使 d、q 轴电流能够分别作为磁链和转矩相关控制量处理。Phase 6H 只提供坐标数学，不提供这些控制环节。

## 3. 坐标含义

- `ABCPhaseValues(a, b, c)`：静止定子三相量。
- `AlphaBetaValues(alpha, beta)`：静止二维正交坐标量。
- `DQValues(d, q)`：按电气角旋转的二维正交坐标量。

本阶段假设三相平衡：

```text
a + b + c = 0
```

零序分量未建模。Clarke 正变换不会保留零序信息，因此不平衡 abc 数据无法通过本阶段的逆变换完整恢复。

## 4. Clarke 变换

幅值不变 Clarke 正变换为：

```text
alpha = a
beta = (a + 2*b) / sqrt(3)
```

该形式建立在 `a + b + c = 0` 的 balanced 假设上。

逆 Clarke 变换为：

```text
a = alpha
b = -0.5*alpha + (sqrt(3)/2)*beta
c = -0.5*alpha - (sqrt(3)/2)*beta
```

逆变换构造的三相量始终满足：

```text
a + b + c = 0
```

## 5. Park 变换

使用电气角 `theta_e`，Park 正变换为：

```text
d = alpha*cos(theta_e) + beta*sin(theta_e)
q = -alpha*sin(theta_e) + beta*cos(theta_e)
```

逆 Park 变换为：

```text
alpha = d*cos(theta_e) - q*sin(theta_e)
beta = d*sin(theta_e) + q*cos(theta_e)
```

正、逆 Park 使用完全相同的角度和符号约定。测试覆盖 `0、pi/6、pi/2、pi、2*pi` 以及完整 abc→alpha-beta→dq→alpha-beta→abc round-trip。

## 6. 机械角与电气角

极对数为 `pole_pairs` 时：

```text
theta_e = pole_pairs * theta_m
```

`electrical_angle()` 返回未包裹的电气角，以保留连续转动信息。需要周期角时，调用：

```text
wrap_electrical_angle(theta_e) -> [0, 2*pi)
```

两个操作保持独立，避免调用者在不知情时丢失累计转角。

## 7. 幅值与功率约定

Amplitude-invariant 约定保持 balanced 正弦空间向量的峰值幅度，但它不是 power-invariant 归一化。未来计算三相瞬时功率、控制器功率限制或能量平衡时，必须与该约定一致处理缩放系数，不能直接混用其他 Clarke/Park 归一化形式。

本阶段没有修改已有 PMSM dq 功率表达或 plant 方程。

## 8. 当前限制

- 没有零序坐标和不平衡三相模型。
- 没有 encoder 模型或转子角度观测器。
- 没有 current sensor 模型、采样噪声或偏置。
- 没有 PWM、开关逆变器或调制时序。
- 没有电流重构。
- 没有速度环。
- 没有解耦前馈或反电势补偿。
- 没有 anti-windup 算法。
- 没有完整 FOC runner。

Phase 6H 只回答坐标之间如何按统一约定进行可逆数学映射，不执行闭环 FOC 控制。
