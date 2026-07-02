# 待决策事项

本文档记录当前尚未关闭、且在修改计算语义前必须确认的决策与工程问题。

更新时间：2026-07-02

## 1. 当前阶段划分

- Phase 3A 已完成
- 当前进入 Phase 3B：严格 SI 额定转矩公式对比
- 当前不进入 Phase 3C

## 2. Phase 3A 固化状态

Phase 3A 已完成并通过验收。

当前开发分支：

- `feature/electrical-semantics`

Phase 3A 提交：

- `724c305` `test: enable standard pytest`
- `98ba044` `refactor: clarify speed and electrical quantity semantics`
- `47e086a` `refactor: separate PMSM and BLDC control mode semantics`
- `db9749d` `test: add electrical semantics coverage`
- `c0da91b` `docs: document electrical quantity definitions`

当前正式测试命令：

```text
python -m pytest -v
```

当前完整测试结果：

```text
25 passed
```

当前确认事项：

- `legacy_baseline.json` 未修改
- 3 组 legacy baseline、18 个输出字段均未发现数值漂移
- PMSM 与 BLDC 的电气语义已经隔离
- BLDC 120°导通下的严格 RMS、peak、`Ke`、`Kt` 关系尚未建立
- legacy `Ke` / `Kt`、`required_voltage_v`、损耗、电感、槽满率等模型尚未修正

## 3. Phase 3B 已批准问题

Phase 3B 只允许处理额定转矩公式：

- legacy：`T = 9.55 * P / n`
- revised：`T = P / omega_m`

必须明确：

- revised 结果不得传播到额定电流、损耗、效率或电压需求
- 所有会改变结果的公式修改都必须保留 legacy 与 revised 并行输出
- Phase 3C 才允许处理 PMSM `Ke` / `Kt`

## 4. Phase 3B 已完成状态

Phase 3B 已完成并确认：

- legacy 额定转矩与 strict SI 额定转矩已并行实现
- legacy 结果仍是当前下游默认值
- revised 结果仅用于比较、测试和报告
- baseline 文件未修改
- legacy regression 仍通过

当前结论：

- 差异来源是 `9.55` 与 `60 / (2π)` 的近似常数差异
- 本阶段不能据此宣称整个电机模型精度已得到实验验证
- 当前不建议直接把 revised 额定转矩设为默认值

## 5. 待确认的关键公式问题

### 4.1 `Kt` / `Ke` 语义

待确认内容：

- `Kt` 当前实现对应的是相电流还是线电流
- 是 RMS 还是 peak
- PMSM 与 BLDC 是否应共用同一套常数关系
- 与 `back_emf_phase_rms_v`、`back_emf_line_rms_v` 的关系是否符合目标驱动方式

当前状态：

- Phase 3A 只完成字段澄清与模式边界隔离
- Phase 3C 前不处理默认公式修正

### 4.2 `9.55 * P / n`

待确认内容：

- 是否继续保留为 downstream legacy 默认值
- revised 严格 SI 结果是否未来应替代 legacy 默认值

影响：

- 额定转矩
- 额定电流
- 铜损
- 效率
- 所需电压

### 4.3 所需电压模型

待确认内容：

- 当前 `sqrt(E^2 + (IR)^2 + (ωLI)^2) * margin` 是否继续保留
- 是否需要区分控制策略、相位角和逆变器调制度

当前状态：

- Phase 3B 明确不修改 `required_voltage_v`

### 4.4 `K_fill`

待确认内容：

- 当前 legacy 定义是否只作为占比代理量保留
- 是否将来替换为真实槽满率模型

### 4.5 经验损耗模型

待确认内容：

- 铁损比例模型是否继续保留
- 机械损耗与风阻损耗是否需要按拓扑细化
- 涡流损耗经验式是否需要限制适用范围

## 6. Phase 3B 的核心决策点

Phase 3B 完成后仍需用户决策：

1. 是否接受在报告层长期并行显示 legacy 与 revised 额定转矩
2. 是否允许未来把 `revised_rated_torque_nm` 设为默认值
3. 若设为默认值，是否同步更新：
   - 额定电流
   - 铜损
   - 效率
   - `required_voltage_v`

当前建议：

- Phase 3B 结束后暂不启用 revised 默认值
- 先保留比较结果和差异报告

## 7. baseline 相关风险

- `legacy_baseline.json` 只覆盖 3 组案例
- 它能防止明显回归，但不能覆盖所有输入边界
- Phase 3B 不得修改 baseline 文件
- 如果未来启用 revised 默认值，应新增差异报告，而不是静默改写 baseline

## 8. 当前不应做的事

- 不要把 revised 额定转矩直接传播到下游
- 不要在未批准时修改 `Ke` / `Kt`
- 不要在未批准时修改 BLDC 模型
- 不要在未批准时修改 `required_voltage_v`
- 不要为了让测试通过而重写 baseline
- 不要把 Phase 3B 的单位严谨性提升夸大为“整个电机模型已得到实验验证”
