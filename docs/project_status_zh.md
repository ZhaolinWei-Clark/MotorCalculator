# 项目状态

更新时间：2026-07-04

## 1. 当前项目目标

当前项目目标仍然是：

- 冻结已批准的模型定义
- 保持 legacy 行为稳定
- 提升结构可维护性、可测试性和语义清晰度
- 在任何会改变结果的公式修改前，先建立并行输出、测试、差异报告与可追溯验证框架

当前项目目标不包括：

- 未经批准直接替换 legacy 电磁经验公式
- 切换任何 revised 默认值
- 自动校准经验系数
- 进入 GUI 优化阶段
- 在没有真实外部证据前宣称物理准确度已被实验验证

## 2. 项目对象

- 目标电机：三相轴向磁通永磁无刷电机 AFPM PMSM/BLDC
- 默认拓扑：双转子、单定子、双气隙
- 默认连接：Y 接

## 3. 已完成阶段

### 第一阶段：审查与问题识别

已完成。

### 第二阶段：安全基线、核心拆分、输入校验

已完成。

### Phase 3A：电气语义澄清与标准 pytest

已完成。

### Phase 3B：legacy 与 strict SI 额定转矩并行比较

已完成。

### Phase 3C：PMSM revised `Ke` / `Kt` 定义与隔离

已完成。

### Phase 3D：独立 PMSM analytical reference cases

已完成。

Phase 3D 验收状态：

- 测试结果：`84 passed`
- 状态固化提交：`958dc23`
- `legacy_baseline.json` SHA-256 固定值未变
- revised PMSM `Ke` / `Kt` 已通过独立 analytical reference validation

### Phase 3E：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference cases

已完成并通过验收。

Phase 3E 验收状态：

- 完整测试结果：`117 passed`
- `legacy_baseline.json` 未修改
- revised BLDC `Ke` / `Kt` 已通过分段解析、独立数值积分、独立 analytical reference、production/reference 交叉验证与 downstream isolation
- revised PMSM 与 revised BLDC 均未设为默认值

### Phase 4A：外部验证框架与 provenance 跟踪

已完成。

Phase 4A 完成内容：

- 建立 `ValidationSourceType` 六类来源枚举
- 建立 `ValidationEvidenceLevel` 五级证据等级
- 建立字段状态 `provided / inferred / unavailable / not_applicable`
- 建立 validation record schema、loader、comparability engine
- 建立 `validation_data/templates/`、`imported/`、`reports/` 结构
- 建立 synthetic example，仅用于测试导入器和比较引擎

Phase 4A 明确未做：

- 未修改任何电磁公式
- 未切换任何默认链路
- 未导入任何真实 published benchmark、真实 FEA 或真实台架数据
- 未修改 `legacy_baseline.json`

### Phase 4B：外部数据源侦察与候选 benchmark 清单

已进入侦察阶段。

Phase 4B 当前完成内容：

- 已创建候选来源清单：`docs/external_data_source_candidates_zh.md`
- 已创建字段匹配矩阵：`docs/external_data_field_mapping_matrix_zh.md`
- 已创建导入优先级计划：`docs/validation_data_import_plan_zh.md`
- 已创建教材候选清单：`docs/textbook_reference_candidates_zh.md`
- 已创建数据侦察说明：`validation_data/README_data_scouting_zh.md`

Phase 4B 当前明确未做：

- 未导入任何真实外部数据到 `validation_data/imported/`
- 未修改任何公式
- 未切换任何 revised 默认值
- 未修改 production calculation chain
- 未进入 GUI 优化

### Phase 4C：CREATOR PMSM 首条真实 validation record 导入

已完成首条真实 record 的正式导入、loader 校验与 comparison engine 运行。

Phase 4C 当前已完成内容：

- 已核验 `CREATOR Case: Permanent Magnet Synchronous Motor Data` 的来源级元数据
- 已下载并审阅：
  - `README.md`
  - `CREATOR_Machine_Data_2024-11-04.pdf`
  - `PM_synchronous_motor.zip`
- 已完成字段级人工抽取并创建正式 imported record：
  - `validation_data/imported/creator_pmsm_initial_record.json`
- 已更新/创建：
  - `validation_data/source_notes/creator_pmsm/source_summary_zh.md`
  - `validation_data/source_notes/creator_pmsm/field_mapping_draft_zh.md`
  - `validation_data/source_notes/creator_pmsm/source_acquisition_checklist_zh.md`
  - `validation_data/reports/creator_pmsm_initial_comparison_zh.md`
  - `docs/creator_pmsm_import_report_zh.md`
- 已确认正式 record 的关键来源字段：
  - `rated_speed_rpm`
  - `dc_bus_voltage_v`
  - `phase_current_a`
  - `winding_connection`
  - `stator_outer_diameter_m`
  - `stator_inner_diameter_m`
  - `air_gap_m`
  - `magnet_thickness_m`
  - `magnet_remanence_t`
  - `rated_torque_nm`
  - `back_emf_phase_peak_v`
  - `phase_resistance_ohm`
