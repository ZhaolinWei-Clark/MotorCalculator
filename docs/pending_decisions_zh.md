# 待决策事项

本文件记录当前尚未关闭、且在继续修改计算语义前必须确认的用户决策与工程边界。

更新时间：2026-07-03

## 1. 当前阶段划分

- Phase 3A 已完成
- Phase 3B 已完成
- Phase 3C 已完成：PMSM 正弦模式 revised `Ke` / `Kt` 定义
- Phase 3D 已完成：独立 PMSM analytical reference validation
- 当前下一阶段只允许进入 Phase 3E：BLDC revised 语义、公式和独立 analytical reference cases

## 2. Phase 3D 已确认结论

- 新增了独立 fixture：`motor_calculator/tests/fixtures/pmsm_reference_cases.json`
- 当前新增 4 个 PMSM 正弦案例，全部标记为 `analytical_reference`
- expected 值由 `motor_calculator/tests/reference_case_builder.py` 独立重建
- reference builder 不导入 `motor_core`、`pmsm_ke_kt_models.py`、`electrical_semantics.py` 或 `calculations.py`
- revised PMSM `Ke` / `Kt` 已通过 analytical reference validation
- legacy baseline 与 PMSM analytical reference 保持两套独立验证路径
- `legacy_baseline.json` 未修改
- 完整测试结果提升为 `84 passed`

## 3. 仍待用户确认的关键问题

### 3.1 PMSM revised `Ke` / `Kt` 的默认值策略

待确认内容：

- 是否长期接受 revised `Ke` / `Kt` 只作为并行输出、测试和报告值
- 是否未来允许 revised `Ke` / `Kt` 替代 legacy 默认值
- 若未来切换默认值，是否同步传播到：
  - 额定电流
  - 铜损
  - 效率
  - `required_voltage_v`
  - GUI 默认链路

当前建议：

- 即使已经通过 analytical validation，仍不建议在本阶段切换默认值

### 3.2 BLDC `Ke` / `Kt` 是否进入下一阶段

待确认内容：

- 是否批准启动 Phase 3E
- 是否接受该阶段必须继续保持 legacy baseline 不变
- 是否接受 BLDC 阶段不得混入以下内容：
  - revised 默认值切换
  - `required_voltage_v` 修正
  - 损耗模型修正
  - 电感模型修正
  - GUI 重设计

当前建议：

- 技术上可以进入 Phase 3E
- 但必须单独审批，且不能和默认链路切换或其他模型修正混做

### 3.3 是否继续补充更高层级验证来源

待确认内容：

- 是否需要补充 `published_reference`
- 是否需要补充 `fea_reference`
- 是否需要补充 `user_supplied_measurement`

当前建议：

- 当前 analytical validation 已足以证明 Phase 3C 的 revised 定义在数学上自洽
- 但若未来考虑默认值切换，应优先补充 FEA、台架测试或公开 benchmark

## 4. 现在已经不再悬而未决的事项

- PMSM revised `Ke` / `Kt` 不再缺少独立 analytical reference case
- Phase 3D 不需要继续修改 PMSM revised `Ke` / `Kt` 公式
- legacy baseline 不能再被误用为 PMSM revised `Ke` / `Kt` 的数值参考

## 5. 当前不应做的事

- 不要把 revised 额定转矩直接传播到下游
- 不要把 revised `Ke` / `Kt` 在未审批时传播到下游
- 不要在未审批时把 revised 结果设为默认值
- 不要在 Phase 3E 中修改 `required_voltage_v`
- 不要在 Phase 3E 中修改损耗模型、电感模型或槽满率
- 不要在 Phase 3E 中切换默认链路
- 不要在 Phase 3E 中修改 PMSM revised 公式
- 不要在 Phase 3E 中修改 `legacy_baseline.json`
- 不要为让测试通过而重写 `legacy_baseline.json`
- 不要把 analytical validation 夸大为实验验证
