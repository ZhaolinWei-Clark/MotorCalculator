# Phase 3 公式变更报告

更新时间：2026-07-02

## 1. 本报告范围

本报告只覆盖 Phase 3B：

- 额定转矩 legacy 公式与 strict SI 公式的并行实现
- 差异计算、测试和报告

本报告不覆盖：

- `Ke` / `Kt` 修正
- PMSM 反电势公式修正
- BLDC 120°导通模型修正
- `required_voltage_v` 修正

## 2. legacy 公式

当前 legacy 额定转矩公式为：

```text
legacy_rated_torque_nm
= 9.55 * rated_power_w / mechanical_speed_rpm
```

说明：

- `rated_power_w` 单位为 `W`
- `mechanical_speed_rpm` 单位为 `rpm`
- `9.55` 是 `60 / (2π)` 的近似常数

## 3. revised 严格 SI 公式

Phase 3B 新增并行 strict SI 公式：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60

revised_rated_torque_nm
= rated_power_w / mechanical_angular_speed_rad_s
```

说明：

- revised 核心公式中不使用 `9.55`
- revised 复用了 Phase 3A 已建立的 `rpm -> rad/s` 转换

## 4. 从 P = Tω 推导转矩公式

基础物理关系为：

```text
P = T * ω
```

因此可得：

```text
T = P / ω
```

当：

- `P` 使用 `W`
- `ω` 使用 `rad/s`

则：

- `T` 的单位自然为 `N·m`

这就是 revised 严格 SI 公式的来源。

## 5. rpm 到 rad/s 的换算

机械转速与机械角速度的严格换算为：

```text
mechanical_angular_speed_rad_s
= mechanical_speed_rpm * 2π / 60
```

这是纯单位换算，不依赖波形、控制策略或电机类型。

## 6. 9.55 与 60/(2π) 的数值差异

精确值：

```text
60 / (2π) = 9.549296585513721...
```

legacy 近似值：

```text
9.55
```

二者差异：

- 绝对差：`0.000703414486280`
- 相对差：`0.000073661392751`
- 相对差百分比：`0.007366139275%`

因此，Phase 3B 中 legacy 与 revised 的差异来源是：

- 常数近似差异

而不是：

- 新的电磁物理模型
- 新的损耗模型
- 新的控制策略模型

## 7. 输入和输出单位

输入单位：

- `rated_power_w`：`W`
- `mechanical_speed_rpm`：`rpm`

中间量：

- `mechanical_angular_speed_rad_s`：`rad/s`

输出单位：

- `legacy_rated_torque_nm`：`N·m`
- `revised_rated_torque_nm`：`N·m`
- `rated_torque_absolute_difference_nm`：`N·m`
- `rated_torque_relative_difference`：无量纲

## 8. 适用条件

本阶段比较公式适用于：

- 额定输出功率已知
- 机械额定转速已知
- 只希望比较 legacy 近似与 strict SI 单位严谨性差异

本阶段不适用于：

- 宣称整个电机模型已完成实验验证
- 推断 `Ke` / `Kt` 已自动变得正确
- 推断效率、损耗、电压需求已自动得到修正

## 9. 非法输入

以下输入在 Phase 3B 中必须抛出明确异常：

- `rated_power_w <= 0`
- `mechanical_speed_rpm <= 0`
- 结果为 `NaN`
- 结果为 `inf`

本阶段不允许：

- 静默返回 `0`
- 静默返回 `None`
- 用 `NaN` 或 `inf` 掩盖错误

## 10. 3 组 legacy baseline 差异表

| 案例 | legacy_rated_torque_nm | revised_rated_torque_nm | absolute_difference_nm | relative_difference | relative_difference_percent |
|---|---:|---:|---:|---:|---:|
| `default_case` | 3.056000000000 | 3.055774907364 | 0.000225092636 | 0.000073661393 | 0.007366139275% |
| `low_power_low_speed_case` | 1.790625000000 | 1.790493109784 | 0.000131890216 | 0.000073661393 | 0.007366139275% |
| `high_power_high_speed_case` | 5.305555555556 | 5.305164769730 | 0.000390785826 | 0.000073661393 | 0.007366139275% |

说明：

- 三组案例的相对差一致，是因为差异完全来自常数 `9.55` 与 `60 / (2π)` 的近似误差
- baseline 文件本身未修改
- legacy 字段未被 revised 数值覆盖

## 11. 绝对误差说明

绝对误差定义为：

```text
absolute_difference_nm
= abs(legacy_rated_torque_nm - revised_rated_torque_nm)
```

它反映的是：

- 近似常数造成的扭矩数值偏差

它不反映：

- 线性化误差之外的其他电磁模型误差

## 12. 相对误差说明

相对误差定义为：

```text
relative_difference
= abs(legacy_rated_torque_nm - revised_rated_torque_nm) / revised_rated_torque_nm
```

这里将 revised strict SI 结果作为比较参考。

## 13. 为什么本阶段不把 revised 传播到下游

当前下游仍保留 legacy 额定转矩，原因是：

1. 当前额定电流仍由 legacy 额定转矩驱动
2. 铜损、效率和 `required_voltage_v` 都依赖额定电流或额定转矩链路
3. 如果在 Phase 3B 直接切换默认值，会引入结果漂移
4. 这会超出“只比较额定转矩公式”的批准范围

因此 Phase 3B 的策略是：

- 并行输出
- 明确比较
- 不改变生产默认链路

## 14. 如果未来启用 revised 默认值，可能影响哪些下游结果

如果未来批准将 `revised_rated_torque_nm` 设为默认值，可能影响：

- `rated current`
- `copper loss`
- `efficiency`
- `required voltage`

也可能进一步影响：

- 基于额定转矩的转矩波形归一化值
- 部分报表摘要字段

## 15. 当前实现结论

Phase 3B 已完成以下内容：

- 保留 legacy 额定转矩公式
- 新增 strict SI 额定转矩公式
- 新增差异输出字段
- 保持 legacy 下游计算不变
- 保持 `legacy_baseline.json` 不变
- 保持 legacy regression 通过

## 16. 结论声明

本阶段提高的是：

- 单位与公式表达的严谨性
- 额定转矩公式的可比对性
- 后续默认值切换前的风险可见性

本阶段不代表：

- 整个电机模型已经得到实验验证
- `Ke` / `Kt` 已经被修正
- BLDC 模型已经被完善
- 电压、损耗、热或磁路模型已经全面升级