- 已运行正式 comparison engine，结果为：
  - 可导入且可进入 gate 的字段被判定为 `topology_mismatch`
  - 其余未安全映射字段保持 `unavailable` 或 `not_available`

Phase 4C 当前明确未做：

- 未修改任何公式
- 未切换任何默认值
- 未修改 production calculation chain
- 未修改 `legacy_baseline.json`
- 未修改既有 PMSM / BLDC analytical fixtures
- 未把该 record 外推为 `BLDC` 或 `AFPM` 的准确度声明

## 4. 当前 Git 状态

- 侦察起始主开发分支：`feature/external-validation-framework`
- 当前 Phase 4B 研究分支：`research/external-data-source-scouting`
- 当前 Phase 4C 工作分支：`data/creator-pmsm-validation-record`
- Phase 4A 冻结后的完整测试结果：`138 passed`

## 5. 当前测试体系

正式测试命令：

```text
.venv\Scripts\python.exe -m pytest -v
```

Phase 4A 与 Phase 4B 进入前完整测试结果：

```text
138 passed
```

进入本轮 Phase 4C 前的完整测试结果：

```text
147 passed
```

本轮 Phase 4C 完成后的完整测试结果：

```text
149 passed
```

## 6. baseline 与 reference fixture 的角色

`motor_calculator/tests/fixtures/legacy_baseline.json` 的作用是：

- 固化重构前程序行为
- 作为 regression baseline
- 防止结构重构无意改变 legacy 输出

它不是：

- 物理真值
- PMSM revised `Ke` / `Kt` 的 benchmark
- BLDC revised `Ke` / `Kt` 的 benchmark
- 公开 benchmark
- FEA 结果
- 实验验证结果

## 7. 当前 revised / legacy 语义状态

当前已具备 revised 并行语义：

- strict SI `rated_torque_nm`
- PMSM revised `Ke`
- PMSM revised `Kt`
- BLDC revised `Ke`
- BLDC revised `Kt`

当前仍保持 legacy 或 provisional 的内容包括：

- `9.55 * P / n` 的下游默认链路
- `required_voltage_v`
- 额定电流默认链路
- 铁损、机械损耗、涡流损耗模型
- 电感模型
- 槽满率代理模型
- 热与退磁限制链路

## 8. 当前验证框架状态

当前验证框架已经支持：

- 来源类型分类
- 证据等级分类
- provenance 字段跟踪
- 缺失值状态管理
- expected / uncertainty / tolerances 结构
- phase / line、RMS / peak、control mode、topology、Y/Delta comparability 检查
- 显式单位转换并记录转换步骤
- legacy / revised 并行误差输出

当前验证框架尚未包含：

- 真实公开 benchmark 数据
- 真实 FEA 数据
- 真实台架测量数据
- 多来源交叉验证结论

## 9. GUI 运行状态

GUI smoke test 已完成，但当前环境下 GUI 运行时仍待修复：

- 当前虚拟环境缺少 `matplotlib`
- Tk runtime 缺少可用 `init.tcl`
- 真实 GUI 未能成功打开
- headless 默认计算成功
- JSON、CSV、文本报告保存可用
- 图表保存存在“提示成功但未生成图像”的问题

当前建议：

- 暂不进入 GUI 优化
- 若后续单独批准，可进入 `Phase 4C-alt: GUI runtime dependency repair`

## 10. 当前未解决问题

- revised PMSM `Ke` / `Kt` 仍未成为默认值
- revised BLDC `Ke` / `Kt` 仍未成为默认值
- `required_voltage_v` 仍是 legacy 简化模型
- 损耗、电感、槽满率、退磁、温升仍是 legacy/provisional
- 已导入第一条真实外部 PMSM validation record，但其来源拓扑与项目默认 AFPM 拓扑不一致
- 仍缺少与默认 AFPM 拓扑直接可比的真实公开 benchmark
- 缺少真实 FEA 导入
- 缺少真实台架实验测量导入
- 缺少多来源交叉验证与不确定度归档
- GUI runtime dependency 仍未修复

## 11. 当前不能做出的声明

当前不能宣称：

- 整体电机模型已经获得实验验证
- `required_voltage_v` 已经物理修正
- 损耗、效率、电感、热限制或退磁限制模型已经获得 external validation
- revised PMSM 或 revised BLDC 已经获批成为默认值
- synthetic example、legacy baseline 或 analytical reference 足以证明真实准确度

## 12. 当前最安全的下一步

当前最安全的下一步候选有三条：

1. 继续 `Phase 4C`：批准并抽取 `CREATOR_Machine_Data_2024-11-04.pdf` 与 `PM_synchronous_motor.zip`，把 draft 升级为正式 record
2. `Phase 4C-alt`：修复 GUI runtime dependency
3. 用户先提供 AFPM 论文 / 教材全文，再做人工字段抽取
