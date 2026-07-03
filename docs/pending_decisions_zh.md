# 待决策事项

本文档记录当前尚未关闭、且在继续修改计算语义前必须确认的用户决策与工程边界。

更新时间：2026-07-03

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 revised `Ke` / `Kt` 定义
- Phase 3D 已完成：独立 PMSM analytical reference validation
- Phase 3E 已完成：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference validation

## 2. Phase 3E 已确认结论

- legacy BLDC 示意波形与本阶段固定的 ideal BLDC 120°平顶梯形 revised 模型不是同一套定义
- revised BLDC 相反电势量已明确区分：
  - `phase_flat_top`
  - `phase_peak`
  - `phase_rms`
  - `line_to_line_peak`
  - `line_to_line_rms`
- revised BLDC 电流量已明确区分：
  - conduction current
  - phase RMS current
- revised BLDC 平均电磁功率在当前理想假设下满足：
  - `P_em_avg = 2 * E_flat_top * I_conduction`
- revised BLDC `Kt` 已从平均功率平衡推导，而不是照搬 PMSM 关系
- 4 个独立 BLDC analytical reference cases 已建立并通过
- `legacy_baseline.json` 未修改
- 完整测试结果提升为 `117 passed`

## 3. 仍待用户确认的关键问题

### 3.1 PMSM revised `Ke` / `Kt` 的默认值策略

待确认内容：

- 是否长期接受 revised PMSM `Ke` / `Kt` 只作为并行输出、测试和报告值
- 是否未来允许 revised PMSM `Ke` / `Kt` 替代 legacy 默认值
- 若未来切换默认值，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路

当前建议：

- 即使已经通过 analytical validation，仍不建议在本阶段切换默认值

### 3.2 BLDC revised `Ke` / `Kt` 的默认值策略

待确认内容：

- 是否长期接受 revised BLDC `Ke` / `Kt` 只作为并行输出、测试和报告值
- 是否未来允许 revised BLDC `Ke` / `Kt` 替代 legacy 默认值
- 若未来切换默认值，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路
  - 转矩波形

当前建议：

- 当前不建议切换 BLDC revised 为默认
- 若未来考虑切换，必须单独审批并补充更高层级验证

### 3.3 是否补充更高层级验证来源

待确认内容：

- 是否需要补充 `published_reference`
- 是否需要补充 `fea_reference`
- 是否需要补充 `user_supplied_measurement`

当前建议：

- 当前 analytical validation 足以证明 PMSM revised 与 BLDC revised 定义在数学上自洽
- 但若未来考虑默认值切换，应优先补充 FEA、台架测试或公开 benchmark

### 3.4 是否单独进入 `required_voltage_v` 修正阶段

待确认内容：

- 是否启动一个独立阶段专门处理 `required_voltage_v` 的量纲、相/线值、调制方式与控制策略语义

当前建议：

- 该工作不能与 default switch 混做
- 也不应在没有单独审批时夹带进 `Ke` / `Kt` 阶段

## 4. 现在已经不再悬而未决的事项

- PMSM revised `Ke` / `Kt` 不再缺少独立 analytical reference case
- BLDC revised `Ke` / `Kt` 不再缺少独立 analytical reference case
- legacy baseline 不再被误用为 PMSM 或 BLDC revised `Ke` / `Kt` 的数值参考
- BLDC 120°导通下 revised `Ke` / `Kt` 的相/线值、flat-top/RMS 与功率平衡关系已经建立

## 5. 当前不应做的事

- 不要把 revised 额定转矩直接传播到下游
- 不要把 revised PMSM `Ke` / `Kt` 在未审批时传播到下游
- 不要把 revised BLDC `Ke` / `Kt` 在未审批时传播到下游
- 不要在未审批时把 revised 结果设为默认值
- 不要修改 `required_voltage_v`
- 不要修改损耗模型、电感模型、槽满率
- 不要修改退磁或温升模型
- 不要切换 GUI 默认链路
- 不要修改 `legacy_baseline.json`
- 不要把 analytical validation 夸大为实验验证
