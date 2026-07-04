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
- 重做 GUI 布局或视觉样式
- 在没有真实外部证据的前提下宣称物理准确度已经得到实验验证

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

Phase 3E 提交：

- `52373c6` `feat: define ideal BLDC waveform semantics`
- `3168ad2` `feat: derive BLDC Ke Kt from 120 degree power balance`
- `2d28905` `test: add independent BLDC analytical reference cases`
- `9716cb0` `test: validate BLDC Ke Kt semantics and isolation`
- `3bba27d` `docs: document BLDC Ke Kt analytical validation`

Phase 3E 验收状态：

- 修改前完整测试结果：`84 passed`
- 修改后完整测试结果：`117 passed`
- `legacy_baseline.json` 未修改
- `legacy_baseline.json` SHA-256：`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- 当前 3 组 legacy baseline 全部为 BLDC 路径
- revised BLDC `Ke` / `Kt` 已通过分段解析、独立数值积分、独立 analytical reference、production/reference 交叉验证与 downstream isolation
- revised PMSM 与 revised BLDC 均未设为默认值

### Phase 4A：外部验证数据框架与 provenance 跟踪

已完成。

Phase 4A 分支：

- `feature/external-validation-framework`

Phase 4A 已记录提交：

- `87240a5` `feat: add external validation record schema`
- `531e342` `feat: add validation loader and comparability engine`
- `84f88d1` `test: cover validation provenance and error metrics`

Phase 4A 完成内容：

- 建立 `ValidationSourceType` 六类来源枚举
- 建立 `ValidationEvidenceLevel` 五级证据等级
- 建立字段状态 `provided / inferred / unavailable / not_applicable`
- 建立独立验证记录 schema：`motor_calculator/motor_core/validation_records.py`
- 建立 JSON 加载与单位检查：`motor_calculator/motor_core/validation_loader.py`
- 建立 comparability / error / uncertainty 比较引擎：`motor_calculator/motor_core/validation_comparison.py`
- 建立 `validation_data/` 模板目录、`imported/` 与 `reports/` 结构
- 建立 synthetic example 仅用于测试导入器和比较引擎
- 建立新增验证测试，且不修改 production 公式链

Phase 4A 明确未做：

- 未修改任何电磁公式
- 未切换任何默认链路
- 未修改 `required_voltage_v`
- 未修改额定电流默认链路
- 未修改损耗、效率、电感、槽满率、热限制或退磁限制公式
- 未导入任何真实公开 benchmark、真实 FEA 或真实台架数据
- 未伪造任何外部来源

## 4. 当前 Git 状态

- 当前分支：`feature/external-validation-framework`
- Phase 3D 状态固化提交：`958dc23` `docs: record phase 3D completion and phase 3E scope`
- Phase 4A 在 Phase 3E 冻结状态之上并行建立验证框架，未触碰 production 公式

## 5. 当前测试体系

正式测试命令：

```text
.venv\Scripts\python.exe -m pytest -v
```

Phase 4A 完成后的完整测试结果：

```text
138 passed
```

说明：

- 原有 `117` 个测试继续通过
- 新增 `21` 个验证框架测试全部通过
- `legacy_baseline`、PMSM analytical reference、BLDC analytical reference 相关测试继续通过

## 6. baseline 与 reference fixture 的角色

`motor_calculator/tests/fixtures/legacy_baseline.json` 的作用是：

- 固化重构前程序行为
- 作为 regression baseline
- 防止结构重构无意改变 legacy 输出

它不是：

- 物理真值
- PMSM revised `Ke` / `Kt` 的数值参考
- BLDC revised `Ke` / `Kt` 的数值参考
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
- provenance 字段追踪
- 缺失值状态管理
- 结构化 expected / uncertainty / tolerances
- phase / line、RMS / peak、control mode、topology、Y/Delta comparability 检查
- 单位显式转换并记录转换步骤
- legacy / revised 并行误差输出
- synthetic 数据隔离

当前验证框架尚未包含：

- 真实公开 benchmark 数据
- 真实 FEA 数据
- 真实台架测量数据
- 多来源交叉验证结论

## 9. 当前不能做出的声明

当前不能宣称：

- 整体电机模型已经获得实验验证
- `required_voltage_v` 已经物理修正
- 损耗、效率、电感、热限制或退磁限制模型已经获得 external validation
- revised PMSM 或 revised BLDC 已经获批成为默认值
- synthetic example、legacy baseline 或 analytical reference 足以证明真实准确度

## 10. 当前未解决问题

- revised PMSM `Ke` / `Kt` 仍未成为默认值
- revised BLDC `Ke` / `Kt` 仍未成为默认值
- `required_voltage_v` 仍是 legacy 简化模型
- 缺少真实公开 benchmark 导入
- 缺少真实 FEA 导入
- 缺少真实台架实验测量导入
- 缺少多来源交叉验证与不确定度归档
