# 项目状态

更新时间：2026-07-03

## 1. 当前项目目标

当前项目目标仍然是：

- 冻结已批准的模型定义
- 保持 legacy 行为稳定
- 提升结构可维护性、可测试性和语义清晰度
- 在任何会改变结果的公式修改前，先建立并行输出、测试和差异报告

当前项目目标不包括：

- 未经批准直接替换 legacy 电磁经验公式
- 重做 GUI 布局或视觉样式
- 删除 `matplotlib`
- EXE 打包
- 在未批准前直接启用新的物理默认值

## 2. 项目对象

- 目标电机：三相轴向磁通永磁无刷电机 AFPM PMSM/BLDC
- 默认拓扑：双转子、单定子、双气隙
- 默认连接：Y 接

## 3. 已完成阶段

### 第一阶段：审查与问题识别

已完成：

- 审查原始单文件程序结构
- 识别 GUI、计算逻辑、依赖和打包风险
- 列出单位、相线值、峰值/有效值、极数/极对数等关键风险

### 第二阶段：安全基线、核心拆分、输入校验

已完成：

- 初始化 Git 仓库
- 保留原始单文件版本
- 创建 baseline 提交
- 建立 `refactor/core-validation` 分支
- 保存 3 组 `legacy baseline`
- 创建 `motor_core/` 纯计算内核
- 创建 `gui/` GUI 包装层
- 集中单位转换、常量、模型假设和输入校验
- 建立回归测试、单位测试和输入校验测试

### Phase 3A：电气语义澄清与标准 pytest

已完成：

- 启用标准 `pytest`
- 标准测试命令固定为 `python -m pytest -v`
- 引入明确的速度、频率、电压、电流和控制模式语义
- 隔离 PMSM 与 BLDC 的电气语义边界
- 保留 legacy 输出字段并新增明确语义字段
- 新增电气语义测试覆盖
- 编写 `docs/electrical_quantity_definitions_zh.md`

Phase 3A 分支与提交：

- 当前开发分支：`feature/electrical-semantics`
- `724c305` `test: enable standard pytest`
- `98ba044` `refactor: clarify speed and electrical quantity semantics`
- `47e086a` `refactor: separate PMSM and BLDC control mode semantics`
- `db9749d` `test: add electrical semantics coverage`
- `c0da91b` `docs: document electrical quantity definitions`

Phase 3A 验证状态：

- 完整测试结果：`25 passed`
- `legacy_baseline.json` 未修改
- 3 组 legacy baseline、18 个输出字段均未发现数值漂移
- PMSM 与 BLDC 的电气语义已经隔离
- BLDC 120°导通下的严格 RMS、peak、`Ke`、`Kt` 关系尚未建立
- legacy `Ke` / `Kt`、`required_voltage_v`、损耗、电感、槽满率等模型尚未修正

## 4. 当前 Git 状态

- 当前开发基线：`feature/strict-si-rated-torque`
- Phase 3B 已完成并验收
- 当前阶段文档固化后，将进入 Phase 3C

关键历史提交：

- `d2f9f67`：`baseline: preserve original single-file motor calculator`
- `aaeb2d7`：`refactor: split motor core and add validation baseline`
- `c2d0039`：`docs: freeze project context and approved assumptions`

## 5. 当前测试体系

正式测试命令：

```text
python -m pytest -v
```

当前完整测试结果：

```text
35 passed
```

兼容测试入口仍保留：

```text
python work/run_pytest_style.py
```

但它只用于临时兼容环境，不再作为正式测试入口。

## 6. legacy baseline 的作用

`motor_calculator/tests/fixtures/legacy_baseline.json` 的作用是：

- 固化重构前程序行为
- 作为回归测试对照
- 防止结构重构无意改变计算结果

它不是：

- 物理真值
- 最终设计值
- 电机模型实验验证结果

## 7. 当前已知公式状态

当前仍保持 legacy 或未修正的内容包括：

- `9.55 * P / n`
- legacy `Ke` / `Kt`
- `required_voltage_v`
- 铁损、机械损耗、涡流损耗模型
- 电感模型
- 槽满率代理模型

所有会改变结果的公式修改都必须保留 legacy 与 revised 并行输出，不得直接覆盖旧字段。

## 8. Phase 3B 状态

Phase 3B 已完成。

本阶段完成内容：

- 新增 legacy 与 strict SI 额定转矩并行比较
- 新增输出字段：
  - `legacy_rated_torque_nm`
  - `revised_rated_torque_nm`
  - `rated_torque_absolute_difference_nm`
  - `rated_torque_relative_difference`
  - `rated_torque_model_status`
- 当前下游仍继续使用 legacy 额定转矩
- 生成 `docs/phase3_formula_change_report_zh.md`

Phase 3B 相关提交：

- Phase 3A 状态固化提交：`d9e675f`
- `1c74397` `feat: add strict SI rated torque comparison`
- `28cc132` `test: cover legacy and strict SI torque models`
- `0adbca7` `docs: document rated torque formula comparison`

Phase 3B 完成后测试状态：

```text
35 passed
```

确认事项：

- legacy regression 仍通过
- `legacy_baseline.json` 未修改
- `revised_rated_torque_nm` 尚未设为默认值
- revised 结果未传播到额定电流、损耗、效率或电压需求
- 未修改 `Ke` / `Kt`
- 未修改 BLDC 模型
- 未修改 `required_voltage_v`

## 9. Phase 3C 范围

Phase 3C 只允许处理 PMSM 正弦模式下的 `Ke` / `Kt` revised 定义：

- 必须保留 legacy `Ke` / `Kt` 输出
- 必须与 legacy 并行输出 revised `Ke` / `Kt`
- revised `Ke` / `Kt` 不得传播到额定电流、损耗、效率、GUI 默认链路或 `required_voltage_v`
- BLDC 120°导通仍保持 legacy / provisional

## 10. 下一阶段状态

当前允许进入：

- Phase 3C：PMSM `Ke` / `Kt` 语义修正

当前不允许进入：

- BLDC `Ke` / `Kt` 修正
- `required_voltage_v` 修正
- 未经批准把任何 revised 结果切换为生产默认值

说明：

- Phase 3C 当前只处理 PMSM 正弦模式
- 所有 revised `Ke` / `Kt` 都必须保持并行输出和下游隔离

## 11. 当前未解决问题

- BLDC 120°导通下的严格 RMS、peak、`Ke`、`Kt` 关系仍未建立
- `9.55 * P / n` 是否应从 legacy 默认值切换为严格 SI 默认值，尚未批准
- PMSM revised `Ke` / `Kt` 尚未成为默认值
- 如果未来启用 revised 默认转矩，将影响额定电流、铜损、效率和所需电压等下游结果

当前建议：

- 暂不将 revised 额定转矩设为默认值
- 暂不将 revised `Ke` / `Kt` 设为默认值
- 先保留并行输出与差异报告
