# 待决策事项

本文档记录当前尚未关闭、且在继续修改计算语义前必须确认的用户决策与工程边界。

更新时间：2026-07-04

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 revised `Ke` / `Kt` 定义
- Phase 3D 已完成：独立 PMSM analytical reference validation
- Phase 3E 已完成并通过验收：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference validation
- 下一阶段已批准为 Phase 4A：外部验证数据框架和数据来源追踪

## 2. Phase 3E 已确认结论

- BLDC revised `Ke` / `Kt` 已通过：
  - 分段解析推导
  - 独立数值积分
  - 独立 analytical reference cases
  - production/reference 交叉验证
  - downstream isolation
- revised BLDC line RMS `Ke` 与 legacy 相差约 `2.4695%`
- legacy BLDC `Kt` 语义仍不完整，不应强制计算误差
- revised PMSM 和 revised BLDC 均未设为默认值
- `required_voltage_v`、额定电流、损耗、效率、GUI 默认链路均未修改
- analytical validation 不等于 FEA、实验或公开 benchmark 验证

## 3. 当前仍待用户确认的关键问题

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

### 3.3 是否补充更高层级验证来源

待确认内容：

- 是否需要补充 `published_reference`
- 是否需要补充 `fea_reference`
- 是否需要补充 `user_supplied_measurement`

### 3.4 是否单独进入 `required_voltage_v` 修正阶段

待确认内容：

- 是否启动一个独立阶段专门处理 `required_voltage_v` 的量纲、相/线值、调制方式与控制策略语义

## 4. 已批准但尚未实施的下一阶段边界

Phase 4A 当前只允许：

- 建立外部验证数据框架
- 建立数据来源追踪与 provenance 结构
- 规范未来 FEA、实验、公开 benchmark、用户测量数据的来源标记

Phase 4A 当前不允许：

- 切换任何默认链路
- 修改任何计算公式
- 修改 `required_voltage_v`
- 修改额定电流默认链路
- 修改损耗、效率、电感、槽满率、退磁或温升公式
- 修改 `legacy_baseline.json`

## 5. 现在已经不再悬而未决的事项

- PMSM revised `Ke` / `Kt` 不再缺少独立 analytical reference case
- BLDC revised `Ke` / `Kt` 不再缺少独立 analytical reference case
- legacy baseline 不再被误用为 PMSM 或 BLDC revised `Ke` / `Kt` 的数值参考
- BLDC 120°导通下 revised `Ke` / `Kt` 的相/线值、flat-top/RMS 与功率平衡关系已经建立

## 6. 当前不应做的事

- 不要把 revised 额定转矩直接传播到下游
- 不要把 revised PMSM `Ke` / `Kt` 在未审批时传播到下游
- 不要把 revised BLDC `Ke` / `Kt` 在未审批时传播到下游
- 不要在未审批时把 revised 结果设为默认值
- 不要在 Phase 4A 中切换任何默认链路
- 不要在 Phase 4A 中修改任何计算公式
- 不要修改 `legacy_baseline.json`
- 不要把 analytical validation 夸大为实验验证
