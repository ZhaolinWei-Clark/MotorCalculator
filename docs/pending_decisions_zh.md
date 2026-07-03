# 待决策事项

本文档记录当前尚未关闭、且在修改计算语义前必须确认的决策与工程问题。

更新时间：2026-07-03

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 `Ke` / `Kt` revised 定义
- 当前进入 Phase 3D：建立独立 PMSM 验证案例
- 当前不进入 BLDC `Ke` / `Kt` 修正

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
- 当前分支：`feature/strict-si-rated-torque`
- Phase 3A 状态固化提交：`d9e675f`
- Phase 3B 提交：
  - `1c74397` `feat: add strict SI rated torque comparison`
  - `28cc132` `test: cover legacy and strict SI torque models`
  - `0adbca7` `docs: document rated torque formula comparison`
- 当前完整测试结果：`35 passed`

当前结论：

- 差异来源是 `9.55` 与 `60 / (2π)` 的近似常数差异
- 本阶段不能据此宣称整个电机模型精度已得到实验验证
- 当前不建议直接把 revised 额定转矩设为默认值
- revised 转矩没有传播到任何下游计算

## 5. 待确认的关键公式问题

### 4.1 `Kt` / `Ke` 语义

待确认内容：

- `Kt` 当前实现对应的是相电流还是线电流
- 是 RMS 还是 peak
- PMSM 与 BLDC 是否应共用同一套常数关系
- 与 `back_emf_phase_rms_v`、`back_emf_line_rms_v` 的关系是否符合目标驱动方式

当前状态：

- Phase 3A 只完成字段澄清与模式边界隔离
- Phase 3C 只允许处理 PMSM 正弦模式 revised 定义
- BLDC `Ke` / `Kt` 仍保持 legacy / provisional

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

### 4.4 PMSM revised `Ke` / `Kt` 的默认值策略

待确认内容：

- revised `Ke` / `Kt` 是否未来允许替代 legacy 默认值
- 若替代，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路

当前状态：

- 本阶段只允许并行输出和功率一致性验证
- 未经批准不得把 revised `Ke` / `Kt` 传播到下游

### 4.5 `K_fill`

待确认内容：

- 当前 legacy 定义是否只作为占比代理量保留
- 是否将来替换为真实槽满率模型

### 4.6 经验损耗模型

待确认内容：

- 铁损比例模型是否继续保留
- 机械损耗与风阻损耗是否需要按拓扑细化
- 涡流损耗经验式是否需要限制适用范围

## 6. Phase 3C 的核心决策点

Phase 3C 完成后仍需用户决策：

1. 是否接受在报告层长期并行显示 legacy 与 revised PMSM `Ke` / `Kt`
2. 是否允许未来把 revised PMSM `Ke` / `Kt` 设为默认值
3. 若设为默认值，是否同步更新：
   - 额定电流
   - 铜损
   - 效率
   - `required_voltage_v`
4. BLDC `Ke` / `Kt` 是否进入后续独立阶段修正

当前建议：

- Phase 3C 结束后暂不启用 revised 默认值
- 先保留比较结果、功率一致性验证和差异报告

Phase 3C 当前完成确认：

- revised PMSM `Ke` / `Kt` 已与 legacy 并行输出
- 功率一致性测试已通过
- revised `Ke` / `Kt` 未传播到额定电流、铜损、效率、`required_voltage_v` 或 GUI 默认链路
- BLDC `Ke` / `Kt` 仍保持 legacy / provisional
- `legacy_baseline.json` 未修改
- 完整测试结果已提升为 `63 passed`
- 现有 3 组 legacy baseline 全部为 BLDC 模式
- 现有 baseline 不能作为 PMSM revised `Ke` / `Kt` 的数值验证案例
- revised PMSM `Ke` / `Kt` 当前仅通过：
  - 单位转换测试
  - 三相功率平衡测试
  - 下游隔离测试
- revised PMSM `Ke` / `Kt` 尚未经过独立 PMSM reference case 验证

## 7. baseline 相关风险

- `legacy_baseline.json` 只覆盖 3 组案例
- 它能防止明显回归，但不能覆盖所有输入边界
- Phase 3C 也不得修改 baseline 文件
- 如果未来启用 revised 默认值，应新增差异报告，而不是静默改写 baseline
- 当前 3 组 baseline 样例仍走 legacy BLDC 分支，因此不能直接当作 PMSM revised `Ke` / `Kt` 误差基准

## 8. Phase 3D 的核心决策点

Phase 3D 完成后仍需用户决策：

1. 是否接受新增独立 PMSM reference case 作为 revised `Ke` / `Kt` 的数值验证样例
2. 是否允许未来基于独立 PMSM 验证案例评估 revised `Ke` / `Kt` 默认值切换
3. 是否继续保持 legacy BLDC baseline 与 PMSM reference case 两套独立验证路径

当前建议：

- 先建立独立 PMSM 验证案例
- 继续保持 BLDC legacy baseline 不变
- 暂不切换任何 revised 默认值

## 9. 当前不应做的事

- 不要把 revised 额定转矩直接传播到下游
- 不要在未批准时把 revised `Ke` / `Kt` 传播到下游
- 不要在 Phase 3D 中修改 BLDC 模型
- 不要在未批准时修改 `required_voltage_v`
- 不要为了让测试通过而重写 baseline
- 不要把 Phase 3B 的单位严谨性提升夸大为“整个电机模型已得到实验验证”
