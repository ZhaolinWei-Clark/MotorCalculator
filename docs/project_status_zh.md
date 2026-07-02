# 项目状态

更新时间：2026-07-02

## 1. 当前项目目标

当前项目的目标是将原始单文件电机计算程序重构为可维护、可测试、可回归验证的工程结构，同时冻结现有模型定义和 legacy 行为。

当前阶段目标不包括：

- 不替换电磁公式
- 不重做 GUI 设计
- 不移除 `matplotlib`
- 不增加优化、成本估算或新的设计功能

## 2. 项目对象

- 目标电机：三相轴向磁通永磁无刷电机 AFPM PMSM/BLDC
- 默认拓扑：双转子、单定子、双气隙
- 默认连接：Y 接
- 模式定义：
  - `PMSM`：正弦反电势、正弦电流
  - `BLDC`：梯形反电势、120° 方波导通

## 3. 已完成阶段

### 第一阶段：审查与问题识别

已完成：

- 审查原始单文件程序结构
- 识别 GUI、计算逻辑、依赖和打包风险
- 列出单位、相线值、峰值/有效值、极数/极对数等关键风险
- 输出静态审查报告

### 第二阶段：安全基线、核心拆分、输入校验

已完成：

- 初始化 Git 仓库
- 保留原始单文件版本
- 创建 baseline 提交
- 建立分支 `refactor/core-validation`
- 保存 3 组 `legacy baseline`
- 创建 `motor_core/` 纯计算内核
- 创建 `gui/` GUI 包装层
- 集中单位转换、常量、模型假设和输入校验
- 补充中文文档
- 建立回归测试、单位测试和输入校验测试

## 4. 当前 Git 状态

- 当前分支：`refactor/core-validation`
- 关键提交：
  - `d2f9f67`：`baseline: preserve original single-file motor calculator`
  - `aaeb2d7`：`refactor: split motor core and add validation baseline`

## 5. 当前文件结构

```text
motor_calculator/
  app.py
  PMDC_Calculator_claude204.py
  motor_core/
    __init__.py
    assumptions.py
    calculations.py
    constants.py
    models.py
    units.py
    validation.py
  gui/
    __init__.py
    main_window.py
  tests/
    test_legacy_regression.py
    test_units.py
    test_validation.py
    fixtures/
      legacy_baseline.json
  docs/
    model_assumptions_zh.md
    formula_inventory_zh.md
work/
  run_pytest_style.py
docs/
  project_status_zh.md
  approved_model_assumptions_zh.md
  pending_decisions_zh.md
```

## 6. legacy baseline 的用途

`motor_calculator/tests/fixtures/legacy_baseline.json` 的用途是：

- 固化重构前程序行为
- 作为回归测试对照
- 防止结构重构无意改变计算结果

它不是：

- 物理真值
- 最终设计值
- 精度证明

## 7. 当前测试方式

当前测试执行方式：

```text
python work/run_pytest_style.py
```

说明：

- 当前运行环境未预装 `pytest`
- 但测试文件已按 pytest 风格命名和组织
- 后续如补齐 `pytest`，可平滑迁移到标准 pytest 运行方式

## 8. 已知经验公式与待确认公式

已知经验公式和状态请以以下文件为准：

- `motor_calculator/docs/formula_inventory_zh.md`
- `motor_calculator/docs/model_assumptions_zh.md`

当前重点：

- 经验公式已被保留并显式标记
- 待确认公式未在本阶段擅自替换

## 9. 当前尚未解决的工程问题

- `Kt` / `Ke` 的相值/线值与峰值/有效值语义仍需最终确认
- `9.55 * P / n` 仍为 legacy 兼容实现
- `K_fill` 仍是 legacy 占比指标，不是真实槽满率
- 所需电压模型仍为简化表达
- 铁损、机械损耗、涡流损耗等仍为经验模型
- 当前测试运行器是轻量替代，不是标准 pytest
- 旧 GUI 仍通过兼容桥接方式依赖 legacy 文件

## 10. 下一阶段目标

继续第三阶段之前，应优先完成：

- 固化所有已批准和未批准的模型决策
- 明确哪些修改只影响结构，哪些会改变结果
- 将“可改”和“需批准后才能改”的内容清楚分层

下一阶段不应直接修改公式，除非先获得批准。

